# Agent 使用说明

## 1. 确认输入

确认目标观众、现有文案或获准研究的参考范围、旁白/字幕、引擎选择和仓库外任务目录。缺少会改变结果的关键信息时再补问。真实 Cookies、下载媒体、声音和输出不得进入公开仓库。

## 2. 参考研究（按需）

先读 [参考片方法](references/reference-analysis.md)。

1. `scripts/fetch_reference.py` 获取任务范围内的一个或多个参考样本；
2. `scripts/probe_reference_media.py` 生成媒体信息、接触图和波形；
3. 实际打开原视频，记录构图、人物姿态、道具接力、遮挡、字幕和声音；
4. 只保留方法，不复制来源角色、台词和连续镜头顺序。

## 3. 内容与资产

按[语义与构图](references/method.md)锁定旁白、拆拍并写入 `collage-plan.json`；再按[组件库与补图](references/assets.md)标记图片来源。已有组件或用户提供图先做输入质检；只有确实缺少必要对象时才调用 ImageGen，等输出文件落盘后做出图质检。运行 `scripts/inspect_transparent_assets.py` 时必须传入真实 `--source-kind`，再逐张打开浅底/深底预览。没有生成文件时不得报告 ImageGen 出图质检通过。

## 4. 制作

```bash
python3 scripts/create_project_workspace.py /path/to/task/remotion --engine remotion
python3 scripts/create_project_workspace.py /path/to/task/hyperframes --engine hyperframes
```

把 `collage-plan.json` 作为 Agent 的制作合同，按[双引擎方法](references/engines.md)落实到所选工程。长片、新画风或复杂合成可先做代表段；简单项目可以直接制作。Remotion 按项目 lint/render；HyperFrames 按项目 `AGENTS.md` 执行 check/snapshot/render。

## 5. 真实复审

用 `scripts/extract_visual_review_frames.py` 生成全片、结尾和逐拍页面；`--beats` 优先直接传入含 `internal_events` 的 `collage-plan.json`，让动作发生帧也进入复审页。扫描后对可疑时间增加 `--detail-times`，打开高清单帧检查手脚裁切、透明残边、穿模和无逻辑遮挡。

先定位时间，再判断原因：源 PNG 不完整、容器裁切、动画位移、遮罩或层级错误不是同一类问题。修复后重新渲染对应区间，最后连续播放全片。
