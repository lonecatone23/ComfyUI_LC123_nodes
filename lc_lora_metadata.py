"""LoRA settings from the submitted API graph, without loading model files.

Graph ancestry is not execution evidence: lazy branches may be unselected.
Keep that distinction explicit in the structured PNG metadata.
"""

import json
import math
import os
import re
from collections import Counter


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


def _image_ancestors(prompt, save_node_id):
    node = prompt.get(str(save_node_id))
    if not node:
        return None
    root = node.get('inputs', {}).get('images')
    pending = [root]
    visited = set()
    while pending:
        link = pending.pop()
        if not (isinstance(link, list) and len(link) == 2):
            continue
        nid = str(link[0])
        if nid in visited or nid not in prompt:
            continue
        visited.add(nid)
        pending.extend(prompt[nid].get('inputs', {}).values())
    return visited


def collect_lora_metadata(prompt, save_node_id=None):
    prompt = {str(k): v for k, v in (prompt or {}).items() if isinstance(v, dict)}
    ancestors = _image_ancestors(prompt, save_node_id)
    records = []
    for nid, node in prompt.items():
        kind = node.get('class_type', '')
        inputs = node.get('inputs', {})
        slots = []
        if kind == 'LCLoraLoader':
            rows = parse_lc_lora_rows(_resolve(inputs.get('lora_rows', '[]'), prompt))
            for index, row in enumerate(rows):
                weight = row['strength']
                model = weight if inputs.get('model') is not None else 0.0
                clip = weight if inputs.get('clip') is not None else 0.0
                slots.append((f'lora_rows[{index}]', row.get('lora'), bool(row.get('on')), model, clip))
        else:
            candidates = [('lora', inputs)] + [
                (key, value) for key, value in inputs.items() if isinstance(value, dict)
            ]
            for slot, values in candidates:
                name = _resolve(values.get('lora_name', values.get('lora')), prompt)
                if name is None or not any(key in values for key in ('strength', 'strength_model', 'strength_clip', 'strengthTwo')):
                    continue
                model = _number(_resolve(values.get('strength_model', values.get('strength')), prompt))
                if 'strength_clip' in values:
                    clip_value = values['strength_clip']
                elif values.get('strengthTwo') is not None:
                    clip_value = values['strengthTwo']
                elif inputs.get('clip') is not None:
                    clip_value = values.get('strength')
                else:
                    clip_value = 0.0
                clip = _number(_resolve(clip_value, prompt))
                if 'strength_clip' not in values and inputs.get('clip') is None:
                    clip = 0.0
                enabled = all(bool(_resolve(values.get(key, True), prompt)) for key in ('on', 'enabled'))
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
        'scope_note': 'image_upstream describes graph ancestry, including possible unselected lazy branches; it does not prove execution or effective patch application.',
        'loras': records,
    }


def append_lora_tags(positive, metadata):
    """Append model-weight tags to the save-only text; retain duplicate slots."""
    existing = Counter(re.findall(r'<lora:[^>]+>', positive, flags=re.I))
    tags = []
    for item in metadata['loras']:
        weight = item['strength_model']
        if not item['nonzero_or_unresolved'] or item['scope'] != 'image_upstream' or weight is None:
            continue
        # Delimiter-bearing names remain available in the structured record.
        if any(c in item['name'] for c in ':<>\n\r'):
            continue
        tag = f"<lora:{item['name']}:{weight:g}>"
        if existing[tag]:
            existing[tag] -= 1
        else:
            tags.append(tag)
    return '\n'.join(part for part in (positive, ' '.join(tags)) if part)
