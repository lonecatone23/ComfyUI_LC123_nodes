"""Metadata regressions independent of GPU generation and model downloads."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from test_lc_lora_metadata import metadata, hashes, save, folders, graph


class CachedExecution:
    def __init__(self, values, local_only=False):
        self.entries = {key: SimpleNamespace(outputs=[value]) for key, value in values.items()}
        self.local_only = local_only
        self.output_cache = SimpleNamespace(get_local=self.entries.get)

    def get_cache(self, source, consumer):
        return None if self.local_only else self.entries.get(source)


def switch_graph(kind):
    return {
        'a': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'selected.safetensors'}},
        'b': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'unused.safetensors'}},
        's': {'class_type': kind, 'inputs': {'any_01': ['a', 0], 'any_02': ['b', 0]}},
        'out': {'class_type': 'LCSaveImage', 'inputs': {'images': ['s', 0]}},
    }


class MetadataContractTests(unittest.TestCase):
    def test_same_basename_verified_file_does_not_hide_unverified_file(self):
        prompt = graph([{'on': True, 'lora': 'known/character.safetensors', 'strength': .8},
                        {'on': True, 'lora': 'unknown/character.safetensors', 'strength': .3}])
        data = metadata.collect_lora_metadata(prompt, '3')
        excluded = set()
        identity = {'type': 'lora', 'modelId': 1, 'modelVersionId': 2}
        with patch.object(hashes, '_resolve', side_effect=lambda name, hint: (name, 'lora')), patch.object(hashes, '_lora_version', side_effect=lambda path: identity if path.startswith('known/') else None), patch.object(hashes, 'autov2', return_value='UNKNOWN') as digest:
            self.assertEqual(hashes.lora_resources_payload(data, excluded), [{**identity, 'weight': .8}])
            result = hashes.collect_hashes(prompt, lora_metadata=data, excluded_lora_paths=excluded)
            digest.assert_called_once_with('unknown/character.safetensors')
        self.assertEqual(result['hashes_json'], {'lora:character': 'UNKNOWN'})

    def test_prompt_mentions_and_disabled_loras_are_not_resources(self):
        prompt = graph([{'on': False, 'lora': 'disabled.safetensors', 'strength': 1}])
        prompt['2']['inputs']['positive'] = ['text', 0]
        prompt['text'] = {'class_type': 'CLIPTextEncode', 'inputs': {'text': '<lora:imaginary:1> checkpoint.safetensors'}}
        data = metadata.collect_lora_metadata(prompt, '3')
        with patch.object(hashes, '_resolve', return_value=('unwanted', 'model')) as resolve:
            result = hashes.collect_hashes(prompt, lora_metadata=data)
        resolve.assert_not_called()
        self.assertEqual(result['hashes_json'], {})

    def test_dynamic_lora_strengths_use_execution_values(self):
        prompt = graph([])
        prompt['1'] = {'class_type': 'LoraLoader', 'inputs': {
            'lora_name': 'character.safetensors', 'strength_model': ['weight', 0], 'strength_clip': ['clipweight', 0]}}
        execution = CachedExecution({'weight': [.8], 'clipweight': [.2]})
        row = metadata.collect_lora_metadata(prompt, '3', execution)['loras'][0]
        self.assertEqual((row['strength_model'], row['strength_clip']), (.8, .2))

    def test_unknown_weight_preserves_verified_identity(self):
        data = metadata.collect_lora_metadata(graph([{'on': True, 'lora': 'a.safetensors', 'strength': .8}]), '3')
        data['loras'][0]['strength_model'] = None
        identity = {'type': 'lora', 'modelId': 1, 'modelVersionId': 2}
        with patch.object(hashes, '_resolve', return_value=('file', 'lora')), patch.object(hashes, '_lora_version', return_value=identity):
            self.assertEqual(hashes.lora_resources_payload(data), [identity])

    def test_any_switch_selected_identity_even_when_both_inputs_cached(self):
        a, b = np.zeros((1, 2, 2, 3)), np.ones((1, 2, 2, 3))
        for kind in ('LCAnySwitch', 'Any Switch (rgthree)'):
            for local_only in (False, True):
                with self.subTest(kind=kind, local_only=local_only):
                    execution = CachedExecution({'a': [a], 'b': [b], 's': [a]}, local_only)
                    warnings = []
                    scope = metadata._image_ancestors(switch_graph(kind), 'out', execution, warnings)
                    self.assertEqual(scope, {'s', 'a'})
                    self.assertEqual(warnings, [])

    def test_lazy_unexecuted_input_and_none_fallthrough(self):
        value = object()
        for values, selected in [({'a': [value], 's': [value]}, 'a'),
                                 ({'a': [None], 'b': [value], 's': [value]}, 'b')]:
            execution = CachedExecution(values)
            self.assertEqual(metadata._image_ancestors(switch_graph('LCAnySwitch'), 'out', execution), {'s', selected})

    def test_unknown_selection_omits_candidates_and_reports(self):
        warnings = []
        self.assertEqual(metadata._image_ancestors(switch_graph('LCAnySwitch'), 'out', None, warnings), {'s'})
        self.assertEqual(warnings, ['s'])

    def test_lc_switch_ignores_inputs_outside_inputcount(self):
        prompt = switch_graph('LCAnySwitch')
        del prompt['s']['inputs']['any_02']
        prompt['s']['inputs']['any_03'] = ['b', 0]
        self.assertEqual(metadata._image_ancestors(prompt, 'out'), {'s', 'a'})

    def test_boolean_runtime_selection_and_mapped_outputs(self):
        prompt = switch_graph('LCBooleanSwitch')
        prompt['s']['inputs'] = {'state': ['bool', 0], 'on_true': ['a', 0], 'on_false': ['b', 0]}
        execution = CachedExecution({'bool': [False]})
        self.assertEqual(metadata._image_ancestors(prompt, 'out', execution), {'s', 'b'})
        a, b = object(), object()
        execution = CachedExecution({'a': [a], 'b': [b], 's': [a, b]})
        self.assertEqual(metadata._image_ancestors(switch_graph('LCAnySwitch'), 'out', execution), {'s', 'a', 'b'})

    def test_repeated_versions_deduplicate_without_inventing_combined_weight(self):
        data = metadata.collect_lora_metadata(graph([
            {'on': True, 'lora': 'a.safetensors', 'strength': .7},
            {'on': True, 'lora': 'a.safetensors', 'strength': .7},
        ]), '3')
        identity = {'type': 'lora', 'modelId': 10, 'modelVersionId': 20}
        with patch.object(hashes, '_resolve', return_value=('file', 'lora')), patch.object(hashes, '_lora_version', return_value=identity):
            self.assertEqual(hashes.lora_resources_payload(data), [{**identity, 'weight': .7}])
            data['loras'][1]['strength_model'] = .3
            self.assertEqual(hashes.lora_resources_payload(data), [identity])
            self.assertEqual([r['strength_model'] for r in data['loras']], [.7, .3])

    def test_hashes_have_no_primary_alias_duplicates(self):
        prompt = {'1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'janima.safetensors'}},
                  '2': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'vae.safetensors'}}}
        def resolve(name, hint):
            return name, 'unet' if name.startswith('janima') else 'vae'
        with patch.object(hashes, '_resolve', side_effect=resolve), patch.object(hashes, 'autov2', side_effect=['MODEL', 'VAE']):
            result = hashes.collect_hashes(prompt)
        self.assertEqual(result['primary_model'], 'janima')
        self.assertEqual(result['hashes_json'], {'model': 'MODEL', 'vae': 'VAE'})

    def test_unverified_lora_keeps_hash_fallback_and_exact_strength_details(self):
        prompt = graph([{'on': True, 'lora': 'unknown.safetensors', 'strength': -.4}])
        buckets = {'lora': [('unknown', 'ABC')], 'hashes_json': {'lora:unknown': 'ABC'}}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(folders, 'get_output_directory', return_value=tmp, create=True), patch.object(folders, 'get_save_image_path', return_value=(tmp, 'test', 1, '', ''), create=True), patch.object(save, 'collect_hashes', return_value=buckets), patch.object(hashes, '_resolve', return_value=('file', 'lora')), patch.object(hashes, '_lora_version', return_value=None):
                save.LCSaveImage().save(np.zeros((1, 16, 24, 3)), prompt=prompt, unique_id='3')
            with Image.open(next(Path(tmp).glob('*.png'))) as image:
                self.assertEqual(json.loads(image.info['hashes']), {'lora:unknown': 'ABC'})
                self.assertNotIn('civitaiResources', image.info)
                self.assertNotIn('AddNet', image.info['parameters'])
                self.assertEqual(json.loads(image.info['lora_metadata'])['loras'][0]['strength_model'], -.4)

    def test_png_contract_preserves_workflow_prompts_resources_scheduler(self):
        prompt = graph([{'on': True, 'lora': 'character.safetensors', 'strength': .8},
                        {'on': False, 'lora': 'disabled.safetensors', 'strength': 1}])
        prompt['9'] = graph([{'on': True, 'lora': 'unrelated.safetensors', 'strength': 1}])['1']
        workflow = {'nodes': [{'id': 9, 'widgets_values': ['stale.safetensors']}]}
        air = 'urn:air:anima:unknown:civitai:2382239@3328902'
        meta = {'positive': 'clean positive', 'negative': 'clean negative', 'width': 1024, 'height': 1536,
                'sampler': 'er_sde', 'scheduler': 'beta', 'steps': 20, 'cfg': 1, 'seed': 123,
                'civitai_air': air, 'models': 'incorrect manual model'}
        buckets = {'primary_model': 'JANIMA', 'hashes_json': {'model': 'ABC'}}
        identity = {'type': 'lora', 'modelId': 2797846, 'modelVersionId': 3153756}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(folders, 'get_output_directory', return_value=tmp, create=True), patch.object(folders, 'get_save_image_path', return_value=(tmp, 'test', 1, '', ''), create=True), patch.object(save, 'collect_hashes', return_value=buckets), patch.object(hashes, '_resolve', return_value=('file', 'lora')), patch.object(hashes, '_lora_version', return_value=identity):
                save.LCSaveImage().save(np.zeros((1, 32, 48, 3)), metadata=meta, prompt=prompt, extra_pnginfo={'workflow': workflow, 'parameters': 'AddNet Enabled: True', 'hashes': {'lora:stale': 'BAD'}}, unique_id='3')
            with Image.open(next(Path(tmp).glob('*.png'))) as image:
                params = image.info['parameters']
                self.assertTrue(params.startswith('clean positive\nNegative prompt: clean negative\nSteps: 20'))
                for expected in ['Sampler: er_sde, Schedule type: beta', 'Size: 1024x1536', 'Model: JANIMA', 'Model hash: ABC', 'Version: ComfyUI']:
                    self.assertIn(expected, params)
                for unwanted in ['AddNet', '<lora:', 'Source size', 'Final size', 'incorrect manual model', 'disabled', 'unrelated']:
                    self.assertNotIn(unwanted, params)
                self.assertEqual(json.loads(image.info['prompt']), prompt)
                self.assertEqual(json.loads(image.info['workflow']), workflow)
                resources = json.loads(image.info['civitaiResources'])
                self.assertEqual(resources[0]['air'], air)
                self.assertEqual(resources[1], {**identity, 'weight': .8})
                self.assertEqual(len(json.loads(image.info['lora_metadata'])['loras']), 1)
                self.assertNotIn('lora:character', json.loads(image.info['hashes']))
                self.assertEqual(json.loads(image.info['hashes']), {'model': 'ABC'})


if __name__ == '__main__':
    unittest.main()
