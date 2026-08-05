# ComfyUI LC123 Nodes

**Version 1.2.3**

Custom nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) by [lonecatone23](https://github.com/lonecatone23).

- **Repo:** https://github.com/lonecatone23/ComfyUI_LC123_nodes  
- **Support:** [Buy me a ☕](https://ko-fi.com/lonecatone)

For Anima regional attention, also install [Sen-sou Anima Regional Conditioning](https://github.com/Sen-sou/Comfyui-Anima-Regional-Conditioning).

## Nodes

| Node | Features | Notes |
|------|----------|-------|
| **📐 Aspect Ratio Simplifier** | Size from image/mask or CR-style presets; resize image and mask together; crop / stretch / pad / total_pixels; empty latent out | A single node for every resize need. |
| **Anima Regional Inline Canvas** | RGB paint canvas; separate GLOBAL / RED / GREEN / BLUE conditioning and masks for Sen-sou; pause until Apply | Simple and easy to use without a separate mask editor. |
| **Krea2 Regional Inline Canvas** | Same paint UI for Krea2 CLIP; combined positive via Comfy mask/area. **BETA — still a work in progress** | Simple and easy to use without a separate mask editor. |
| **LC Slider** | On-node slider face; min / max / step / decimals in Settings; INT or FLOAT output | Makes it easy to change values. Works in Nodes 2.0. |
| **LC Dynamic Overlay** | Overlay B on A; A sets resolution; B fit-scaled; live circular opacity knob after one queue | Adjust the blend and save the final image without regenerating. |
| **LC Combo Selector** | Wire into a converted combo input; dropdown mirrors that node’s options (scheduler, etc.) | Lets you collapse nodes while still keeping selections available. |
| **LC AnySwitch** | Top-down any-type switch; type-locks from first connection; blocks Use Everywhere auto-wire; 2–20 inputs | Avoids the circular-reference issues common with rgthree Any Switch. |
| **LC Bypasser** | Frontend per-node bypass; optional BOOLEAN enable sockets; 🔒 when driven remotely | Turn multiple nodes on or off with a single boolean. |
| **LC Groups Bypasser** | Frontend per-group bypass; discovers graph groups; optional BOOLEAN per group | Turn multiple groups on or off with a single boolean. |

## License

MIT — see [LICENSE](LICENSE).
