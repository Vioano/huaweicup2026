# 官方一核 baseline：100 / 100

用户于2026-09-24在方案成绩台维护任务明确要求尽快批量计算。每图一次未修改官方 `singlecore_evaluate.py` CLI；固定图/config/代码哈希执行前校验，命令逐例记录。

- 100成功，0失败，0超时；100次E0 CLI，0次solver/E1/E2，无重试。
- 开始：2026-09-24T12:40:10.041784Z；结束：2026-09-24T12:48:51.928905Z。
- 8并发；总批次521.884秒（包括CLI、结果压缩校验与归档，不包括此前环境准备及之后网站接入）。
- 各CLI累计墙钟2646.442秒；中位1.918秒；P95最近秩128.242秒；最长366.787秒。并发墙钟和CPU时间不是同一量；未测峰值RSS。
- 操作性超时600秒/CLI，本轮均未触发；不是赛题硬时限。
- `manifest.json`记录运行驱动固定提交、源码/依赖/环境与冻结身份；`progress.json`完整100条索引；`verification.json`本机归档核验及与LYX旧报告对比。
- 每图目录保留完整 `result.json.gz`、`trace.json.gz`、`run.json`和原日志；压缩往返验证原始CLI输出字节，未删改结果字段。
- 与LYX固定e041bca2快照的86个成功单核周期一致，原14个超时用例本轮成功；不拿两端wall作速度结论。
- 单核分母可按冻结身份共享给P1/P2/P3报告；不伪装为200次P1/P2 k1 solver，也不把P3相对单核当作同plan Cache收益。

运行命令（新运行必须使用新输出目录，不能覆盖本批）：

```sh
uv sync --locked
python scripts/a_materials.py --extract
uv run python src/benchmark_board/run_singlecore.py --output results/benchmark-board/NEW-UNIQUE-RUN --workers 8 --timeout 600
```

本次实际输出目录为 `results/benchmark-board/official-singlecore-20260924`。现有结果足够复用，请勿为补网站格式重复运行。
