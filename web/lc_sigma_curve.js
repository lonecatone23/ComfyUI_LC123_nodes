import { app } from "../../scripts/app.js";

const BUILTINS = new Set([
    "simple",
    "linear",
    "normal",
    "karras",
    "exponential",
    "sgm_uniform",
    "ddim_uniform",
    "beta",
    "beta57",
    "beta_1_1",
    "linear_quadratic",
    "kl_optimal",
    "bong_tangent",
    "gits",
    "ays",
    "ays+",
    "ays_30",
    "ays_30+",
    "from_input",
    "Custom",
]);

function parseCurve(text) {
    if (!text) return [];
    return String(text)
        .replace(/[\[\]]/g, " ")
        .split(/[,\s]+/)
        .map((p) => p.trim())
        .filter(Boolean)
        .map(Number)
        .filter((n) => Number.isFinite(n));
}

function formatCurve(vals) {
    return vals.map((v) => {
        const n = Number(v);
        if (!Number.isFinite(n)) return "0";
        return n.toFixed(6).replace(/\.?0+$/, "");
    }).join(", ");
}

function lerpCurve(sigmas, newSteps) {
    if (!sigmas.length || newSteps < 1) return sigmas.slice();
    const out = [];
    for (let i = 0; i <= newSteps; i++) {
        const x = i / newSteps;
        if (x <= 0) {
            out.push(sigmas[0]);
            continue;
        }
        if (x >= 1) {
            out.push(sigmas[sigmas.length - 1]);
            continue;
        }
        const pos = (sigmas.length - 1) * x;
        const idx = Math.floor(pos);
        const frac = pos - idx;
        if (idx >= sigmas.length - 1) out.push(sigmas[sigmas.length - 1]);
        else out.push((1 - frac) * sigmas[idx] + frac * sigmas[idx + 1]);
    }
    return out;
}

function buildPreset(name, steps, hi, lo) {
    steps = Math.max(1, steps | 0);
    hi = Math.max(Number(hi) || 1, 1e-8);
    lo = Math.max(Number(lo) || 0, 0);
    const n = steps;
    const linear = () => {
        const s = [];
        for (let i = 0; i < n; i++) s.push(hi + (lo - hi) * (i / n));
        s.push(lo === 0 ? 0 : lo);
        if (s[s.length - 1] !== 0) s[s.length - 1] = 0;
        return s;
    };
    name = String(name || "simple").toLowerCase();
    if (name === "simple" || name === "linear" || name === "normal") return linear();
    if (name === "karras") {
        const rho = 7;
        const smin = Math.max(lo, 1e-5);
        const minInv = smin ** (1 / rho);
        const maxInv = hi ** (1 / rho);
        const s = [];
        for (let i = 0; i < n; i++) {
            const r = n === 1 ? 0 : i / (n - 1);
            s.push((maxInv + r * (minInv - maxInv)) ** rho);
        }
        s.push(0);
        return s;
    }
    if (name === "exponential" || name === "sgm_uniform") {
        const smin = Math.max(lo, 1e-5);
        const s = [];
        const denom = name === "sgm_uniform" ? n : Math.max(n - 1, 1);
        for (let i = 0; i < n; i++) {
            s.push(Math.exp(Math.log(hi) + (Math.log(smin) - Math.log(hi)) * (i / denom)));
        }
        s.push(0);
        return s;
    }
    if (name === "beta" || name === "beta57" || name === "beta_1_1") {
        let a = 0.6, b = 0.6;
        if (name === "beta57") { a = 0.5; b = 0.7; }
        if (name === "beta_1_1") { a = 1; b = 1; }
        const s = [];
        for (let i = 0; i < n; i++) {
            const t = n === 1 ? 0 : i / (n - 1);
            const w = a === 1 && b === 1 ? t : Math.pow(t, a / Math.max(b, 1e-6));
            s.push(hi + (lo - hi) * w);
        }
        s.push(0);
        return s;
    }
    if (name === "ddim_uniform") {
        const s = [];
        for (let i = 0; i < n; i++) s.push(hi * (1 - i / n));
        s.push(0);
        return s;
    }
    if (name === "kl_optimal") {
        const smin = Math.max(lo, 1e-5);
        const s = [];
        for (let i = 0; i < n; i++) {
            const t = n === 1 ? 0 : i / (n - 1);
            s.push(Math.tan((1 - t) * Math.atan(hi) + t * Math.atan(smin)));
        }
        s.push(0);
        return s;
    }
    if (name === "linear_quadratic") {
        if (n <= 1) return [hi, 0];
        const threshold = 0.025;
        const linearSteps = Math.max(1, Math.floor(n / 2));
        const linear = [];
        for (let i = 0; i < linearSteps; i++) linear.push((i * threshold) / linearSteps);
        const diff = linearSteps - threshold * n;
        const qSteps = Math.max(n - linearSteps, 1);
        const qCoef = diff / (linearSteps * qSteps * qSteps);
        const lCoef = threshold / linearSteps - (2 * diff) / (qSteps * qSteps);
        const cnst = qCoef * linearSteps * linearSteps;
        const quad = [];
        for (let i = linearSteps; i < n; i++) quad.push(qCoef * i * i + lCoef * i + cnst);
        return linear.concat(quad, [1]).map((x) => Math.max(0, 1 - x) * hi);
    }
    if (name === "bong_tangent") {
        const slope = 0.2, pivotFrac = 0.6, N = n + 2, middle = (hi + lo) * 0.5;
        const midpoint = Math.floor((N * pivotFrac * 2) / 2);
        const slope1 = slope / Math.max(N / 40, 1e-6);
        const slope2 = slope1;
        const stage2 = Math.max(N - midpoint, 1);
        const stage1 = Math.max(N - stage2, 1);
        const pivot1 = Math.floor(N * pivotFrac);
        const pivot2 = pivot1;
        const piece = (len, sl, piv, a, b) => {
            const smax = ((2 / Math.PI) * Math.atan(-sl * (0 - piv)) + 1) / 2;
            const smin = ((2 / Math.PI) * Math.atan(-sl * ((len - 1) - piv)) + 1) / 2;
            const srange = smax - smin || 1;
            const row = [];
            for (let x = 0; x < len; x++) {
                row.push(((((2 / Math.PI) * Math.atan(-sl * (x - piv)) + 1) / 2) - smin) / srange * (a - b) + b);
            }
            return row;
        };
        const raw = piece(stage1, slope1, pivot1, hi, middle).slice(0, -1)
            .concat(piece(stage2, slope2, pivot2 - stage1, middle, lo), [0]);
        const out = lerpCurve(raw.map((v) => Math.max(0, v)), n);
        if (out.length) { out[0] = hi; out[out.length - 1] = 0; }
        return out;
    }
    if (name === "gits" || name === "ays" || name === "ays+" || name === "ays_30" || name === "ays_30+") {
        const tables = {
            gits: [1, 0.86, 0.7, 0.52, 0.36, 0.24, 0.15, 0.09, 0.05, 0.025, 0],
            ays: [1, 0.89, 0.72, 0.54, 0.38, 0.25, 0.16, 0.1, 0.06, 0.03, 0],
            "ays+": [1, 0.93, 0.82, 0.68, 0.52, 0.38, 0.26, 0.17, 0.11, 0.06, 0.03, 0],
            ays_30: [1, 0.95, 0.88, 0.8, 0.71, 0.62, 0.53, 0.44, 0.36, 0.29, 0.23, 0.18, 0.14, 0.11, 0.08, 0.06, 0.04, 0.03, 0.02, 0.01, 0],
            "ays_30+": [1, 0.96, 0.91, 0.84, 0.76, 0.67, 0.58, 0.49, 0.41, 0.34, 0.27, 0.22, 0.17, 0.13, 0.1, 0.07, 0.05, 0.035, 0.02, 0.01, 0],
        };
        return lerpCurve(tables[name].map((v) => v * hi), n);
    }
    return linear();
}

function projectDescending(vals, lockZero) {
    if (!vals.length) return vals;
    const s = vals.map((v) => Math.max(0, v));
    if (lockZero) s[s.length - 1] = 0;
    for (let i = 1; i < s.length; i++) if (s[i] > s[i - 1]) s[i] = s[i - 1];
    for (let i = s.length - 2; i >= 0; i--) if (s[i] < s[i + 1]) s[i] = s[i + 1];
    return s.map((v) => Math.max(0, v));
}

function widget(node, name) {
    return (node.widgets || []).find((w) => w.name === name);
}

function widgetVal(node, name, fallback) {
    const w = widget(node, name);
    if (!w) return fallback;
    return w.value;
}

function setWidget(node, name, value) {
    const w = widget(node, name);
    if (!w) return;
    w.value = value;
}

function markCustom(node) {
    const p = widget(node, "preset");
    if (p && p.value !== "Custom") p.value = "Custom";
}

function curveVals(node) {
    let vals = parseCurve(widgetVal(node, "curve", ""));
    const steps = Math.max(1, Number(widgetVal(node, "total_steps", 20)) || 20);
    const hi = Number(widgetVal(node, "sigma_max", 1)) || 1;
    const lo = Number(widgetVal(node, "sigma_min", 0)) || 0;
    const preset = String(widgetVal(node, "preset", "simple"));
    if (vals.length < 2) {
        vals = buildPreset(BUILTINS.has(preset) && preset !== "Custom" && preset !== "from_input" ? preset : "simple", steps, hi, lo);
    } else if (vals.length - 1 !== steps) {
        vals = lerpCurve(vals, steps);
    }
    return vals;
}

app.registerExtension({
    name: "LC123.SigmaCurve",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "LCSigmaCurve") return;

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            if (onExecuted) onExecuted.apply(this, arguments);
            const raw = message && (message.curve || message.text);
            const txt = Array.isArray(raw) ? raw[0] : raw;
            if (txt) {
                const vals = parseCurve(String(txt));
                if (vals.length >= 2) {
                    setWidget(this, "curve", formatCurve(vals));
                    setWidget(this, "total_steps", vals.length - 1);
                }
            }
            this.setDirtyCanvas(true, true);
        };

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onNodeCreated) onNodeCreated.apply(this, arguments);
            this.title = "LC Sigma Curve";
            this.lcDrag = -1;
            this.lcGraphH = 140;

            const self = this;
            const presetW = widget(this, "preset");
            if (presetW) {
                const prev = presetW.callback;
                presetW.callback = function (v) {
                    if (prev) prev.apply(this, arguments);
                    if (v && String(v).startsWith("─")) return;
                    if (v === "from_input" || v === "Custom") {
                        self.setDirtyCanvas(true, true);
                        return;
                    }
                    if (!BUILTINS.has(String(v)) && v && !String(v).startsWith("─")) {
                        const file = encodeURIComponent(v) + ".json";
                        ["/extensions/ComfyUI_LC123_nodes/sigma_curves/", "/extensions/comfyui_lc123_nodes/sigma_curves/"].forEach((root) => {
                            fetch(root + file + "?t=" + Date.now()).then((r) => r.ok ? r.json() : null).then((body) => {
                                if (!body) return;
                                const pts = parseCurve(body.sigmas || body);
                                if (pts.length >= 2) {
                                    setWidget(self, "curve", formatCurve(pts));
                                    self.setDirtyCanvas(true, true);
                                }
                            }).catch(() => {});
                        });
                        return;
                    }
                    if (BUILTINS.has(String(v))) {
                        const steps = Number(widgetVal(self, "total_steps", 20)) || 20;
                        const hi = Number(widgetVal(self, "sigma_max", 1)) || 1;
                        const lo = Number(widgetVal(self, "sigma_min", 0)) || 0;
                        setWidget(self, "curve", formatCurve(buildPreset(v, steps, hi, lo)));
                    }
                    self.setDirtyCanvas(true, true);
                };
            }
            const stepsW = widget(this, "total_steps");
            if (stepsW) {
                const prev = stepsW.callback;
                stepsW.callback = function (v) {
                    if (prev) prev.apply(this, arguments);
                    const preset = String(widgetVal(self, "preset", "simple"));
                    const steps = Math.max(1, Number(v) || 20);
                    const hi = Number(widgetVal(self, "sigma_max", 1)) || 1;
                    const lo = Number(widgetVal(self, "sigma_min", 0)) || 0;
                    if (preset !== "Custom" && preset !== "from_input" && BUILTINS.has(preset) && !String(preset).startsWith("─")) {
                        setWidget(self, "curve", formatCurve(buildPreset(preset, steps, hi, lo)));
                    } else {
                        const cur = parseCurve(widgetVal(self, "curve", ""));
                        if (cur.length >= 2) setWidget(self, "curve", formatCurve(lerpCurve(cur, steps)));
                    }
                    self.setDirtyCanvas(true, true);
                };
            }

            this.widgets = (this.widgets || []).filter(function (w) {
                if (!w) return false;
                if (w.name === "lc_graph") return false;
                if (w.type === "button") return false;
                if (w.type === "LC_SIGMA_GRAPH" || w.type === "custom") return false;
                return true;
            });
            var sn = widget(this, "save_name");
            if (sn && (sn.value == null || String(sn.value) === "null")) sn.value = "";
            var sc = widget(this, "save_curve");
            if (sc && sc.value == null) sc.value = false;

            if (!this.widgets.some((w) => w && w.type === "button")) {
                const btn = this.addWidget("button", "Save curve", "save", () => {
                    const nameW = widget(self, "save_name");
                    if (nameW && !String(nameW.value || "").trim()) nameW.value = "custom_curve";
                    setWidget(self, "save_curve", true);
                    const nm = nameW ? String(nameW.value).trim() : "";
                    if (nm && typeof setPresetList === "function") setPresetList([nm]);
                });
                if (btn) btn.serialize = false;
            }

            const presetCombo = widget(this, "preset");
            const nodeRef = this;
            const tryUrls = [
                "/extensions/ComfyUI_LC123_nodes/sigma_curves/index.json",
                "/extensions/comfyui_lc123_nodes/sigma_curves/index.json",
            ];
            const builtinOrder = [
                "from_input", "────────",
                "simple", "linear", "normal", "karras", "exponential", "sgm_uniform",
                "ddim_uniform", "beta", "beta57", "beta_1_1", "linear_quadratic",
                "kl_optimal", "bong_tangent", "gits", "ays", "ays+", "ays_30", "ays_30+",
            ];
            function existingSaved() {
                const cur = (presetCombo && presetCombo.options && presetCombo.options.values) || [];
                return cur.filter((n) => n && n !== "Custom" && n !== "from_input" && !String(n).startsWith("─") && !BUILTINS.has(String(n)));
            }
            function setPresetList(savedNames) {
                if (!presetCombo || !presetCombo.options) return;
                const extra = {};
                existingSaved().forEach((n) => { extra[n] = true; });
                (savedNames || []).forEach((n) => {
                    if (n && n !== "index" && n !== "Custom" && n !== "from_input") extra[n] = true;
                });
                const saved = Object.keys(extra).sort();
                const vals = builtinOrder.slice();
                if (saved.length) vals.push("────────", ...saved);
                vals.push("────────", "Custom");
                presetCombo.options.values = vals;
                try {
                    const spec = nodeRef.constructor.nodeData.input.required.preset;
                    if (Array.isArray(spec)) spec[0] = vals;
                } catch (e) { /* ignore */ }
            }
            (async () => {
                for (const url of tryUrls) {
                    try {
                        const res = await fetch(url + "?t=" + Date.now());
                        if (!res.ok) continue;
                        const data = await res.json();
                        const names = (data && data.curves) || [];
                        setPresetList(names);
                        const want = presetCombo.value;
                        if (want && names.indexOf(want) >= 0) {
                            const jr = await fetch(url.replace("index.json", encodeURIComponent(want) + ".json") + "?t=" + Date.now());
                            if (jr.ok) {
                                const body = await jr.json();
                                const pts = parseCurve(body.sigmas || body);
                                if (pts.length >= 2) setWidget(nodeRef, "curve", formatCurve(pts));
                            }
                        }
                        nodeRef.setDirtyCanvas(true, true);
                        return;
                    } catch (e) { /* next url */ }
                }
            })();
        };

        const GRAPH_H = 140;
        const _computeSize = nodeType.prototype.computeSize;
        nodeType.prototype.computeSize = function () {
            const base = _computeSize ? _computeSize.apply(this, arguments) : [300, 220];
            return [Math.max(300, base[0] || 300), (base[1] || 220) + GRAPH_H + 10];
        };
        nodeType.prototype.lcGraphRect = function () {
            const ws = this.widgets || [];
            let top = LiteGraph.NODE_TITLE_HEIGHT + 8;
            for (let i = 0; i < ws.length; i++) {
                if (ws[i] && ws[i].last_y != null) top = Math.max(top, ws[i].last_y + 22);
            }
            const h = Math.max(GRAPH_H, this.size[1] - top - 10);
            return { x: 28, y: top, w: Math.max(40, this.size[0] - 40), h };
        };
        nodeType.prototype.lcEndDrag = function () {
            this.lcDrag = -1;
            this.lcDragOrig = null;
            if (this._lcUp) {
                window.removeEventListener("pointerup", this._lcUp, true);
                window.removeEventListener("mouseup", this._lcUp, true);
                this._lcUp = null;
            }
        };
        nodeType.prototype.onMouseDown = function (e, pos) {
            const r = this.lcGraphRect();
            if (pos[0] < r.x || pos[0] > r.x + r.w || pos[1] < r.y || pos[1] > r.y + r.h) return false;
            const vals = curveVals(this);
            const n = Math.max(vals.length - 1, 1);
            this.lcDrag = Math.max(0, Math.min(vals.length - 1, Math.round(((pos[0] - r.x) / r.w) * n)));
            this.lcDragOrig = vals.slice();
            const node = this;
            if (this._lcUp) {
                window.removeEventListener("pointerup", this._lcUp, true);
                window.removeEventListener("mouseup", this._lcUp, true);
            }
            this._lcUp = function () {
                node.lcEndDrag();
                node.setDirtyCanvas(true, true);
            };
            window.addEventListener("pointerup", this._lcUp, true);
            window.addEventListener("mouseup", this._lcUp, true);
            return true;
        };
        nodeType.prototype.onMouseMove = function (e, pos) {
            if (this.lcDrag < 0) return false;
            if (e && typeof e.buttons === "number" && e.buttons === 0) {
                this.lcEndDrag();
                return false;
            }
            const r = this.lcGraphRect();
            const vals = this.lcDragOrig ? this.lcDragOrig.slice() : curveVals(this);
            const hi = Math.max(Number(widgetVal(this, "sigma_max", 1)) || 1, 1e-6);
            const yMax = Math.max(hi, ...vals, 1e-6);
            let ny = Math.max(0, yMax * (1 - (pos[1] - r.y) / r.h));
            const mode = String(widgetVal(this, "edit_mode", "smooth"));
            const radius = Math.max(0, Number(widgetVal(this, "smooth_radius", 1)) || 0);
            const k = this.lcDrag;
            if (mode === "spike" || radius <= 0) vals[k] = ny;
            else {
                for (let i = 0; i < vals.length; i++) {
                    const d = (i - k) / Math.max(radius, 0.001);
                    const wgt = Math.exp(-0.5 * d * d);
                    vals[i] = (1 - wgt) * vals[i] + wgt * ny;
                }
            }
            if (widgetVal(this, "descending", true)) {
                const locked = projectDescending(vals, true);
                for (let i = 0; i < vals.length; i++) vals[i] = locked[i];
            }
            setWidget(this, "curve", formatCurve(vals.map((v) => Math.max(0, v))));
            markCustom(this);
            this.setDirtyCanvas(true, true);
            return true;
        };
        nodeType.prototype.onMouseUp = function () {
            this.lcEndDrag();
            return false;
        };
        const onDrawFg = nodeType.prototype.onDrawForeground;
        nodeType.prototype.onDrawForeground = function (ctx) {
            if (onDrawFg) onDrawFg.apply(this, arguments);
            if (this.flags && this.flags.collapsed) return;
            const r = this.lcGraphRect();
            const vals = curveVals(this);
            if (vals.length < 2) return;
            const hi = Math.max(Number(widgetVal(this, "sigma_max", 1)) || 1, 1e-6);
            const yMax = Math.max(hi, ...vals, 1e-6);
            const n = Math.max(vals.length - 1, 1);
            ctx.save();
            ctx.fillStyle = "rgba(0,0,0,0.28)";
            ctx.fillRect(r.x, r.y, r.w, r.h);
            ctx.strokeStyle = "rgba(255,255,255,0.25)";
            ctx.strokeRect(r.x, r.y, r.w, r.h);
            ctx.beginPath();
            ctx.rect(r.x, r.y, r.w, r.h);
            ctx.clip();
            ctx.strokeStyle = "#8fd4c4";
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            vals.forEach((v, i) => {
                const px = r.x + (i / n) * r.w;
                const py = r.y + (1 - v / yMax) * r.h;
                if (i === 0) ctx.moveTo(px, py);
                else ctx.lineTo(px, py);
            });
            ctx.stroke();
            ctx.fillStyle = "#c8efe4";
            vals.forEach((v, i) => {
                const px = r.x + (i / n) * r.w;
                const py = r.y + (1 - v / yMax) * r.h;
                ctx.beginPath();
                ctx.arc(px, py, i === this.lcDrag ? 4 : 2.4, 0, Math.PI * 2);
                ctx.fill();
            });
            ctx.restore();
            ctx.fillStyle = "rgba(255,255,255,0.55)";
            ctx.font = "10px sans-serif";
            ctx.fillText(yMax.toFixed(2), 4, r.y + 10);
            ctx.fillText("0", 4, r.y + r.h - 2);
        };
    },
});

