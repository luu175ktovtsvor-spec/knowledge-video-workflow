# 二维拼贴知识动画 Remotion 母版

先运行：

~~~bash
python3 /path/to/knowledge-video-workflow/scripts/create_project_workspace.py /absolute/project/remotion --engine remotion
cd /absolute/project/remotion
npm ci
~~~

新工程会在 `public/media/house-components/` 中得到固定风格的 260 个单件组件、关系群像和项目内组合锚点索引。

母版提供黑红标题卡、scene 环境舞台、diagram 图解舞台、透明 PNG 角色、证据/手机/流程面板、姿态替换、道具接触和白字黑描边字幕。它是视觉语法样例，不是可直接改标题交付的成片。

使用时：

1. 先从 `public/media/house-components/` 选择适合当前语义的背景、角色姿态、关系群像、场景模块和道具；
2. 从项目 collage-plan.json 驱动真实旁白节拍；
3. 按需使用 SceneBackdrop/DiagramStage、SpriteLayer/PoseSwap、EvidencePanel、TypewriterCard、OutlinedSubtitle 等母版机制；
4. `SpriteLayer` 和 `PoseSwap` 已使用固定宽高安全框与 `object-fit: contain`；调整坐标、尺寸和入场路径时仍需确保完整外接矩形不越界、不进入字幕区；
5. 长片、新画风或复杂合成可先完成代表段并真实看片，再渲染全片；
6. 不把原作者 IP、媒体或临时生成文件带入项目。

npm run render:starter 只验证母版渲染。

首次 `npm ci` 需要联网；Remotion 第一次渲染还会自动下载约 94MB 的 Headless Chrome。下载位置由 Remotion 管理，不应把浏览器缓存提交回 Skill 仓库。
