# 已核对的实现细节与六次烟测

本文件只记录此次实际检查，不代替 FORM 工作。来源均为随项目上传的 ZIP；哈希见同目录 `official_source_manifest.json`。没有运行大规模性能基准，也没有实现 E1/E2。

## 一、源码核对

|编号|实际观察|代码位置|对任务契约的影响|
|---|---|---|---|
|A01|基础方案校验明确不保证最终执行可行性|`code/stub_multicore_cut_and_schedule.py:105–112`|接口区分 input/plan/execution|
|A02|A 合并子图依赖和同核 Task 顺序检查环|`code/evaluation_validation.py:217–224`|不能只检查子图 DAG|
|A03|B/题三检查本地 data/memory、Pipe FIFO 和跨核 COPY 组合环|`code/evaluation_validation.py:226–243`|代理没有完整展开时不得宣称 execution pass|
|A04|Step3 用虚拟字节额度，复用时产生 WAR/WAW 依赖|`code/schedule_step3.py:124–178`|形式化不额外引入物理地址碎片问题|
|A05|Step3 导出 execution_graph 与固定 pipe_orders；多核阶段不重排|`code/schedule_step3.py:595–639,675–703`|“换成更优核内排序”不是等效加速|
|A06|COPY 参考耗时按关联大小取整且至少 1 cycle；其他操作也至少 1 cycle|`code/schedule_step3.py:74–92`|零值和周期临界需单元测试；理想连续带宽并不等于 E0|
|A07|共享池剩余工作使用浮点、1e-9 容差及整数化|`code/multicore_cut_evaluate_problem_3.py:352–396`|E1 保留相关数值/控制流语义，E2 明列近似|
|A08|题三 Cache 键取 COPY 对应局部 tensor 的 logical_tid（缺省为 id）；资格函数只检查 COPY_IN|`code/multicore_cut_evaluate_problem_3.py:398–414,523–581`|不能凭题面概述另加“仅原始外部输入”白名单|
|A09|FIFO 插入不刷新已有键；完成 COPY_IN 时调用插入函数|`code/multicore_cut_evaluate_problem_3.py:416–434,487–521`|不仅要写理想 miss→insert；还要审查命中读在途时被淘汰等实现边界|
|A10|题三 data_movement_bytes 在 Task/Spill 展开阶段生成，与运行期 hit_stats 分开|`code/multicore_cut_evaluate_problem_3.py:244–290,676–722`|不得自行把 hit_bytes 从 scheduled_copy_bytes 中减掉|
|A11|memory_peak_by_core 取自各 Task 的 Step3 结果|`code/multicore_cut_evaluate_problem_3.py:700–714`；题二同类位置 `:574–590`|报告应说明该字段来源，不重定义成另一种峰值|
|A12|B 的子图优先级是对 raw_seq 做稳定排序，随后查拓扑|`code/multicore_cut_evaluate_problem_2.py:43–59`|稳定排序和原始同桶顺序是兼容点|
|A13|Step1 tie-break 使用操作类型、深度及 id；Step2 spill 并列依赖稳定插入顺序|`code/schedule_step1.py:104–184`；`code/schedule_step2.py:131–173`|不要默认节点重命名/对象重排保持官方指标|
|A14|当前 validate_graph 拒绝 Tensor→Tensor，但未一概拒绝 Op→Op|`code/evaluation_validation.py:171–215`|记录与题面第 2 页原始二部图要求的输入域差别，不据此扩张竞赛输入域|
|A15|原版 CLI 严格检测重复 JSON 键；默认输出路径会随同图同问题重复使用|`code/contest_io.py:43–54,181–192,254–258`|批量运行必须独立输出路径，防止覆盖或读取旧产物|
|A16|单核基准入口建立全非 COPY 操作的单子图方案，并调用场景 A|`code/singlecore_evaluate.py:22–57`|单核基准口径不能随代理/搜索器改变|

备注：源代码注释、附件文档、PDF 有些描述层级不同。FORM 必须独立核对并提交差异清单，不能把本表理解成一份完整、已裁决的形式化规范。

## 二、数据规模核对

此次读取到 100 个正式 `case_*.json`。Op 数最小 766、中位数 4,223、最大 38,666。完整逐用例记录在 manifest 中。这只是输入规模，不说明任何函数已经被证明是性能瓶颈。

## 三、实际运行的六次烟测

运行方式：直接调用未修改源码的 `evaluate_scene_a`、`evaluate_scene_b`、`evaluate_problem_3`，统一使用附件原版 config。返回值按 JSON 序列化后保存；尚未加 CLI 的 `input_graph/input_plan` 元数据，因此这些 golden 是函数层输出。

|微型图|问题|Makespan（cycles）|原始 COPY bytes|调度 COPY bytes|新增 COPY bytes|Cache（仅问题三）|
|---|---|---:|---:|---:|---:|---|
|minimal|1|6|32|32|0|不适用|
|minimal|2|6|32|32|0|不适用|
|minimal|3|6|32|32|0|0 hit / 1 miss，miss 16 bytes|
|shared_input_concurrent|1|8|48|64|16|不适用|
|shared_input_concurrent|2|8|48|64|16|不适用|
|shared_input_concurrent|3|8|48|64|16|0 hit / 2 miss，miss 32 bytes|

第二个图中，同一 16-byte 核内输入被两个独立计算使用，两计算分别放到两核。两核的首次 COPY_IN 在数据尚未入共享 Cache 时发射，因此两者均 miss。它提醒我们：**“多个核共用输入”不自动意味着“第一个 miss，其他必 hit”**。这与查 Cache 的发射时机和完成时插入有关。

两个图均不产生 spill，故不能用来证明内存压力、执行环、FIFO 淘汰等行为。它们只为团队提供立即可复跑的接口锚点。

## 四、复现

在本任务包目录运行（将路径换成自己机器上未修改的附件目录）：

```text
python verify_smoke.py --official-root /path/to/original_attachment
```

脚本检查 code/config 哈希，调用三个原版函数，并与本包的六份函数层 golden 做严格结构比较。该脚本不是待实现的完整 TEST harness。
