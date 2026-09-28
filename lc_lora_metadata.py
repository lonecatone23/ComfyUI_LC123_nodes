"""LoRA settings from the submitted API graph, without loading model files.

Graph ancestry is not execution evidence: lazy branches may be unselected.
Keep that distinction explicit in the structured PNG metadata.
"""

import json
import math
import os

from .lc_lora_weights import row_strengths


def _number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def parse_lc_lora_rows(value):
    """Read LC's serialized rows using the loader's strength defaults."""
    try:
        rows = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(rows, list):
        return []
    return [
        {**row, 'strength': _number(row.get('strength', 1.0)) or 0.0}
        for row in rows if isinstance(row, dict)
    ]


def _resolve(value, prompt, seen=None):
    if not (isinstance(value, list) and len(value) == 2):
        return value
    nid = str(value[0])
    seen = set() if seen is None else seen
    if nid in seen or value[1] != 0:
        return None
    seen.add(nid)
    node = prompt.get(nid, {})
    # Only literal primitive outputs are safe to resolve without execution.
    if node.get('class_type') not in ('PrimitiveFloat', 'PrimitiveInt', 'PrimitiveBoolean', 'PrimitiveString'):
        return None
    return _resolve(node.get('inputs', {}).get('value'), prompt, seen)


def _cached_values(link, consumer, execution_list):
    if execution_list is None or not isinstance(link, list) or len(link) != 2:
        return None
    entry = execution_list.get_cache(str(link[0]), str(consumer))
    if entry is None:
        entry = execution_list.output_cache.get_local(str(link[0]))
    if entry is None or entry.outputs is None or not isinstance(link[1], int) or not 0 <= link[1] < len(entry.outputs):
        return None
    return entry.outputs[link[1]]


def _image_ancestors(prompt, save_node_id, execution_list=None, unresolved=None):
    node = prompt.get(str(save_node_id))
    if not node:
        return None
    pending = [(node.get('inputs', {}).get('images'), str(save_node_id))]
    visited = set()
    while pending:
        link, consumer = pending.pop()
        if not (isinstance(link, list) and len(link) == 2):
            continue
        nid = str(link[0])
        if nid in visited or nid not in prompt:
            continue
        visited.add(nid)
        inputs = prompt[nid].get('inputs', {})
        kind = prompt[nid].get('class_type')
        links = list(inputs.values())
        if kind in ('BooleanSwitchNode', 'LCBooleanSwitch'):
            state = _resolve(inputs.get('state', inputs.get('boolean')), prompt)
            states = _cached_values(inputs.get('state'), nid, execution_list)
            if states is not None and all(isinstance(v, bool) for v in states):
                links = [inputs.get('on_true' if v else 'on_false') for v in set(states)]
            elif isinstance(state, bool):
                links = [inputs.get('on_true' if state else 'on_false')]
            else:
                if unresolved is not None:
                    unresolved.append(nid)
                links = []
        if kind in ('LCAnySwitch', 'Any Switch (rgthree)'):
            if kind == 'LCAnySwitch':
                count = _resolve(inputs.get('inputcount', 2), prompt)
                if not isinstance(count, int):
                    if unresolved is not None:
                        unresolved.append(nid)
                    continue
                candidates = [inputs[f'any_{i:02d}'] for i in range(1, max(2, min(20, count)) + 1)
                              if f'any_{i:02d}' in inputs]
            else:
                candidates = [v for k, v in inputs.items() if k.startswith('any_')]
            if len(candidates) <= 1:
                links = candidates
            else:
                output = _cached_values(link, consumer, execution_list)
                values = [(v, _cached_values(v, nid, execution_list)) for v in candidates]
                selected = []
                if output is not None:
                    for item in output:
                        for candidate, cached in values:
                            if item is not None and cached is not None and any(item is value for value in cached):
                                if candidate not in selected:
                                    selected.append(candidate)
                                break
                        else:
                            selected = []
                            break
                if not selected:
                    if unresolved is not None:
                        unresolved.append(nid)
                    links = []  # Do not assert that every candidate contributed to the image.
                else:
                    links = selected
        pending.extend((value, nid) for value in links)
    return visited


def collect_lora_metadata(prompt, save_node_id=None, execution_list=None):
    prompt = {str(k): v for k, v in (prompt or {}).items() if isinstance(v, dict)}
    ancestors = _image_ancestors(prompt, save_node_id, execution_list)
    def resolve(value, consumer):
        literal = _resolve(value, prompt)
        if literal is not None:
            return literal
        cached = _cached_values(value, consumer, execution_list)
        if cached and all(isinstance(v, (str, bool, int, float)) for v in cached):
            if all(v == cached[0] for v in cached):
                return cached[0]
        return None

    records = []
    for nid, node in prompt.items():
        kind = node.get('class_type', '')
        inputs = node.get('inputs', {})
        slots = []
        if kind in ('LCLoraLoader', 'LCGroupLoraLoader'):
            rows = parse_lc_lora_rows(resolve(inputs.get('lora_rows', '[]'), nid))
            for index, row in enumerate(rows):
                model, clip = row_strengths(row) if kind == 'LCGroupLoraLoader' else (row['strength'], row['strength'])
                model = model if inputs.get('model') is not None else 0.0
                clip = clip if inputs.get('clip') is not None else 0.0
                slots.append((f'lora_rows[{index}]', row.get('lora'), bool(row.get('on')), model, clip))
        else:
            candidates = [('lora', inputs)] + [
                (key, value) for key, value in inputs.items() if isinstance(value, dict)
            ]
            for slot, values in candidates:
                name = resolve(values.get('lora_name', values.get('lora')), nid)
                if name is None or not any(key in values for key in ('strength', 'strength_model', 'strength_clip', 'strengthTwo')):
                    continue
                model = _number(resolve(values.get('strength_model', values.get('strength')), nid))
                if 'strength_clip' in values:
                    clip_value = values['strength_clip']
                elif values.get('strengthTwo') is not None:
                    clip_value = values['strengthTwo']
                elif inputs.get('clip') is not None:
                    clip_value = values.get('strength')
                else:
                    clip_value = 0.0
                clip = _number(resolve(clip_value, nid))
                if 'strength_clip' not in values and inputs.get('clip') is None:
                    clip = 0.0
                enabled = all(bool(resolve(values.get(key, True), nid)) for key in ('on', 'enabled'))
                slots.append((slot, name, enabled, model, clip))
        for slot, name, enabled, model, clip in slots:
            if not isinstance(name, str) or not name or name.lower() == 'none':
                continue
            active = enabled and (model != 0.0 or clip != 0.0)
            scope = 'unknown' if ancestors is None else ('image_upstream' if nid in ancestors else 'configured_only')
            records.append({
                'node_id': nid, 'slot': slot, 'loader': kind, 'filename': name,
                'name': os.path.splitext(name.replace('\\', '/').rsplit('/', 1)[-1])[0],
                'enabled': enabled, 'nonzero_or_unresolved': active,
                'strength_model': model, 'strength_clip': clip,
                'scope': scope, 'execution_verified': False,
            })
    return {
        'schema_version': 1, 'source': 'submitted_prompt',
        'scope_note': 'image_upstream follows the saved image graph and supported switch selections; it does not prove effective patch application.',
        'loras': records,
    }
