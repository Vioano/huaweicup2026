# 新鲜 100×1–5 核全批申请（未获评分 release）

四格试跑 `393417263`：4 solver、8 native E2、4 独立 E0、0 fallback；总墙钟 19.26 秒，三格改善、一格保留。小样本不能代表 500 格尾部。最小改动是扩展现有 `gap_solver_pilot.py` 的坐标和累计账本，固定 `923b25e` solver、E2 `603b074`、官方配置，预检 100 图及旧统一 feed 身份；旧分数只用于事后比较。

申请上限：1 worker；每格 solver 60 秒（含在线评分）、E0 60 秒；全批含预检 2 小时、RSS 4 GiB、0 retry。最多 500 solver、1000 公开 E2、500 独立 E0，预留 1000 潜在 fallback；首个 fallback、未知在途、超时、异常或身份漂移即停。每格留独立目录、进程收据、plan、ledger、E0 原件及调用账。用 `score_adapter` 规范 plan SHA 定位所选 native record，核对 M、五项搬运量和跨 Task 流量；零评分仅在 plan 等于冻结基线时核旧 truth。非 `UnsupportedStructure` 构造错误必须失败。

同算法身份是固定 solver SHA、入口、参数及选案规则；runner 另记 SHA。修复当前只排除单 runner 的预检：923b25e 的 39 个 `.py` 逐字核，辅助 `.py` 另列提交清单，现场文件集合及 solver ledger 的 glob 哈希须与两者并集完全一致，不改冻结 solver。新全批共用 run ID、manifest 和累计预算；不实现自动续跑；输出目录已存在即拒绝，任何异常停并保留原件。如需后续执行，另行申请固定范围和剩余预算，不覆盖或重试已开始格；不足 500 格只作预览，不混四格试跑或历史最优。还需根 Agent 核对并取得调度 release，当前不启动。
