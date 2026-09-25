# 三格统一入口准入修正（零评分）

协调者在60b865版本发现准入只检查非空，故未放行且未启动评分。本修正保持原算法、输入和调用预算，要求JSON gate的status=admitted、scope=p1-unified-integration-three、owner_session、source_head、manifest_sha256、runner_sha256、精确整数budget、UTC未来expires_at_utc及未使用的绝对output_dir全部对应。实际run先校验，后原子创建输出目录；prepare-only只核验、不消费输出。过期时间是T0截止，不是中途终止时间；运行中仍按原1320秒总预算。

Sol medium复用上下文，软预算4000 tokens/8分钟（非硬限额，实际tokens不可用）。首轮纯mock 2项因macOS临时路径别名失败，修正夹具后7/7通过。Root检查补上空白准入、错owner、无时区expiry，并让每个无效门直接经run验证无stage调用/无输出目录；末次7/7通过。三轮原始stdout/stderr分别保留，不隐藏失败。命令：`../../.venv/bin/python -B -m unittest discover -s tests/q1 -p test_p1_unified_integration_three.py -v`。所有子进程/评分执行均mock，真实构造/Task/E0/E1/E2均0。

预算保持worker1，3solver/30E1/3E0，E2与重试0，solver300s/E0120s/全批1320s，RSS1536MiB，variable编译512/2048；本文件不是准入。冻结提交和外部manifest由root发布后交协调者独立复核。

## 启动前第二次窄修

已发出的第一张gate在尚未T0且attempt-1不存在时，由root发现每格E0后缺少真实目标值比较而停止启动；协调者关闭旧gate，实际solver/Task/E0/E1/E2均0。新增对官方scene=A、cores=5、正整数makespan、非负整数scheduled COPY及与selected_objective精确相等的校验；不一致即停发下一格，保留已消费调用账及全部原件。Sol medium软1800tokens/4min，真实用量不可用；一次纯mock8/8通过（stderr-r3.raw），包含首格E0不等时仅消费1solver/3E1/1E0 mock、后两格not-run。算法/图/预算均未变，需重新固定源码与独立准入。
