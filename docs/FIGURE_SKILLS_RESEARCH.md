# 科研绘图 Skill 与 Astra 适配调研

核查日期：2026-09-22。本次只接入用户指定的本地排版原型，形成 `scientific-figures`；下表 GitHub 候选均未安装。依据为实际 SKILL.md / 依赖目录、GitHub API、skills.sh 搜索和本机 CLI，不以星数或搜索摘要代替内容审查。

## 原来的排版能力在哪里

| 位置 | 实际内容 | 本次处理 |
| --- | --- | --- |
| 用户级 `~/.codex/skills/visual-diagram-qa/` | 通用图件检查规范；未包含 ELK / Draw.io 排版执行脚本 | 参考可编辑性、文字与拓扑检查，不修改用户级文件 |
| “精算云画图”项目 `.agents/skills/diagram-recreation-qa/` | 客户图件复刻与视觉 QA 规范 | 参考检查要点，不原样复制客户验收门槛 |
| 同项目 `引擎测试/compute-layout.mjs` | ELK layered 泳道内布局，固定客户节点尺寸和泳道框；跨泳道使用规则路由 | 抽取图结构 → ELK → 布局结果的方式 |
| 同项目 `引擎测试/drawio-pic2/generate-drawio.mjs` | ELK 配合大量特定模块布局，生成 Draw.io XML | 抽取导出方式，改成通用节点、真实端点绑定和显式输入 |

这次查到的可执行引擎在项目里，用户级主要已有检查规范。源项目存在未提交内容，且 `引擎测试/` 未纳入它的 Git；不能把源仓库 HEAD 当成原型版本。本次按读取文件的 SHA-256 留下[来源快照记录](scientific-figures-source.json)，没有把客户图、文字和未提交产物带入团队仓库。

新入口：[scientific-figures](../.agents/skills/scientific-figures/SKILL.md)。依赖固定为 `elkjs 0.10.0`，并提交 npm lock。它支持单层有向图、中文节点、自动扩展页面、正交连线和重叠/穿框检查；不声称已迁移客户专用泳道、图标或复杂公式处理。布局算法选项参照 [ELK 官方文档](https://eclipse.dev/elk/reference/options/org-eclipse-elk-layered-nodePlacement-bk-fixedAlignment.html)。

## GPT-6 Astra：官方建议与本项目决策

官方强调 Astra 对 Skill / AGENTS 指令更敏感，建议审查冲突、模糊的停顿条件；明确授权后的持续执行、适度测试和按需委派。我们据此把旧版泛化的询问门槛、循环自评分改成具体产物检查，并保留语义不明时的澄清。[OpenAI 模型指南](https://developers.openai.com/api/docs/guides/latest-model)

Astra 支持文本输出与图像输入，并可调用代码执行、图像生成等工具。它可以编写绘图程序或 SVG/XML；位图生成属于工具能力。官方页没有给出科研图表准确率或任意复杂布局的保证。因而模型负责内容和代码、绘图库负责数值渲染、ELK 负责布局，最后检查实际导出物，是本项目的工程选择。[OpenAI Astra 模型页](https://developers.openai.com/api/docs/models/gpt-6-astra)

旧原型没有模型调用，未发现需要修改的 GPT-5.5 API 配置。本次是工作流程与可移植性适配，不改用户的模型设置，也不新建付费 API 调用。将来若独立接入 Astra API，再按官方迁移指南核对 Responses 工具调用、reasoning 和不支持的采样参数；当前无需增加这些配置。

Skill 的价值在于保存本队约定：`results/` 中的结果表、单位与不确定性、论文宽度、配色含义、可编辑源文件、输入哈希及真实验收范围。它不能增加新的观测数据，也不能保证论文结论正确。

## GitHub 候选

安装数为 skills.sh 本次显示的近似累计值；星数属于整个仓库，不能当作单个 Skill 的使用量或质量分数。

| 候选及源文件 | 适合什么 | 本次热度 | 依赖、局限与建议 |
| --- | --- | --- | --- |
| [K-Dense scientific-visualization](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-visualization/SKILL.md) | Python 论文多面板、误差表达、色彩审查、导出及来源记录 | 约 1.9K 安装；仓库 45,929 星 | MIT；有离线检查与导出脚本，Python 3.11+。Plotly 静态导出另需 Kaleido / 浏览器。与本队任务最贴合，优先候选 |
| [K-Dense matplotlib](https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/matplotlib/SKILL.md) | 细调坐标轴、子图、图例、2D / 3D 和矢量输出 | 约 1.8K 安装；同上仓库 | 与上一项有重叠；项目已有 Matplotlib，不应因 Skill 再执行泛化的环境升级。更适合作为按需参考 |
| [jgraph 官方 drawio](https://github.com/jgraph/drawio-mcp/blob/main/plugins/codex/drawio/skills/drawio/SKILL.md) | Mermaid / XML → 可编辑图、Desktop 导出，包含 ELK 布局说明 | 约 3K 安装；5,484 星 | Apache-2.0；优先的格式参考。先探测 CLI 版本；本机 30.0.2 未列出 `--layout`。其导出后删除中间源文件的约定不适合本项目，需保留 JSON / `.drawio` |
| [Draw.io Academic Overlay](https://github.com/bahayonghang/drawio-skills/blob/main/skills/drawio-academic-skills/SKILL.md) | 论文路线图、架构图、公式、黑白印刷与样式 | 约 873 安装；284 星；同仓库基础 drawio 约 8K 安装 | MIT；必须同时有同级 `drawio` 基础 Skill。存在配色问答、计划审批及特定字体规则，安装前需对齐本队授权和字体环境。值得试验，暂不替代本地轻量引擎 |
| [MathWorks matlab-build-chart](https://github.com/matlab/matlab-agentic-toolkit/blob/main/skills-catalog/matlab-app-building/matlab-build-chart/SKILL.md) | MATLAB 科研曲线、表面/场图、tiledlayout、多轴、标注及 exportgraphics | 42 安装；1,085 星 | MathWorks 来源，使用其 PMRL 许可；需要 MATLAB，部分新图型取决于版本。提供专门参考目录。多面板会触发原 Skill 的计划确认，应对齐用户已有授权。MATLAB 用户首选候选 |
| [Wolfram Research wolfram-language](https://github.com/WolframResearch/AgentTools/blob/main/AgentSkills/Skills/wolfram-language/SKILL.md) | 符号计算、函数/区域可视化、代码执行与结果核验 | 9 安装；90 星 | MIT；含 `.wls` 脚本和参考文件，需要可用的 Wolfram Engine / Mathematica 或相应 MCP。官方但仍低采用量，适合有 Wolfram 模型时试用；它是计算工具 Skill，不是排版模板库 |
| [Mindrally julia](https://github.com/mindrally/skills/blob/main/julia/SKILL.md) | Julia 开发约定和性能基础 | 652 安装；260 星 | Apache-2.0；实际内容是通用编程规范，没有 Makie 论文图模板或导出验证。科研绘图针对性不足，不建议为画图优先安装 |

**Julia 的实际建议**：需要 Julia 时优先使用 [Makie / CairoMakie 官方文档](https://docs.makie.org/stable/explanations/backends/cairomakie)，支持 SVG/PDF 等矢量输出，再让本项目 Skill 约束结果来源与交付。Makie 是绘图库，不是本次发现的 Skill。本次搜索未找到能充分验证、且比这条路线更合适的专门 Julia 科研绘图 Skill；这不代表生态中不存在。

**Wolfram 的补充**：同一 [AgentTools](https://github.com/WolframResearch/AgentTools/tree/main/AgentSkills/Skills) 还包含 `wolfram-notebooks` 及读写脚本，可用于 Notebook 交付；不要只复制 SKILL.md 而漏掉配套脚本。另一个 [WolframResearch/skills](https://github.com/WolframResearch/skills) 当前主要是 setup 和天文规划，不能笼统当成通用科研绘图包。

另查到 [MathModelAgent](https://github.com/jihe520/MathModelAgent) 的 `4drawio` / `mathmodel-figure-templates`（仓库 5,859 星），但本次没有完成这些 Skill 的内容与许可核验，不列为已审查推荐。

## 本次验证与复现

- `npm test --prefix .agents/skills/scientific-figures`：布局重复性、XML 回读与端点绑定、坏输入、文字尺寸、几何缺陷及文件覆盖保护。
- 用实际 Draw.io 30.0.2 导出随附 6 节点 / 6 连线示例的 PNG 与 PDF，检查中文、连线方向及遮挡。
- 本机发现 MATLAB R2026a 和 `wolframscript` 可执行入口，没有为本任务启动它们验证许可证或绘图；PATH 中未找到 Julia。
- GitHub 候选只做文档与目录检查，未逐个安装或运行。Astra 未做与 GPT-5.5 的控制变量性能对照，不能宣称本次迁移使绘图质量提升了某个百分比。

具体安装命令仅供以后确认选型使用，**本次未执行**：

```sh
npx skills add K-Dense-AI/scientific-agent-skills --skill scientific-visualization
npx skills add jgraph/drawio-mcp --skill drawio
npx skills add matlab/matlab-agentic-toolkit --skill matlab-build-chart
npx skills add WolframResearch/AgentTools --skill wolfram-language
```

后续安装仍需固定所选版本、检查完整依赖及本项目约定。当前推荐先用本项目 `scientific-figures`，Python 扩展优先评估 K-Dense；具体任务采用 MATLAB 或 Wolfram 时，再选择对应官方 Skill。
