"""
LC startup banner, shared by every LC pack (each carries a copy): the first LC pack to load shows the Lonecat logo
as colored half blocks (two pixels per character) with the wordmark, tagline and its pack line beside it; the packs
after it print one line each, lined up under that text. Colors only in a real console (plain blocks in log files, or set NO_COLOR); LC_NO_BANNER=1
prints a single plain line instead. LOGO is the logo PNG at 40 x 40 pixels, "rrggbb" per pixel, "......" = see-through.
"""

import os
import sys

LOGO = (
    "................................................................................................................................................................................................................................................",
    "..................................................................................................................495d6f........................................................................................................................",
    "............................................................................................................44596a4a6174........................................................................................................................",
    "............................................................................................................475d71..............................................................................................................................",
    "......................................................................................................465a6d4a5e72............7f8388............................................................................................................",
    "..........................................................................................c2c2c2bdbdbd526578707b87d6d4d28a8d9194979bcfd0d1c0c1c1b7b8b9aeafaf....................................................................................",
    "..............................................................................ccccccd4d4d4e5e4e3a8aeb341576c9da0a3cccbcab2b5b7555a5e7073768385889fa2a3c0c2c1b9bcbdaaaeb0........................................................................",
    "..................................................................cdcdcedfdededbdbdbd1d2d1cfcecd637382506271c0bfbdcacbcbc7cbcc555a5e494e5254595d53585c5f62668c8f91bcc0c1b2b7b8..................................................................",
    "......................................................bdbdbfd5d6d6ddddddd1d1d1cececed5d4d3aeb1b43e566b848c93c3c2c1cececed4d8d9888d90............5056594f53574e5357616569a0a4a6bdc1c29ba0a2......................................................",
    "................................................c0c1c3e2e2e3d4d4d4d0d0d0d0d0d0d8d9d9d8d7d576838f39526a............d9d9dad8dadb989ea0........................50555a50555a4e52568d9193bdc2c3999ea0................................................",
    "..........................................bebfbfe6e7e7d4d4d4d1d1d1d2d2d2dededdd0d2d0......425b71434a5b............e4e3e3cacbcca0a7a9..............................4d535651565a484d528a8e90b9bfbf929999..........................................",
    "....................................b7b9bbe4e4e4d3d3d3d1d1d1d3d4d3d7d7d7c6c6c8............4b657e4c343d......bca7a7f2f0f0968686acb2b57a8082............53585d............4b4f5351555a494e52969b9caeb1b3..........................................",
    "....................................d6d6d6d6d6d6d1d1d1d4d4d4d5d5d5..................42596f4b566b592325......cdd5d7ecdada863e3ea5aeb29fa3a8............53575c52585b............4b50544c5156585b5fadb0b29ca0a3....................................",
    "..............................c6c7c7dddddcd0d0d0d2d2d2d9d9d9........................46637a4f3e4b761718......d8e2e2d5aaaa9926278b9b9fa2a5a9............4f54585a5f634a4e53............4e535743484c777b7db3b7b8....................................",
    "..............................e0e0e0d0d0d0cfcfd0ddddddc8c8c8..................405466405e75642b329e1214......edf8f8ba77799b23246f8085b0b4b7............585d6250555a..................464b4f4c5256505458a6aaab999d9f..............................",
    "........................c6c8c8dadadad0d0cfd4d4d4cdcdcd........................475e7533556d7d1f20b7181bc4a7a7e0f3f3c03e3eb43133607177afb1b59ba1a53c40465b5f64............494d54............51555a414549838789a9adae..............................",
    "........................d7d7d7d0d0d0cfcfcedcdcdcc3c3c3............4140443c526647617a............b82928eecdcad7f5f7......c34143496369a3a5a89a9a9e554f524e5054......464950575d61............4c505542464b575b5f818587a1a5a6919596..................",
    "..................c1c1c1dfdfdecececed0d0cfcccccb............393e424b4d533c556c3b556b4f272b......ab7156f7f1efcdc8cb......b14545......979a9eafb1b47d5050......474c514e5358565b604d5358......494f54464b4e3d42474a4f52a3a7a8979b9d..................",
    "..................c8c8c8d9d9d9cdcdcdd8d8d8c6c6c6..................4953613c5971384353781f23b41f13c59373dff0f6b95b5bdc0707aa3d3d43535a706f739fafb29d5f5c6934344e575b52575b4f5358............4a4f5445494d42464b474b4f95999a999c9e..................",
    "..................cac9cad2d2d2cbcbcbdadadac0c2c2..................3f53683d556c323b4885161bd53f16e0bfa4d1dae2b82e2efc0d0dae36374d5f65605e6395a4a8ac8281a6352d5155584e4f54............3f43484b4f5444484c41464a43474b9193959a9e9f..................",
    "..................cdcdcdcecececcccccd8d8d7..................3a4f643d546a3b4f64............dc6c27dededac4b2b4ba1312ef1312a734344c5f635152578b91949e9e9ecf3527664343..................42474b464b4f43484c40454941454a8e9294979d9d..................",
    "..................cfd0d0cdcdcdcbcbcbd4d5d4............3e53663e566b384f64364a5f............d98f58dfeef4af7c7bb80806df15129f33324d5e634b4d52797b7e97adafc9564bb91305............3c3f44484d5145494d3a3f44383c42454a4e94999995999a..................",
    "..................cfcfcfcbcbcbcacacad3d4d4......23374e445d74374d63384e6637495f............d4cdcadae2e3944544ab0a08c3120e9031304c5b604b4d516266699ba2a39895967d4f4f......3b3e44474c5142474b45494d2e3239353a3f4f53589ca0a2939797..................",
    "..................cbcbcbcacacac8c8c7d3d3d4............3b5066364c63364d652a3d54a09898dddfe1dedfdfc9c8c8791f1e960e0ba10e0a7d2e2d4c595e4c4f5351565a919697949b9b949e9f5d616631353b474c5042464b3e42472c3138393d42616568a4a8a98e9292..................",
    "..................c6c6c6cbcbcbc6c6c5d3d3d3b4b6b6......36495c374f6532485e20354dabaaabe8e8e6d6d7d7c0bcbc6313107a0e0a7f0a066a2b2b4b585d4b4e534b50548d93949096969ca0a1565b5f2a2f3543484c45494d2e333933383e3b3f437d8183a2a8a8........................",
    "..................c3c3c3cececec3c3c2cdcdccb7b9b9............2f445a2e445a2a4056......d1d0cfdfdfdfc5c5c45318175b08056007035829284b565c484b504f5458909596959a9b858a8b2c30332e313742464b373c41252a323b3f434c4f53959a9b929697........................",
    "..................bbbbbcd1d1d0c1c1c0c3c3c1bfbfbf..................2a3f562c445b1a2c44......d3d3d3dce0e06445443700004c08054a27284c555b40444863686b989d9f959a9b44484b22242a383c413c40451d222b3a3e44363a3f767a7da1a5a68c9090........................",
    "........................cdcdccc1c0bebebebccacbc9b2b2b2..................233a51283e55............d3d4d5c6c4c33e1c1b200000371d1e40484d4f545892979a94999b4d515423262b32363a353a3f1a1f28353a40363b3f54595c979c9c939898..............................",
    "........................bdbdbec2c2c1bcbcbabfbfbebababb........................1e354c22384d............d2d4d3c7c7c6817474504547747a7f95999d7b80843d414526292e2d3035242930171d2634393e393e4143484c8b90919ea3a38a8f8f..............................",
    "........................b1b1b3cbcbcab9b9b7bbbab9b1b2b4747e88........................1a2d42213347..................cfd1d189898c7175794d5054292c3024262b1e21271418211f232c3a3e43363b3f3f444886898b9ba0a18d9393....................................",
    "..............................babababdbdbcb5b5b4bbbbba909498384656......................................................30303320242a14181f181c23171a221f242a33383d3c414433373b494e51868b8c999e9f8f9595..........................................",
    "..............................a7a7a9c6c6c5c2c2c0adaeaeabaaa8a5a7a849556017293d..........................................272e372a30362c32382f333934393e363a3f32363b3a3e426166689095959ba0a08e9595................................................",
    "....................................afafb09293956c6e72......b3b5b4b4b4b273797c223242182c4124354b2335482534462332432131431e28341f222723282e2e33382e33374044495f6466828989979b9c999e9e8d9494......................................................",
    "..........................................64666ac2c2c2acacad......adafb0c4c5c4b0afaf............0c213814273f17293d162b411a26321a1b1e22272b31363b7276788f9595989e9d9aa0a18f94968e9292............................................................",
    "................................................b0b0b0c2c2c2acacac......9ea0a0acaeaebcbebfaeaeaf................................................858b8c9da2a38a90918d9193........................................................................",
    "......................................................a9a9a9c0c1c0acacac............9d9fa1a3a4a7b0b2b5a4a6a89d9ea0a4a7a8a9abab..................................................................................................................",
    "............................................................a1a2a2b3b3b2b8b8b8a6a7a7......909195a9aaaca2a2a3a0a0a1a9a9ac939396..................................................................................................................",
    "........................................................................a2a3a2b3b3b3b4b5b6a3a4a69e9ea0a0a0a19b9d9d..................83898b9095988b8e90..........................................................................................",
    "....................................................................................9a9d9d9c9d9ea2a4a5a2a3a3a0a3a3a5a8aaa2a7a8a1a6a6a1a7a8a9b0b0919697..........................................................................................",
    "......................................................................................................9295979192959498999398999297988d90938c9193................................................................................................",
)


# ---------------------------------------------------------------- drawing
SILVER, STEEL, CRIMSON, DIM = (200, 200, 200), (107, 110, 115), (200, 16, 46), (140, 140, 140)
_ESC = "\x1b["
GAP = 3  # columns between the logo and the text


def _color_ok(stream):
    """Colors wherever the terminal already shows them: Linux / Mac, Windows Terminal, a Windows console that
    something else has switched to escape-code mode, or a log viewer (not a console). Only a plain Windows console
    with escape codes off gets the plain block logo. Nothing is changed, only read. NO_COLOR or LC_BANNER_COLOR=0
    turns colors off."""
    if os.environ.get("NO_COLOR") or os.environ.get("LC_BANNER_COLOR", "").strip() == "0":
        return False
    if os.name != "nt" or os.environ.get("WT_SESSION"):
        return True
    try:
        import ctypes

        k = ctypes.windll.kernel32
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(k.GetStdHandle(-11), ctypes.byref(mode)):
            return True  # not a console: ComfyUI Desktop or another log viewer
        return bool(mode.value & 0x0004)  # escape-code mode already on
    except Exception:
        return False


def _sgr(*codes):
    """One escape sequence from its numbers: _sgr(38, 2, r, g, b) sets the text color."""
    return _ESC + ";".join(str(c) for c in codes) + "m"


RESET = _sgr(0)


def _rgb(hexs):
    return None if hexs == "......" else tuple(int(hexs[i:i + 2], 16) for i in (0, 2, 4))


def _logo_lines(color):
    """Two pixel rows per text line: upper half block coloured with the top pixel, background with the bottom one."""
    px = [[_rgb(row[i:i + 6]) for i in range(0, len(row), 6)] for row in LOGO]
    out = []
    for y in range(0, len(px), 2):
        top, bot = px[y], px[y + 1] if y + 1 < len(px) else [None] * len(px[y])
        cells = []
        for t, b in zip(top, bot):
            if not color:
                a = (t is not None) + (b is not None)
                cells.append(" ▄▀█"[(b is not None) + 2 * (t is not None)] if a else " ")
            elif t and b:
                cells.append(_sgr(38, 2, *t, 48, 2, *b) + "▀" + RESET)
            elif t:
                cells.append(_sgr(38, 2, *t) + "▀" + RESET)
            elif b:
                cells.append(_sgr(38, 2, *b) + "▄" + RESET)
            else:
                cells.append(" ")
        out.append("".join(cells))
    return out


def paint(text, rgb, color, bold=False, italic=False):
    if not color or not text:
        return text
    style = ([1] if bold else []) + ([3] if italic else [])
    return _sgr(*style, 38, 2, *rgb) + text + RESET


def pack_line(name, version, count, color, failed=0):
    """'LC123 v1.47.0 ........ 141 nodes' (+ failures in crimson)."""
    left = f"{name} v{version} "
    right = f" {count} nodes"
    dots = "." * max(3, 34 - len(left) - len(right))
    line = paint(left, SILVER, color, bold=True) + paint(dots, STEEL, color) + paint(right, SILVER, color)
    if failed:
        line += paint(f"  {failed} failed (see above)", CRIMSON, color, bold=True)
    return line


def pack_version(pack_dir):
    """The version in a pack's pyproject.toml ("?" when it cannot be read)."""
    try:
        with open(os.path.join(pack_dir, "pyproject.toml"), encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("version"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "?"


def _write(out, stream):
    try:
        print(out, file=stream, flush=True)
    except UnicodeEncodeError:  # a console that cannot show block characters: never fail the load over a banner
        enc = getattr(stream, "encoding", None) or "ascii"
        print(out.encode(enc, errors="replace").decode(enc, errors="replace"), file=stream, flush=True)


def show(pack, version, count, failed=0, stream=None):
    """Called once by each LC pack after it has loaded its nodes."""
    stream = stream or sys.stdout
    if os.environ.get("LC_NO_BANNER"):
        _write(f"[{pack}] v{version}: {count} nodes" + (f", {failed} failed" if failed else ""), stream)
        return
    color = _color_ok(stream)
    if color and stream is sys.stdout and sys.__stdout__ is not None:
        # another pack can wrap sys.stdout in a filter that strips truecolor codes: write to the real console under it
        try:
            sys.stdout.flush()
        except Exception:
            pass
        stream = sys.__stdout__
    if getattr(sys, "_lc_banner_shown", False):  # another LC pack already showed it this session
        _write(indent(color) + pack_line(pack, version, count, color, failed), stream)
        return
    sys._lc_banner_shown = True
    logo = _logo_lines(color)
    text = [""] * len(logo)
    mid = len(logo) // 2
    put = {
        mid - 4: paint("L O N E C A T", SILVER, color, bold=True),
        mid - 3: paint("LC nodes for ComfyUI", STEEL, color),
        mid - 1: paint("True Nothing is. Permitted Everything is", CRIMSON, color, italic=True),
        mid: paint("- Yoda Auditore", DIM, color),
        mid + 2: pack_line(pack, version, count, color, failed),
        mid + 4: paint("https://github.com/lonecatone23  ·  https://ko-fi.com/lonecatone", STEEL, color),
    }
    for i, t in put.items():
        if 0 <= i < len(text):
            text[i] = t
    if color:
        lines = [""] + [f"  {l}{' ' * GAP}{t}".rstrip() for l, t in zip(logo, text)] + [""]
    else:  # block art without colors reads as stripes in most console fonts: the text alone
        lines = [""] + [f"  {t}".rstrip() for t in text[mid - 4:mid + 5]] + [""]
    _write("\n".join(lines), stream)


def indent(color=True):
    """Where the text column starts, so other LC packs' lines line up under the banner."""
    return " " * (2 + (len(LOGO[0]) // 6 + GAP if color else 0))


if __name__ == "__main__":  # preview: python lc_banner.py
    show("LC123", "1.47.0", 141)
    for name, ver, n in (("LC AV", "0.3.8", 16), ("LC MaskMaker", "0.15.0", 14), ("LC ModelBuilder", "0.3.0", 9), ("LC Vision", "1.2.6", 4)):
        show(name, ver, n)
