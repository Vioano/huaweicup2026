# 数学建模 Skill 调研（暂不安装）

调研日期：2026-09-19。结论来自 GitHub 上游的真实 `SKILL.md`、仓库元数据和 skills.sh 检索；**没有安装或运行下面任何候选 Skill**。仓库目前只含用户指定的 `team-mailbox`。

## 选型建议

本项目已经有目录、锁定环境、任务卡和通信机制，优先补充单项能力更容易接入：先考虑 **statistical-analysis + sympy**；论文图表增多后考虑 **scientific-visualization**；遇到多目标优化题再考虑 **pymoo**。这是结合本项目的选型判断，尚未做同题效果比较。

完整竞赛流程可重点比较 XiaoMaColtAI 与 zhnnky329 两套，但建议只选一套主流程，先映射到现有目录和任务卡再试用。多套总控一起触发，会出现重复产物、不同阶段门槛和相互冲突的工作约定。

## 已核对的候选

安装数为 `npx skills find` 当日显示的约数；星数为当日 GitHub API 快照。它们仅表示使用/关注规模，不证明数学正确性、安全性或赛题效果。`未取得` 不等于零。

| 候选 | 对本队的用途 | 当日规模 | 接入成本与限制 |
| --- | --- | --- | --- |
| [K-Dense / statistical-analysis](https://github.com/K-Dense-AI/scientific-agent-skills/blob/330c8e764435a731eff571e3efdda70b363d0792/skills/statistical-analysis/SKILL.md) | 检验选择、假设检查、效应量、样本量与统计结果报告 | Skill 安装约 1.8K；整库 45,563 stars | 含 Python 示例和检查脚本；按需增加 pingouin/statsmodels 等并更新 uv.lock。APA 报告格式需适配中文论文；不能机械套用检验决策表。**优先候选。** |
| [K-Dense / sympy](https://github.com/K-Dense-AI/scientific-agent-skills/blob/330c8e764435a731eff571e3efdda70b363d0792/skills/sympy/SKILL.md) | 公式推导、方程/微分方程、符号矩阵、生成 LaTeX 与数值函数 | 安装约 1.6K；同一整库 | 需要 SymPy。适合检查解析推导，仍需写清定义域、物理假设并与数值结果交叉核对。**优先候选。** |
| [K-Dense / scientific-visualization](https://github.com/K-Dense-AI/scientific-agent-skills/blob/330c8e764435a731eff571e3efdda70b363d0792/skills/scientific-visualization/SKILL.md) | 论文图、误差/不确定性展示、配色、PDF/PNG 导出检查 | 安装约 1.9K；同一整库 | 支持 Matplotlib/Seaborn/Plotly；部分导出路径有额外依赖。本仓库已有 Matplotlib，可从这一分支试用；不必提前引入浏览器导出栈。 |
| [K-Dense / pymoo](https://github.com/K-Dense-AI/scientific-agent-skills/blob/330c8e764435a731eff571e3efdda70b363d0792/skills/pymoo/SKILL.md) | 多目标/约束优化、NSGA-II/III、Pareto 前沿、混合变量 | 安装约 1.5K；同一整库 | 需要 pymoo。适合确有目标冲突的题；应比较基线、约束可行性和多个种子，不能把启发式解声称为已证明全局最优。 |
| [Anthropic / statistical-analysis](https://github.com/anthropics/knowledge-work-plugins/blob/67e216dbe5621470581dd3d944df22d1cc8231ce/data/skills/statistical-analysis/SKILL.md) | 描述统计、异常值、趋势、相关性与显著性解释 | 安装约 4.1K；整库 24,959 stars | 来源为 Anthropic 官方仓库；示例偏商业数据分析，理论建模覆盖较少。与 K-Dense 同名，宜二选一，避免发现和触发冲突。 |
| [XiaoMaColtAI / math-modeling](https://github.com/XiaoMaColtAI/math-modeling-skill/blob/8fd8ddbca28b413d188aeb095ace6bb926015844/SKILL.md) | 中文完整流程：建模分析 → Python/MATLAB 实现 → 论文 | 安装约 897；1,619 stars | 角色、资料、工具齐全；默认强制独立子代理质检，并有固定图件数量和文档产出要求。LaTeX 请求仍要求 Word 双格式，接入较重。上游 GitHub 未识别许可证，正式引入前需进一步核对。 |
| [zhnnky329 / MathModeling-skills](https://github.com/zhnnky329/MathModeling-skills/blob/046a6e74814c2e5fef72b5ee56305509a8635e1d/.codex/skills/workflow-orchestrator/SKILL.md) | 按子问题记录状态、阶段验收、模型选择与实验交付 | 本次未取得可靠单项安装数；928 stars | 总控读取 manifests/decision ledger；模型选择有明确人工决策环节。使用 planning/methods 等额外目录，并依赖配套项目规则，不能只复制总控文件。适合愿意采用完整流程的团队。 |
| [BZD / bzd-review-paper](https://github.com/BZDmathclub/bzd-math-modeling-skills/blob/5395fb591a47f8f3b906feb9647bebdf1f4779e8/skills/综合评审与自我定位类/bzd-review-paper/SKILL.md) | 完整题面与论文的结构化评阅、定位证据缺口、HTML 报告 | 本次未取得可靠单项安装数；354 stars | 主要按本科 CUMCM 材料校准，非 CUMCM 默认走另一套近似位次路径。对研究生华为杯宜只借鉴检查项，**不采用其获奖/位次预测**。GitHub 未识别许可证。 |

K-Dense 仓库总体为 MIT，个别 Skill 的元数据另列库许可；zhnnky329 为 MIT，Anthropic 仓库为 Apache-2.0。应保留实际引入文件的许可，不能从整库标签推断每项附带材料都采用相同许可。

## 为什么不立即安装整套数模流程

XiaoMa 的入口有强制独立质检、固定产物数量和双格式交付要求；这些可以形成纪律，但对小任务也有额外开销。zhnnky329 的总控明确把模型选择权留给人，并依赖题目状态与决策台账，和当前任务卡需要先做对照。这些判断直接来自上述固定版本入口，未把作者宣传当作效果测试。

BZD 的论文检查可以作为补充读者，但其评分、格式阈值与排名映射不能代替华为杯真实评审；尤其不能把“其他比赛”的统一近似分布迁移成研究生竞赛排名证据。

未来试装时，建议在独立分支用一个已知答案的小问题比较：能否按当前目录落盘、能否恢复参数、能否完整记录证据、是否额外请求很多人工确认，以及对代码/论文是否提出实质改进。通过后只合并需要的 Skill 和依赖。

## 后续安装命令备忘（本次均未执行）

以下命令仅用于确认选型后的参考；默认项目安装，不带 `-g`。不要整段执行，先选一个并核对实际发现目录。CLI 默认拉取当时的上游版本，正式引入应固定提交并记录来源。

```sh
npx skills add K-Dense-AI/scientific-agent-skills --skill statistical-analysis
npx skills add K-Dense-AI/scientific-agent-skills --skill sympy
npx skills add K-Dense-AI/scientific-agent-skills --skill scientific-visualization
npx skills add K-Dense-AI/scientific-agent-skills --skill pymoo
# 下项与上面的 statistical-analysis 二选一
npx skills add anthropics/knowledge-work-plugins --skill statistical-analysis
```

安装数核对入口：[统计分析 K-Dense](https://skills.sh/k-dense-ai/scientific-agent-skills/statistical-analysis)、[SymPy](https://skills.sh/k-dense-ai/scientific-agent-skills/sympy)、[科研绘图](https://skills.sh/k-dense-ai/scientific-agent-skills/scientific-visualization)、[Pymoo](https://skills.sh/k-dense-ai/scientific-agent-skills/pymoo)、[统计分析 Anthropic](https://skills.sh/anthropics/knowledge-work-plugins/statistical-analysis)、[中文数模流程](https://skills.sh/xiaomacoltai/math-modeling-skill/math-modeling)。

## 调研范围

已做：skills.sh 目录/CLI 搜索、GitHub 仓库与目录真实性核验、8 个候选入口关键流程/依赖/约束阅读、许可证元数据和提交版本记录。搜索还出现其他社区数模包，但未深入核验，不据此推荐。

未做：安装候选 Skill、运行候选脚本、完整逐文件安全审计、同题横向评测、竞赛获奖能力验证。所有候选源文件仅下载到本机临时目录供阅读，没有放入项目技能目录，也没有因此安装其 Python 依赖。
