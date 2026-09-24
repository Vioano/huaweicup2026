# r02 实际读取与证据边界

## 上传原件：全文读取，字节身份核对

固定提交：`Vioano/huaweicup2026@ceaed932e1951af00969c481e5ebc0f7d2bd1e82`。

| 文件 | bytes | SHA-256 | Git blob SHA-1 |
|---|---:|---|---|
| PRO_R02_RESEARCH_BRIEF.md | 15214 | 7a134759c04d69ff91912078601a0bd0c2362b10bbadd3d5c90f56f0fd02a1a3 | 176054276ad48e11cc4d15833e10defcc0a7562c |
| CONCURRENT_EVALUATION_DESIGN.md | 20244 | 48c87ae20a87e24243ddc497f75d220e8fa0361b7ac54f053380b7f054bd9602 | cfa9a126417585be1ecce19d2e99ba9907c4324c |

本机根据上传原件原始字节计算的 Git blob，分别等于授权连接返回的固定提交文件 blob。GitHub只取两份文件头用于元数据核对；正文依据完整上传原件，不声称重复下载了两份完整网络副本。

## 本轮通过授权 GitHub 连接全文读取的18份文本

仓库始终为 Vioano/huaweicup2026；未使用组织仓库或匿名网页替代。

| 固定提交 | 路径 |
|---|---|
| 997813c7c83d4d18a0a8e2a19b5be37b90223e01 | research/a/e2_search/scene_b.py |
| 997813c7c83d4d18a0a8e2a19b5be37b90223e01 | research/a/e2_search/pool.py |
| 603b0741e21c449d3db652ebd67c94f2dc014cc9 | research/a/e2_search/P23_HANDOFF.md |
| 4dff90ef699fd51845cf482951e8477066f5f566 | src/q1/search.py |
| 4dff90ef699fd51845cf482951e8477066f5f566 | src/q1/profile_candidates.py |
| 4dff90ef699fd51845cf482951e8477066f5f566 | src/q1/profile_refine.py |
| 4dff90ef699fd51845cf482951e8477066f5f566 | src/q1/prospective_priority.py |
| 4dff90ef699fd51845cf482951e8477066f5f566 | docs/a/Q1_RELEASE_IDEALS_REVIEW.md |
| 4dff90ef699fd51845cf482951e8477066f5f566 | results/a/q1-q2-mechanism-pro008-20260924/REPORT.md |
| 0b58c123cccf02fc993b741d79dcd8511e4dd38f | src/q2/proposals.py |
| 0b58c123cccf02fc993b741d79dcd8511e4dd38f | src/q2/budget_search.py |
| 74c46372faf5910b9b3cce6ad9a61a7e040b17aa | src/q2_nikolastarx/joint.py |
| 74c46372faf5910b9b3cce6ad9a61a7e040b17aa | results/a/q2-nikolastarx/joint-20260924/REPORT.md |
| 517cd105d1330cfbcf7b11b9a1ab9061242f3d54 | src/q3/construct.py |
| 517cd105d1330cfbcf7b11b9a1ab9061242f3d54 | docs/a/q3/METHOD.md |
| 517cd105d1330cfbcf7b11b9a1ab9061242f3d54 | docs/a/q3/EVALUATION_PROFILE.md |
| c1935ab51e48b6f239212a4ba11bc8c326c7fd00 | docs/a/q3/EXPLORATION_FEEDBACK.md |
| c1935ab51e48b6f239212a4ba11bc8c326c7fd00 | results/a/q3-nikolastarx/pilot-20260924/metrics.csv |

最后一项CSV为7行候选的已有记录。本轮没有重新计算其数值或运行生成程序。

## 静态核读发现的三个接口事实

1. `search.py`只有在ok且更优时更新incumbent，但未在评分非ok后统一break；它的best_plan文件在最终E0前已写出。不能把该入口当成已经实现“所有非ok立即停且只有已确认checkpoint”。`profile_refine.py`、`prospective_priority.py`的停止/确认路径不同；原源码和拟议新政策需分开。
2. Fang `proposals.py`多处 `range(4)`、长度4的数组及计划输出；本固定版本的算法空间/实验不证明1–5核适用。
3. 当前P23原生异常会触发对应E0；`native_enabled=False`不是no-oracle开关，`full=True`也消耗E0。原生后返回route才核算无法阻止越权调用。

另：`profile_candidates.py`在候选生成阶段调用官方局部Task构建并临时替换捕获函数。该成本不在“最终评分调用数”中，却必须计入生成与准备CPU；共享线程直调需要隔离审查。

## 未读与未验证

没有重读全部冻结官方源码、当前全部C++内核、32候选逐op/FIFO压缩原始输出、所有实验ledger/protocol、全部正式图、完整源数据清单及平台构建物。没有核验本轮新后端全域正确性、长跑或Windows验收；不提升其现有证据等级。

尚无团队全体“图族暴露/用于选算法”账本，不能指定真正未见的封存图。当前未取得任何新实验批准、已登记host配额或已验收三客户端服务。本轮并不需要重新上传旧ZIP才能形成静态设计；未来执行至少需要这些新登记项、固定输入/代码/预算和具体客户端政策。

## 外部原始资料：仅阅读与本设计有关的摘要/正文片段

- López-Ibáñez et al. (2016), The irace Package: Iterated Racing for Automatic Algorithm Configuration. 作者补充材料： https://iridia.ulb.ac.be/supp/IridiaSupp2016-003/index.html
- Jamieson & Talwalkar (2016), Non-stochastic Best Arm Identification and Hyperparameter Optimization. PMLR： https://proceedings.mlr.press/v51/jamieson16.html
- Li et al. (2018), Hyperband: A Novel Bandit-Based Approach to Hyperparameter Optimization. JMLR： https://www.jmlr.org/papers/volume18/16-558/16-558.pdf
- Kuhn, Kacker & Lei (2010), NIST SP 800-142, Practical Combinatorial Testing. 官方： https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-142.pdf
- Cawley & Talbot (2010), On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation. JMLR： https://www.jmlr.org/papers/volume11/cawley10a/cawley10a.pdf
- Lindauer et al. (2022), SMAC3: A Versatile Bayesian Optimization Package for Hyperparameter Optimization. JMLR： https://jmlr.org/papers/volume23/21-0888/21-0888.pdf
- Howard et al. (2021), Time-uniform, nonparametric, nonasymptotic confidence sequences. 作者稿/期刊元数据： https://arxiv.org/abs/1810.08240

文献证明不自动迁移到本题：低阶组合测试不是最优算法覆盖定理；早停依赖的资源—最终质量关系不等于P2→P3；条件参数BO的可表达性不证明小样本预测可靠；置信序列不消除图族错配。
