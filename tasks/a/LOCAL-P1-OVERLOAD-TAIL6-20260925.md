# P1 overload-list 五核六格独立补测

负责人：@NikolaStarx；执行会话 `nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc`

1. **任务目标**：固定算法 `q1-component-overload-list` 的五核全100图仍有六格缺少本批官方有效分数：098/099/100 在先前首异常停派后未启动；014/041/079 已启动但官方 E0 各在60秒界限超时。为这六格启动明确的新批次，保留旧超时/未启动历史，不将同计划旧评分冒充新运行结果。
2. **输入文件**：原始图 `case_001.json` 至 `case_100.json` 中清单指定六图，冻结配置与官方源码，求解器固定提交 `3c6e41b938c764d207de45584fb526c64f4eb845`；坐标和限制在 `src/local_benchmarks/s59ee_p1_overload_tail6_manifest.json`。
3. **输出要求**：独立目录 `results/a/local-q1-overload-tail6-20260925/<run_id>/`，六格各保留 plan、官方 E0 result/trace/log、诊断、真实调用账与标准成绩台 feed。旧82格和研发方原18格保留原提交与批次身份。
4. **限制条件**：最多6次solver、6次官方P1 E0、0 E1/E2、0自动重试；每格solver30秒、E0 180秒、整批900秒，最多2 workers。前3格为原未派发坐标，后3格为原超时坐标；首异常停新派，在途收尾。P3高并发批结束并释放资源后才启动。
5. **验收标准**：运行前固定runner/manifest/source与官方输入哈希一致；六格均有真实终态/调用账，成功格的plan/result/run和标准feed在同一Git固定提交可按SHA逐项读取。只有单一固定算法的完整100图五核有效集才能用于该算法均值；不足100注明n/100。
6. **截止时间**：无用户日历截止；按本机资源窗口尽快执行。

完成后补实际环境、T0/T1、结果、未验证项和接收回执。
