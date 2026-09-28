import asyncio
import importlib.util
import json
import os
import ssl
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer


folders = types.ModuleType('folder_paths')
spec = importlib.util.spec_from_file_location('lc_library_test', Path(__file__).resolve().parents[1] / 'lc_lora_library.py')
library = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'folder_paths': folders}):
    spec.loader.exec_module(library)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.body = json.dumps(payload).encode()
        self.status = status
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def raise_for_status(self):
        if self.status >= 400:
            raise library.aiohttp.ClientError('Remote error')

    async def iter_chunked(self, size):
        await asyncio.sleep(0)
        yield self.body


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


class LoraLibraryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'sample.safetensors'
        header = json.dumps({'__metadata__': {'modelspec.trigger_phrase': 'local trigger', 'ss_base_model_version': 'anima'}}).encode()
        self.path.write_bytes(struct.pack('<Q', len(header)) + header + b'weights')
        folders.get_filename_list = lambda category: ['sample.safetensors']
        folders.get_full_path = lambda category, name: str(self.path) if name == 'sample.safetensors' else None
        self.version = {
            'id': 123, 'modelId': 45, 'name': 'V2', 'baseModel': 'Anima',
            'model': {'name': 'Example LoRA'}, 'trainedWords': ['one', 'two'],
            'images': [{'url': 'https://image.civitai.com/example.jpeg', 'type': 'image'}],
        }

    async def test_invalid_header_still_allows_sidecar_details(self):
        self.path.with_suffix('.civitai.info').write_text(json.dumps(self.version))
        for data in [[], None, 3, {'__metadata__': []}]:
            header = json.dumps(data).encode()
            self.path.write_bytes(struct.pack('<Q', len(header)) + header)
            with self.subTest(header=data):
                info = library.read_info('sample.safetensors', self.path, details=True)
                self.assertEqual(info['metadata'], {})
                self.assertEqual(info['trigger_words'], ['one', 'two'])
                self.assertTrue(info['has_info_file'])

    async def test_full_scan_orders_newest_first(self):
        other = self.path.parent / 'new.safetensors'
        other.write_bytes(b'new')
        os.utime(self.path, ns=(1000000000, 1000000000))
        os.utime(other, ns=(2000000000, 2000000000))
        scanned = (['sample.safetensors', 'new.safetensors'], {}, 0)
        with patch.object(folders, 'get_filename_list_', return_value=scanned, create=True) as scanner, patch.object(folders, 'filename_list_cache', {}, create=True), patch.object(folders, 'get_full_path', side_effect=lambda category, name: str(self.path.parent / name)):
            for _ in range(2):
                result = library.scan_library()
                self.assertEqual(result['loras'], ['new.safetensors', 'sample.safetensors'])
                self.assertEqual(result['session'], library.SERVER_SESSION)
            self.assertEqual(scanner.call_count, 2)
            self.assertEqual(folders.filename_list_cache['loras'], scanned)

    async def test_certificate_compatibility_preserves_chain_and_hostname_checks(self):
        reason = ssl.SSLCertVerificationError(1, 'Missing Authority Key Identifier')
        reason.verify_code = 85
        error = library.aiohttp.ClientConnectorCertificateError(None, reason)
        with patch.object(library, 'download_civitai', new_callable=AsyncMock, side_effect=[error, self.version]) as download:
            result = await library.download_with_certificate_compatibility(None, 'hash')
        self.assertEqual(result, self.version)
        self.assertEqual(download.call_count, 2)
        context = download.call_args.args[2]
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertFalse(context.verify_flags & ssl.VERIFY_X509_STRICT)

    async def test_other_certificate_errors_are_not_retried(self):
        for code in [10, 18, 20, 62]:
            reason = ssl.SSLCertVerificationError(1, 'Invalid certificate')
            reason.verify_code = code
            error = library.aiohttp.ClientConnectorCertificateError(None, reason)
            with patch.object(library, 'download_civitai', new_callable=AsyncMock, side_effect=error) as download:
                with self.assertRaises(library.aiohttp.ClientConnectorCertificateError):
                    await library.download_with_certificate_compatibility(None, 'hash')
                self.assertEqual(download.call_count, 1)

    async def test_only_civitai_sidecars_are_used(self):
        for suffix in ('.rgthree-info.json', '.cm-info.json', '.json'):
            Path(str(self.path) + suffix).write_text(json.dumps(self.version))
        info = library.read_info('sample.safetensors', self.path, details=True)
        self.assertFalse(info['has_info_file'])
        self.assertFalse(info['has_info'])
        self.assertEqual(info['trigger_words'], ['local trigger'])
        self.assertEqual(info['images'], [])
        self.path.with_suffix('.civitai.info').write_text(json.dumps(self.version))
        info = library.read_info('sample.safetensors', self.path, details=True)
        self.assertTrue(info['has_info'])
        self.assertEqual(info['trigger_words'], ['one', 'two'])
        self.assertEqual(info['metadata']['modelspec.trigger_phrase'], 'local trigger')
        self.assertEqual(info['civitai_url'], 'https://civitai.com/models/45?modelVersionId=123')
        light = library.read_info('sample.safetensors', self.path)
        self.assertEqual(light['metadata'], {})
        self.assertEqual(light['raw_info'], {})

    async def test_path_validation_and_local_preview(self):
        for name in ['../sample.safetensors', str(self.path), '', None, 'missing.safetensors']:
            with self.subTest(name=name), self.assertRaises(FileNotFoundError):
                library.resolve_lora(name)
        self.path.with_suffix('.preview.png').write_bytes(b'preview')
        info = library.read_info('sample.safetensors', self.path)
        self.assertEqual(info['preview_url'], '/lc123/group_lora_loader/preview?lora=sample.safetensors')

    async def test_downloads_standard_info_once_for_concurrent_requests(self):
        session = FakeSession(FakeResponse(self.version))
        service = library.LoraInfoService()
        with patch.object(library.aiohttp, 'ClientSession', return_value=session):
            results = await asyncio.gather(*(service.fetch_missing('sample.safetensors', self.path) for _ in range(3)))
            await service.fetch_missing('sample.safetensors', self.path)
        self.assertEqual(len(session.calls), 1)
        self.assertIn('/api/v1/model-versions/by-hash/', session.calls[0][0])
        self.assertEqual(session.calls[0][0].rsplit('/', 1)[1], library.file_sha256(self.path))
        self.assertFalse(session.calls[0][1]['allow_redirects'])
        self.assertTrue(all(info['has_info_file'] for info in results))
        self.assertEqual(json.loads(self.path.with_suffix('.civitai.info').read_text()), self.version)
        self.assertEqual(list(self.path.parent.glob('.lc-info-*')), [])

    async def test_existing_info_is_not_overwritten(self):
        target = Path(str(self.path) + '.civitai.info')
        target.write_text(json.dumps(self.version))
        with patch.object(library.aiohttp, 'ClientSession', side_effect=AssertionError('No network for existing info')):
            data = await library.LoraInfoService().fetch_missing('sample.safetensors', self.path)
        self.assertEqual(data['version'], 'V2')
        self.assertFalse(self.path.with_suffix('.civitai.info').exists())

    async def test_force_refresh_replaces_existing_sidecar(self):
        target = Path(str(self.path) + '.civitai.info')
        target.write_text(json.dumps(self.version))
        updated = {**self.version, 'name': 'Updated version'}
        session = FakeSession(FakeResponse(updated))
        with patch.object(library.aiohttp, 'ClientSession', return_value=session):
            data = await library.LoraInfoService().fetch_missing('sample.safetensors', self.path, force=True)
        self.assertEqual(data['version'], 'Updated version')
        self.assertEqual(json.loads(target.read_text()), updated)
        self.assertFalse(self.path.with_suffix('.civitai.info').exists())
        self.assertEqual(len(session.calls), 1)

    async def test_failed_refresh_preserves_existing_info(self):
        target = self.path.with_suffix('.civitai.info')
        target.write_text(json.dumps(self.version))
        original = target.read_bytes()
        with patch.object(library.aiohttp, 'ClientSession', return_value=FakeSession(FakeResponse({}, 500))):
            data = await library.LoraInfoService().fetch_missing('sample.safetensors', self.path, force=True)
        self.assertIn('fetch_error', data)
        self.assertTrue(data['has_info_file'])
        self.assertEqual(target.read_bytes(), original)

    async def test_remote_failure_keeps_selection_available(self):
        for payload, status in [({}, 404), ({'error': 'invalid'}, 200), ({}, 500)]:
            with self.subTest(status=status):
                session = FakeSession(FakeResponse(payload, status))
                with patch.object(library.aiohttp, 'ClientSession', return_value=session):
                    data = await library.LoraInfoService().fetch_missing('sample.safetensors', self.path)
                self.assertIn('fetch_error', data)
                self.assertFalse(data['has_info_file'])
                self.assertFalse(self.path.with_suffix('.civitai.info').exists())

    async def test_invalid_json_and_preview_urls(self):
        self.path.with_suffix('.civitai.info').write_text('{broken')
        self.assertFalse(library.read_info('sample.safetensors', self.path)['has_info_file'])
        data = {'images': [{'url': 'javascript:alert(1)'}, {'url': 'http://localhost:123/private'},
                           {'url': 'https://image.civitai.com/video.mp4', 'type': 'video'},
                           {'url': 'https://image.civitai.com/a.jpeg'}]}
        self.assertEqual(library.image_urls(data), ['https://image.civitai.com/a.jpeg'])

    async def test_http_routes_local_browse_then_explicit_download(self):
        routes = web.RouteTableDef()
        library.register_routes(routes)
        app = web.Application()
        app.add_routes(routes)
        async with TestClient(TestServer(app)) as client:
            response = await client.get('/lc123/group_lora_loader/library')
            self.assertEqual((await response.json())['loras'], ['sample.safetensors'])
            with patch.object(library.aiohttp, 'ClientSession', side_effect=AssertionError('Browsing must be local')):
                response = await client.get('/lc123/group_lora_loader/info?lora=sample.safetensors&details=1')
                self.assertEqual(response.status, 200)
                self.assertEqual((await response.json())['trigger_words'], ['local trigger'])
            response = await client.get('/lc123/group_lora_loader/info?lora=../sample.safetensors')
            self.assertEqual(response.status, 404)
            session = FakeSession(FakeResponse(self.version))
            with patch.object(library.aiohttp, 'ClientSession', return_value=session):
                response = await client.post('/lc123/group_lora_loader/info', json={'lora': 'sample.safetensors'})
                self.assertEqual(response.status, 200)
                self.assertTrue((await response.json())['has_info_file'])
            updated = {**self.version, 'name': 'HTTP refresh'}
            with patch.object(library.aiohttp, 'ClientSession', return_value=FakeSession(FakeResponse(updated))):
                response = await client.post('/lc123/group_lora_loader/info', json={'lora': 'sample.safetensors', 'force': True})
                self.assertEqual((await response.json())['version'], 'HTTP refresh')
            response = await client.post('/lc123/group_lora_loader/info', data='not json', headers={'Content-Type': 'application/json'})
            self.assertEqual(response.status, 400)


if __name__ == '__main__':
    unittest.main()
