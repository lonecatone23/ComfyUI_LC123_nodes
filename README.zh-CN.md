# ComfyUI LC123 Nodes — RocketM 分支

[English](README.md) | 简体中文

## 相对上游的改动

| 改动节点 | 改动点 |
| --- | --- |
| LC Save Image 💾 | `Size` 优先记录元数据管线中的原始生成尺寸，仅在缺失时回退到输出尺寸；不另存最终尺寸。保持提示词原样，通过 `Civitai resources` 保存 LoRA 版本与强度，精简的 PNG 记录保留独立模型/CLIP 强度。资源仅沿保存图片的上游收集，利用执行缓存判断 LC/rgthree 开关实际选择的分支；移除 AddNet 和主模型/VAE 的重复别名。 |
| LC Group LoRA Loader Stack 🎚️ | 复用分组、可视化选择和独立权重界面，输出标准 `(名称, 模型强度, CLIP 强度)` 列表，可连接 LC Apply LoRA Stack 等兼容节点。 |
| LC Group LoRA Loader 🎚️ | 新增独立节点，支持分组、拖拽排序、可拉伸批量选择面板、`.civitai.info` 预览和模型/CLIP 独立强度。原加载器和 Stack 保留原有界面与加载行为。 |
| LC LoRA Loader 🎚️ | 将行设置接入强度元数据与 LoRA 哈希收集，遵循逐行开关、强度以及仅连接 MODEL 或 CLIP 的情况。加载器的采样行为不变。 |

启用 `embed_civitai` 时写入元数据，不修改采样提示词或图片尺寸。LC LoRA Loader 🎚️ 与 LC Group LoRA Loader 🎚️ 均使用专门适配，其他加载器统一按输入字段识别。LC LoRA Stack / LC Group LoRA Loader Stack / LC Apply LoRA Stack 尚未接入强度元数据收集。图关联不代表实际执行，因此结构化记录标记为 `execution_verified: false`。

早期 feature 版本保存的 LC LoRA Loader 若包含 `lc_lora_groups`，打开工作流时会迁移到 LC Group LoRA Loader；普通原版工作流不变。

## 安装

在 `ComfyUI/custom_nodes` 内执行：

```sh
git clone --branch main https://github.com/RocketM/ComfyUI_LC123_nodes.git
```

只保留一份 LC123 插件，安装后重启 ComfyUI 并刷新浏览器。

## 上游节点说明

节点用法、图片与示例请参阅[上游 README](https://github.com/lonecatone23/ComfyUI_LC123_nodes#readme)。原始节点及资源由 [lonecatone23](https://github.com/lonecatone23) 提供，本 fork 沿用原项目[许可证](LICENSE)。
