# 008/K5 单例：已准备、未执行的真实接口验证包

算法固定于 `4fc5e5e91e4a2ac9feaf05267c1f8ab713ca5990`；提案见同一研究分支 `results/a/p1-packet-seed-20260925/pilot-proposal.json`。这是一个结构初始候选的模型接口验证，不是预期刷新成绩的正式批次。当前尚未获资源窗口、未启动 VM、未运行真实 Task/Fraction/solver/E0/E1/E2。

预算：008/K5、20 次 Task 编译（含最终整图）、3 次 Fraction 响应（含最终回放）、2 次查询、1 个研究进程，0 E0/E1/E2/重复执行。构造段 30 秒，进程组 45 秒及 512 MiB；新 CPU Standard VM 从创建前 T0 起目标至多 300 秒。`controller.py` 在 T0+270 秒安排独立停机进程，每一步还受绝对截止时间与收证/停止预留约束。成功必须完成真实文件下载、逐文件大小/SHA核对、报告与计划匹配，以及停机回读；未知停机不报告成功。

## 已验证

- 全部 72 个源/输入文件与固定 Git blob 或官方 ZIP 中的 008 原始字节一致；73 个 tar 成员路径、大小和 SHA 全部核对。
- `rebuild_bundle.py` 可从固定 Git 和本目录 manifest 精确重建 9,237,091 字节包，SHA 为 `b78c67f1c535625ac6ff31545b179cb2a5bfcd1f762fff99248d9364c7101ab9`；不必再提交一份已有原始数据包。
- 冻结入口 `--help`、脚本 AST、5 项 fake 控制流程（成功、执行失败收证、已有会话不创建、停机不明、坏包不接收）通过。隔离临时目录的独立 watchdog 子进程通过立即截止的假 CLI 检查；没有网络调用。

## 待验证与使用边界

尚未验证云端 Python/uv setup、真实编译/响应、Linux 子进程资源监督、真实下载或真实 VM 停止。fake 测试和源码哈希不证明这些真实路径已成功。`--execute` 只是一项显式操作开关，不能替代协调者分配窗口；不可因没有活动 VM 就自行抢占。不要重用已有 controller-run/evidence 输出目录，也不要重复新建或重跑未知结果。

本目录不含重复的源码包。资源窗口获批且检查通过后，可先用 `python rebuild_bundle.py --repo <已有仓库> --output <本目录>/lazy-seed-source-bundle.tar.gz` 重建完全相同的字节，再使用控制器。离线测试命令为 `python -B test_controller.py`，不调用 Colab。执行前后保留全部回执，不把失败收证当作探针成功。
