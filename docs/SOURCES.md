# 来源与版本

核对日期：2026-09-19。

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

- 引入日期：2026-09-21；用户指定本地项目与上游当前主分支均为 0.4.0。
- 上游：<https://github.com/NikolaStarx/system-atlas>
- 固定提交：`f70784c1250679b57e4de516b07d9c00677acc69`（包含 0.4.0 团队协作及恢复时保留并发编辑的修复）。
- 上游仓库根目录就是 Skill；完整安装至 `.agents/skills/system-atlas/`，没有嵌套 `.git`。
- 230 个上游文件逐一核对，内容保持一致；文件 SHA-256 清单在 [system-atlas-install.json](system-atlas-install.json)。
- 保留 MIT LICENSE 及 Archify 2.16 归属说明。没有复制开发机的 node_modules、私钥或私有运行状态。
- 本次核对时上游尚未创建 GitHub Release；0.4.0 来自该固定提交的 SKILL.md、package.json 和 skill-release.json。

## LaTeX 训练模板

- 来源：教学演示的 `materials/2025LaTeX模板_课堂副本.zip`。
- 社区上游：<https://github.com/zhanwen/MathModel/tree/master/2025年数模悉知%26论文模版>
- 本项目解压至 `paper/template-2025/`，保持归档内文件内容不变。
- 含 `MathModel.tex`、`gmcmthesis.cls`、`figures/`、`test.jpg`、`MathModel.pdf`、`READ_ME_FIRST.txt`。
- `MathModel.pdf` 是上游附带的旧示例，并非本项目编译成果；来源清单与归档哈希见 `paper/template-source.json`。
- 这是 2025 社区训练材料，非 2026 官方格式认证；正式使用时需核对当届要求与上游授权。
