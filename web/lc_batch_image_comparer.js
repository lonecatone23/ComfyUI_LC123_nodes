/**
 * LC Batch Image Comparer  (v5)
 * -----------------------------
 * - Freely movable
 * - Single synchronized index: Aₙ vs Bₙ
 * - Fixed-height selector bar so image area never jumps
 * - All custom drawing pushed BELOW the input/output socket row
 * - Socket display names appear on either side of the pair control:
 *     "Post Processed"  ◀  Pair N / Total  ▶  "Original"
 * - Mode label removed from the bar (still available in Properties)
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPE = "LCBatchImageComparer";
const SELECTOR_HEIGHT = 30;
const MIN_W = 300;
const DEFAULT_W = 300;
const DEFAULT_H = 420;
const MIN_H = 400;
const SIDE_PAD = 44;          // clear of left/right socket dots
const SLOT_HEIGHT = 22;

function imageDataToUrl(data) {
    if (!data) return null;
    return api.apiURL(
        `/view?filename=${encodeURIComponent(data.filename)}` +
        `&type=${data.type}` +
        `&subfolder=${data.subfolder || ""}` +
        `${app.getPreviewFormatParam()}${app.getRandParam()}`
    );
}

function slotDisplayName(slot) {
    if (!slot) return "";
    // Prefer the user-visible label, then localized_name, then name
    return (slot.label || slot.localized_name || slot.name || "").trim();
}

class LCBatchImageComparer {
    constructor(node) {
        this.node = node;
        this.imagesA = [];
        this.imagesB = [];
        this.index   = 0;
        this.mode    = "Slide";
        this.selectedSide = 0;
        this.pointerOver  = false;
        this.pointerPos   = [0, 0];
        this.imgA = null;
        this.imgB = null;

        this._prevBtn = null;
        this._nextBtn = null;

        this._bind(node);
    }

    /** Vertical offset so we draw below the socket label row */
    _socketOffset() {
        const node = this.node;
        const nIn  = (node.inputs  || []).filter(s => s && s.type).length;
        const nOut = (node.outputs || []).filter(s => s && s.type).length;
        const rows = Math.max(nIn, nOut, 1);
        return rows * SLOT_HEIGHT + 4;
    }

    _bind(node) {
        if (!node.size || node.size[0] < MIN_W) {
            node.size = [
                Math.max(node.size?.[0] || 300, MIN_W),
                Math.max(node.size?.[1] || 420, MIN_H)
            ];
        }

        if (node.properties?.comparer_mode === undefined) {
            node.addProperty?.("comparer_mode", "Slide", "combo", {
                values: ["Slide", "Click"]
            });
            if (!node.properties) node.properties = {};
            node.properties.comparer_mode = "Slide";
        }

        const self = this;

        const origDrawFG = node.onDrawForeground;
        node.onDrawForeground = function (ctx, graphCanvas) {
            if (origDrawFG) origDrawFG.apply(this, arguments);
            if (this.flags?.collapsed) return;
            self.draw(ctx);
        };

        const origMouseDown = node.onMouseDown;
        node.onMouseDown = function (e, pos, canvas) {
            if (pos[1] < 0) {
                return origMouseDown ? origMouseDown.apply(this, arguments) : false;
            }
            const handled = self.onMouseDown(e, pos, canvas);
            if (handled) return true;
            return origMouseDown ? origMouseDown.apply(this, arguments) : false;
        };

        const origMouseMove = node.onMouseMove;
        node.onMouseMove = function (e, pos, canvas) {
            self.onMouseMove(e, pos, canvas);
            return origMouseMove ? origMouseMove.apply(this, arguments) : false;
        };

        const origMouseEnter = node.onMouseEnter;
        node.onMouseEnter = function (e) {
            self.pointerOver = true;
            if (origMouseEnter) origMouseEnter.apply(this, arguments);
        };

        const origMouseLeave = node.onMouseLeave;
        node.onMouseLeave = function (e) {
            self.pointerOver = false;
            app.canvas?.setDirty?.(true, true);
            if (origMouseLeave) origMouseLeave.apply(this, arguments);
        };

        const origExecuted = node.onExecuted;
        node.onExecuted = function (message) {
            if (origExecuted) origExecuted.apply(this, arguments);
            self.onExecuted(message);
        };

        const origResize = node.onResize;
        node.onResize = function (size) {
            if (size[0] < MIN_W) size[0] = MIN_W;
            if (size[1] < MIN_H) size[1] = MIN_H;
            if (origResize) origResize.apply(this, arguments);
        };
    }

    onExecuted(message) {
        if (!message) return;
        this.imagesA = message.a_images || [];
        this.imagesB = message.b_images || [];

        const maxIdx = Math.max(
            0,
            Math.max(this.imagesA.length, this.imagesB.length) - 1
        );
        this.index = Math.min(this.index, maxIdx);
        this._loadImages();
        app.canvas?.setDirty?.(true, true);
    }

    _loadImages() {
        const self = this;
        const idx = this.index;

        if (this.imagesA.length > 0) {
            const data = this.imagesA[Math.min(idx, this.imagesA.length - 1)];
            const url = imageDataToUrl(data);
            if (url) {
                const img = new Image();
                img.onload = () => { self.imgA = img; app.canvas?.setDirty?.(true, true); };
                img.src = url;
            }
        } else {
            this.imgA = null;
        }

        if (this.imagesB.length > 0) {
            const data = this.imagesB[Math.min(idx, this.imagesB.length - 1)];
            const url = imageDataToUrl(data);
            if (url) {
                const img = new Image();
                img.onload = () => { self.imgB = img; app.canvas?.setDirty?.(true, true); };
                img.src = url;
            }
        } else {
            this.imgB = null;
        }
    }

    // ------------------------------------------------------------------
    draw(ctx) {
        const node = this.node;
        const w = node.size[0];
        const h = node.size[1];
        const top = this._socketOffset();

        // Selector background
        ctx.fillStyle = "#1a1a1a";
        ctx.fillRect(0, top, w, SELECTOR_HEIGHT);

        ctx.strokeStyle = "#333";
        ctx.beginPath();
        ctx.moveTo(0, top + SELECTOR_HEIGHT - 0.5);
        ctx.lineTo(w, top + SELECTOR_HEIGHT - 0.5);
        ctx.stroke();

        const total = Math.max(this.imagesA.length, this.imagesB.length);
        const hasBatch = total > 1;

        // Socket display names (whatever the user renamed them to)
        const nameA = slotDisplayName(node.inputs?.[0]) || "A";
        const nameB = slotDisplayName(node.inputs?.[1]) || "B";

        ctx.font = "12px sans-serif";
        ctx.textBaseline = "middle";
        ctx.textAlign = "left";

        this._prevBtn = null;
        this._nextBtn = null;

        const midY = top + SELECTOR_HEIGHT / 2;

        // ----- Build the three pieces: left name | centre control | right name
        const arrowW = 14;
        const gap    = 8;

        const label = total === 0
            ? "No images"
            : (hasBatch
                ? `Pair  ${this.index + 1}  /  ${total}`
                : `Pair  1  /  1`);

        const labelW = ctx.measureText(label).width;
        const nameAW = ctx.measureText(nameA).width;
        const nameBW = ctx.measureText(nameB).width;

        // Centre control width (arrows + label)
        const ctrlW = (hasBatch ? arrowW + gap : 0) + labelW + (hasBatch ? gap + arrowW : 0);

        // Ideal centred position of the control
        let ctrlX = (w - ctrlW) / 2;

        // Make sure left/right names have room and stay inside SIDE_PAD
        const leftLimit  = SIDE_PAD + nameAW + 12;
        const rightLimit = w - SIDE_PAD - nameBW - 12;
        ctrlX = Math.max(leftLimit, Math.min(ctrlX, rightLimit - ctrlW));

        // --- Left socket name
        ctx.fillStyle = "#aaa";
        ctx.textAlign = "left";
        ctx.fillText(nameA, SIDE_PAD, midY);

        // --- Centre control
        let x = ctrlX;

        if (hasBatch) {
            ctx.fillStyle = "#6af";
            ctx.fillText("◀", x, midY);
            this._prevBtn = { x: x - 2, w: arrowW + 4, y: top };
            x += arrowW + gap;
        }

        ctx.fillStyle = total === 0 ? "#666" : "#ccc";
        ctx.fillText(label, x, midY);
        x += labelW;

        if (hasBatch) {
            x += gap;
            ctx.fillStyle = "#6af";
            ctx.fillText("▶", x, midY);
            this._nextBtn = { x: x - 2, w: arrowW + 4, y: top };
        }

        // --- Right socket name
        ctx.fillStyle = "#aaa";
        ctx.textAlign = "right";
        ctx.fillText(nameB, w - SIDE_PAD, midY);
        ctx.textAlign = "left";

        // ---- Image area
        const imgY = top + SELECTOR_HEIGHT;
        const imgH = h - imgY;

        if (imgH > 0) {
            ctx.fillStyle = "#111";
            ctx.fillRect(0, imgY, w, imgH);
            this._drawComparison(ctx, 0, imgY, w, imgH);
        }
    }

    _drawComparison(ctx, x, y, w, h) {
        const imgA = this.imgA;
        const imgB = this.imgB;

        if (!imgA && !imgB) {
            ctx.fillStyle = "#444";
            ctx.font = "14px sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("No images", x + w / 2, y + h / 2);
            ctx.textAlign = "left";
            return;
        }

        const drawCover = (img, dx, dy, dw, dh) => {
            if (!img) return;
            const scale = Math.min(dw / img.width, dh / img.height);
            const sw = img.width  * scale;
            const sh = img.height * scale;
            const ox = dx + (dw - sw) / 2;
            const oy = dy + (dh - sh) / 2;
            ctx.drawImage(img, ox, oy, sw, sh);
        };

        const mode = this.node.properties?.comparer_mode || this.mode;

        if (mode === "Click") {
            const showB = this.selectedSide === 1 && imgB;
            drawCover(showB ? imgB : (imgA || imgB), x, y, w, h);
        } else {
            if (imgB) drawCover(imgB, x, y, w, h);
            else if (imgA) drawCover(imgA, x, y, w, h);

            if (imgA && imgB) {
                let splitX = w / 2;
                if (this.pointerOver) {
                    splitX = Math.max(0, Math.min(w, this.pointerPos[0]));
                }

                ctx.save();
                ctx.beginPath();
                ctx.rect(x, y, splitX, h);
                ctx.clip();
                drawCover(imgA, x, y, w, h);
                ctx.restore();

                ctx.strokeStyle = "rgba(255,255,255,0.9)";
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(x + splitX, y);
                ctx.lineTo(x + splitX, y + h);
                ctx.stroke();
            }
        }
    }

    // ------------------------------------------------------------------
    onMouseMove(e, pos, canvas) {
        this.pointerPos = pos;
        const mode = this.node.properties?.comparer_mode || this.mode;
        const top = this._socketOffset();
        if (mode === "Slide" && pos[1] >= top + SELECTOR_HEIGHT) {
            app.canvas?.setDirty?.(true, true);
        }
    }

    onMouseDown(e, pos, canvas) {
        if (pos[1] < 0) return false;

        const top = this._socketOffset();

        if (pos[1] >= top && pos[1] < top + SELECTOR_HEIGHT) {
            return this._handleSelectorClick(pos[0]);
        }

        if (pos[1] >= top + SELECTOR_HEIGHT) {
            const mode = this.node.properties?.comparer_mode || this.mode;
            if (mode === "Click") {
                this.selectedSide = this.selectedSide === 0 ? 1 : 0;
                app.canvas?.setDirty?.(true, true);
                return true;
            }
        }
        return false;
    }

    _handleSelectorClick(px) {
        const total = Math.max(this.imagesA.length, this.imagesB.length);
        if (total <= 1) return false;

        if (this._prevBtn && px >= this._prevBtn.x && px < this._prevBtn.x + this._prevBtn.w) {
            this.index = (this.index - 1 + total) % total;
            this._loadImages();
            app.canvas?.setDirty?.(true, true);
            return true;
        }

        if (this._nextBtn && px >= this._nextBtn.x && px < this._nextBtn.x + this._nextBtn.w) {
            this.index = (this.index + 1) % total;
            this._loadImages();
            app.canvas?.setDirty?.(true, true);
            return true;
        }

        return false;
    }
}

// ------------------------------------------------------------------
app.registerExtension({
    name: "LC123.BatchImageComparer",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_TYPE) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onNodeCreated) onNodeCreated.apply(this, arguments);
            if (this.flags) this.flags.pinned = false;
            this.color = "#325A5A";
            this.bgcolor = "#325A5A";
            this.lcComparer = new LCBatchImageComparer(this);
        };
    },
});
