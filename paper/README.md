# 论文工作区

当前论文模板是 [`template-2026/`](template-2026/README.md)。它替换了此前用于训练的 2025 社区模板；旧版仅保留在 Git 历史中。模板中的姓名、队号、正文、图、数据和文献都是排版示例，不是本队的比赛成果。

在仓库根目录运行：

```sh
cd paper/template-2026
latexmk -outdir=../build main.tex       # 带封面：paper/build/main.pdf
latexmk -outdir=../build anonymous.tex  # 无封面：paper/build/anonymous.pdf
```

需要 XeLaTeX、latexmk、BibTeX 和支持中文的 TeX 环境。编译产物放在 Git 忽略的 `paper/build/`，不会覆盖模板自带的预览。正式参赛信息优先写入 Git 忽略的 `template-2026/config.local.tex`；正文编辑 `sections/`，参考文献编辑 `reference.bib`。把已验收的项目图件从根目录 `figures/` 引入模板 `figures/` 时保留来源与相对路径，论文中的数字须对应 `results/` 的实际产物。

压缩包原样解压，逐文件哈希见 [`template-source.json`](template-source.json)。模板代码的 MIT 许可不自动涵盖字体、Logo 和官方附件；分发或提交前应核对各自许可。模板自称参照 2026 年附件 2、3，但正式交稿仍须按当届赛事公告核对封面、匿名要求、页数和附件。本机编译成功仅证明排版链路可运行，不构成赛事格式验收。

## A 题绘图任务

[A 题绘图分工与验收任务书](notes/A-FIGURE-WORK-PLAN.md)列出甲独立负责的 10 组图、乙独立负责的 8 组图，以及逐图绘图流程、输入、交付指标和验收标准。图 5-4 全部由甲负责；文末提供三问初稿及证据索引的固定提交入口。
