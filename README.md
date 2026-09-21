# huaweicup2026

华为杯数学建模团队工作区。仓库：<https://github.com/huaweibei123/huaweicup2026>。

按教学演示第 6–8 屏及附录手册建立：统一环境、可复跑实验、任务卡、分支协作和可追溯论文。当前只提供备赛基础设施与**合成数据示例**，尚未导入 2026 赛题或实际实验结论。

## 第一次运行

先安装 [Git](https://git-scm.com/downloads)、[uv](https://docs.astral.sh/uv/getting-started/installation/)；通信另外需要 [GitHub CLI](https://cli.github.com/)。组织私有仓库需要相应访问权限。

```sh
git clone https://github.com/huaweibei123/huaweicup2026.git
cd huaweicup2026
uv sync --locked
uv run python src/demo.py
```

命令在 macOS/Linux 终端或 Windows PowerShell 中逐行执行。项目使用 Python 3.12；uv 可按 `.python-version` 获取解释器。`uv.lock` 固定 Python 包版本，TeX 和 GitHub CLI 独立安装。

macOS 的 ExFAT 外置盘可能产生 `._*` 元数据文件，导致依赖安装或 Matplotlib 样式读取失败。若错误路径指向 `.venv` 内的 `._*`，在项目根目录执行 `dot_clean .venv` 后重试 `uv sync --locked`。这只处理可重建的本项目虚拟环境，不清理原始数据或整盘。

示例比较普通最小二乘与 Soft-L1 稳健拟合，随机种子固定为 2026；数据在内存合成，输出为：

- `results/demo/input.csv`：合成观测、真值与离群点标记。
- `results/demo/predictions.csv`、`metrics.csv`：预测、带单位的参数与误差。
- `results/demo/run.json`：实际命令、随机种子、参数、环境版本、Git 状态及输入/脚本/锁文件哈希。
- `figures/demo/fit.png`、`fit.pdf`：对比图。

这些演示产物可以重新生成，默认不提交；正式实验应使用独立运行目录并提交经过验收的结果。示例不能当作真实赛题结果，也不复刻课件中另一组教学数值。

## 目录

```text
.
├── .agents/skills/
│   ├── team-mailbox/            # GitHub Issues 团队通信
│   ├── system-atlas/            # 0.4.0 系统设计与图谱协作
│   └── scientific-figures/      # 科研绘图约定与 ELK → Draw.io 排版
├── .github/                    # PR / 任务卡模板、跨平台示例检查
├── AGENTS.md                   # Agent 协作和实验约定
├── pyproject.toml / uv.lock     # Python 依赖及固定版本
├── data/
│   ├── raw/                    # 原始数据，只读，保留来源与哈希
│   └── processed/              # 可重新生成的清洗数据，记录来源
├── src/demo.py                 # 可运行的合成拟合示例
├── results/                    # CSV 指标、运行记录、失败案例
├── figures/                    # 论文 PDF / PNG 图件
├── paper/template-2025/         # 课件引用的完整 2025 社区模板
├── tasks/                      # 六字段任务卡
└── docs/                       # 分工、通信、来源与 Skill 调研
```

## 三人协作

每个人负责自己任务的模型/代码、证据和论文段落，由整合负责人统一验收。先复制 [任务卡](tasks/TEMPLATE.md) 约定输入、输出和验收标准，再从 `main` 建功能分支，提交后推送并发起 PR。

```sh
git switch main
git pull --ff-only
git switch -c feat/q1-baseline
# 完成任务后逐项检查、提交指定文件
git diff
git add src/your_script.py tasks/your_task.md
git commit -m "feat: add q1 baseline"
git push -u origin feat/q1-baseline
```

路径与分支名是示例，需要替换。PR 写明真实运行命令、结果和未验证项，按 [PR 模板](.github/pull_request_template.md) 交付；跨平台 CI 通过不等于模型正确或论文验收。

## 队友通信

已将 [NikolaStarx/team-mailbox](https://github.com/NikolaStarx/team-mailbox) 放入 `.agents/skills/team-mailbox/`。每位队友克隆仓库后使用自己的 GitHub 身份：

```sh
gh auth login --hostname github.com
gh api user --jq .login
uv run python .agents/skills/team-mailbox/scripts/mailbox.py init
uv run python .agents/skills/team-mailbox/scripts/mailbox.py check --full
```

完整查收后，Agent 还需逐个读取返回索引中的话题全文。任务通过 Issue 留言和 `@GitHub账号` 寻址，成果通过 PR 交付。默认无 Hook、无自动回信、无空闲唤醒。详见 [团队通信](docs/TEAM.md) 和 [Skill](.agents/skills/team-mailbox/SKILL.md)。

## 系统设计与图谱协作

已安装 [System Atlas 0.4.0](.agents/skills/system-atlas/SKILL.md)，完整保留渲染器、团队协作代码、文档与测试。它让 Human 和 Agent 查看同一份已确认模型，支持队长发布、节点/字段授权、签名变更请求和冲突回执。需要 Node.js 18+，本项目使用 Node.js 22 验证。

从项目根目录体验随附示例：

```sh
node .agents/skills/system-atlas/bin/system-atlas.mjs preview .agents/skills/system-atlas/examples/service.system.json --repo-root .agents/skills/system-atlas
```

打开终端打印的本机地址，结束时按 Ctrl-C。示例为上游演示模型，不代表本队建模方案。项目接入、测试和多人协作边界见 [System Atlas 使用说明](docs/SYSTEM_ATLAS.md)。实际成员授权与团队同步尚未初始化。

## 论文和资料

科研绘图使用 [scientific-figures](.agents/skills/scientific-figures/SKILL.md)。从“精算云画图”原型抽取的排版工具已接入；见 [Draw.io 使用方法](.agents/skills/scientific-figures/references/drawio.md) 和 [可编辑示例](figures/workflow/modeling-workflow.drawio)。

![建模工作流程示例，不代表真实赛题结果](figures/workflow/modeling-workflow.png)

排版工具需 Node.js 22+；`npm ci --ignore-scripts --prefix .agents/skills/scientific-figures` 安装固定依赖。PNG / PDF 导出另需 Draw.io Desktop；数据图继续使用现有 Python 环境。

先看 [论文说明](paper/README.md)：2025 模板是课件的训练参考，不能声称符合 2026 正式格式。来源见 [SOURCES](docs/SOURCES.md)。不把模板示例正文、参考文献或旧 PDF 当成团队成果。

数学建模相关 Skill 的选型见 [原调研报告](docs/SKILLS_RESEARCH.md)；科研绘图、Python / MATLAB / Wolfram / Julia 与 Astra 适配见 [绘图专项报告](docs/FIGURE_SKILLS_RESEARCH.md)。第三方候选尚未安装。当前项目 Skill 是 `team-mailbox`、`system-atlas` 与 `scientific-figures`。
