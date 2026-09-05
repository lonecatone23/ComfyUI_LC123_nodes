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
        const sched = linear.concat(quad, [1]).map((x) => Math.max(0, 1 - x) * hi);
        return sched;
    }
    if (name === "bong_tangent") {
        const slope = 0.2;
        const pivot = (n - 1) * 0.6;
        const atanRow = (sl, piv) => {
            const smax = ((2 / Math.PI) * Math.atan(-sl * (0 - piv)) + 1) / 2;
            const smin = ((2 / Math.PI) * Math.atan(-sl * ((n - 1) - piv)) + 1) / 2;
            const srange = smax - smin || 1;
            const sscale = hi - lo;
            const row = [];
            for (let x = 0; x < n; x++) {
                row.push(((((2 / Math.PI) * Math.atan(-sl * (x - piv)) + 1) / 2) - smin) / srange * sscale + lo);
            }
            return row;
        };
        return atanRow(slope, pivot).concat([0]);
    }
    if (name === "gits" || name === "ays" || name === "ays+" || name === "ays_30" || name === "ays_30+") {
        const tables = {
            gits: [1, 0.86, 0.7, 0.52, 0.36, 0.24, 0.15, 0.09, 0.05, 0.025, 0],
            ays: [1, 0.89, 0.72, 0.54, 0.38, 0.25, 0.16, 0.1, 0.06, 0.03, 0],
            "ays+": [1, 0.93, 0.82, 0.68, 0.52, 0.38, 0.26, 0.17, 0.11, 0.06, 0.03, 0],
            ays_30: [1, 0.95, 0.88, 0.8, 0.71, 0.62, 0.53, 0.44, 0.36, 0.29, 0.23, 0.18, 0.14, 0.11, 0.08, 0.06, 0.04, 0.03, 0.02, 0.01, 0],
            "ays_30+": [1, 0.96, 0.91, 0.84, 0.76, 0.67, 0.58, 0.49, 0.41, 0.34, 0.27, 0.22, 0.17, 0.13, 0.1, 0.07, 0.05, 0.035, 0.02, 0.01, 0],
        };
        const shape = tables[name].map((v) => v * hi);
        return lerpCurve(shape, n);
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

app.registerExtension({
    name: "LC123.SigmaCurve",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "LCSigmaCurve") return;

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            if (onExecuted) onExecuted.apply(this, arguments);
            const curveTxt = message && (message.lc_curve || message.curve);
            const stepsTxt = message && message.lc_steps;
            if (stepsTxt && stepsTxt[0] != null) {
                const n = Math.max(1, parseInt(stepsTxt[0], 10) || 1);
                setWidget(this, "total_steps", n);
            }
            if (curveTxt && curveTxt[0]) {
                setWidget(this, "curve", String(curveTxt[0]));
            }
            if (message && message.save_curve && message.save_curve[0] === false) {
                setWidget(this, "save_curve", false);
            }
            this.setDirtyCanvas(true, true);
        };

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onNodeCreated) onNodeCreated.apply(this, arguments);
            this.title = "LC Sigma Curve";
            if (!this.color) this.color = "#1c6d6d";
            if (!this.bgcolor) this.bgcolor = "#1c6d6d";
            this.lcDrag = -1;
            this.lcPad = { l: 28, r: 10, t: 8, b: 22 };
            this.lcGraphH = 140;

            const self = this;
            const presetW = widget(this, "preset");
            if (presetW) {
                const prev = presetW.callback;
                presetW.callback = function (v) {
                    if (prev) prev.apply(this, arguments);
                    if (v && String(v).startsWith("─")) return;
                    if (v === "from_input") {
                        self.setDirtyCanvas(true, true);
                        return;
                    }
                    if (v !== "Custom" && BUILTINS.has(String(v))) {
                        const steps = Number(widgetVal(self, "total_steps", 20)) || 20;
                        const hi = Number(widgetVal(self, "sigma_max", 1)) || 1;
                        const lo = Number(widgetVal(self, "sigma_min", 0)) || 0;
                        const built = buildPreset(v, steps, hi, lo);
                        setWidget(self, "curve", formatCurve(built));
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
                    if (preset !== "Custom" && preset !== "from_input" && BUILTINS.has(preset) && !preset.startsWith("─")) {
                        setWidget(self, "curve", formatCurve(buildPreset(preset, steps, hi, lo)));
                    } else {
                        const cur = parseCurve(widgetVal(self, "curve", ""));
                        if (cur.length >= 2) setWidget(self, "curve", formatCurve(lerpCurve(cur, steps)));
                    }
                    self.setDirtyCanvas(true, true);
                };
            }
            const maxW = widget(this, "sigma_max");
            if (maxW) {
                const prev = maxW.callback;
                maxW.callback = function () {
                    if (prev) prev.apply(this, arguments);
                    const preset = String(widgetVal(self, "preset", "simple"));
                    if (preset !== "Custom" && BUILTINS.has(preset)) {
                        const steps = Number(widgetVal(self, "total_steps", 20)) || 20;
                        const hi = Number(widgetVal(self, "sigma_max", 1)) || 1;
                        const lo = Number(widgetVal(self, "sigma_min", 0)) || 0;
                        setWidget(self, "curve", formatCurve(buildPreset(preset, steps, hi, lo)));
                    }
                    self.setDirtyCanvas(true, true);
                };
            }

            this.addWidget("button", "Save curve", "save", () => {
                const nameW = widget(self, "save_name");
                if (nameW && !String(nameW.value || "").trim()) {
                    nameW.value = "custom_curve";
                }
                setWidget(self, "save_curve", true);
                // Do not queue from this callback — that throws
                // "can't find output of null" and can wipe save_name.
                // Next Queue Prompt writes the file.
            });

            const curveW = widget(this, "curve");
            if (curveW) {
                curveW.options = curveW.options || {};
                curveW.options.multiline = false;
            }

            const graphW = {
                name: "lc_graph",
                type: "LC_SIGMA_GRAPH",
                value: "",
                options: {},
                serialize: false,
                computeSize: function () {
                    return [270, self.lcGraphH + 16];
                },
                draw: function (ctx, node, width, y) {
                    const padL = 28;
                    const padR = 10;
                    const h = node.lcGraphH || 140;
                    const r = { x: padL, y: y + 4, w: Math.max(40, width - padL - padR), h };
                    node.lcLastGraphRect = r;
                    const vals = node.lcCurveVals();
                    if (vals.length < 2) return;
                    const hi = Math.max(Number(widgetVal(node, "sigma_max", 1)) || 1, 1e-6);
                    const yMax = Math.max(hi, ...vals, 1e-6);
                    const n = Math.max(vals.length - 1, 1);

                    ctx.save();
                    ctx.fillStyle = "rgba(0,0,0,0.45)";
                    ctx.fillRect(r.x, r.y, r.w, r.h);
                    ctx.strokeStyle = "rgba(255,255,255,0.28)";
                    ctx.strokeRect(r.x, r.y, r.w, r.h);

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
                        ctx.arc(px, py, i === node.lcDrag ? 4 : 2.4, 0, Math.PI * 2);
                        ctx.fill();
                    });

                    ctx.fillStyle = "rgba(255,255,255,0.55)";
                    ctx.font = "10px sans-serif";
                    ctx.fillText(yMax.toFixed(2), 4, r.y + 10);
                    ctx.fillText("0", 4, r.y + r.h - 2);
                    ctx.restore();
                },
                mouse: function (event, pos, node) {
                    const r = node.lcLastGraphRect;
                    if (!r) return false;
                    const localX = pos[0];
                    const localY = pos[1];
                    const over =
                        localX >= r.x - 4 &&
                        localX <= r.x + r.w + 4 &&
                        localY >= r.y - 4 &&
                        localY <= r.y + r.h + 4;

                    if (event.type === "pointerdown" || event.type === "mousedown") {
                        if (!over) return false;
                        const vals = node.lcCurveVals();
                        const n = Math.max(vals.length - 1, 1);
                        let idx = Math.round(((localX - r.x) / r.w) * n);
                        idx = Math.max(0, Math.min(vals.length - 1, idx));
                        node.lcDrag = idx;
                        node.lcDragOrig = vals.slice();
                        return true;
                    }
                    if ((event.type === "pointermove" || event.type === "mousemove") && node.lcDrag >= 0) {
                        const vals = node.lcDragOrig ? node.lcDragOrig.slice() : node.lcCurveVals();
                        const hi = Math.max(Number(widgetVal(node, "sigma_max", 1)) || 1, 1e-6);
                        const yMax = Math.max(hi, ...vals, 1e-6);
                        let ny = yMax * (1 - (localY - r.y) / r.h);
                        ny = Math.max(0, ny);
                        const mode = String(widgetVal(node, "edit_mode", "smooth"));
                        const radius = Math.max(0, Number(widgetVal(node, "smooth_radius", 1)) || 0);
                        const k = node.lcDrag;
                        if (mode === "spike" || radius <= 0) vals[k] = ny;
                        else {
                            for (let i = 0; i < vals.length; i++) {
                                const d = (i - k) / Math.max(radius, 0.001);
                                const wgt = Math.exp(-0.5 * d * d);
                                vals[i] = (1 - wgt) * vals[i] + wgt * ny;
                            }
                        }
                        if (widgetVal(node, "descending", true)) {
                            const locked = projectDescending(vals, true);
                            for (let i = 0; i < vals.length; i++) vals[i] = locked[i];
                        }
                        setWidget(node, "curve", formatCurve(vals.map((v) => Math.max(0, v))));
                        markCustom(node);
                        node.setDirtyCanvas(true, true);
                        return true;
                    }
                    if (event.type === "pointerup" || event.type === "mouseup") {
                        node.lcDrag = -1;
                        node.lcDragOrig = null;
                    }
                    return false;
                },
            };

            const idx = this.widgets.findIndex((w) => w.name === "curve");
            if (idx >= 0) this.widgets.splice(idx + 1, 0, graphW);
            else this.widgets.push(graphW);
        };

        nodeType.prototype.lcCurveVals = function () {
            let vals = parseCurve(widgetVal(this, "curve", ""));
            const steps = Math.max(1, Number(widgetVal(this, "total_steps", 20)) || 20);
            const hi = Number(widgetVal(this, "sigma_max", 1)) || 1;
            const lo = Number(widgetVal(this, "sigma_min", 0)) || 0;
            const preset = String(widgetVal(this, "preset", "simple"));
            if (vals.length < 2) {
                vals = buildPreset(BUILTINS.has(preset) && preset !== "Custom" ? preset : "simple", steps, hi, lo);
            } else if (vals.length - 1 !== steps) {
                vals = lerpCurve(vals, steps);
            }
            return vals;
        };

        const _computeSize = nodeType.prototype.computeSize;
        nodeType.prototype.computeSize = function () {
            const base = _computeSize ? _computeSize.apply(this, arguments) : [280, 200];
            return [Math.max(280, base[0] || 280), Math.max(base[1] || 200, 220)];
        };
    },
});
