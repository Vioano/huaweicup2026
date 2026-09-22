# figures4papers 接入

按用户指定，将 [ChenLiu-1996/figures4papers](https://github.com/ChenLiu-1996/figures4papers/tree/3c181f85e82c6f24948fcaaf3be6696102b41d8d/scientific-figure-making) 的 `scientific-figure-making/` 安装到项目 `.agents/skills/scientific-figure-making/`。固定提交 `3c181f85e82c6f24948fcaaf3be6696102b41d8d`，上游没有在 Skill 中声明语义版本。6 个文档及仓库根 LICENSE 原样保留，逐文件来源见 [安装清单](scientific-figure-making-install.json)。

作者/来源：ChenLiu-1996 / figures4papers；许可 **Creative Commons Attribution-NonCommercial 4.0（CC BY-NC 4.0）**，见 [完整许可证](../.agents/skills/scientific-figure-making/LICENSE)。引用或改编其代码/设计材料时保留归属、许可链接并说明改动，遵守非商业使用条件；上游不是 MIT。没有替上游变更许可证。

## 与现有绘图 Skill 配合

- `scientific-figures`：本项目的数据来源、单位、结果路径、可编辑源、导出与视觉验收；以及 ELK → Draw.io 技术路线图工具。
- `scientific-figure-making`：Matplotlib 论文图的设计原则、配色、版面和图种代码配方，适用于趋势、散点、柱状、热图和多面板。
- `system-atlas`：系统模型、协作图谱和任务看板，不替代论文实验图件。

新增 Skill 是供 Agent 阅读的文档，**不是已安装的 Python 模块**。`references/api.md` 中的示意函数需要实现或从 demo 改编，不能直接假设 import 存在。用现有 `uv.lock` 环境作图；新增依赖另走项目流程。上游 demos 链接当前 main，需要引用时记录实际取用的提交和文件，不把动态链接当固定材料。

此 Skill 未绑定 Codex 或具体模型；其他 Agent 可显式读取 [SKILL.md](../.agents/skills/scientific-figure-making/SKILL.md)。绘图仍使用本队真实结果，示例数据/论文数字不自动导入。此次只接入并核对文件，没有为本项目重新运行上游全部绘图 demo 或声称图件已验收。
