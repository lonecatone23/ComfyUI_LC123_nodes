"""Verify weight execution and stack interoperability without loading a GPU model."""

import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from aiohttp import web


class LoraWeightTests(unittest.TestCase):
    def setUp(self):
        package = types.ModuleType('lc_weight_test')
        package.__path__ = [str(Path(__file__).resolve().parents[1])]
        folders = types.ModuleType('folder_paths')
        folders.get_full_path = lambda kind, name: '/fixture/' + name
        comfy = types.ModuleType('comfy')
        comfy.__path__ = []
        comfy.sd = types.ModuleType('comfy.sd')
        comfy.sd.load_lora_for_models = Mock(side_effect=lambda model, clip, *args, **kwargs: (model, clip))
        comfy.utils = types.ModuleType('comfy.utils')
        comfy.utils.load_torch_file = Mock(return_value=({}, {'test': 'metadata'}))
        server = types.ModuleType('server')
        server.PromptServer = types.SimpleNamespace(instance=types.SimpleNamespace(routes=web.RouteTableDef()))
        with patch.dict(sys.modules, {
            'lc_weight_test': package, 'folder_paths': folders, 'comfy': comfy,
            'comfy.sd': comfy.sd, 'comfy.utils': comfy.utils, 'server': server,
        }):
            self.group_module = importlib.import_module('lc_weight_test.lc_group_lora_loader')
            self.loader = self.group_module.LCGroupLoraLoader()
            self.original_module = importlib.import_module('lc_weight_test.lc_lora_loader')
            self.original = self.original_module.LCLoraLoader()
            self.weights = importlib.import_module('lc_weight_test.lc_lora_weights')
            self.hashes = importlib.import_module('lc_weight_test.lc_civitai_hashes')
            self.routes = server.PromptServer.instance.routes
            self.group_stack_module = importlib.import_module('lc_weight_test.lc_group_lora_stack')
            self.group_stack = self.group_stack_module.LCGroupLoraLoaderStack()
            stack = importlib.import_module('lc_weight_test.lc_lora_stack')
            self.stack, self.apply = stack.LCLoraLoaderStack(), stack.LCApplyLoraStack()
            self.metadata = importlib.import_module('lc_weight_test.lc_lora_metadata')
        self.comfy = comfy

    def test_loader_stack_and_metadata_agree_on_independent_weights(self):
        rows = [
            {'on': True, 'lora': 'a.safetensors', 'strength': 0, 'strengthTwo': 0.65},
            {'on': True, 'lora': 'a.safetensors', 'strength': -0.4, 'strengthTwo': 0},
            {'on': True, 'lora': 'legacy.safetensors', 'strength': 0.8},
            {'on': True, 'lora': 'zero.safetensors', 'strength': 0, 'strengthTwo': 0},
            {'on': False, 'lora': 'disabled.safetensors', 'strength': 1, 'strengthTwo': 1},
        ]
        serialized = json.dumps(rows)
        expected = [(0, 0.65), (-0.4, 0), (0.8, 0.8)]
        self.assertEqual(self.loader.load('model', 'clip', serialized), ('model', 'clip'))
        calls = self.comfy.sd.load_lora_for_models.call_args_list
        self.assertEqual([call.args[3:5] for call in calls], expected)
        self.assertEqual(self.comfy.utils.load_torch_file.call_count, 2)
        self.assertTrue(all(call.kwargs['lora_metadata'] == {'test': 'metadata'} for call in calls))
        built = self.group_stack.build(serialized)[0]
        self.assertEqual([entry[1:] for entry in built], expected)
        self.comfy.sd.load_lora_for_models.reset_mock()
        self.apply.apply(model='model', clip='clip', lora_stack=built)
        self.assertEqual([call.args[3:5] for call in self.comfy.sd.load_lora_for_models.call_args_list], expected)
        graph = {'1': {'class_type': 'LCGroupLoraLoader', 'inputs': {
            'model': ['0', 0], 'clip': ['0', 1], 'lora_rows': serialized,
        }}}
        records = self.metadata.collect_lora_metadata(graph)['loras']
        self.assertEqual([(row['strength_model'], row['strength_clip']) for row in records[:3]], expected)
        self.assertEqual(self.hashes._collect_from_prompt(graph), [('a.safetensors', 'loras'), ('legacy.safetensors', 'loras')])

    def test_legacy_defaults_and_invalid_weights(self):
        rows = [
            {'on': True, 'lora': 'default'},
            {'on': True, 'lora': 'null_clip', 'strength': 0.3, 'strengthTwo': None},
            {'on': True, 'lora': 'invalid_model', 'strength': 'bad', 'strengthTwo': 0.6},
            {'on': True, 'lora': 'invalid_clip', 'strength': 0.4, 'strengthTwo': 'bad'},
            {'on': True, 'lora': 'nonfinite', 'strength': float('inf'), 'strengthTwo': float('nan')},
        ]
        self.assertEqual([self.weights.row_strengths(row) for row in rows],
                         [(1, 1), (0.3, 0.3), (0, 0.6), (0.4, 0), (0, 0)])

    def test_clip_only_row_is_applied_without_model(self):
        row = {'on': True, 'lora': 'clip.safetensors', 'strength': 0, 'strengthTwo': 0.7}
        self.assertEqual(self.loader.load(None, 'clip', json.dumps([row])), (None, 'clip'))
        self.assertEqual(self.comfy.sd.load_lora_for_models.call_args.args[3:5], (0, 0.7))

    def test_original_loader_and_stack_retain_shared_strength(self):
        row = {'on': True, 'lora': 'original.safetensors', 'strength': 0.4, 'strengthTwo': 0.9}
        self.original.load('model', 'clip', json.dumps([row]))
        self.assertEqual(self.comfy.sd.load_lora_for_models.call_args.args[3:5], (0.4, 0.4))
        self.assertEqual(self.stack.build(json.dumps([row]))[0], [('original.safetensors', 0.4, 0.4)])
        graph = {'1': {'class_type': 'LCLoraLoader', 'inputs': {
            'model': ['0', 0], 'clip': ['0', 1], 'lora_rows': json.dumps([row]),
        }}}
        record = self.metadata.collect_lora_metadata(graph)['loras'][0]
        self.assertEqual((record['strength_model'], record['strength_clip']), (0.4, 0.4))

    def test_group_clip_only_metadata_and_hashes(self):
        row = {'on': True, 'lora': 'clip.safetensors', 'strength': 0, 'strengthTwo': 0.7}
        graph = {'1': {'class_type': 'LCGroupLoraLoader', 'inputs': {
            'clip': ['0', 1], 'lora_rows': json.dumps([row]),
        }}}
        record = self.metadata.collect_lora_metadata(graph)['loras'][0]
        self.assertEqual((record['strength_model'], record['strength_clip']), (0, 0.7))
        self.assertEqual(self.hashes._collect_from_prompt(graph), [('clip.safetensors', 'loras')])

    def test_distinct_node_mappings_and_routes(self):
        group, original = self.group_module, self.original_module
        self.assertEqual(group.NODE_DISPLAY_NAME_MAPPINGS, {'LCGroupLoraLoader': 'LC Group LoRA Loader 🎚️'})
        self.assertEqual(original.NODE_DISPLAY_NAME_MAPPINGS, {'LCLoraLoader': 'LC LoRA Loader 🎚️'})
        paths = [(route.method, route.path) for route in self.routes]
        self.assertIn(('GET', '/lc123/lora_loader/info'), paths)
        self.assertIn(('GET', '/lc123/group_lora_loader/info'), paths)
        self.assertEqual(len(paths), len(set(paths)))

    def test_group_loader_ignores_malformed_rows_and_names(self):
        for value in ['null', '{}', '3', 'true', 'bad', None, '[null, 3]',
                      '[{"on": true, "lora": 3}]', '[{"on": true, "lora": "none"}]']:
            with self.subTest(value=value):
                self.assertEqual(self.loader.load('model', 'clip', value), ('model', 'clip'))
        self.comfy.utils.load_torch_file.assert_not_called()
        self.comfy.sd.load_lora_for_models.assert_not_called()

    def test_group_stack_validation_and_hashes(self):
        for value in ['null', '{}', 'bad', None, '[null, 3]']:
            self.assertEqual(self.group_stack.build(value), ([],))
        rows = [{'on': True, 'lora': 'clip.safetensors', 'strength': 0, 'strengthTwo': 0.5},
                {'on': False, 'lora': 'disabled.safetensors', 'strength': 1},
                {'on': True, 'lora': 'zero.safetensors', 'strength': 0, 'strengthTwo': 0}]
        graph = {'1': {'class_type': 'LCGroupLoraLoaderStack', 'inputs': {'lora_rows': json.dumps(rows)}}}
        self.assertEqual(self.hashes._collect_from_prompt(graph), [('clip.safetensors', 'loras')])
        self.assertEqual(self.group_stack.RETURN_TYPES, ('LORA_STACK',))
        self.assertEqual(set(self.group_stack.INPUT_TYPES()['optional']), {'lora_rows'})
        self.assertEqual(self.group_stack_module.NODE_DISPLAY_NAME_MAPPINGS,
                         {'LCGroupLoraLoaderStack': 'LC Group LoRA Loader Stack 🎚️'})


if __name__ == '__main__':
    unittest.main()
