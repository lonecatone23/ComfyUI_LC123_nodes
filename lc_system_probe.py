"""
System & Model Optimization Report probe: what this machine has, and what actually works on it.

Used by the System & Model Optimization Report button (POST /lc123/syscheck/run) and saved as user/LC123/system_profile.json for the
LC Optimizer node. It also runs on its own, without ComfyUI:  python lc_system_probe.py [out.json]
Nothing is installed or changed. The live GPU tests are small (a few hundred MB, a few seconds).
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time

PROFILE_VERSION = 1


def _run(cmd, timeout=10):
    try:
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW: no console flash on Windows
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=flags)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _mb(b):
    return round(b / 2**20)


def _gb(b):
    return round(b / 2**30, 1)


# ---------------------------------------------------------------- machine
def cpu_name():
    if os.name == "nt":
        try:
            import winreg

            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except Exception:
            pass
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or platform.machine()


def machine():
    out = {"os": f"{platform.system()} {platform.release()} ({platform.version()})", "python": sys.version.split()[0], "cpu": cpu_name(), "cpu_threads": os.cpu_count()}
    try:
        import psutil

        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        out.update(ram_total_gb=_gb(vm.total), ram_free_gb=_gb(vm.available), swap_total_gb=_gb(sw.total), cpu_cores=psutil.cpu_count(logical=False))
    except Exception:
        pass
    if os.name == "nt":
        out.update(pagefile_windows())
    return out


def pagefile_windows():
    """Windows-managed page files start small and grow when needed, so the current size alone says little."""
    ps = (
        "$cs=Get-CimInstance Win32_ComputerSystem; $s=@(Get-CimInstance Win32_PageFileSetting | ForEach-Object { @{name=$_.Name; initial=$_.InitialSize; max=$_.MaximumSize} });"
        "@{auto=$cs.AutomaticManagedPagefile; files=$s} | ConvertTo-Json -Compress -Depth 3"
    )
    try:
        j = json.loads(_run(["powershell", "-NoProfile", "-Command", ps], timeout=15) or "{}")
    except Exception:
        return {}
    files = j.get("files") or []
    if isinstance(files, dict):
        files = [files]
    auto = bool(j.get("auto"))
    # a file with initial = max = 0 is also "system managed size" for that drive
    managed = auto or any(not f.get("initial") and not f.get("max") for f in files)
    cap_mb = sum(int(f.get("max") or 0) for f in files) if not managed else None
    return {"swap_managed": managed, "swap_max_gb": round(cap_mb / 1024, 1) if cap_mb is not None else None, "swap_none": not auto and not files}


def disk_info(paths):
    """Free space and drive type for each drive that holds models. Type = NVMe / SSD / HDD where Windows or Linux says so."""
    seen, out = set(), []
    for p in paths:
        if not p or not os.path.isdir(p):
            continue
        root = os.path.splitdrive(os.path.abspath(p))[0] or "/"
        key = root.upper()
        if key in seen:
            continue
        seen.add(key)
        d = {"drive": root, "example_path": p}
        try:
            u = shutil.disk_usage(p)
            d.update(free_gb=_gb(u.free), total_gb=_gb(u.total))
        except Exception:
            pass
        if os.name == "nt" and len(root) >= 2 and root[1] == ":":
            ps = (
                f"$n=(Get-Partition -DriveLetter {root[0]} -ErrorAction Stop).DiskNumber;"
                "Get-PhysicalDisk | Where-Object DeviceId -eq \"$n\" | Select-Object FriendlyName,MediaType,BusType | ConvertTo-Json -Compress"
            )
            j = _run(["powershell", "-NoProfile", "-Command", ps], timeout=15)
            try:
                info = json.loads(j) if j else {}
                if isinstance(info, list):
                    info = info[0] if info else {}
                bus, media = str(info.get("BusType", "")), str(info.get("MediaType", ""))
                d["model"] = info.get("FriendlyName", "")
                d["kind"] = "NVMe" if bus.lower() == "nvme" else "HDD" if media.lower() == "hdd" else "SSD" if media.lower() == "ssd" else (bus or media or "unknown")
                d["network"] = False
            except Exception:
                d["kind"] = "network" if root.startswith("\\\\") else "unknown"
        elif os.name != "nt":
            d["kind"] = _linux_disk_kind(p)
        try:
            big = _biggest_model_file(p)
            if big and big[1] > 64 * 2**20:
                d["read_mb_s"] = read_speed(big[0], big[1]) or read_speed(big[0], big[1])  # one retry
                d["read_file"] = os.path.basename(big[0])
        except Exception as e:
            d["read_error"] = _err(e)
        out.append(d)
    return out


def _biggest_model_file(root, budget_s=2.0):
    """The largest model file under root (a quick walk, time-capped): the file whose read speed matters."""
    best, t0 = None, time.time()
    for dp, dns, fns in os.walk(root):
        for fn in fns:
            if fn.lower().endswith((".safetensors", ".gguf", ".ckpt", ".pth", ".bin")):
                try:
                    sz = os.path.getsize(os.path.join(dp, fn))
                except OSError:
                    continue
                if not best or sz > best[1]:
                    best = (os.path.join(dp, fn), sz)
        if time.time() - t0 > budget_s:
            break
    return best


def read_speed(path, size, max_bytes=512 * 2**20, max_s=3.0):
    """Sequential read speed in MB/s, straight from the drive (the OS file cache is bypassed, or the number would be
    RAM speed for any file read recently). Reads from the middle of the file, at most 512 MB or 3 seconds."""
    chunk = 8 * 2**20
    start = max(0, (size // 2) // chunk * chunk - max_bytes // 2) if size > max_bytes else 0
    got, t0 = 0, time.perf_counter()
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k32.VirtualAlloc.restype = wintypes.LPVOID
        k32.VirtualAlloc.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
        k32.VirtualFree.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
        k32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        k32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        # GENERIC_READ, share read/write, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING | FILE_FLAG_SEQUENTIAL_SCAN
        h = k32.CreateFileW(path, 0x80000000, 3, None, 3, 0x20000000 | 0x08000000, None)
        if h in (None, wintypes.HANDLE(-1).value):
            return None
        buf = k32.VirtualAlloc(None, chunk, 0x3000, 0x04)  # page-aligned, as unbuffered reads require
        try:
            k32.SetFilePointerEx(h, start, None, 0)
            n = wintypes.DWORD(0)
            # the first chunk is not timed: opening a huge file can stall once (an antivirus scan, the drive waking up)
            if not k32.ReadFile(h, buf, chunk, ctypes.byref(n), None) or n.value == 0:
                return None
            t0 = time.perf_counter()
            while got < max_bytes and time.perf_counter() - t0 < max_s:
                if not k32.ReadFile(h, buf, chunk, ctypes.byref(n), None) or n.value == 0:
                    break
                got += n.value
        finally:
            k32.VirtualFree(buf, 0, 0x8000)
            k32.CloseHandle(h)
    else:
        import mmap

        flags = os.O_RDONLY | getattr(os, "O_DIRECT", 0)
        try:
            fd = os.open(path, flags)
        except OSError:
            return None
        buf = mmap.mmap(-1, chunk)  # page-aligned for O_DIRECT
        try:
            os.lseek(fd, start, os.SEEK_SET)
            if os.readv(fd, [buf]) <= 0:  # untimed first chunk, as above
                return None
            t0 = time.perf_counter()
            while got < max_bytes and time.perf_counter() - t0 < max_s:
                n = os.readv(fd, [buf])
                if n <= 0:
                    break
                got += n
        finally:
            os.close(fd)
            buf.close()
    dt = time.perf_counter() - t0
    return round(got / dt / 1e6) if got and dt > 0 else None


def _linux_disk_kind(path):
    try:
        dev = os.stat(path).st_dev
        base = f"/sys/dev/block/{os.major(dev)}:{os.minor(dev)}"
        real = os.path.realpath(base)
        while real and real != "/":
            rot = os.path.join(real, "queue", "rotational")
            if os.path.exists(rot):
                name = os.path.basename(real)
                with open(rot) as f:
                    spinning = f.read().strip() == "1"
                return "NVMe" if name.startswith("nvme") else ("HDD" if spinning else "SSD")
            real = os.path.dirname(real)
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------- GPU
def nvidia_smi():
    q = ("index,name,driver_version,memory.total,pcie.link.gen.max,pcie.link.gen.gpumax,pcie.link.width.current,pcie.link.width.max,power.limit,"
         "pci.bus_id")
    txt = _run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"])
    rows = []
    for line in txt.splitlines():
        v = [x.strip() for x in line.split(",")]
        if len(v) < 9:
            continue
        num = lambda s: int(float(s)) if s.replace(".", "", 1).isdigit() else None
        bus = None
        if len(v) > 9:  # "00000000:02:00.0" -> 2, the same number torch reports as pci_bus_id
            try:
                bus = int(v[9].split(":")[-2], 16)
            except (ValueError, IndexError):
                bus = None
        rows.append({"index": num(v[0]), "name": v[1], "driver": v[2], "vram_mb": num(v[3]), "pcie_gen": num(v[4]), "pcie_gen_gpu": num(v[5]),
                     "pcie_width": num(v[6]), "pcie_width_max": num(v[7]), "power_limit_w": num(v[8]), "bus": bus})
    return rows


def _smi_row(rows, i, p):
    """The nvidia-smi row for torch device i. nvidia-smi numbers every card, torch only the visible ones
    (CUDA_VISIBLE_DEVICES), so match by PCI bus first, then by a unique name, and by index only when nothing is hidden."""
    bus = getattr(p, "pci_bus_id", None)
    if bus is not None:
        hit = [r for r in rows if r.get("bus") == bus]
        if len(hit) == 1:
            return hit[0]
    same = [r for r in rows if r["name"] == p.name]
    if len(same) == 1:
        return same[0]
    if not os.environ.get("CUDA_VISIBLE_DEVICES"):
        return next((r for r in rows if r["index"] == i), None)
    return None


def gpus(torch):
    out = []
    if torch is None or not torch.cuda.is_available():
        return out
    smi = nvidia_smi()
    hip = getattr(torch.version, "hip", None)
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        g = {"index": i, "name": p.name, "vendor": "AMD" if hip else "NVIDIA", "vram_gb": _gb(p.total_memory), "sm_count": p.multi_processor_count}
        if hip:
            g["arch"] = getattr(p, "gcnArchName", "")
        else:
            g["capability"] = f"{p.major}.{p.minor}"
            g["arch"] = ARCH.get(p.major * 10 + p.minor, f"SM{p.major}{p.minor}")
            s = _smi_row(smi, i, p)
            if s:
                g.update(driver=s["driver"], pcie_gen=s["pcie_gen"], pcie_gen_gpu=s["pcie_gen_gpu"], pcie_width=s["pcie_width"], pcie_width_max=s["pcie_width_max"], power_limit_w=s["power_limit_w"])
        try:
            free, total = torch.cuda.mem_get_info(i)
            g["vram_free_gb"] = _gb(free)
        except Exception:
            pass
        out.append(g)
    return out


ARCH = {
    61: "Pascal (GTX 10)", 70: "Volta", 75: "Turing (RTX 20 / GTX 16)", 80: "Ampere (A100)", 86: "Ampere (RTX 30)", 87: "Ampere (Jetson)",
    89: "Ada (RTX 40)", 90: "Hopper (H100)", 100: "Blackwell (B200)", 120: "Blackwell (RTX 50)", 121: "Blackwell (DGX Spark)",
}


def software(torch):
    s = {"torch": getattr(torch, "__version__", None) if torch else None}
    if torch:
        s["cuda"] = torch.version.cuda
        s["hip"] = getattr(torch.version, "hip", None)
        try:
            s["cudnn"] = torch.backends.cudnn.version()
        except Exception:
            pass
    from importlib import metadata

    for pkg in ("sageattention", "triton", "triton-windows", "flash_attn", "xformers", "comfy-kitchen", "bitsandbytes", "nunchaku", "psutil", "gguf"):
        try:
            s[pkg] = metadata.version(pkg)
        except Exception:
            pass
    return s


# ---------------------------------------------------------------- live tests
def _time(fn, n=10, sync=None):
    fn()
    if sync:
        sync()
    t = time.perf_counter()
    for _ in range(n):
        fn()
    if sync:
        sync()
    return (time.perf_counter() - t) / n


def live_tests(torch):
    """Each test: {"ok": True / False / None (not available), "detail": text, plus numbers}. Small and bounded."""
    T = {}
    if torch is None or not torch.cuda.is_available():
        T["gpu"] = {"ok": False, "detail": "No GPU that PyTorch can use"}
        return T
    dev = torch.device("cuda", 0)
    sync = torch.cuda.synchronize
    cap = torch.cuda.get_device_capability(0)
    hip = bool(getattr(torch.version, "hip", None))

    # math speed per precision (a 4096 x 4096 matrix multiply)
    for name, dt in (("fp16", torch.float16), ("bf16", torch.bfloat16), ("fp32", torch.float32)):
        try:
            a = torch.randn(4096, 4096, device=dev, dtype=dt)
            b = torch.randn(4096, 4096, device=dev, dtype=dt)
            s = _time(lambda: a @ b, 10, sync)
            T[f"matmul_{name}"] = {"ok": True, "tflops": round(2 * 4096**3 / s / 1e12, 1), "detail": f"{2 * 4096**3 / s / 1e12:.1f} TFLOPS"}
            del a, b
        except Exception as e:
            T[f"matmul_{name}"] = {"ok": False, "detail": _err(e)}
    try:
        if not hasattr(torch, "float8_e4m3fn") or not hasattr(torch, "_scaled_mm"):
            raise RuntimeError("this PyTorch has no fp8 matmul")
        a = torch.randn(4096, 4096, device=dev).to(torch.float8_e4m3fn)
        b = torch.randn(4096, 4096, device=dev).to(torch.float8_e4m3fn).t()
        one = torch.ones((), device=dev)
        f = lambda: torch._scaled_mm(a, b, scale_a=one, scale_b=one, out_dtype=torch.bfloat16)
        s = _time(f, 10, sync)
        T["matmul_fp8"] = {"ok": True, "tflops": round(2 * 4096**3 / s / 1e12, 1), "detail": f"{2 * 4096**3 / s / 1e12:.1f} TFLOPS (fast fp8 works)"}
        del a, b
    except Exception as e:
        T["matmul_fp8"] = {"ok": False, "detail": "No fast fp8 on this card: fp8 models still load, but run through fp16 / bf16 math" if cap < (8, 9) and not hip else _err(e)}

    # int8 tensor-core math: what int8 and int8-convrot model files run on
    try:
        a = torch.randint(-64, 64, (4096, 4096), device=dev, dtype=torch.int8)
        b = torch.randint(-64, 64, (4096, 4096), device=dev, dtype=torch.int8)
        s = _time(lambda: torch._int_mm(a, b), 10, sync)
        T["matmul_int8"] = {"ok": True, "tops": round(2 * 4096**3 / s / 1e12, 1), "detail": f"{2 * 4096**3 / s / 1e12:.1f} TOPS"}
        del a, b
    except Exception as e:
        T["matmul_int8"] = {"ok": False, "detail": _err(e)}

    # attention: the standard PyTorch path is the yardstick; Sage must match its output
    q = torch.randn(1, 24, 4096, 128, device=dev, dtype=torch.float16)
    k = torch.randn_like(q)
    v = torch.randn_like(q)
    F = torch.nn.functional
    ref = None
    try:
        s = _time(lambda: F.scaled_dot_product_attention(q, k, v), 10, sync)
        ref = F.scaled_dot_product_attention(q, k, v).float()
        T["attention_sdpa"] = {"ok": True, "ms": round(s * 1000, 2), "detail": f"{s * 1000:.2f} ms per attention call (the speed yardstick)"}
    except Exception as e:
        T["attention_sdpa"] = {"ok": False, "detail": _err(e)}
    T["sageattention"] = _test_sage(torch, q, k, v, ref, sync)
    T["flash_attn"] = _test_import_run("flash_attn", lambda m: m.flash_attn_func(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)), sync)
    T["xformers"] = _test_import_run("xformers.ops", lambda m: m.memory_efficient_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)), sync)
    del q, k, v, ref
    T["triton"] = _test_triton(torch)
    T["sol_kitchen"] = _test_sol_kitchen(torch, sync)
    T["sol_pack"] = _test_sol_pack(torch, sync)

    # RAM <-> GPU transfer: what offloading and big text encoders lean on. 256 MB, gentle on the link.
    try:
        n = 256 * 2**20
        pinned = torch.empty(n, dtype=torch.uint8, pin_memory=True)
        plain = torch.empty(n, dtype=torch.uint8)
        g = torch.empty(n, dtype=torch.uint8, device=dev)
        s_pin = _time(lambda: g.copy_(pinned, non_blocking=True), 5, sync)
        s_plain = _time(lambda: g.copy_(plain), 3, sync)
        s_back = _time(lambda: pinned.copy_(g, non_blocking=True), 5, sync)
        s_vram = _time(lambda: g.clone(), 5, sync)
        T["transfer"] = {"ok": True, "to_gpu_gbs": round(n / s_pin / 1e9, 1), "to_gpu_plain_gbs": round(n / s_plain / 1e9, 1), "to_ram_gbs": round(n / s_back / 1e9, 1),
                         "vram_gbs": round(2 * n / s_vram / 1e9), "detail": f"RAM to GPU {n / s_pin / 1e9:.1f} GB/s (pinned), {n / s_plain / 1e9:.1f} GB/s (plain); GPU to RAM {n / s_back / 1e9:.1f} GB/s"}
        del pinned, plain, g
    except Exception as e:
        T["transfer"] = {"ok": False, "detail": _err(e)}
    try:
        torch.cuda.empty_cache()
    except Exception:
        pass
    return T


def _err(e):
    s = str(e).strip().splitlines()
    return (type(e).__name__ + ": " + (s[0] if s else ""))[:300]


def _missing_or_broken(name, e):
    """Not installed at all, or installed but it will not load (a wrong build for this PyTorch / CUDA is common)."""
    from importlib import metadata

    for dist in (name, name.replace("_", "-"), name + "-windows"):
        try:
            ver = metadata.version(dist)
            return {"ok": False, "detail": f"Installed ({dist} {ver}) but will not load: " + _err(e)}
        except Exception:
            pass
    return {"ok": None, "detail": "Not installed"}


def _test_sage(torch, q, k, v, ref, sync):
    try:
        import sageattention
    except Exception as e:
        return _missing_or_broken("sageattention", e)
    try:
        out = sageattention.sageattn(q, k, v, tensor_layout="HND", is_causal=False)
        sync()
        o = out.float()
        if not torch.isfinite(o).all():
            return {"ok": False, "detail": "Runs, but gives NaN / Inf: output would be black or noise"}
        s = _time(lambda: sageattention.sageattn(q, k, v, tensor_layout="HND", is_causal=False), 10, sync)
        d = {"ms": round(s * 1000, 2)}
        if ref is not None:
            cos = torch.nn.functional.cosine_similarity(o.flatten(), ref.flatten(), dim=0).item()
            d["match"] = round(cos, 4)
            if cos < 0.99:
                return {**d, "ok": False, "detail": f"Runs, but its result does not match standard attention (similarity {cos:.3f}): expect grey noise or broken images"}
        return {**d, "ok": True, "detail": f"Works and matches standard attention; {s * 1000:.2f} ms per call"}
    except Exception as e:
        return {"ok": False, "detail": "Installed, but fails on this card: " + _err(e)}


def _test_import_run(mod, fn, sync):
    try:
        import importlib

        m = importlib.import_module(mod)
    except Exception as e:
        return _missing_or_broken(mod.split(".")[0], e)
    root = sys.modules.get(mod.split(".")[0])
    # a stand-in another node pack put in sys.modules: no file and no folder (SeedVR2 does this for flash_attn, with
    # __path__ = [] and its functions set to None)
    if root is not None and getattr(root, "__file__", None) is None and not list(getattr(root, "__path__", None) or []):
        return {"ok": None, "detail": "Not installed"}
    try:
        fn(m)
        sync()
        return {"ok": True, "detail": "Installed and works"}
    except TypeError as e:
        if "NoneType" in str(e):  # the package imported, but its compiled part did not load, so its functions are None
            return {"ok": False, "detail": "Installed, but its compiled part did not load: it was built for a different PyTorch / CUDA. "
                                           "Reinstall a build made for your PyTorch and CUDA, or uninstall it (ComfyUI does not need it). " + _err(e)}
        return {"ok": False, "detail": "Installed, but fails on this card: " + _err(e)}
    except Exception as e:
        return {"ok": False, "detail": "Installed, but fails on this card: " + _err(e)}


def _sol_inputs(torch, t=8192):
    """(B, T, H, 128) bf16, the layout both Sol-Attn kernels take. Sol wins from ~12k tokens; 8k keeps the test small."""
    # video-like tokens (neighbours alike), not pure noise: sparse attention skips the blocks that matter least, and
    # random data has no such blocks, so it would look broken even when it works
    g = torch.Generator(device="cuda").manual_seed(0)
    shape = (1, t, 8, 128)
    base = torch.cumsum(torch.randn(shape, device="cuda", generator=g) * 0.15, dim=1)
    base = base / base.std()
    q = (base + 0.3 * torch.randn(shape, device="cuda", generator=g)).bfloat16()
    k = (base + 0.3 * torch.randn(shape, device="cuda", generator=g)).bfloat16()
    v = torch.randn(shape, device="cuda", dtype=torch.bfloat16, generator=g)
    return q, k, v


def _compare(torch, out, q, k, v):
    ref = torch.nn.functional.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)).transpose(1, 2).float()
    o = out.float()
    if not torch.isfinite(o).all():
        return None
    return torch.nn.functional.cosine_similarity(o.flatten(), ref.flatten(), dim=0).item()


def _run_sol(torch, fn, sync):
    q, k, v = _sol_inputs(torch)
    out = fn(q, k, v)
    sync()
    cos = _compare(torch, out, q, k, v)
    if cos is None:
        return {"ok": False, "detail": "Runs, but gives NaN / Inf"}
    s = _time(lambda: fn(q, k, v), 5, sync)
    if cos < 0.98:
        return {"ok": False, "match": round(cos, 3), "detail": f"Runs, but its result is far off (similarity {cos:.3f})"}
    return {"ok": True, "ms": round(s * 1000, 2), "match": round(cos, 3), "detail": f"Works; {s * 1000:.2f} ms per call at 8k tokens (similarity {cos:.3f})"}


def _test_sol_kitchen(torch, sync):
    try:
        import comfy_kitchen as ck
    except Exception as e:
        return _missing_or_broken("comfy_kitchen", e)
    if not hasattr(ck, "sol_attn_is_available"):  # older Comfy Kitchen builds have no Sol-Attn at all
        try:
            from importlib import metadata
            ver = metadata.version("comfy-kitchen")
        except Exception:
            ver = ""
        return {"ok": None, "detail": f"Your Comfy Kitchen{' ' + ver if ver else ''} has no Sol-Attn yet. Update ComfyUI (it installs the matching comfy-kitchen) to get it."}
    try:
        if not ck.sol_attn_is_available():
            return {"ok": False, "detail": "Comfy Kitchen is installed, but its compiled Sol-Attn kernel is not available on this card"}
        return _run_sol(torch, lambda q, k, v: ck.sol_attn(q, k, v, tau=1.0), sync)
    except Exception as e:
        return {"ok": False, "detail": "Fails on this card: " + _err(e)}


def _test_sol_pack(torch, sync):
    """The ComfyUI-sol-attn pack's own Triton kernel (only when ComfyUI loaded the pack)."""
    in_pack = lambda m: m is not None and "sol-attn" in str(getattr(m, "__file__", "")).lower()
    mods = list(sys.modules.items())
    mod = next((m for n, m in mods if n.endswith("sol_kernel") and in_pack(m)), None)
    if mod is None or not hasattr(mod, "sol_attn"):
        return {"ok": None, "detail": "Not installed"}
    arches = next((m.SUPPORTED_ARCHES for n, m in mods if n.endswith(".nodes") and in_pack(m) and hasattr(m, "SUPPORTED_ARCHES")), None)
    cap = tuple(torch.cuda.get_device_capability(0))
    if arches and cap not in arches:
        return {"ok": False, "detail": f"Not supported on SM{cap[0]}{cap[1]}: the pack supports " + ", ".join(f"SM{a}{b}" for a, b in sorted(arches))}
    try:
        return _run_sol(torch, lambda q, k, v: mod.sol_attn(q, k, v, tau=1.0), sync)
    except Exception as e:
        return {"ok": False, "detail": "Fails on this card (it needs Triton): " + _err(e)}


def kitchen_info():
    """Comfy Kitchen: ComfyUI's kernel library (int8 / fp8 / nvfp4 matmuls, int8 attention, Sol-Attn)."""
    try:
        import comfy_kitchen as ck
    except Exception as e:
        r = _missing_or_broken("comfy_kitchen", e)
        return {"installed": r["ok"] is not None, "detail": r["detail"]}
    from importlib import metadata

    out = {"installed": True}
    try:
        out["version"] = metadata.version("comfy-kitchen")
    except Exception:
        pass
    try:
        out["backends"] = {
            n: {"available": b["available"], "disabled": b["disabled"], "reason": b["unavailable_reason"], "ops": len(b["capabilities"])}
            for n, b in ck.registry.list_backends().items()
        }
    except Exception as e:
        out["backends_error"] = _err(e)
    for k, f in (("sol_attn", "sol_attn_is_available"), ("int8_attention", "int8_attention_is_available"), ("flash_decode", "flash_attention_decode_is_available")):
        try:
            out[k] = bool(getattr(ck, f)())
        except Exception:
            out[k] = None
    return out


def llama_cpp_info():
    """LC Vision runs Qwen-VL GGUF models through the JamePeng llama-cpp-python fork (the only build with the vision handlers)."""
    try:
        import llama_cpp
    except Exception as e:
        r = _missing_or_broken("llama_cpp", e)
        if r["ok"] is None:
            r = _missing_or_broken("llama-cpp-python", e)
        return {"installed": r["ok"] is not None, "detail": r["detail"]}
    out = {"installed": True, "version": getattr(llama_cpp, "__version__", "?")}
    try:
        gpu = bool(llama_cpp.llama_supports_gpu_offload())
        if not gpu:
            # newer builds keep the GPU backend (ggml-cuda.dll / .so) as a plugin that loads on first use: load it
            # from the package's lib folder, the same place llama-cpp itself loads it from, then ask again
            import ctypes

            lib = os.path.join(os.path.dirname(llama_cpp.__file__), "lib")
            for name in ("ggml.dll", "libggml.so", "libggml.dylib"):
                path = os.path.join(lib, name)
                if os.path.exists(path):
                    fn = getattr(ctypes.CDLL(path), "ggml_backend_load_all_from_path", None)
                    if fn:
                        fn.argtypes = [ctypes.c_char_p]
                        fn(lib.encode())
                    break
            gpu = bool(llama_cpp.llama_supports_gpu_offload())
        out["gpu_offload"] = gpu
    except Exception:
        out["gpu_offload"] = None
    try:
        from llama_cpp import llama_chat_format as cf

        out["qwen3_vl"] = hasattr(cf, "Qwen3VLChatHandler")
        out["qwen25_vl"] = hasattr(cf, "Qwen25VLChatHandler")
    except Exception:
        out["qwen3_vl"] = out["qwen25_vl"] = False
    return out


# ---------------------------------------------------------------- LC Vision model suggestion
# Qwen3-VL GGUF sizes in GiB (weights; mmproj f16 added separately), best quality first. KV cache per token in f16:
# 2 (K and V) x layers x KV heads x head dim x 2 bytes: 4B / 8B = 36 x 8 x 128, 32B = 64 x 8 x 128.
LCV_MODELS = {"4B": {"q": {"f16": 7.50, "Q8_0": 3.99, "Q6_K": 3.08, "Q5_K_M": 2.69, "Q4_K_M": 2.33}, "mmproj": 0.78, "kv_per_tok": 147456},
              "8B": {"q": {"f16": 15.26, "Q8_0": 8.11, "Q6_K": 6.27, "Q5_K_M": 5.45, "Q4_K_M": 4.68}, "mmproj": 1.08, "kv_per_tok": 147456},
              "32B": {"q": {"Q8_0": 32.4, "Q6_K": 25.0, "Q5_K_M": 21.7, "Q4_K_M": 18.4}, "mmproj": 1.10, "kv_per_tok": 262144}}
LCV_RANK = [("32B", "Q8_0"), ("32B", "Q6_K"), ("32B", "Q5_K_M"), ("32B", "Q4_K_M"), ("8B", "f16"), ("8B", "Q8_0"), ("8B", "Q6_K"), ("8B", "Q5_K_M"),
            ("8B", "Q4_K_M"), ("4B", "f16"), ("4B", "Q8_0"), ("4B", "Q6_K"), ("4B", "Q5_K_M"), ("4B", "Q4_K_M")]
LCV_CTX = (32768, 16384, 8192, 4096)  # LC Vision's default context is 32768; a caption of one or two images fits in 4096
LCV_SPARE_GB = 1.8  # the Windows desktop / display (~0.8) plus llama.cpp's compute buffers and the image encoder (~1.0)


def _lcv_need(size, quant, ctx):
    m = LCV_MODELS[size]
    return m["q"][quant] + m["mmproj"] + m["kv_per_tok"] * ctx / 2**30


def _lcv_on_disk():
    """Qwen3-VL GGUFs already in the LLM folder(s), as {(size, quant)} found in the file names."""
    import re

    found = set()
    try:
        import folder_paths

        dirs = folder_paths.get_folder_paths("LLM")
    except Exception:
        dirs = []
    for d in dirs:
        for root, _, files in os.walk(d) if os.path.isdir(d) else []:
            for f in files:
                fl = f.lower()
                if not fl.endswith(".gguf") or "mmproj" in fl or not re.search(r"qwen3[-_.]?vl", fl):
                    continue
                size = next((sz for sz in ("32b", "8b", "4b") if re.search(rf"(?<![0-9]){sz}(?![a-z0-9])", fl)), None)
                quant = next((q for q in ("q8_0", "q6_k", "q5_k_m", "q4_k_m", "f16", "bf16") if q in fl), None)
                if size and quant:
                    found.add((size.upper(), "f16" if quant in ("f16", "bf16") else quant.upper()))
    return found


def lc_vision_suggestion(prof):
    """Quality / Optimal / Fast Qwen3-VL picks for LC Vision on this card. Assumes LC Vision gets the GPU to itself while
    it runs (it loads, answers, and can unload before the image model). Sizes are fixed per file, so this is exact
    arithmetic, not a benchmark."""
    g = prof["gpus"][0] if prof.get("gpus") else None
    if not g:
        return {"note": "No usable GPU: LC Vision would run on the CPU. Use 4B Q4_K_M, and expect it to be slow.",
                "tiers": {"Optimal": {"size": "4B", "quant": "Q4_K_M", "ctx": 8192, "need_gb": round(_lcv_need("4B", "Q4_K_M", 8192), 1), "cpu": True}}}
    budget = g["vram_gb"] - LCV_SPARE_GB

    def pick(cands, headroom=1.0):
        # 8k context or more first (room for several images); 4k only when nothing else fits at all
        for min_ctx in (8192, 4096):
            for size, quant in cands:
                for ctx in (c for c in LCV_CTX if c >= min_ctx):
                    need = _lcv_need(size, quant, ctx)
                    if need <= budget * headroom:
                        return {"size": size, "quant": quant, "ctx": ctx, "need_gb": round(need, 1)}
        return None

    quality = pick(LCV_RANK)
    # Optimal: 4B / 8B only (32B is several times slower), no f16 (about the same answers as Q8_0 at twice the size),
    # and 20 % of the card left free
    opt_cands = [c for c in LCV_RANK if c[0] != "32B" and c[1] != "f16"]
    optimal = pick(opt_cands, 0.8) or pick(opt_cands)
    fast = None
    if optimal:
        # Fast: the 4B one step smaller than Optimal (Q8_0 at most): fewer bytes per token means quicker answers
        smaller = [c for c in LCV_RANK if c[0] == "4B" and c[1] in ("Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M")]
        after = smaller[smaller.index((optimal["size"], optimal["quant"])) + 1:] if (optimal["size"], optimal["quant"]) in smaller else smaller
        fast = pick(after, 0.8) or pick(after)
    note = ""
    if not quality:  # nothing fits fully on the GPU, not even 4B Q4_K_M at 8k context
        optimal = {"size": "4B", "quant": "Q4_K_M", "ctx": 8192, "need_gb": round(_lcv_need("4B", "Q4_K_M", 8192), 1), "cpu": True}
        quality = fast = None
        note = "Even the smallest model does not fit on this card: LC Vision will put part of it on the CPU (slow)."
    key = lambda t: t and (t["size"], t["quant"])
    tiers = {"Quality": quality, "Optimal": optimal, "Fast": fast}
    # the same model twice says nothing: keep it once, under Optimal, with the larger context that still fits
    if key(quality) == key(optimal):
        if quality["ctx"] > optimal["ctx"]:
            tiers["Optimal"] = quality
        tiers["Quality"] = None
    if key(fast) == key(optimal):
        tiers["Fast"] = None
    have = _lcv_on_disk()
    for t in tiers.values():
        if t:
            t["on_disk"] = (t["size"], t["quant"]) in have
    return {"vram_gb": g["vram_gb"], "tiers": {k: v for k, v in tiers.items() if v}, "note": note, "chat": lc_vision_chat(g["vram_gb"]),
            "assumes": "LC Vision has the GPU to itself while it runs. If an image or video model stays loaded next to it, step down one row."}


def lc_vision_chat(vram_gb):
    """The Vision Assistant chat's pick for this card: the same rule as its Auto setting (at most 45 % of the card,
    11 GB tops, loaded only while you chat). Text only, so no mmproj. Measured on an RTX 5090, 2026-10-12."""
    # flash attention + 8-bit cache: file + 0.08 GB per 1k tokens + 0.7 GB (measured on a 5090 and an 8 GB 5060 Laptop)
    budget = min(vram_gb * 0.5, 11.0)
    ctxs = (16384, 8192, 4096) if vram_gb >= 20 else (8192, 4096)
    for ctx in ctxs:
        for size, quant in (("8B", "Q8_0"), ("8B", "Q5_K_M"), ("4B", "Q8_0"), ("4B", "Q4_K_M")):
            need = LCV_MODELS[size]["q"][quant] + 0.08 * ctx / 1024 + 0.7
            if need <= budget:
                return {"size": size, "quant": quant, "ctx": ctx, "need_gb": round(need, 1), "tours": ctx >= 16384}
    return {"cpu": True, "size": "4B", "quant": "Q4_K_M", "ctx": 4096,
            "note": "Vision Assistant chat: on the CPU (this card is too small to hold a chat model next to the image model). Under 1 GB of VRAM, 10 to 30 seconds an answer."}


def h3_native():
    """H3-Optimizations' own compiled library: the int8 convrot quantizer its fused Q path uses."""
    if "h3_optimizations" not in sys.modules:
        return None
    try:
        import importlib

        n = importlib.import_module("h3_optimizations.native.convrot")
        return {"int8_convrot256": bool(n.int8_rowwise_convrot256_is_available())}
    except Exception as e:
        return {"error": _err(e)}


def _test_triton(torch):
    try:
        import triton
        import triton.language as tl
    except Exception as e:
        return _missing_or_broken("triton", e)
    try:

        @triton.jit
        def _lc_add(x_ptr, y_ptr, n, BLOCK: tl.constexpr):
            i = tl.program_id(0) * BLOCK + tl.arange(0, BLOCK)
            m = i < n
            tl.store(y_ptr + i, tl.load(x_ptr + i, mask=m) + 1, mask=m)

        x = torch.zeros(1024, device="cuda")
        y = torch.empty_like(x)
        _lc_add[(1,)](x, y, 1024, BLOCK=1024)
        torch.cuda.synchronize()
        if float(y.sum()) != 1024.0:
            return {"ok": False, "detail": "Compiles, but gives a wrong result"}
        return {"ok": True, "detail": f"Compiles and runs (Triton {triton.__version__})"}
    except Exception as e:
        return {"ok": False, "detail": "Installed, but cannot compile (a missing compiler is common on Windows): " + _err(e)}


# ---------------------------------------------------------------- ComfyUI (only when running inside it)
def comfy_info():
    if "comfy.model_management" not in sys.modules:  # run on its own: there is no ComfyUI to describe
        return None
    try:
        import comfy.cli_args as ca
        import comfy.model_management as mm
    except Exception:
        return None
    out = {"argv": sys.argv[1:]}
    try:
        import comfyui_version

        out["version"] = comfyui_version.__version__
    except Exception:
        pass
    # which quantized formats this ComfyUI can load at all (older builds lack mxfp8, w4a8, int8 convrot, etc.)
    try:
        import comfy.quant_ops as qo

        out["quant_algos"] = sorted(getattr(qo, "QUANT_ALGOS", {}).keys())
    except Exception:
        pass
    try:
        import inspect
        import comfy.ops

        out["int8_convrot"] = "convrot" in inspect.getsource(comfy.ops)
    except Exception:
        pass
    for k, f in (("dynamic_vram", getattr(ca, "enables_dynamic_vram", None)), ("sage", mm.sage_attention_enabled), ("flash", mm.flash_attention_enabled),
                 ("xformers", mm.xformers_enabled), ("pytorch_attention", mm.pytorch_attention_enabled)):
        try:
            out[k] = bool(f()) if f else None
        except Exception:
            out[k] = None
    for k in ("supports_fp8_compute", "supports_nvfp4_compute", "supports_mxfp8_compute"):
        try:
            out[k] = bool(getattr(mm, k)())
        except Exception:
            pass
    try:
        out["vram_state"] = mm.vram_state.name
    except Exception:
        pass
    a = ca.args
    plain = lambda v: sorted(str(x) for x in v) if isinstance(v, (set, frozenset)) else v  # --fast is a set
    out["flags"] = {k: plain(getattr(a, k, None)) for k in ("lowvram", "novram", "highvram", "gpu_only", "cpu", "reserve_vram", "fast_disk", "disable_fast_disk", "use_sage_attention", "use_flash_attention", "use_ck_attention", "enable_triton_backend", "disable_triton_backend", "fast", "disable_smart_memory", "cache_none", "cache_lru")}
    return out


def model_dirs():
    try:
        import folder_paths

        paths = []
        for kind in ("diffusion_models", "unet", "checkpoints", "text_encoders", "clip", "vae"):
            try:
                paths += folder_paths.get_folder_paths(kind)
            except Exception:
                pass
        return paths
    except Exception:
        return [os.getcwd()]


def installed_packs():
    """The optimizer packs the model profiles care about: installed or not."""
    wanted = {"KJNodes": "comfyui-kjnodes", "H3-Optimizations": "h3-optimizations", "GGUF": "comfyui-gguf", "Nunchaku": "comfyui-nunchaku",
              "MultiGPU": "comfyui-multigpu", "WanVideoWrapper": "comfyui-wanvideowrapper", "LTXVideo": "comfyui-ltxvideo", "MiniMax-H3-Turbo": "comfyui-minimax-h3-turbo", "Sol-Attn": "comfyui-sol-attn"}
    try:
        import folder_paths

        dirs = folder_paths.get_folder_paths("custom_nodes")
    except Exception:
        return {}
    names = set()
    for d in dirs:
        try:
            names |= {n.lower() for n in os.listdir(d) if os.path.isdir(os.path.join(d, n))}
        except Exception:
            pass
    return {label: folder in names for label, folder in wanted.items()}


def h3_preflights(torch):
    """H3-Optimizations' own checks, one per sparse attention backend, reported word for word."""
    if "h3_optimizations" not in sys.modules:  # the pack registers itself under this name when ComfyUI loads it
        return None
    import importlib

    mods = {}
    for mod in ("kitchen_sparse", "frost_bf16", "fp8_flex", "triton_bf16", "triton_sparse", "sparse_sage"):
        try:
            mods[mod] = importlib.import_module(f"h3_optimizations.attention.sparse.{mod}")  # loaded lazily by the pack
        except Exception:
            pass
    checks = (("Kitchen INT8 (default)", "kitchen_sparse", "preflight_sparse_kitchen"), ("FROST BF16", "frost_bf16", "preflight_frost_bf16"),
              ("FP8 Flex", "fp8_flex", "preflight_fp8_flex"), ("BF16 Triton", "triton_bf16", "preflight_triton_bf16"),
              ("Triton sparse (portable)", "triton_sparse", "preflight_triton_sparse"), ("Hybrid Sparse Sage", "sparse_sage", "preflight_sparse_sage"))
    out = {}
    cap = lambda: torch.cuda.get_device_capability(0)
    for label, mod, fn in checks:
        f = getattr(mods.get(mod), fn, None)
        if f is None:
            out[label] = {"ok": None, "detail": "Check not found in this version"}
            continue
        try:
            try:
                f(cuda_available=torch.cuda.is_available, capability_getter=cap)
            except TypeError:
                f()
            out[label] = {"ok": True, "detail": "Available"}
        except Exception as e:
            out[label] = {"ok": False, "detail": str(e).strip().splitlines()[0][:300] if str(e).strip() else type(e).__name__}
    return out


# ---------------------------------------------------------------- the whole profile
def probe(run_gpu_tests=True):
    t0 = time.time()
    try:
        import torch
    except Exception:
        torch = None
    prof = {"profile_version": PROFILE_VERSION, "when": time.strftime("%Y-%m-%d %H:%M:%S"), "machine": machine(), "gpus": gpus(torch), "software": software(torch)}
    prof["comfy"] = comfy_info()
    prof["disks"] = disk_info(model_dirs())
    prof["packs"] = installed_packs()
    prof["tests"] = live_tests(torch) if run_gpu_tests else {}
    prof["kitchen"] = kitchen_info()
    prof["llama_cpp"] = llama_cpp_info()
    try:
        prof["lc_vision"] = lc_vision_suggestion(prof)
    except Exception as e:
        prof["lc_vision"] = {"error": _err(e)}
    try:
        prof["h3_native"] = h3_native()
    except Exception as e:
        prof["h3_native"] = {"error": _err(e)}
    try:
        prof["h3_preflight"] = h3_preflights(torch) if torch is not None and torch.cuda.is_available() else None
    except Exception as e:
        prof["h3_preflight"] = {"error": _err(e)}
    prof["seconds"] = round(time.time() - t0, 1)
    prof["findings"] = findings(prof)
    return prof


# ---------------------------------------------------------------- findings (what the report shows)
# level: 3 = problem (⚠️), 2 = works (✅), 1 = worth changing (💡), 0 = info (ℹ️), -1 = not installed / does not apply (➖)
def findings(p):
    F = []
    add = lambda kind, level, title, text: F.append({"kind": kind, "level": level, "title": title, "text": text})
    g = p["gpus"][0] if p["gpus"] else None
    m = p["machine"]
    t = p.get("tests") or {}
    c = p.get("comfy") or {}

    # graphics card
    if not g:
        add("gpu", 3, "No usable GPU", "PyTorch cannot see a graphics card. Everything would run on the CPU, which is far too slow for these models.")
    else:
        vram = g["vram_gb"]
        tier = "8 GB or less: only small or heavily quantized models, with offloading" if vram <= 8.5 else "12 GB: most image models with fp8 / GGUF; video needs offloading" if vram <= 12.5 else "16 GB: image models comfortably; big video models with offloading" if vram <= 16.5 else "24 GB: most models; the largest video models still offload" if vram <= 24.5 else "32 GB or more: nearly everything fits"
        add("gpu", 0, f"{g['name']}, {vram:g} GB", f"{g.get('arch', '')}. VRAM tier: {tier}.")
        if g["vendor"] == "NVIDIA":
            major = int(str(g.get("capability", "0.0")).split(".")[0])
            if major < 7:
                add("gpu", 3, "Older card generation", "Pascal-era cards have no tensor cores for fp16 / bf16: expect very slow generation, and most speed-ups here will not work.")
            elif g.get("capability") == "7.0":  # Volta has fp16 tensor cores, but no bf16
                add("gpu", 1, "No fast bf16 on Volta (Titan V / V100)", "Volta cards run bf16 models slowly. Prefer fp16 or GGUF files where the model offers them.")
            elif g.get("capability") == "7.5":
                add("gpu", 1, "No fast bf16 on RTX 20 / GTX 16", "Turing cards run bf16 models slowly. Prefer fp16 or GGUF files where the model offers them.")
        pg, pw = g.get("pcie_gen"), g.get("pcie_width")
        if pg and pw:
            slow = pg <= 3 and pw <= 8 or pw <= 4
            add("gpu", 1 if slow else 0, f"PCIe Gen{pg} x{pw}", ("A slow link: offloading big models to system RAM will be slow on this machine." if slow else "Link speed for offloading models to system RAM.") + (f" The card itself supports Gen{g['pcie_gen_gpu']}." if g.get("pcie_gen_gpu") and g["pcie_gen_gpu"] > pg else ""))

    # memory
    ram = m.get("ram_total_gb")
    if ram:
        lvl, txt = (3, "Too little for the big models: their text encoders alone can be 15 to 50 GB. Expect heavy page-file use or crashes.") if ram < 24 else (1, "Enough for image models. The big video models and their text encoders will lean on the page file.") if ram < 48 else (2, "Plenty for offloading.")
        add("memory", lvl, f"System RAM {ram:g} GB", txt)
    sw = m.get("swap_total_gb")
    if m.get("swap_none"):
        add("memory", 3, "No page file", "When RAM runs out ComfyUI crashes instead of slowing down. Turn the page file back on (let Windows manage it).")
    elif m.get("swap_managed"):
        add("memory", 2, "Page file managed by Windows", (f"Currently {sw:g} GB. " if sw is not None else "") + "Windows grows it when RAM runs out, as long as the drive has free space.")
    elif sw is not None and ram:
        cap = m.get("swap_max_gb") or sw
        if cap < 16:
            add("memory", 1 if ram >= 64 else 3, f"Page file capped at {cap:g} GB", "A fixed, small page file: when RAM runs out ComfyUI crashes instead of slowing down. Let Windows manage it, or allow at least 32 GB on a fast drive.")
        else:
            add("memory", 0, f"Page file up to {cap:g} GB", "Room to spill over when RAM runs out.")
    for d in p.get("disks") or []:
        kind = d.get("kind", "unknown")
        if kind == "HDD":
            add("memory", 3, f"Models on a hard drive ({d['drive']})", "Loading big models from a spinning drive takes minutes. Move the models folder to an SSD if you can.")
        elif kind in ("NVMe", "SSD"):
            add("memory", 2, f"Models on {kind} ({d['drive']})", f"{d.get('free_gb', '?')} GB free.")
        else:
            add("memory", 0, f"Models on {d['drive']}", f"Drive type not reported. {d.get('free_gb', '?')} GB free.")
        mbs = d.get("read_mb_s")
        if mbs:
            per10 = 10_000 / mbs
            slow = mbs < 400
            add("memory", 1 if slow else 0, f"Reads {mbs:,} MB/s ({d['drive']})",
                f"A 10 GB model takes about {per10:.0f} s to load from here" + (", so big models and text encoders load slowly. An NVMe drive is 5 to 20 times faster." if slow else ".") + " Measured straight from the drive.")

    # speed-ups
    tr = t.get("transfer") or {}
    if tr.get("ok"):
        add("speed", 0, "RAM ↔ GPU transfer", tr["detail"] + ". Offloading moves models over this link.")
    f8 = t.get("matmul_fp8") or {}
    if f8:
        add("speed", 2 if f8.get("ok") else 0, "Fast fp8 math", f8["detail"])
    sa = t.get("sageattention") or {}
    if sa.get("ok") is None:
        maj = int(str((g or {}).get("capability", "0.0")).split(".")[0]) if g else 0
        add("speed", 1 if g and g["vendor"] == "NVIDIA" and maj >= 8 else -1, "SageAttention", "Not installed. On RTX 30 and newer it is usually the biggest single speed-up for video models." if g and maj >= 8 else "Not installed (needs an NVIDIA RTX 30 or newer).")
    elif sa.get("ok"):
        sd = (t.get("attention_sdpa") or {}).get("ms")
        gain = f" About {sd / sa['ms']:.1f}x the speed of standard attention." if sd and sa.get("ms") else ""
        add("speed", 2, "SageAttention", sa["detail"] + "." + gain)
    else:
        add("speed", 3, "SageAttention", sa["detail"] + (". It is switched on at launch (--use-sage-attention): remove that flag, or fix the install." if (c.get("flags") or {}).get("use_sage_attention") else ". Leave the Sage nodes and flag off until this is fixed."))
    i8 = t.get("matmul_int8") or {}
    if i8:
        add("speed", 2 if i8.get("ok") else 3, "int8 math (int8 and int8-convrot models)", i8["detail"] if i8.get("ok") else "Fails: " + i8["detail"] + ". int8 / int8-convrot model files will not run fast here.")
    ki = p.get("kitchen") or {}
    if not ki.get("installed"):
        add("speed", 3, "Comfy Kitchen", (ki.get("detail") or "Not installed") + ". ComfyUI's fast int8 / fp8 / nvfp4 kernels come from it: update ComfyUI's requirements.")
    else:
        be = ki.get("backends") or {}
        live = [n for n, b in be.items() if b["available"] and not b["disabled"]]
        off = [f"{n} ({b['reason'] or 'disabled'})" for n, b in be.items() if not b["available"] or b["disabled"]]
        add("speed", 2 if ("cuda" in live or "hip" in live) else 1, ("Comfy Kitchen " + ki.get("version", "")).strip(),
            "Backends working: " + (", ".join(live) or "none") + (". Not in use: " + "; ".join(off) if off else "") + ".")
    for key, name in (("sol_kitchen", "Sol-Attn (Comfy Kitchen)"), ("sol_pack", "Sol-Attn (ComfyUI-sol-attn pack)")):
        r = t.get(key) or {}
        if r:
            add("speed", 2 if r.get("ok") else -1 if r.get("ok") is None else 3, name, r["detail"] + (". Sparse attention for long videos: it pays off above ~12k tokens." if r.get("ok") else ""))
    hn = p.get("h3_native") or {}
    if "int8_convrot256" in hn:
        add("packs", 2 if hn["int8_convrot256"] else -1, "H3 int8 convrot kernel",
            "Available: H3-Optimizations' fused int8 path can run." if hn["int8_convrot256"] else "Not in this build of H3-Optimizations' native library; it falls back to the standard path.")
    lc = p.get("llama_cpp") or {}
    if lc:
        if not lc.get("installed"):
            add("packs", -1, "llama-cpp (LC Vision)", lc.get("detail", "Not installed") + ". LC Vision's install.py sets up the right build.")
        elif not (lc.get("qwen3_vl") or lc.get("qwen25_vl")):
            add("packs", 3, f"llama-cpp {lc.get('version')} (LC Vision)", "Installed, but not the vision build: LC Vision needs the JamePeng fork. Run LC Vision's install.py.")
        elif lc.get("gpu_offload") is False:
            add("packs", 3, f"llama-cpp {lc.get('version')} (LC Vision)", "A CPU-only build: LC Vision will work, but very slowly. Reinstall the CUDA build (LC Vision's install.py).")
        else:
            add("packs", 2, f"llama-cpp {lc.get('version')} (LC Vision)", "Vision build with GPU support: LC Vision can run here.")
    for key, name in (("triton", "Triton"), ("flash_attn", "Flash Attention"), ("xformers", "xformers")):
        r = t.get(key) or {}
        if r:
            add("speed", 2 if r.get("ok") else -1 if r.get("ok") is None else 3, name, r["detail"])

    # ComfyUI setup
    if c:
        fl = c.get("flags") or {}
        add("setup", 0, f"ComfyUI {c.get('version', '?')}", f"Dynamic VRAM {'on' if c.get('dynamic_vram') else 'off'}; memory mode {c.get('vram_state', '?')}. Launch flags: {' '.join(c.get('argv') or []) or 'none'}.")
        algos = c.get("quant_algos")
        if algos is not None:
            names = {"mxfp8": "mxfp8", "asym_w4a8_int8": "w4a8", "int8_tensorwise": "int8", "nvfp4": "nvfp4", "convrot_w4a4": "int4_convrot"}
            miss = [v for k, v in names.items() if k not in algos]
            if "int8_tensorwise" in algos and c.get("int8_convrot") is False:
                miss.append("int8_convrot")
            if miss:
                add("setup", 1, "Update ComfyUI for newer model formats",
                    f"This ComfyUI cannot load {', '.join(miss)} files yet, so the picks below leave them out. Updating ComfyUI "
                    "(it brings the matching comfy-kitchen) adds them. On RTX 40 and 50 cards they are often the fastest choice.")
        if fl.get("lowvram") and c.get("dynamic_vram"):
            add("setup", 1, "--lowvram does nothing here", "Dynamic VRAM is on, which already offloads as needed. The flag can be removed.")
        if fl.get("highvram") or fl.get("gpu_only"):
            if g and g["vram_gb"] <= 16.5:
                add("setup", 3, "--highvram / --gpu-only on a small card", "Forces everything to stay on the GPU. Big models will run out of memory. Remove the flag.")
    sw_ = p.get("software") or {}
    add("setup", 0, "PyTorch " + str(sw_.get("torch")), f"CUDA {sw_.get('cuda')}" if sw_.get("cuda") else f"ROCm {sw_.get('hip')}" if sw_.get("hip") else "CPU build")

    # packs
    h3 = p.get("h3_preflight")
    if h3 and not h3.get("error"):
        ok = [k for k, v in h3.items() if v.get("ok")]
        add("packs", 2 if ok else 3, "H3-Optimizations sparse attention", ("Works here: " + ", ".join(ok) + ".") if ok else "No sparse backend works on this machine.")
        for k, v in h3.items():
            if v.get("ok") is False:
                add("packs", -1, f"H3 {k}", v["detail"])
    for label, have in (p.get("packs") or {}).items():
        if not have and label in ("KJNodes", "GGUF"):
            add("packs", 1, f"{label} not installed", "KJNodes holds most of the memory and speed nodes." if label == "KJNodes" else "GGUF lets smaller cards run big models as quantized files.")
    return F


if __name__ == "__main__":
    prof = probe()
    out = sys.argv[1] if len(sys.argv) > 1 else "system_profile.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(prof, f, indent=1, ensure_ascii=False, default=str)
    for x in prof["findings"]:
        print({3: "[!]", 2: "[ok]", 1: "[tip]", 0: "[i]", -1: "[-]"}[x["level"]], x["title"], "-", x["text"])
    for tier, t in (prof.get("lc_vision") or {}).get("tiers", {}).items():
        print(f"[LC Vision {tier}] Qwen3-VL-{t['size']} {t['quant']}, context {t['ctx']}, ~{t['need_gb']} GB" + (" (on disk)" if t.get("on_disk") else "") + (" (partly CPU)" if t.get("cpu") else ""))
    print("saved", out)
