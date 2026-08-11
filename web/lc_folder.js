/**
 * LC Easy / Advanced Folder — default color #325A5A + default sizes
 */
import { app } from "../../scripts/app.js";

const DEFAULTS = {
    LCEasyFolder: { color: "#325A5A", bgcolor: "#325A5A", size: [300, 160] },
    LCAdvancedFolder: { color: "#325A5A", bgcolor: "#325A5A", size: [300, 200] },
};

app.registerExtension({
    name: "LC123.FolderColors",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        const cfg = DEFAULTS[nodeData.name];
        if (!cfg) return;
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            if (onNodeCreated) onNodeCreated.apply(this, arguments);
            this.color = cfg.color;
            this.bgcolor = cfg.bgcolor;
            this.size = cfg.size.slice();
        };
    },
});
