# 论文工作区

`template-2025/` 是用户指定教学演示中的完整社区模板，文件保持原样。

```sh
cd paper/template-2025
xelatex -interaction=nonstopmode -halt-on-error MathModel.tex
xelatex -interaction=nonstopmode -halt-on-error MathModel.tex
```

需要独立安装 TeX Live / MiKTeX，并使用 XeLaTeX。模板指定 Times New Roman、Courier New、Arial、SimSun、KaiTi、STXinwei、LiSu；字体缺失时不能视为成功编译。跨系统修改字体前应另建工作副本并核对版式。

2026-09-19 本机在临时副本上实际试编译：XeLaTeX 因缺少 `SimSun` 退出 1，未生成页面。当前只完成模板原文件与哈希核对，未完成本机排版验收；没有修改原模板的字体配置。

`MathModel.pdf` 是归档自带的参考示例；编译会覆盖同名文件，所以建议先将模板复制到 `paper/draft/` 再写作。模板中有占位正文、重复标签和示例文献，必须替换核验。

2026 比赛论文尚未开始。先按当届正式公告核对封面、匿名要求、页数和附件等，再确定最终模板。不要从这里的 2025 训练版推断 2026 提交规则。

正式论文引用 `figures/` 的已验收图件及 `results/` 的实际指标，每问均包含问题、假设、模型、求解、证据和局限。
