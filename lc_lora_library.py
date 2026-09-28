"""Local LoRA sidecars and previews; Civitai lookup only on an explicit selection."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import ssl
import uuid
from urllib.parse import quote, urlparse

import aiohttp
from aiohttp import web
import folder_paths


SERVER_SESSION = uuid.uuid4().hex

MAX_INFO_BYTES = 8 * 1024 * 1024
MAX_HEADER_BYTES = 64 * 1024 * 1024
PREVIEW_EXTENSIONS = ('.webp', '.png', '.jpg', '.jpeg')


def resolve_lora(name):
    # Membership in ComfyUI's registry also rejects absolute paths and traversal.
    if not isinstance(name, str) or name not in folder_paths.get_filename_list('loras'):
        raise FileNotFoundError('LoRA not found in the configured model folders.')
    path = folder_paths.get_full_path('loras', name)
    if not path or not os.path.isfile(path):
        raise FileNotFoundError('LoRA file is no longer available.')
    return Path(path)


def read_header(path):
    if path.suffix.lower() != '.safetensors':
        return {}
    with path.open('rb') as stream:
        size_bytes = stream.read(8)
        if len(size_bytes) != 8:
            return {}
        size = struct.unpack('<Q', size_bytes)[0]
        if not 0 < size <= MAX_HEADER_BYTES:
            return {}
        header = json.loads(stream.read(size))
    meta = header.get('__metadata__', {}) if isinstance(header, dict) else {}
    return meta if isinstance(meta, dict) else {}


def header_words(meta):
    for key in ('modelspec.trigger_phrase', 'trigger_phrase', 'ss_trigger_word'):
        if meta.get(key):
            return [str(meta[key])]
    freq = meta.get('ss_tag_frequency')
    if isinstance(freq, str):
        try:
            freq = json.loads(freq)
        except ValueError:
            freq = None
    counts = {}
    if isinstance(freq, dict):
        for tags in freq.values():
            if isinstance(tags, dict):
                for tag, count in tags.items():
                    try:
                        counts[tag] = counts.get(tag, 0) + int(count)
                    except (TypeError, ValueError):
                        continue
    return sorted(counts, key=counts.get, reverse=True)[:25]


def sidecar_paths(path):
    return list(dict.fromkeys([
        path.with_suffix('.civitai.info'), Path(str(path) + '.civitai.info'),
    ]))


def read_sidecar(path):
    for candidate in sidecar_paths(path):
        try:
            if candidate.stat().st_size > MAX_INFO_BYTES:
                continue
            data = json.loads(candidate.read_text(encoding='utf-8-sig'))
            if isinstance(data, dict) and data:
                return data, candidate
        except (OSError, ValueError):
            continue
    return {}, None


def preview_path(path):
    for suffix in ('.preview', ''):
        for ext in PREVIEW_EXTENSIONS:
            candidate = path.with_suffix(suffix + ext)
            if candidate.is_file():
                return candidate
    return None


def image_urls(data):
    result = []
    for item in data.get('images', []) if isinstance(data.get('images'), list) else []:
        if not isinstance(item, dict) or item.get('type') == 'video':
            continue
        url = item.get('url')
        if not isinstance(url, str):
            continue
        parsed = urlparse(url)
        if parsed.scheme == 'https' and parsed.hostname in ('image.civitai.com', 'images.civitai.com'):
            result.append(url)
    return result


def read_info(name, path, details=False):
    data, sidecar = read_sidecar(path)
    civitai = data
    try:
        meta = read_header(path) if details else {}
    except (OSError, ValueError, UnicodeError):
        meta = {}
    words = []
    for source in (data, civitai):
        for key in ('trainedWords', 'triggerWords'):
            values = source.get(key, [])
            if not isinstance(values, list):
                continue
            for value in values:
                word = value.get('word') if isinstance(value, dict) else value
                if isinstance(word, str) and word.strip() and word not in words:
                    words.append(word)
    if not words:
        words = header_words(meta)
    images = list(dict.fromkeys(image_urls(data) + image_urls(civitai)))
    if preview_path(path):
        images.insert(0, '/lc123/group_lora_loader/preview?lora=' + quote(name, safe=''))
    model = civitai.get('model') if isinstance(civitai.get('model'), dict) else {}
    model_id, version_id = civitai.get('modelId'), civitai.get('id')
    link = None
    if isinstance(model_id, int):
        link = f'https://civitai.com/models/{model_id}'
        if isinstance(version_id, int):
            link += f'?modelVersionId={version_id}'
    return {
        'lora': name,
        'name': model.get('name') or data.get('name') or path.stem,
        'version': civitai.get('name') if model else '',
        'base_model': data.get('baseModel') or civitai.get('baseModel') or meta.get('ss_base_model_version') or meta.get('modelspec.architecture') or meta.get('ss_sd_model_name'),
        'description': civitai.get('description') or model.get('description') or '',
        'trigger_words': words, 'images': images,
        'preview_url': images[0] if images else None,
        'has_info': sidecar is not None, 'has_info_file': sidecar is not None,
        'has_metadata': bool(meta), 'metadata': meta,
        'info_file': sidecar.name if sidecar else None,
        'raw_info': data if details else {}, 'civitai_url': link,
        'source': 'sidecar' if sidecar else ('metadata' if meta else 'none'),
    }


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def save_sidecar(path, data, force=False):
    # Atomic publish; reuse any sidecar that appeared while the request was running.
    existing = read_sidecar(path)[1]
    if existing and not force:
        return
    target = existing or path.with_suffix('.civitai.info')
    fd, temp = tempfile.mkstemp(prefix='.lc-info-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


async def download_civitai(session, digest, context=None):
    async with session.get(
        f'https://civitai.com/api/v1/model-versions/by-hash/{digest}',
        headers={'User-Agent': 'ComfyUI-LC123-LoRA-Library'},
        allow_redirects=False, ssl=context,
    ) as response:
        if response.status == 404:
            raise ValueError('No matching model was found on Civitai.')
        response.raise_for_status()
        if response.status != 200:
            raise ValueError('Unexpected Civitai response.')
        body = bytearray()
        async for chunk in response.content.iter_chunked(65536):
            body.extend(chunk)
            if len(body) > MAX_INFO_BYTES:
                raise ValueError('Civitai info exceeds the size limit.')
        data = json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get('id'), int):
            raise ValueError('Civitai returned invalid model information.')
        return data


async def download_with_certificate_compatibility(session, digest):
    try:
        return await download_civitai(session, digest)
    except aiohttp.ClientConnectorCertificateError as error:
        # Python 3.13 enables RFC-strict checks. Some trusted local proxy CAs lack AKI.
        # Retry only that exact compatibility error; chain and hostname checks stay on.
        reason = error.certificate_error
        if not isinstance(reason, ssl.SSLCertVerificationError) or getattr(reason, 'verify_code', None) != 85:
            raise
        context = ssl.create_default_context()
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
        return await download_civitai(session, digest, context)


def scan_library():
    scanner = getattr(folder_paths, 'get_filename_list_', None)
    if scanner:
        scanned = scanner('loras')
        folder_paths.filename_list_cache['loras'] = scanned
        names = scanned[0]
    else:
        names = folder_paths.get_filename_list('loras')
    modified = {}
    for name in names:
        try:
            modified[name] = os.stat(folder_paths.get_full_path('loras', name)).st_mtime_ns
        except (OSError, TypeError):
            modified[name] = 0
    return {'loras': sorted(names, key=lambda name: (-modified[name], name.casefold())), 'session': SERVER_SESSION}


class LoraInfoService:
    def __init__(self):
        self.pending = {}
        self.limit = asyncio.Semaphore(2)

    async def fetch_missing(self, name, path, force=False):
        key = (str(path.resolve()), force)
        if key not in self.pending:
            task = asyncio.create_task(self._fetch(name, path, force))
            self.pending[key] = task
            task.add_done_callback(lambda done: self.pending.pop(key, None))
        return await asyncio.shield(self.pending[key])

    async def _fetch(self, name, path, force=False):
        async with self.limit:
            info = await asyncio.to_thread(read_info, name, path)
            if info['has_info_file'] and not force:
                return info
            try:
                digest = await asyncio.to_thread(file_sha256, path)
                timeout = aiohttp.ClientTimeout(total=35, connect=10)
                async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
                    data = await download_with_certificate_compatibility(session, digest)
                await asyncio.to_thread(save_sidecar, path, data, force)
                return await asyncio.to_thread(read_info, name, path)
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as error:
                info['fetch_error'] = 'Could not download model information. ' + str(error)
                return info


def register_routes(routes):
    service = LoraInfoService()

    @routes.get('/lc123/group_lora_loader/library')
    async def library(request):
        return web.json_response(await asyncio.to_thread(scan_library))

    @routes.get('/lc123/group_lora_loader/info')
    async def local_info(request):
        name = request.query.get('lora', '')
        try:
            path = await asyncio.to_thread(resolve_lora, name)
            info = await asyncio.to_thread(read_info, name, path, request.query.get('details') == '1')
        except FileNotFoundError as error:
            return web.json_response({'error': str(error)}, status=404)
        return web.json_response(info)

    @routes.post('/lc123/group_lora_loader/info')
    async def fetch_info(request):
        try:
            body = await request.json()
            name = body.get('lora') if isinstance(body, dict) else None
            path = await asyncio.to_thread(resolve_lora, name)
        except (ValueError, TypeError):
            return web.json_response({'error': 'Expected a LoRA filename.'}, status=400)
        except FileNotFoundError as error:
            return web.json_response({'error': str(error)}, status=404)
        return web.json_response(await service.fetch_missing(name, path, force=body.get('force') is True))

    @routes.get('/lc123/group_lora_loader/preview')
    async def local_preview(request):
        try:
            path = await asyncio.to_thread(resolve_lora, request.query.get('lora', ''))
            image = await asyncio.to_thread(preview_path, path)
        except FileNotFoundError:
            raise web.HTTPNotFound()
        if image is None:
            raise web.HTTPNotFound()
        return web.FileResponse(image)
