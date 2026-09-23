# 本轮证据索引与复现边界

## A. 环境
Linux 6.18.44 x86_64/glibc2.41；Python 3.13.5，GCC14.2；Intel Xeon Platinum8272CL@2.60GHz；5个可见逻辑CPU。没有GPU基准。实验用未经修改的官方Python源码与固定config值，调用Python函数API；不是完整CLI性能对比，不应引用微秒/毫秒耗时推断大型正式用例吞吐。

## B. 本轮结果

| 证据 | 文件 | 范围 |
|---|---|---|
| 官方114文件、FORM38payload哈希核对；旧10微图重跑 | `new_evidence/asset_and_replay_audit.json` | 0身份差异；7接受的完整JSON值一致，3预期环拒绝一致 |
| 旧运行344项的可读性与缺失明细 | `new_evidence/archived_runs_integrity.json` | 661存在文件哈希匹配；295完整result.json不在旧ZIP，逐路径列出 |
| 理想集超图最小割 | `new_evidence/structure_checks.json`、同名`.py` | 240 DAG×5价格=1200对照穷举，0差异；整数代理，非NPU成绩 |
| max-plus端口消元 | 同上 | 300固定整数DAG×8释放=2400，0差异；没有动态带宽/Cache |
| FIFO队首阻塞/顺序改善 | `new_evidence/new_official_probes_v3/head_*_p{2,3}/` | 同图、同核心归属、同切分，仅顺序变化：1410→818；搬运五字段一致 |
| 固定工作追加空核 | 同上`append_empty_core_p2/` | 818→818，2核到3核但工作不变 |
| spill logical key的实际命中 | 同上`spill_logical_cache_p{2,3}/` | 3490→2670；逻辑tid3、物理tid29，spill COPY_IN28真实走CACHE_READ |
| 独立复跑成员ranking fixture | 同上`form_ranking_{a,b}_p1/` | 1052 vs152；固定config，全部搬运字段一致 |
| 数量对称性特例与接口反例 | `new_evidence/repeated_counts/` | 32份5分支赋值，计数内0差异；相同局部标签但不同接口的823 vs1326反例 |

`new_official_probes_v3/summary.json`对应9次完整官方运行；`repeated_counts/`对应34次。上述是本轮新官方函数调用。旧10探针的本轮重跑另外记录，不与成员36条规则的独立验收混算。

### 真实执行历史

`official_new_probes_attempt1.txt`与`attempt2.txt`保留两次包装脚本开发失误：第一次对私有build函数的参数位置理解错误，第二次返回tuple解包错误。它们不是官方判定某合法plan非法。对应`new_official_probes/`和`_v2/`只含部分运行，**完整报告仅使用v3**。不把部分目录累加为更多独立实验。

## C. 源码位置（相对未修改的官方 code/）

- `multicore_cut_evaluate_problem_2.py:381–410`：`queue_if_ready`检查`pipe_ops[pipe][pipe_cursor]`，`advance_pipe`在完成后前进。
- `multicore_cut_evaluate_problem_3.py:443–472`：问题3对应FIFO逻辑。
- `multicore_cut_evaluate_problem_3.py:487–510`：完成COPY_IN时调用`insert_cache`，没有先检查此前路径是miss。未构造命中期间条目被淘汰并在完成时重插的端到端反例，故仅登记实现分支。
- `multicore_cut_evaluate_problem_3.py:398–434`：logical_tid key与FIFO插入/容量。
- `multicore_cut_evaluate_problem_2.py:189–215`附近：逐源/目标核心插入COPY对；问题3为约197–223。
- `multicore_cut_evaluate_problem_2.py:52`、问题3`:60`：按子图顺序稳定调整局部序列；具体边界ID也会影响原始排序。
- `schedule_step3.py:74–92`：COPY独占时长与DDR端点；非COPY最少1周期。
- `schedule_step3.py:144–183`：FIFO虚拟额度来源与消费。
- `evaluation_validation.py:217–243`：Task顺序和全局执行图环检查。

本轮重算的逐文件hash在官方原件及FORM规则卡之间一致；集合哈希de11a83...的计算recipe未在本批取得，因此不能把ZIP SHA、逐文件SHA或拼接SHA混为该集合标识。

## D. 本轮没有做什么

没有重新执行正式100case算法对比，没有完成新的1–5核曲线，没有实现完整A/B/C候选求解器，没有E1/E2独立验收，没有运行NVIDIA GPU或Apple Metal。新的两种数学核验不证明任意实例正确实现，更不证明原题全局最优。理论证明需要独立检查其条件。

旧全体统计可作为选择反例和研究范围的存档证据；295完整结果缺口意味着部分细节不能从本包立即重查。用户已有原官方图和方案时可以有界重跑，不能把旧摘要复述成新实测。
