# FORM 四个既有反例：交接索引与勘误

本包只接收有限资料交接任务，**不等于 FORM 最终验收、公开 CLI 实跑或 E1/E2 通过**。代码与旧数值原件固定在 `65d6c0e6facee2ec8ce9694c30dd805de99abf7e`。本次队长只核对源码/文档对应和 GitHub 原始记录，0 新样本、0 重跑/评分。

阅读顺序：本页 → [作者勘误](AUTHOR_ERRATA.md) → 按需 [最初四条表原文](ORIGINAL_HANDOFF.md)。两条原评论逐字保存，原文中的错误未改；有效引用须同时采用下列队长核验注记。来源、大小与 SHA-256 见 [manifest](manifest.json)。

| 条目 | 输入/构造与原命令所在脚本 | 已保存观测 | 可复用范围 |
| --- | --- | --- | --- |
| F-PLAN-005 商图成环 | [输入/构造](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/tests/adversarial/fplan-005-quotient-cycle.json) · [脚本](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/src/adversarial/add_fplan005_fixture.py) | [JSON](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/results/a/form/r1-20260923-farmeruncle123/fixtures-observations.json) | 内嵌graph/plan已存在；原DAG通过而商图成环方案被拒。属于非法方案回归，不能当合法构造收益。 |
| 相同搬运特征，不同Makespan | [输入/构造](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/tests/adversarial/ranking-inversion-pair.json) · [脚本](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/src/adversarial/verify_ranking_fixture.py) | [JSON](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/results/a/form/r1-20260923-farmeruncle123/ranking-fixture-verification.json) | P1双核、同划分两种分核顺序；作者API记录1052/152 cycles。三搬运特征相同只能说明无法区分，不证明任何具体预测器必然反序。 |
| F-RESOURCE-001 DDR竞争 | [输入/构造](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/src/adversarial/verify_time_r1.py) · [脚本](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/src/adversarial/verify_time_r1.py) | [JSON](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/results/a/form/r1-20260923-farmeruncle123/time-resource-observations.json) | build_two_cores已有普通graph/plan；projected_end_history来自官方ddr_contention_log的汇总。24/44比较混合不同工作量，不能用作加核结论。 |
| F-RESOURCE-008 在飞命中退休重插 | [输入/构造](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/src/adversarial/verify_l2_r3.py) · [脚本](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/src/adversarial/verify_l2_r3.py) | [JSON](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/results/a/form/r1-20260923-farmeruncle123/l2c-observations.json) | graph()已有普通graph/plan；1200/1201/600容量是机制探针参数，不是官方固定config成绩。重插直接证据是cache_events事件链，39/46本身不够。 |

## 复用前的明确边界

四项都是微型构造，不能代表官方100例或所有图。①②已有JSON内嵌graph/plan；③④有构造代码，尚未独立落盘为CLI输入。旧脚本直接调用官方函数的观测与公开CLI实跑分开。此次未运行任一脚本，链接不是运行许可。

冻结 [contest_io.py](https://github.com/huaweibei123/huaweicup2026/blob/65d6c0e6facee2ec8ce9694c30dd805de99abf7e/data/raw/a/official/code/contest_io.py) 读取graph/plan，调用对应评价函数，并整体写出result。由此可给出cache_events/ddr_contention_log能够沿结果写出的源码层判断；CLI执行、路径/配置装配和输出仍未验。不能再写“没有公开graph”或默认字段不导出。公开入口是multicore_cut_evaluate_problem_N.py，stub是方案构造示例。

②将来若验证，需要落盘graph和两份plan并分别评价两个候选；不是只存两份plan或只启动一次CLI便可获得完整对照。④若要复现相同事件链，需明确其探针容量与冻结配置的差异，不修改冻结config，也不泛称所有官方图不会出现该机制。任何新运行须按接收任务的固定版本和实际预算安排。

本索引对rank fixture原purpose中的“且会给出与官方相反的偏好”作显式勘误：同特征只证明该组特征不能区分两个结果；原数值和旧文件保留。作者勘误已承认该过强句，不能继续把它传播成定理。

## 原始发布时间与耗时更正

作者补充及勘误中的时间仍有混淆。以本轮完整GitHub API抓取为准：

| 记录 | created_at（UTC） |
| --- | --- |
| [接手回信](https://github.com/huaweibei123/huaweicup2026/issues/14#issuecomment-5806755029) | 2026-09-24T03:08:17Z |
| [四条表](https://github.com/huaweibei123/huaweicup2026/issues/14#issuecomment-5806791066) | 2026-09-24T03:11:27Z |
| [Atlas补充](https://github.com/huaweibei123/huaweicup2026/issues/14#issuecomment-5806862704) | 2026-09-24T03:18:03Z |
| [作者勘误](https://github.com/huaweibei123/huaweicup2026/issues/14#issuecomment-5806976497) | 2026-09-24T03:27:44Z |

作者首次自报T0为03:08Z，之后撤回精确T0的可信性；本包不替其补造实际开工时刻。可确认接手评论至四条表发布时间相隔3分10秒，至勘误相隔19分27秒。原文的12分钟、03:15Z及“接手03:11:27Z”均不采用；不能把发布时间间隔当作全部实际工作耗时。

队长核验结论：资料层面的四项来源、结论收窄与CLI复用状态可以交接；原件数值仍按作者报告标注。原FORM PR17与所有算法/CLI运行验收保持各自原状态。成员Git TLS仍暂停，本次经Issue交付，由队长归档，不转授队长身份或改校验证书。
