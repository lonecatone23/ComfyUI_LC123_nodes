"""Run with python -m unittest discover -s tests, without starting ComfyUI."""

import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

package = types.ModuleType('lc_metadata_test')
package.__path__ = [str(Path(__file__).resolve().parents[1])]
sys.modules[package.__name__] = package
folders = types.ModuleType('folder_paths')
pipe = types.ModuleType('lc_metadata_test.lc_pipe_io')
pipe.PIPE_TYPE = 'LC_PIPE'
with patch.dict(sys.modules, {'folder_paths': folders, pipe.__name__: pipe}):
    metadata = importlib.import_module('lc_metadata_test.lc_lora_metadata')
    hashes = importlib.import_module('lc_metadata_test.lc_civitai_hashes')
    save = importlib.import_module('lc_metadata_test.lc_save_image')


def graph(rows, model=True, clip=True):
    inputs = {'lora_rows': json.dumps(rows)}
    if model:
        inputs['model'] = ['0', 0]
    if clip:
        inputs['clip'] = ['0', 1]
    return {
        '1': {'class_type': 'LCLoraLoader', 'inputs': inputs},
        '2': {'class_type': 'ExampleImage', 'inputs': {'model': ['1', 0], 'clip': ['1', 1]}},
        '3': {'class_type': 'LCSaveImage', 'inputs': {'images': ['2', 0]}},
    }


class LCLoraMetadataTests(unittest.TestCase):
    def test_original_size_and_missing_size_fallback(self):
        for sw, sh, expected in [(1024, 1536, '1024x1536'), (0, 0, '24x16'), (24, 0, '24x16')]:
            with self.subTest(source=(sw, sh)), tempfile.TemporaryDirectory() as tmp:
                with patch.object(folders, 'get_output_directory', return_value=tmp, create=True), patch.object(folders, 'get_save_image_path', return_value=(tmp, 'test', 1, '', ''), create=True):
                    save.LCSaveImage().save(np.zeros((1, 16, 24, 3)), metadata={'width': sw, 'height': sh}, hash_resources=False)
                with Image.open(next(Path(tmp).glob('*.png'))) as image:
                    self.assertIn('Size: ' + expected, image.info['parameters'])
                    self.assertNotIn('Source size:', image.info['parameters'])
                    self.assertNotIn('Final size:', image.info['parameters'])
                    self.assertEqual(image.size, (24, 16))

    def test_generic_flat_inputs_ignore_loader_name(self):
        for kind in ['LoraLoader', 'LoraLoaderModelOnly', 'Krea2ControlLoRALoader', 'CustomAdapter']:
            with self.subTest(kind=kind):
                prompt = graph([])
                prompt['1'] = {'class_type': kind, 'inputs': {
                    'lora_name': ['4', 0], 'strength_model': ['5', 0], 'strength_clip': 0.25,
                }}
                prompt['4'] = {'class_type': 'PrimitiveString', 'inputs': {'value': 'generic.safetensors'}}
                prompt['5'] = {'class_type': 'PrimitiveFloat', 'inputs': {'value': -0.6}}
                data = metadata.collect_lora_metadata(prompt, '3')
                self.assertEqual(len(data['loras']), 1)
                self.assertEqual((data['loras'][0]['strength_model'], data['loras'][0]['strength_clip']), (-0.6, 0.25))

    def test_generic_dictionary_slots_ignore_loader_name(self):
        for kind in ['Power Lora Loader (rgthree)', 'Power Lora Loader - WeiLin Panel', 'CustomAdapter']:
            with self.subTest(kind=kind):
                prompt = graph([])
                prompt['1'] = {'class_type': kind, 'inputs': {
                    'clip': ['0', 1],
                    'any_slot': {'lora': 'a.safetensors', 'strength': 0, 'strengthTwo': 0.8},
                    'other_slot': {'lora_name': 'b.safetensors', 'strength': 0.4},
                    'off': {'lora': 'off.safetensors', 'strength': 1, 'on': False},
                    'disabled': {'lora': 'disabled.safetensors', 'strength': 1, 'enabled': False},
                }}
                data = metadata.collect_lora_metadata(prompt, '3')
                rows = data['loras']
                self.assertEqual([(r['strength_model'], r['strength_clip']) for r in rows], [(0, 0.8), (0.4, 0.4), (1, 1), (1, 1)])
                self.assertEqual([r['nonzero_or_unresolved'] for r in rows], [True, True, False, False])
                del prompt['1']['inputs']['clip']
                rows = metadata.collect_lora_metadata(prompt, '3')['loras']
                self.assertEqual([r['strength_clip'] for r in rows], [0, 0, 0, 0])

    def test_generic_ignores_unrecognized_fields(self):
        prompt = {'1': {'class_type': 'CustomLoader', 'inputs': {'name': 'checkpoint.safetensors', 'strength': 1}},
                  '2': {'class_type': 'CustomLoader', 'inputs': {'lora_name': 'a.safetensors'}}}
        self.assertEqual(metadata.collect_lora_metadata(prompt)['loras'], [])

    def test_strengths_and_enabled_rows(self):
        rows = [
            {'on': True, 'lora': 'active.safetensors', 'strength': 0.65},
            {'on': False, 'lora': 'off.safetensors', 'strength': 1},
            {'on': True, 'lora': 'zero.safetensors', 'strength': 0},
            {'on': True, 'lora': 'negative.safetensors', 'strength': -0.4},
            {'on': True, 'lora': 'default.safetensors'},
            {'on': True, 'lora': 'invalid.safetensors', 'strength': 'bad'},
        ]
        prompt = graph(rows)
        data = metadata.collect_lora_metadata(prompt, '3')
        self.assertEqual([r['strength_model'] for r in data['loras']], [0.65, 1, 0, -0.4, 1, 0])
        self.assertEqual([r['nonzero_or_unresolved'] for r in data['loras']], [True, False, False, True, True, False])
        self.assertEqual(hashes._collect_from_prompt(prompt), [('active.safetensors', 'loras'), ('negative.safetensors', 'loras'), ('default.safetensors', 'loras')])
        self.assertEqual(hashes._collect_from_prompt(prompt, {'1'}), [])

    def test_optional_connections(self):
        for model, clip in [(True, False), (False, True), (False, False)]:
            with self.subTest(model=model, clip=clip):
                prompt = graph([{'on': True, 'lora': 'a.safetensors', 'strength': 0.7}], model, clip)
                row = metadata.collect_lora_metadata(prompt, '3')['loras'][0]
                self.assertEqual(row['strength_model'], 0.7 if model else 0)
                self.assertEqual(row['strength_clip'], 0.7 if clip else 0)
                self.assertFalse(row['execution_verified'])

    def test_invalid_serialization(self):
        for value in ['bad', '{}', 'null', '[1, null]', None, ['4', 0]]:
            self.assertEqual(metadata.parse_lc_lora_rows(value), [])

    def test_graph_scope_duplicates_and_primitive_string(self):
        prompt = graph([{'on': True, 'lora': 'a.safetensors', 'strength': 0.5}] * 2)
        prompt['4'] = {'class_type': 'PrimitiveString', 'inputs': {'value': prompt['1']['inputs']['lora_rows']}}
        prompt['1']['inputs']['lora_rows'] = ['4', 0]
        prompt['9'] = graph([{'on': True, 'lora': 'unrelated.safetensors', 'strength': 1}])['1']
        data = metadata.collect_lora_metadata(prompt, '3')
        self.assertEqual(data['loras'][-1]['scope'], 'configured_only')

    def test_workflow_hash_rows(self):
        rows = json.dumps([{'on': True, 'lora': 'a.safetensors', 'strength': 0.5}, {'lora': 'off.safetensors', 'strength': 1}])
        for widgets in [[rows], {'lora_rows': rows}]:
            prompt = {'1': {'class_type': 'LCLoraLoader', 'widgets_values': widgets}}
            self.assertEqual(hashes._collect_from_prompt(prompt), [('a.safetensors', 'loras')])

    def test_png_round_trip_and_existing_loader(self):
        prompt = graph([{'on': True, 'lora': 'lc.safetensors', 'strength': 0.65}], clip=False)
        prompt['0'] = {'class_type': 'LoraLoader', 'inputs': {'lora_name': 'stock.safetensors', 'strength_model': 0.8, 'strength_clip': 0.2}}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(folders, 'get_output_directory', return_value=tmp, create=True), patch.object(folders, 'get_save_image_path', return_value=(tmp, 'test', 1, '', ''), create=True), patch.object(save, 'collect_hashes', return_value={}), patch.object(save, 'format_hash_fields', return_value=()):
                save.LCSaveImage().save(np.zeros((1, 16, 24, 3), dtype=np.float32), metadata={'positive': 'test', 'width': 832, 'height': 1216}, prompt=prompt, unique_id='3', hash_resources=False)
            with Image.open(next(Path(tmp).glob('*.png'))) as image:
                self.assertEqual(image.size, (24, 16))
                params = image.info['parameters']
                self.assertEqual(params.split('\nNegative prompt:')[0].split('\nSteps:')[0].split('\nSize:')[0], 'test')
                self.assertNotIn('<lora:', params)
                for text in ['Size: 832x1216', 'Version: ComfyUI']:
                    self.assertIn(text, params)
                rows = json.loads(image.info['lora_metadata'])['loras']
                self.assertEqual((rows[0]['strength_model'], rows[0]['strength_clip']), (0.65, 0))


    def test_scoped_hashes_and_primary_agreement(self):
        prompt = graph([])
        prompt['0'] = {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'janima.safetensors'}}
        prompt['9'] = {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'other.safetensors'}}
        workflow = {'workflow': {'nodes': [
            {'id': 9, 'type': 'CheckpointLoaderSimple', 'widgets_values': ['other.safetensors']},
            {'id': 10, 'type': 'UNETLoader', 'widgets_values': ['unused.safetensors']},
        ]}}
        calls = []
        def resolve(name, hint):
            calls.append(name)
            return name, 'unet' if name == 'janima.safetensors' else 'model'
        with patch.object(hashes, '_resolve', side_effect=resolve), patch.object(hashes, 'autov2', return_value='E85715BE65'):
            result = hashes.collect_hashes(prompt, workflow, '3')
        self.assertEqual(calls, ['janima.safetensors'])
        self.assertEqual(result['hashes_json']['model'], 'E85715BE65')
        self.assertEqual(hashes.format_hash_fields(result)[0], 'Model hash: E85715BE65')
        result['model'] = [('other', 'BAD')]
        self.assertEqual(hashes.format_hash_fields(result)[0], 'Model hash: E85715BE65')

    def test_boolean_branch_scope(self):
        prompt = graph([])
        prompt['2']['inputs'] = {'image': ['4', 0]}
        prompt['4'] = {'class_type': 'BooleanSwitchNode', 'inputs': {
            'state': ['5', 0], 'on_true': ['1', 0], 'on_false': ['9', 0]}}
        prompt['5'] = {'class_type': 'PrimitiveBoolean', 'inputs': {'value': True}}
        prompt['9'] = {'class_type': 'CheckpointLoaderSimple', 'inputs': {}}
        self.assertIn('1', metadata._image_ancestors(prompt, '3'))
        self.assertNotIn('9', metadata._image_ancestors(prompt, '3'))

    def test_save_keeps_manual_prompt_without_addnet(self):
        prompt = graph([{'on': True, 'lora': 'lc.safetensors', 'strength': 0.65}])
        buckets = {'lora': [('lc', '123456ABCD')], 'hashes_json': {'lora:lc': '123456ABCD'}}
        positive = 'test <lora:manually_written:0.2>'
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(folders, 'get_output_directory', return_value=tmp, create=True), patch.object(folders, 'get_save_image_path', return_value=(tmp, 'test', 1, '', ''), create=True), patch.object(save, 'collect_hashes', return_value=buckets) as collect:
                save.LCSaveImage().save(np.zeros((1, 16, 24, 3), dtype=np.float32), metadata={'positive': positive, 'negative': 'bad', 'civitai_air': '3328902'}, prompt=prompt, unique_id='3')
                self.assertEqual(collect.call_args.args, ({k: v for k, v in prompt.items() if k != '3'}, None))
                self.assertIn('lora_metadata', collect.call_args.kwargs)
            with Image.open(next(Path(tmp).glob('*.png'))) as image:
                params = image.info['parameters']
                self.assertEqual(params.split('\nNegative prompt:')[0], positive)
                self.assertNotIn('<lora:lc:', params)
                self.assertNotIn('AddNet', params)
                self.assertEqual(image.info['civitai_air'], '3328902')

    def test_verified_lora_version_and_stale_sidecar(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'character.safetensors'
            path.write_bytes(b'character weights')
            sidecar = path.with_suffix('.civitai.info')
            info = {'id': 3153756, 'modelId': 2797846, 'model': {'type': 'LORA'},
                    'files': [{'hashes': {'SHA256': hashlib.sha256(path.read_bytes()).hexdigest()}}]}
            sidecar.write_text(json.dumps(info), encoding='utf-8')
            data = metadata.collect_lora_metadata(graph([{'on': True, 'lora': 'character.safetensors', 'strength': 0.8}]), '3')
            with patch.object(hashes, '_resolve', return_value=(str(path), 'lora')):
                expected = [{'type': 'lora', 'modelId': 2797846, 'modelVersionId': 3153756, 'weight': 0.8}]
                self.assertEqual(hashes.lora_resources_payload(data), expected)
                self.assertEqual(hashes.lora_resources_payload(data), expected)
                data['loras'][0]['scope'] = 'configured_only'
                self.assertEqual(hashes.lora_resources_payload(data), [])
                data['loras'][0]['scope'] = 'image_upstream'
                data['loras'][0]['nonzero_or_unresolved'] = False
                self.assertEqual(hashes.lora_resources_payload(data), [])
                data['loras'][0]['nonzero_or_unresolved'] = True
                path.write_bytes(b'changed model weights')
                self.assertEqual(hashes.lora_resources_payload(data), [])
                sidecar.write_text('bad json', encoding='utf-8')
                self.assertEqual(hashes.lora_resources_payload(data), [])

    def test_explicit_lora_resources_in_both_png_fields(self):
        resources = [{'type': 'lora', 'modelId': 2797846, 'modelVersionId': 3153756, 'weight': 0.8}]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(folders, 'get_output_directory', return_value=tmp, create=True), patch.object(folders, 'get_save_image_path', return_value=(tmp, 'test', 1, '', ''), create=True), patch.object(save, 'collect_hashes', return_value={}), patch.object(save, 'lora_resources_payload', return_value=resources):
                save.LCSaveImage().save(np.zeros((1, 16, 24, 3), dtype=np.float32), metadata={'positive': 'clean', 'civitai_air': '3328902'}, prompt=graph([]), unique_id='3')
            with Image.open(next(Path(tmp).glob('*.png'))) as image:
                records = json.loads(image.info['civitaiResources'])
                self.assertEqual(records[1], resources[0])
                self.assertEqual(records[0]['modelVersionId'], 3328902)
                self.assertIn('"modelVersionId":3153756,"weight":0.8', image.info['parameters'])
                self.assertNotIn('<lora:', image.info['parameters'])


if __name__ == '__main__':
    unittest.main()
