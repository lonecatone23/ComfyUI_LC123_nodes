/**
 * Default node colors for LC123 utility / sampling nodes
 */
import { app } from "../../scripts/app.js";

const COLORS = {
    AspectRatioSimplifier: { color: "#324b4b", bgcolor: "#324b4b" },
    LCAspectRatioPipeOut: { color: "#324b4b", bgcolor: "#324b4b" },
    LCAspectRatioPipe: { color: "#324b4b", bgcolor: "#324b4b" },
    LCSamplerConfigure: { color: "#324b4b", bgcolor: "#324b4b" },
    LCSamplerConfigurePipeOut: { color: "#324b4b", bgcolor: "#324b4b" },
    LCSamplerConfigurePipe: { color: "#324b4b", bgcolor: "#324b4b" },
    LCSplitSigmaScheduler: { color: "#324b4b", bgcolor: "#324b4b" },
    LCBasicScheduler: { color: "#324b4b", bgcolor: "#324b4b" },
    LCSplitSigmasAdvanced: { color: "#324b4b", bgcolor: "#324b4b" },
    LCVRAMCacheClear: { color: "#28281E", bgcolor: "#28281E", size: [270, 30] },
    LCPipeIn: { color: "#324b4b", bgcolor: "#324b4b" },
    LCPipeOut: { color: "#324b4b", bgcolor: "#324b4b" },
    LCPipeEdit: { color: "#324b4b", bgcolor: "#324b4b" },
    LCDetailPipeOut: { color: "#324b4b", bgcolor: "#324b4b" },
    LCDynamicOverlay: { color: "#324b4b", bgcolor: "#324b4b" },
    LCGetImage: { color: "#324b4b", bgcolor: "#324b4b" },
    LCLastImageHolder: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageCrop: { color: "#324B4B", bgcolor: "#324B4B" },
    LCFilmGrain: { color: "#324B4B", bgcolor: "#324B4B" },
    LCApplyLUT: { color: "#324B4B", bgcolor: "#324B4B" },
    LCBloom: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageDenoise: { color: "#324B4B", bgcolor: "#324B4B" },
    LCColorMatch: { color: "#324B4B", bgcolor: "#324B4B" },
    LCLensProfile: { color: "#324B4B", bgcolor: "#324B4B" },
    LCTextOverlay: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageDesaturate: { color: "#324B4B", bgcolor: "#324B4B" },
    LCChromaticAberration: { color: "#324B4B", bgcolor: "#324B4B" },
    LCFilmStockColor: { color: "#324B4B", bgcolor: "#324B4B" },
    LCFilmStockBW: { color: "#324B4B", bgcolor: "#324B4B" },
    LCVignette: { color: "#324B4B", bgcolor: "#324B4B" },
    LCVibrance: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageRGB: { color: "#324B4B", bgcolor: "#324B4B" },
    LCLiftGammaGain: { color: "#324B4B", bgcolor: "#324B4B" },
    LCLensFX: { color: "#324B4B", bgcolor: "#324B4B" },
    LCClarity: { color: "#324B4B", bgcolor: "#324B4B" },
    LCAutoWhiteBalance: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageAdjust: { color: "#324B4B", bgcolor: "#324B4B" },
    LCAnySwitch: { color: "#28281E", bgcolor: "#28281E" },
    LCComboSelector: { color: "#28281E", bgcolor: "#28281E" },
    LCInvertBoolean: { color: "#28281E", bgcolor: "#28281E" },
    LCBoolean: { color: "#28281E", bgcolor: "#28281E" },
    LCIntCompare: { color: "#28281E", bgcolor: "#28281E" },
    LCSeedJump: { color: "#28281E", bgcolor: "#28281E" },
    LCNotify: { color: "#649632", bgcolor: "#649632" },
    LCCivitaiStrip: { color: "#643232", bgcolor: "#643232" },
    LCFloatCompare: { color: "#28281E", bgcolor: "#28281E" },
    LC123SaveText: { color: "#28281E", bgcolor: "#28281E" },
    LCTextReplace: { color: "#28281E", bgcolor: "#28281E" },
    LCTextRemove: { color: "#28281E", bgcolor: "#28281E" },
    LCShowText: { color: "#28281E", bgcolor: "#28281E" },
    LCJoinStrings: { color: "#28281E", bgcolor: "#28281E" },
    LCPromptToConditioning: { color: "#28281E", bgcolor: "#28281E", size: [270, 50] },
    LCPromptToConditioningZero: { color: "#28281E", bgcolor: "#28281E", size: [270, 60] },
    LCSlider: { color: "#28281E", bgcolor: "#28281E" },
    "LC Bypasser": { color: "#28281E", bgcolor: "#28281E" },
    "LC Groups Bypasser": { color: "#28281E", bgcolor: "#28281E" },

};

app.registerExtension({
    name: "LC123.NodeColors",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        const cfg = COLORS[nodeData.name];
        if (!cfg) return;
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onNodeCreated) onNodeCreated.apply(this, arguments);
            this.color = cfg.color;
            this.bgcolor = cfg.bgcolor;
            if (cfg.size) this.size = cfg.size.slice();
        };
    },
});
