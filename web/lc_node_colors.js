/**
 * Default node colors for LC123 utility / sampling nodes
 */
import { app } from "../../scripts/app.js";

const COLORS = {
    // NOTE: LCAspectRatioPipe, LCSamplerConfigure(+PipeOut/Pipe), LCPipeOut,
    // LCPipeEdit, LCDetailPipeOut are NOT listed here — they're painted #707070
    // by lc_pipe_sampler_chrome.js, which is the single source of truth for the
    // pipe/sampler-configure family. Do not re-add them here; a stale duplicate
    // entry here previously conflicted with that file's color (both fired, one
    // silently overrode the other depending on load order).
    AspectRatioSimplifier: { color: "#324b4b", bgcolor: "#324b4b" },
    LCAspectRatioPipeOut: { color: "#324b4b", bgcolor: "#324b4b" },
    LCSplitSigmaScheduler: { color: "#324b4b", bgcolor: "#324b4b" },
    LCBasicScheduler: { color: "#324b4b", bgcolor: "#324b4b" },
    LCSamplerScheduler: { color: "#324b4b", bgcolor: "#324b4b" },
    LCSplitSigmasAdvanced: { color: "#324b4b", bgcolor: "#324b4b" },
    LCChangeStepCount: { color: "#1c6d6d", bgcolor: "#1c6d6d" },
    LCSigmaResample: { color: "#1c6d6d", bgcolor: "#1c6d6d" },
    LCSigmaCurve: { color: "#1c6d6d", bgcolor: "#1c6d6d" },
    LCSpeedBoost: { color: "#7d1919", bgcolor: "#7d1919" },
    LCSpeedBoostKSampler: { color: "#7d1919", bgcolor: "#7d1919" },
    LCVRAMCacheClear: { color: "#28281E", bgcolor: "#28281E", size: [270, 30] },
    // LCPipeIn is now painted #707070 by lc_pipe_sampler_chrome.js, same as
    // LCPipeOut/LCPipeEdit — do not re-add an entry for it here.
    LCDynamicOverlay: { color: "#324b4b", bgcolor: "#324b4b" },
    LCGetImage: { color: "#324b4b", bgcolor: "#324b4b" },
    LCSkinBeauty: { color: "#324B4B", bgcolor: "#324B4B" },
    LCSkinUpscale: { color: "#324B4B", bgcolor: "#324B4B" },
    LCSkinTexture: { color: "#324B4B", bgcolor: "#324B4B" },
    LCSkinMaster: { color: "#324B4B", bgcolor: "#324B4B" },
    LCDimensionResize: { color: "#324B4B", bgcolor: "#324B4B", size: [270, 110] },
    LCLastImageHolder: { color: "#324B4B", bgcolor: "#324B4B" },
    LCBatchImage: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageStitchMulti: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageBatchFromFolder: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageCrop: { color: "#324B4B", bgcolor: "#324B4B" },
    LCFilmGrain: { color: "#324B4B", bgcolor: "#324B4B" },
    LCFilmGrainVideo: { color: "#324B4B", bgcolor: "#324B4B" },
    LCRTXSuperResolution: { color: "#324B4B", bgcolor: "#324B4B" },
    LCSizePad: { color: "#324b4b", bgcolor: "#324b4b" },
    LCBoundingBoxes: { color: "#324B4B", bgcolor: "#324B4B" },
    LCFlux3LayoutPrompt: { color: "#28281E", bgcolor: "#28281E" },
    LCMOSSLayoutPrompt: { color: "#143c14", bgcolor: "#143c14" },
    LCFlux3ReferenceLatent: { color: "#1C6D6D", bgcolor: "#1C6D6D" },
    LCApplyLUT: { color: "#324B4B", bgcolor: "#324B4B" },
    LCBloom: { color: "#324B4B", bgcolor: "#324B4B" },
    LCDepthFX: { color: "#324B4B", bgcolor: "#324B4B" },
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
    LCNaturalLook: { color: "#324B4B", bgcolor: "#324B4B" },
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
    LCAnyEmptyBool: { color: "#28281E", bgcolor: "#28281E" },
    LCAnyEmptyInt: { color: "#28281E", bgcolor: "#28281E" },
    LCAnyEmptyFloat: { color: "#28281E", bgcolor: "#28281E" },
    LCIntSplit: { color: "#28281E", bgcolor: "#28281E" },
    LCSeedJump: { color: "#28281E", bgcolor: "#28281E" },
    LCNotify: { color: "#649632", bgcolor: "#649632" },
    LCCivitaiStrip: { color: "#643232", bgcolor: "#643232" },
    LCFloatCompare: { color: "#28281E", bgcolor: "#28281E" },
    LCSaveImage: { color: "#28281E", bgcolor: "#28281E" },
    LCSaveImageMetadata: { color: "#28281E", bgcolor: "#28281E" },
    LC123SaveText: { color: "#28281E", bgcolor: "#28281E" },
    LCTextReplace: { color: "#28281E", bgcolor: "#28281E" },
    LCDuplicateTags: { color: "#28281E", bgcolor: "#28281E" },
    LCTextRemove: { color: "#28281E", bgcolor: "#28281E" },
    LCShowText: { color: "#28281E", bgcolor: "#28281E" },
    LCShowAny: { color: "#28281E", bgcolor: "#28281E" },
    LCWidgetToString: { color: "#324B4B", bgcolor: "#324B4B" },
    LCJoinStrings: { color: "#28281E", bgcolor: "#28281E" },
    LCPromptToConditioning: { color: "#28281E", bgcolor: "#28281E", size: [270, 50] },
    LCPromptToConditioningZero: { color: "#28281E", bgcolor: "#28281E", size: [270, 60] },
    LCWeightedPrompt: { color: "#232", bgcolor: "#353" },
    LCAnimaBoxPrompt: { color: "#232", bgcolor: "#353" },
    LCSlider: { color: "#28281E", bgcolor: "#28281E" },
    LCLight: { color: "#000000", bgcolor: "#000000" },
    LCTimer: { color: "#000000", bgcolor: "#000000" },
    "LC Bypasser": { color: "#28281E", bgcolor: "#28281E" },
    "LC Mute": { color: "#28281E", bgcolor: "#28281E" },
    "LC Groups Bypasser": { color: "#28281E", bgcolor: "#28281E" },
    "LC Bypasser Panel": { color: "#28281E", bgcolor: "#28281E" },
    LCBypassRelay: { color: "#28281E", bgcolor: "#28281E" },
    "LC Bypass Relay": { color: "#28281E", bgcolor: "#28281E" },
    LCImagePass: { color: "#28281E", bgcolor: "#28281E" },
    LCMaskPass: { color: "#28281E", bgcolor: "#28281E" },

    // --- Gap-fill pass: nodes with no prior color source anywhere ---
    // Utility (#28281E)
    LCBooleanFlip: { color: "#28281E", bgcolor: "#28281E" },
    LCBooleanSwitch: { color: "#28281E", bgcolor: "#28281E" },
    LCBooleanValue: { color: "#28281E", bgcolor: "#28281E" },
    LCCustomCombo: { color: "#28281E", bgcolor: "#28281E" },
    LCCustomComboPanel: { color: "#28281E", bgcolor: "#28281E" },
    LCIndexSwitch: { color: "#28281E", bgcolor: "#28281E" },
    LCNodeSnapshot: { color: "#28281E", bgcolor: "#28281E" },
    LCSeed: { color: "#822305", bgcolor: "#822305" },

    // Image / catch-all (#324B4B)
    LCBatchImageComparer: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageGrid: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageMaskResize: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageToTotalMegapixels: { color: "#324B4B", bgcolor: "#324B4B" },
    LCImageSplit: { color: "#324B4B", bgcolor: "#324B4B" },
    LCPhoneLook: { color: "#324B4B", bgcolor: "#324B4B" },
    LCRelight: { color: "#324B4B", bgcolor: "#324B4B" },
    LCLightingControlV2: { color: "#324B4B", bgcolor: "#324B4B" },
    LCToneMatch: { color: "#324B4B", bgcolor: "#324B4B" },
    LCWatermark: { color: "#324B4B", bgcolor: "#324B4B" },
    AnimaRegionalCanvasInline: { color: "#324B4B", bgcolor: "#324B4B" },
    Krea2RegionalCanvasInline: { color: "#324B4B", bgcolor: "#324B4B" },

    // Sampler-related (#1C6D6D)
    LCDenoise: { color: "#1C6D6D", bgcolor: "#1C6D6D" },

    // Exceptions — dedicated colors, not part of the base palette
    LCStop: { color: "#963232", bgcolor: "#963232" },
    LCPositive: { color: "#326432", bgcolor: "#326432" },
    LCNegative: { color: "#643232", bgcolor: "#643232" },
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
