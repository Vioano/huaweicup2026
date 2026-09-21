# ELK → Draw.io

从项目根目录执行，需 Node.js 22+；首次安装排版依赖：

```sh
npm ci --ignore-scripts --prefix .agents/skills/scientific-figures
node .agents/skills/scientific-figures/scripts/drawio.mjs .agents/skills/scientific-figures/examples/modeling-workflow.json figures/workflow/modeling-workflow.drawio
```

将示例 JSON 复制到 `src/figures/<name>.json` 再按实际任务编辑。示例是工作流程，不含真实赛题结论。命令输出 `.drawio`、`.layout.json` 与 `.qa.json`；已有任一输出时退出，换一个版本文件名，勿覆盖队友的编辑。

JSON 字段：

- `title`：Draw.io 页面名称，图注仍由论文提供。
- `direction`：`RIGHT`（默认）、`DOWN`、`LEFT`、`UP`。
- `nodes`：每项含唯一 `id`、`label`，可选 `role`（`data`、`model`、`check`、`output`）、`width`、`height`。标签用 `\n` 显式分行；尺寸按保守字宽估算，过小尺寸会报错。
- `edges`：每项含唯一 `id`、`source`、`target`。端点必须存在，连线 id 不能与节点重复。未支持字段会报错，避免静默丢失内容。

当前范围是单层有向图和矩形节点，不接收嵌套泳道、图标、边标签、超边或自动 LaTeX 排版。复杂图保留语义后拆图，或直接使用 Draw.io 原生容器/公式能力；不要强行删掉信息来适应脚本。自动布局不保证消除所有边交叉。

工具沿用旧原型的 ELK layered + orthogonal 路由，去掉客户节点与固定版面。页面随内容扩展，避免为了塞进固定画布而缩小文字。导出仍需检查纸面字号；长流程可换方向或拆图。XML 用 `source` / `target` 绑定节点和可编辑折线控制点。

## 原生导出

先检查 `drawio --help`，按实际 CLI 支持的选项运行。若不在 PATH，可传本机应用内的可执行文件路径；不把个人绝对路径写进仓库。

```sh
drawio -x -f png -s 2 -b 16 -o figures/workflow/modeling-workflow.png figures/workflow/modeling-workflow.drawio
drawio -x -f pdf --crop -b 16 -o figures/workflow/modeling-workflow.pdf figures/workflow/modeling-workflow.drawio
drawio -x -f svg -e -o figures/workflow/modeling-workflow.svg figures/workflow/modeling-workflow.drawio
```

保留 `.drawio`，即便 SVG 已嵌入源 XML。没有 Desktop 时仍能生成并交付 `.drawio`；说明预览尚未导出，不将几何报告标成视觉通过。中文显示依赖本机字体回退。导出不调用在线图像服务。

`.qa.json` 的 `visualReview` 默认为 `pending`，人工或 Agent 查看 PNG / PDF 后，在任务卡记下实际检查内容与缺陷；不要靠修改一个状态字段冒充验收。

当前本机 Draw.io 30.0.2 的帮助未提供 `--layout`。虽然上游最新官方 Skill 已介绍该参数，这里使用独立锁定的 `elkjs` 排版，不假定队友已安装支持它的 Desktop 版本。

测试：`npm test --prefix .agents/skills/scientific-figures`，XML 回读测试另需 PATH 中的 `python3`（可用 `uv run npm test --prefix ...`）。
