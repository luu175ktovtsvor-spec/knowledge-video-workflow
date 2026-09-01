---
name: collage-knowledge-video-workflow
description: "Create 16:9 2D collage knowledge videos from a script or permitted reference samples, using semantic visual beats, reusable transparent assets, optional ImageGen additions, Remotion or HyperFrames, and real video review. Use for illustrated knowledge explainers rather than talking heads or fictional drama."
---

# 二维拼贴知识视频完整工作流

本 Skill 定义从参考研究到成片交付的流程，不绑定某篇文案。真实链接、Cookies、下载媒体、声音和结果留在仓库外任务工作区。

## 执行顺序

1. 确认观众问题、参考范围、画幅和现有文案状态。
2. 需要参考研究时，按[参考片与拉片](references/reference-analysis.md)获取任务范围内的样本，探测并真实看片；只提炼方法，不复制来源内容。
3. 锁定文案、旁白和字幕时间，再按[语义与构图](references/method.md)拆成由语义变化和可见动作决定的信息拍。
4. 每拍写 `start_state → visible_action → end_state`，按[组件库与补图](references/assets.md)先检查已有组件或用户提供图片；源文件存在时做输入质检。只有缺少必要对象时才调用 Codex 内置 ImageGen，等生成文件真实落盘后再做出图质检。无论来源，透明 PNG 通过源图检查后才能进入组件库和时间线。
5. 按[双引擎制作](references/engines.md)选择 Remotion 或 HyperFrames；用户要求对照时共用同一计划分别制作。
6. 长片、新画风或复杂合成可先做代表段；简单项目可以直接制作。
7. 渲染后按[人工复审](references/review.md)先扫全片、结尾和逐拍页，再检查动作事件帧和可疑时间的高清单帧，最后连续播放成片。修复具体时间点后再交付。

## 核心方法

- 章节不是镜头；旁白换意时，主体、姿态、关系、道具、景别或状态至少改变一项。
- 图像只为建立、接触、替换、组建和退场而运动，不统一漂浮。
- 组件库是起始词汇，不是万能图库；缺少因果链必要对象才补图。
- 文字、数字、表格、流程和路径由代码生成，不烤进图片。
- 先记录图片来源再判断责任：已有组件或用户提供图残缺是输入资产问题；ImageGen 输出残缺是生成结果问题；源图完整但成片被切是构图实现问题。没有生成文件时不能声称完成了 ImageGen 出图质检。
- 自动检查只能标出透明通道和贴边风险；人物是否缺头、缺手、缺脚，道具是否残缺，必须在真实存在的源图预览中人工确认。
- 全身人物和独立道具进入引擎后必须放进固定宽高安全框，并使用 `object-fit: contain`；安全框、入场位移和移动终点都不能越出画布或进入字幕区。
- 不用测试数量、规则命中数或脚本状态评价画面质量。自动检查保持最小，最终结论来自实际打开源图、渲染抽帧和连续看片。
- 每拍只有一个主焦点；层级用大小、位置、对比和留白建立，不靠一味提高 `z-index`。遮挡必须有真实的前后或接触关系，不能遮脸、主动手势、道具接触点或结果。
- 这类二维图层运动通常可由 Remotion 或 HyperFrames 完成；是否使用其他生成工具由任务需要和用户选择决定。
- 不强制使用 TTS；用户已提供可用旁白时直接把该音频作为节目时钟。用户提供的 SRT 默认只用于断句和时间，不直接烧录。
- 工程检查只能发现缺文件、时间线或编码错误；裁切、残边、穿模、主次和遮挡必须通过实际帧和连续看片判断。

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/collage-knowledge-video-workflow"
python3 "$SKILL_DIR/scripts/create_project_workspace.py" /path/to/task/remotion --engine remotion
python3 "$SKILL_DIR/scripts/create_project_workspace.py" /path/to/task/hyperframes --engine hyperframes
```
