# 组件库使用说明

这里是随 Skill 一起下载的正式组件库，共 260 个可组合元素。它们是人物、道具和场景零件，不是可以直接替换文字交付的完整镜头。

| 分类 | 数量 | 内容 | 目录 |
|---|---:|---|---|
| 背景 | 15 | 办公、门店、教室、医疗、仓储等横版空间 | [backgrounds](backgrounds) |
| 角色姿态 | 73 | 海狸、水獭、豚鼠和猫头鹰的独立动作 | [characters](characters) |
| 关系群像 | 22 | 对话、协作、交接、排队和团队组合 | [groups](groups) |
| 场景模块 | 42 | 柜台、货架、白板、桌椅、设备和建筑 | [modules](modules) |
| 道具 | 108 | 办公、分析、支付、生活、传播和服务道具 | [props](props) |

`catalog.json` 是给 Agent 和脚本读取的完整索引。每条记录包含：

- 组件 ID、分类和文件路径；
- 图片宽高、透明通道要求和 SHA-256；
- 标签、朝向、建议层级；
- 透明前景的可见边界、中心、顶部和脚底基线锚点。

如本机安装了 `jq`，可以按标签查找：

```bash
jq '.entries[] | select(.kind == "characters" and (.tags | index("explain"))) | {id,path,width,height}' \
  assets/component-library/catalog.json
```

创建工程时，`scripts/create_project_workspace.py` 会自动复制完整组件库：

- Remotion：`public/media/house-components/`
- HyperFrames：`assets/house-components/`

## 使用边界

- 先按旁白中的主体、动作对象和结果选择组件，不按关键词堆装饰。
- 全身人物和独立道具必须放进固定宽高安全框，使用 `object-fit: contain`，并避开字幕区。
- 新图片进入工程前，先运行 `scripts/inspect_transparent_assets.py`，再实际打开浅底和深底预览检查完整身体、道具轮廓、透明残边和多余对象。
- `ok` 只代表程序没有发现透明通道或贴边问题，不代表人物一定没有缺头、缺手或缺脚。

## 清晰度

当前组件库以 1920×1080 成片为主要目标。每张图片的实际尺寸写在 `catalog.json`；部分前景组件和背景不是原生 4K。直接把工程导出为 4K 只会放大这些位图，不会增加真实细节。制作原生 4K 成片时，应替换为足够分辨率的背景和关键前景，再按 4K 画布重新排版。

除非文件另有说明，这些组件与仓库其余内容一起按根目录 [MIT License](../../LICENSE) 使用。
