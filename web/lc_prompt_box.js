/**
 * LC Positive / Negative — default node colors
 * Positive: green  #326432
 * Negative: red    #643232
 */

import { app } from "../../scripts/app.js";

const COLORS = {
    LCPositive: { color: "#326432", bgcolor: "#326432" },
    LCNegative: { color: "#643232", bgcolor: "#643232" },
};

app.registerExtension({
    name: "LC123.PromptBoxColors",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        const cfg = COLORS[nodeData.name];
        if (!cfg) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onNodeCreated) onNodeCreated.apply(this, arguments);
            this.color = cfg.color;
            this.bgcolor = cfg.bgcolor;
        };
    },
});
