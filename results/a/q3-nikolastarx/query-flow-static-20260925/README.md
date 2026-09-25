# R8 原查询流联合分核：冻结静态机制实验

假设：同一原查询流中的前处理、全部并行head row、后处理共同owner，能够减少现有逐模块决策的计算增强DAG往返，且完整Task物理tensor支持不超过L1/UB。首要检验正确性，其次看新计划计算FIFO下界是否低于已保存官方incumbent计划的同口径下界；它仍不是官方Makespan。

固定输入：官方原图071、069及原config，以source-manifest.json原字节验证。均为已见开发样本，5核，cross-delay读取固定500。完整源码以调用--source的完整提交为准；输入、所有q3源码和uv.lock哈希写入输出summary。

唯一命令：`python3 -m src.q3.query_flow_static results/a/q3-nikolastarx/query-flow-static-20260925/run --source <冻结提交>`。源与参数冻结后才调用。一次顺序运行071再069，各一次query_flow.construct和一次独立pipe_bound，1worker，60秒，0Task/Step1/Step2/Step3/E0/E1/E2/VM，首异常停，0自动重试。真实构造不属于单元测试。

检查完整singleton覆盖、所有真实原边、阶段不回退、同一DAG最长路、任一路径跨核边不超过2、按P3重建规则的物理Task全支持容量。Pro的071下界4538/069下界5846仅作作者参考，不改结果以追逐其数字。若同口径完整计算界不降，不进入官方验证；若适用性/容量/依赖guard拒绝，保留负证据而非按case编号放松。069本轮仅检验结构取舍，不申请其E0。

任何后续071官方验证须另冻结计划、完整观察器和预算并取得共享资源准入；此静态阶段绝不消耗或重置已结束044实验的预算。本轮完成后按用户要求暂停，不自动发R9。
