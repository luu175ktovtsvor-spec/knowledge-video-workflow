# HyperFrames 项目说明

1. 先读根目录 `collage-plan.json`，按批准旁白拆场景。
2. 组件位于 `assets/house-components/`；缺必要资产时在任务工程补图，不改公开母版。
3. 每个 timed element 使用 `data-start`、`data-duration` 和 `class="clip"`。
4. 所有 GSAP timeline 必须 `{paused:true}` 并注册到 `window.__timelines`。
5. 禁止 `Date.now()`、未设种子的随机数、异步建 timeline 和无限 repeat。
6. 修改后运行 `npm run check`，实际 snapshot/preview 后再 `npm run render`。
7. 全身人物和独立道具必须放进固定宽高安全框，图片使用 `object-fit: contain`；安全框、入场位移和移动终点都不能进入字幕区或越出画布。
