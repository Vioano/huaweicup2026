# R9 实际阅读、身份与缺件账本

## 1. 身份与边界

原ZIP 554451 B；SHA256 `c4bbc20854999ed402c2487de7521a67dd5bd776b9bfe1bb8c1e96729b464825`。101个成员，100份载荷hash全部匹配。`input_verification.json`保留MANIFEST及校验结论。MANIFEST记录提交`c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43`；没有另行GitHub fetch或独立回读镜像。

“全部hash验证”不等于“全部文件语义审查”。未列为阅读的其余载荷只做了字节身份检查。Files索引没有返回可引用的包内正文，实际通过已挂载ZIP解包读取，不提供虚构filecite。

## 2. 实际阅读清单

| 引用 | 包内路径 | 实际范围/操作 | SHA256 |
|---|---|---|---|
|S1|`results/a/q3-nikolastarx/layered-query-flow-audit-20260925/PRO_BRIEF.md`|全文；先读|`99e3b8d1caf3c0feede0794750f2a044b569076ecb57c21504d18e17da94432b`|
|S1|`results/a/q3-nikolastarx/layered-query-flow-audit-20260925/REPORT.md`|全文；随后读|`d3270c7e4dc6a5b7f1785150be16a1e66c5f874c07724e03d88ed3f7157fe04e`|
|S2|`results/a/q3-nikolastarx/layered-query-flow-audit-20260925/audit.py`|全文源码阅读；没有执行该审计脚本|`bc557fef0153bc8d7212535bc56a7c6d7730d97e8876e2421af9f573edab87ae`|
|S2|`results/a/q3-nikolastarx/layered-query-flow-audit-20260925/005.json`|全文JSON解析，588条保存路径逐跳原边复核|`c1be132c2718c25f91fd6956c70f9200d71b801e83621be512eb3d4dc5d67f4c`|
|S2|`results/a/q3-nikolastarx/layered-query-flow-audit-20260925/086.json`|全文JSON解析，768条保存路径逐跳原边复核|`fd659ff3346171c109152c7b795572e92d24b8c11baf29e0d16676c2739bf129`|
|S2|`data/raw/a/official/data/case_005.json`|完整JSON解析、全部原边/ops/tensors用于静态构造与独立检查|`c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f`|
|S2|`data/raw/a/official/data/case_086.json`|完整JSON解析、全部原边/ops/tensors用于静态构造与独立检查|`ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a`|
|S3|`src/q3/attention_rows.py`|阅读1–280，重点_ports、_recognize；只执行这两个静态辅助函数；未审完其余文件|`a4076188bda3037cdaa22686bf85d20051a3d8020e02d78d46db36adc5c10bb9`|
|S3|`src/q3/construct.py`|阅读1–94、128–184；未调用官方流程|`942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73`|
|S4|`src/q3/query_flow.py`|全文1–365；未执行R8官方probe|`88aca80c6e5dac46e56a6894a165e40aab7e21ac68db66b6dac83539a1d2d2f0`|
|S4|`src/q3/query_flow_static.py`|全文1–90|`8ac10baa2222ba5432f713387f0cecc70b8c3408df73458c3a577f6fd087345d`|
|S4|`src/q3/query_flow_probe.py`|阅读1–145，重点check_prepared；未运行|`729c2cded7b316c2999343da66c42a10e41df2e7bc93597990277be6f0d760c5`|
|S1|`results/a/q3-nikolastarx/query-flow-one-shot-20260925/RESULTS.md`|全文历史报告；非官方结果原件|`8027d613e2a23ae722644bd7aa4f4383e4a82fe2859e0dad20f8c27fdbc6d599`|
|S1|`results/a/q3-nikolastarx/query-flow-one-shot-20260925/comparison.json`|完整JSON历史对照；非重新跑分|`e09393ff7fbba1f1cf6cf48d8004adb1781559c4fef112e42a9c8fa99a8e404c`|
|S5|`data/raw/a/official/code/multicore_cut_evaluate_problem_3.py`|阅读1–463，重点Task构造51–290、Cache/remote-release；未阅读464–729的完整执行循环，未运行|`eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0`|
|S6|`data/raw/a/official/code/schedule_step1.py`|全文1–213；仅源码|`d8fe721ff3dbe036e34a20c00cce6430960860000a49eb467e63465f76b84034`|
|S6|`data/raw/a/official/code/schedule_step2.py`|阅读1–464；未审完末尾辅助代码；未运行|`2836baac176f4e0bdd9eec59b8d9ce254e209e5f7a251e23837ab684312fa0c3`|
|S7|`data/raw/a/official/code/schedule_step3.py`|阅读1–357、436–506、579–655、668–703；不是全文件执行/逐行验收|`50053db0436f1d166dd75436693ba3af49b5c339576beb6e7299477f6b69fc7a`|
|S8|`data/raw/a/official/code/stub_multicore_cut_and_schedule.py`|阅读1–248；仅接口/派生计划语义|`0a3a3b79b5173b466fc05fc8d33b72d11d90b4df78995435853d91c632a35892`|
|S8|`data/raw/a/official/code/evaluation_validation.py`|阅读135–243；联合执行DAG契约；未调用|`103206b8c5c25e37de50cc3193de3989d7c1e01d4a11cc5f509dedd8f9be9a64`|
|S9|`data/raw/a/official/code/multicore_cut_evaluate_problem_2.py`|仅_build_scene_b_tasks、_prioritize_task_seq、_append_tensor、_append_op源码/AST与P3对比；非P2全文件审阅|`0b39f84d5ec0a7fba9a4c92a598a9044b97ab79c71393824c1ba130ecfe6c464`|
|S10|`data/raw/a/official/data/config.txt`|全文，自有最小解析器读取固定参数|`dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`|
|S10|`docs/a/OFFICIAL_OBJECTIVES.md`|读取前100行（如文件更短则至末尾）；未声称读到原题PDF|`9a5207f18053ff1fc46ba6992442287c97b4e479717bc3d18f696109a5eb455a`|
|ID|`MANIFEST.json`|全部载荷条目读取并逐件字节/hash验证|`c82ee797de632b5c9698f6a0b9b6bbbeb115f30e9f785e1aba375ea3ca8c77ce`|

## 3. 关键定位

- [S5] P3 `_prioritize_task_seq` 51–67；Task tensor/输入/输出/跨核COPY归桶约145–215；Step调用与prepared返回约245–290。
- [S6] Step2 `_build_tensor_uses` 39–67；lifecycle约113–129；alloc→check→execute→free 224–289；仅pending_spills创建incarnation 291–405、重接消费者407–464。
- [S7] Step3管理内存与FIFO credits 123–278；四pipe投影及allocation_order 280–300；严格按分配顺序发射450–495；MEMORY_REUSE生成579–609；输出契约612–655；prepare/replay契约675–703。
- [S9] 四个函数去掉各自函数docstring后AST完全相同；原文本中builder/prioritize只有说明文字不同。对比结果见`p2_p3_source_identity.json`。这不声称P2/P3评价器整体相同。
- [S4] 旧probe中113–118行的“内存边必须为空”和“tensor并集不超过容量”不适用于R9新证书。

## 4. 缺件与未验证事项

审计目录引用但包内缺失：`summary.json`、`FROZEN.md`、`stdout.txt`、`stderr.txt`。完整100载荷清单可以在`input_verification.json`复查。

历史071两mode完整官方gzip结果、其worker/supervisor原始收据、旧005/086完整plan及精确配对P2/P3结果、完整500计划/结果表，均未随本包提供。没有为这些文件补造内容，也没有从rounded G倒算旧M2。原题PDF不在此次包内，未读取。没有官方prepared图或运行trace可供本轮验证MEMORY_REUSE向前lemma。

071的5785/7070及全500指标只维持用户/历史报告原有证据身份；本轮没有验证监督器终态，也没有冷solver效率验收。没有把局部结果拼入全量。

## 5. 本轮确实执行的工作

ZIP/逐件哈希；两份原图JSON解析；冻结_ports/_recognize静态识别；自有归属/DP/优先序/区间证书/路径分析；自有独立原边与plan覆盖检查；小型合成toy。没有调用官方Task/Step/P2/P3/E0。构造脚本设有禁止官方入口调用的profile拦截；metadata中记录空forbidden_official_calls。

`elapsed_static_seconds`仅为本地带profile与输入校验的脚本记录，不是solver冷启动效率、比赛墙钟或并发监督验收。

## 6. 交付证据位置

`candidate_*/plan.json`只含两个合法提交字段。`metadata.json`为静态推导和预测；`evidence.json`含每个原计算op归属、全局优先序、每个core/tensor闭区间及预期cross_links。`independent_static_checks.json`、`raw_witnesses.json`、`broadcast_factorization.json`提供原图复核；`toy_results.json`明确只有合成检查。
