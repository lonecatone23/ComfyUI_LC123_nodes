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
    def test_source_size_variants(self):
        for width, height, sw, sh, expected in [
            (24, 16, 24, 16, None),
            (48, 32, 24, 16, '24x16'),
            (12, 8, 24, 16, '24x16'),
            (12, 16, 24, 16, '24x16'),
            (24, 16, None, None, None),
            (24, 16, 0, 16, None),
        ]:
            with self.subTest(output=(width, height), source=(sw, sh)):
                text = save._build_parameters({}, width, height, source_width=sw, source_height=sh)
                self.assertIn(f'Size: {width}x{height}', text)
                if expected is None:
                    self.assertNotIn('Source size:', text)
                else:
                    self.assertIn('Source size: ' + expected, text)

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
                self.assertEqual(metadata.append_lora_tags('', data), '<lora:generic:-0.6>')

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
                self.assertEqual(metadata.append_lora_tags('', data), '<lora:a:0> <lora:b:0.4>')
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
        self.assertEqual(metadata.append_lora_tags('test', data), 'test\n<lora:active:0.65> <lora:negative:-0.4> <lora:default:1>')
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
        self.assertEqual(metadata.append_lora_tags('', data), '<lora:a:0.5> <lora:a:0.5>')
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
            with patch.object(folders, 'get_output_directory', return_value=tmp, create=True), patch.object(folders, 'get_save_image_path', return_value=(tmp, 'test', 1, '', ''), create=True), patch.object(save, 'collect_hashes', return_value={}), patch.object(save, 'format_hash_fields', return_value=None):
                save.LCSaveImage().save(np.zeros((1, 16, 24, 3), dtype=np.float32), metadata={'positive': 'test', 'width': 832, 'height': 1216}, prompt=prompt, unique_id='3', hash_resources=False)
            with Image.open(next(Path(tmp).glob('*.png'))) as image:
                self.assertEqual(image.size, (24, 16))
                params = image.info['parameters']
                for text in ['Size: 24x16', 'Source size: 832x1216', '<lora:lc:0.65>', '<lora:stock:0.8>']:
                    self.assertIn(text, params)
                rows = json.loads(image.info['lora_metadata'])['loras']
                self.assertEqual((rows[0]['strength_model'], rows[0]['strength_clip']), (0.65, 0))


if __name__ == '__main__':
    unittest.main()
