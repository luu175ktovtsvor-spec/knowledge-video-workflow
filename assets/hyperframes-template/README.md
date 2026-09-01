# HyperFrames 母版

```bash
npm ci
npm run check
npm run render
```

用当前项目的旁白节拍替换示例场景，并从复制到工程内的 `assets/house-components/` 选择组件。时间线写法以项目 `AGENTS.md` 为准。

全身人物和独立道具使用固定宽高安全框与 `object-fit: contain`，不要只设置宽度后让自然高度越过画布或字幕区。

首次 `npm ci` 和默认示例渲染需要联网：依赖从 npm 安装，示例中的 GSAP 从 jsDelivr 加载。需要离线制作时，应把经过许可的 GSAP 文件放入项目并改成本地引用。
