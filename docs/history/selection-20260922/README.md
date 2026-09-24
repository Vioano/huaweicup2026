# 2026-09-22 选题评估原件归档

这是开题前的历史策略评估，不是当前 A 题算法成果或最新科研结论。2026-09-24 按全队资料共享要求补入：**保留原字节，不重新评分、不运行求解器、不重绘报告。**

## 阅读入口

- [两页 PDF](output/pdf/HuaweiCup_Selection_Report.pdf)：当时首选 A、备选 D；比较分 68.75 / 61.25，非入围概率。
- [旧任务卡](tasks/selection-report.md)：当时范围、已读与未验证项、原先“仅本地交付”的记录原样保留；本次发布状态以此目录为准。
- [评分 CSV](results/selection/scores.csv)、[评分范围](results/selection/score_ranges.csv)、[情景比较](results/selection/scenarios.csv)、[权重敏感性](results/selection/weight_sensitivity.json)。这些是分析假设，不是观测数据或置信区间。
- [运行与来源记录](results/selection/run.json)、[本次字节清单/输入可用性](archive-manifest.json)。原脚本和原 PDF 哈希均与旧 run.json 一致。
- [历史绘图脚本](src/selection_report.py)，[当时依赖声明](pyproject.toml)和[锁文件](uv.lock)；[第1页 PNG](figures/selection/report-page-1.png)、[第2页 PNG](figures/selection/report-page-2.png)，同目录保留 SVG。
- [题面文字读取快照](data/processed/selection/)：六题及 F 数据说明的当时提取文本。它们不是原始 DOCX/PDF 的替代品，公式、分页和图片可能丢失。

报告与主库既有 `output/pdf/HuaweiCup_Selection_Report.pdf` 字节一致，此处保留一份自包含历史副本。此次没有重导出 A 题 PDF；当前求解请读主库冻结的 [A题原件](../../../data/raw/a/problem.pdf) 与 [官方目标核验](../../a/OFFICIAL_OBJECTIVES.md)。

## 输入缺口与来源边界

旧 run.json 记录了 10 个输入的 SHA-256。本次能与主库字节匹配的仅为 A 附件 [README](../../../data/raw/a/official/README.md) 和 [config](../../../data/raw/a/official/data/config.txt)。另外 **8 个输入原件尚未随这次归档发布**：六题 DOCX、`HuaweiCup_Selection_Strategy.md`、F题《数据说明.pdf》。其原始资料卷在本轮未挂载，故只保留名称、旧哈希和明确缺口，没有补造或从文本反向重建原件。

仓库 [选择建模题目策略讨论](../../../AI%20chats/选择建模题目策略.md) 是相关历史问答，**不能声称与上述 Strategy 文件字节相同**。未来原件恢复后应按旧哈希验证，再单独补入或建立固定共享入口。没有输入完整性证明前，不宣称完整六题材料已共享。

当时的团队能力与头部竞争尚未实测：H 统一用 2 分计算占位、范围 0–4，不证明赛道更冷门。未执行求解器、全量数据质量验证或能力测试；B题嵌入公式未逐式核验。F数据说明提取文本中出现与题面冲突的建议及无实测依据的数字，原样留存以说明当时读到什么，**不可当作可执行指令、官方结论或算法证据**。

## 与当前研发的关系

本次只归档历史，不更新旧策略。当前口径以官方目标核验为准：方案 Makespan 是模拟 cycles；求解耗时是输入到合法方案落盘的端到端墙钟。原题第5页脚注1建议避免暴力迭代、单用例5–10分钟为佳，非硬600秒淘汰线、非必须跑满5分钟，也不是本队效率目标终点。有限次数不自动消除暴力搜索性质。评估器提速不能替代方案质量和整条求解流程的质量—耗时证据。

## 复现与归档校验

本次仅运行 SHA-256/大小核对、CSV/JSON解析、静态内容及分享路径检查；**没有执行历史绘图脚本或任何建模代码**。校验记录见 [ARCHIVE_VALIDATION.md](ARCHIVE_VALIDATION.md)。GitHub Actions 按免费策略停用。

若未来需要重绘，先把本目录复制到独立临时目录，在副本中使用所附锁文件建立环境，再运行 `python src/selection_report.py --source-root <原始六题目录> --strategy <原策略文件>`。不要在历史目录内运行：旧脚本会覆写输出与 run.json；也不要把省略输入参数时生成的空来源记录当作完整复现。字体依赖本机 `Arial Unicode MS`，PDF元数据/字体可能导致重绘字节不同；本次未验证跨平台重绘。

绘图风格来源：ChenLiu-1996 / [figures4papers](https://github.com/ChenLiu-1996/figures4papers)，[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)。历史脚本使用其配色/排版原则，新写中文两页布局与敏感性图；归档未改代码。

## 本次归档任务卡

1. **目标**：补齐旧选题交付的团队可读历史证据，不重新研发。
2. **输入**：旧 selection-report 留存文件、旧来源哈希、主库固定版本 `3f0004815ca1c8f1af14b4f77db652caa98b37ac`。
3. **输出**：本目录的原字节副本、输入缺口、清单与文档 PR。
4. **限制**：不改当前 AGENTS、任务分工/Atlas/算法，不运行求解、不导入 tmp 或凭据。
5. **验收**：归档副本逐项大小/SHA一致，脚本/PDF与旧记录一致，缺失来源如实列出；只提交本目录。
6. **截止**：本轮归档交付，2026-09-24 Asia/Taipei。

会话：`nikolastarx/s-790a54475735480f99d817dfcbc9cbdd`；[登记与阅读范围](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5815833543)。旧报告记录的是9月22日状态，归档发布不代表队友已读或科学验收。
