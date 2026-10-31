"""
System & Model Optimization Report, server side.

POST /lc123/syscheck/run runs lc_system_probe (hardware, software, small live GPU tests, pack pre-flight checks),
saves the result as user/LC123/system_profile.json for the LC Optimizer node, and returns it with its findings.
GET /lc123/syscheck/profile returns the last saved profile. Nothing is installed or changed.
"""

from __future__ import annotations

import json
import os
import threading

from . import lc_system_probe

_LOCK = threading.Lock()


def profile_path():
    try:
        import folder_paths

        root = folder_paths.get_user_directory()
    except Exception:
        root = os.path.join(os.path.dirname(__file__), "user")
    return os.path.join(root, "LC123", "system_profile.json")


def _add_install(prof):
    """Recommended to install: links only, worked out fresh each time (so a saved report shows current advice)."""
    try:
        from . import lc_install_recs

        prof["install"] = lc_install_recs.install_recs(prof)
    except Exception as e:
        prof["install"] = {"error": str(e), "items": []}
    return prof


def run_and_save():
    """Runs in a worker thread. One run at a time."""
    if not _LOCK.acquire(blocking=False):
        return {"error": "A system check is already running."}
    try:
        prof = lc_system_probe.probe()
        try:
            from . import lc_model_calc

            prof["shopping"] = lc_model_calc.shopping_guide(prof)  # model-independent: what file formats suit this machine
        except Exception as e:
            prof["shopping"] = {"error": str(e)}
        _add_install(prof)
        path = profile_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(prof, f, indent=1, ensure_ascii=False, default=str)
            prof["saved_to"] = path
        except OSError as e:
            prof["saved_to"] = None
            prof["save_error"] = str(e)
        return prof
    finally:
        _LOCK.release()


try:
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.post("/lc123/syscheck/run")
    async def _lc123_syscheck_run(request):
        import asyncio

        try:
            busy = PromptServer.instance.prompt_queue.get_tasks_remaining() > 0
        except Exception:
            busy = False
        if busy:  # the live tests use the GPU: never while a workflow is generating
            return web.json_response({"error": "ComfyUI is generating right now. Run the system check when the queue is empty."}, status=409)
        prof = await asyncio.get_running_loop().run_in_executor(None, run_and_save)
        return web.json_response(json.loads(json.dumps(prof, default=str)))

    @PromptServer.instance.routes.get("/lc123/syscheck/profile")
    async def _lc123_syscheck_profile(request):
        try:
            with open(profile_path(), encoding="utf-8") as f:
                return web.json_response(json.loads(json.dumps(_add_install(json.load(f)), default=str)))
        except Exception:
            return web.json_response({"error": "No system check has been run yet."}, status=404)

    @PromptServer.instance.routes.get("/lc123/syscheck/models")
    async def _lc123_syscheck_models(request):
        from . import lc_model_calc as calc

        out = []
        for mid, m in calc.load_profiles().items():
            sizes = set()
            for ref in calc._references(m):
                sizes |= {r["megapixels"] for r in ref.get("runs", [])}
            out.append({"id": mid, "name": m["name"], "kind": m.get("kind"), "sizes": sorted(sizes)})
        return web.json_response(sorted(out, key=lambda x: (x["kind"] != "image", x["name"])))

    @PromptServer.instance.routes.get("/lc123/syscheck/recommend")
    async def _lc123_syscheck_recommend(request):
        from . import lc_model_calc as calc

        try:
            with open(profile_path(), encoding="utf-8") as f:
                sysp = json.load(f)
        except Exception:
            return web.json_response({"error": "Run the system check first."}, status=404)
        q = request.rel_url.query
        models = calc.load_profiles([q.get("model")])
        if not models:
            return web.json_response({"error": "Unknown model."}, status=404)
        try:
            mp = float(q["mp"]) if q.get("mp") else None
        except ValueError:
            return web.json_response({"error": "mp must be a number."}, status=400)
        rec = calc.recommend(next(iter(models.values())), sysp, q.get("goal", "Optimal"), mp)
        return web.json_response(json.loads(json.dumps(rec, default=str)))

except Exception:
    pass
