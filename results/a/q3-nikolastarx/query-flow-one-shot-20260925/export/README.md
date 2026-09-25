# R8 071/K5 feed 导出说明

`generate_feed.py` 从固定 P3/P2 worker 原件、同一冻结 plan、历史官方单核 baseline 与监督器收据生成 `feed.json`。导出脚本只核身份/哈希并映射 JSON 字段，不运行评分或修改原件。

本feed含两个官方 E0 单格：P3（Cache read-only）M=5785，同计划无 Cache P2 M=7070，配对值 P2/P3=1.222126。复用的官方单核 scene A baseline 为 M=18919；其压缩原件 SHA256 为 `d2e46fd00db3766c4ca574084cde6d94b1aa062cab5b5199474c86013e51daa5`，与同图已有已交付基线身份相符。P3搬运来源是原result的 `scheduled_copy_bytes`，不是实测硬件DDR计数；Cache指标直接来自原result。

这是一个 query-flow affinity 固定计划的局部机制证据，不是已集成完整solver、全500覆盖、独立复跑或最终算法验收。端到端冷solver墙钟没有测量；solver/evaluator单独墙钟均留空，worker诊断时间没有冒充它们。worker和probe run原件报告完成；外部监督器的原始receipt明确为 `failed`，原因是 parent identity/process-group verification 与 cleanup verification 失败。导出保留该差异，没有把监督器改写为成功；原receipt及stdout/stderr留在同级 `resource-control/`。

根 Agent 对最终 `feed.json` 在主项目当前 `src/benchmark_board/protocol.py` 上重新运行 `--submission` 预检（feed和artifact读取自固定工作树），返回 `valid:true, eligible:2, records:2`。原始命令和返回值保存于 `preflight.json`、`preflight.stdout.txt`、`preflight.stderr.txt`。`eligible`只是协议字段/原件匹配结果，不能解释为机制完成度或科学验收。

来源修订：静态阶段原始 summary 记录实际方案生成 commit 为 `b1eb32aca82436b20cc82da8c86d4301ef00cfb1`；one-shot probe/E0 runner 使用冻结 commit `65d7355ee0856783ede81328915e8bd43227c842`。两提交中的 `query_flow.py` 与 `query_flow_static.py` blob SHA256分别相同（`88aca80c6e5dac46e56a6894a165e40aab7e21ac68db66b6dac83539a1d2d2f0`、`8ac10baa2222ba5432f713387f0cecc70b8c3408df73458c3a577f6fd087345d`）；feed保留实际生成来源和评分runner来源，不将二者合并成同一历史。
