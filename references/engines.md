# Remotion 与 HyperFrames

两条引擎共享同一份文案、旁白时间、`collage-plan.json` 和资产目录。计划是给 Agent 读取和实现的制作合同，不是自动把 JSON 编译成成片的运行时。

- **Remotion**：React/TypeScript、`useCurrentFrame`、`interpolate`、`spring`；适合类型安全组件、复杂数据驱动和 React 生态。
- **HyperFrames**：HTML/CSS、`data-start/data-duration`、暂停的 GSAP timeline；适合 Agent 直接编辑和无 React 构建的确定性渲染。

已有 React 组件或大量数据模板优先 Remotion；网页式布局或 GSAP 团队优先 HyperFrames。用户要比较时，Agent 用同一计划分别实现两版，不同时修改文案、声音和资产。

实现顺序：

1. 把计划中的背景、角色、群像、模块和道具路径映射到工程资产；
2. 把每拍的起点、动作、结果和层级写进所选引擎；
3. 接入同一旁白和字幕时间；
4. 渲染代表内容并看片；
5. 扩展全片后执行同一套人工复审。

两者都不负责生成素材；ImageGen 按需补图，FFmpeg 负责探测、编码和抽帧。

两种引擎使用同一条前景安全规则：全身人物和独立道具先进入固定宽高容器，图片在容器内使用 `object-fit: contain` 和底部对齐。容器、入场位移、移动终点和缩放后的完整外接矩形都要避开画布边界与字幕区；只有计划明确记录 `crop_intent` 时才允许裁切。

Remotion 依赖由工程内的 `package-lock.json` 固定。HyperFrames 依赖同样通过 `npm ci` 安装；默认示例还从 jsDelivr 加载 GSAP，因此首次安装和默认示例渲染需要联网。需要离线制作时，先把经过许可的 GSAP 文件放入任务工程并改成本地引用。
