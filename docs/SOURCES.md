# 来源与版本

初始核对日期：2026-09-19；Skill 更新核对：2026-09-22。

## 结构与工作方法

用户指定的本地教学演示 `华为杯/教学演示/index.html`：

- 第 6 屏：`pyproject.toml`、`uv.lock`、`src/demo.py`，data/src/results/figures/paper 五个主目录，以及相对路径原则。
- 第 7–8 屏：功能分支、三人任务协作、代码/图表/论文共同验收。
- 手册第 2 节：2025 社区 LaTeX 模板、XeLaTeX、完整保留类文件与配图。
- 手册第 4–5 节：GitHub 私有仓库、PR 协作、六字段任务卡。

教学演示仅作建仓依据，不复制其全部课件、赛题或论文。

## Team Mailbox

- 上游：<https://github.com/NikolaStarx/team-mailbox>
- 固定提交：`77581d464fa8d1b0d2182c31bee4fb0a8e03c83a`
- 上游路径：`skills/team-mailbox/`
- 本地路径：`.agents/skills/team-mailbox/`
- 完整保留 SKILL.md、references、脚本、tests、agents 和 MIT LICENSE。
- 更新应先核对上游变更，备份旧版，再明确替换；不在后台自动追随 main。

## System Atlas

- 引入日期：2026-09-21（0.4.0）；2026-09-22 按用户要求更新为 0.5.0，本地源码和 GitHub 主分支核对一致。
- 上游：<https://github.com/NikolaStarx/system-atlas>
- 固定提交：`fc258c92d12d36bc9fbbabe0713056958b6cc7e2`（共享任务看板与 Agent 任务操作协议）。
- 上游仓库根目录就是 Skill；完整安装至 `.agents/skills/system-atlas/`，没有嵌套 `.git`。
- 243 个上游文件逐一核对，内容保持一致；文件 SHA-256 清单在 [system-atlas-install.json](system-atlas-install.json)。
- 保留 MIT LICENSE 及 Archify 2.16 归属说明。没有复制开发机的 node_modules、私钥或私有运行状态。
- 0.5.0 版本号来自该固定提交的 SKILL.md、package.json 和 skill-release.json；不以未核对的 Release 标签替代固定提交。

## LaTeX 训练模板

- 来源：教学演示的 `materials/2025LaTeX模板_课堂副本.zip`。
- 社区上游：<https://github.com/zhanwen/MathModel/tree/master/2025年数模悉知%26论文模版>
- 本项目解压至 `paper/template-2025/`，保持归档内文件内容不变。
- 含 `MathModel.tex`、`gmcmthesis.cls`、`figures/`、`test.jpg`、`MathModel.pdf`、`READ_ME_FIRST.txt`。
- `MathModel.pdf` 是上游附带的旧示例，并非本项目编译成果；来源清单与归档哈希见 `paper/template-source.json`。
- 这是 2025 社区训练材料，非 2026 官方格式认证；正式使用时需核对当届要求与上游授权。

## Scientific Figures

- 引入日期：2026-09-22；用户要求迁入“精算云画图”中的排版原型并对齐 Astra 和本项目。
- 本地原型、用户级 QA 与项目级 QA 的位置和适配取舍见 [绘图调研](FIGURE_SKILLS_RESEARCH.md)；逐文件读取哈希见 [来源快照](scientific-figures-source.json)。原型没有已提交版本，未以源仓库 HEAD 冒充它的版本。
- 项目实现位于 `.agents/skills/scientific-figures/`，独立锁定 [elkjs](https://github.com/kieler/elkjs) 0.10.0（EPL-2.0），通过 npm 获取；未把第三方库源码复制进仓库。
- 只迁移可复用逻辑和检查方式，不带入客户图件。示例是本项目工作流程示意，不是原图复刻或赛题实验结果。
- figures4papers 现已按用户指定安装，其他 GitHub 科研绘图候选仍仅做调研。

## figures4papers / scientific-figure-making

- 引入日期：2026-09-22；上游 [ChenLiu-1996/figures4papers](https://github.com/ChenLiu-1996/figures4papers)。
- 固定提交：`3c181f85e82c6f24948fcaaf3be6696102b41d8d`；上游目录 `scientific-figure-making/` 的 6 个文件，加仓库根 LICENSE，原样保留在 `.agents/skills/scientific-figure-making/`。
- 上游没有在 Skill 中声明语义版本，使用提交 SHA 标识；不是发布一个本项目自造版本。
- 许可证 CC BY-NC 4.0，保留作者/来源；[接入约定](FIGURES4PAPERS.md)，[逐文件哈希](scientific-figure-making-install.json)。
- 只安装 Skill 文档，没有安装新的 Python 包、下载论文示例数据或把演示数字当本项目结果。
