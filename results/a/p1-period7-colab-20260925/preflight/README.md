# 008/K5 显式周期 seed 离线执行包

此目录只准备一次研究接口验证；**未启动 Colab、真实 Task/Fraction、solver 或 E0/E1/E2**，也未获本包资源窗口。固定源码提交 `030f2b8aff4dc5e6b1acf9d88dc4984e54f1b5fa`。新会话 `p1-period7-008-20260925`，远端根 `/content/p1_period7_window`，与旧 seed 包隔离。显式 `q=7,s=3` 只核这条完整周期路径；源码已将显式模式的后续 search 查询额度设为 0，失败不会扩查其他候选。最终整图编译及模型回放仍是成功条件；这不提供 E0 成绩。

冻结预算：Task 编译总上限 40（其中预留最终 20），Fraction 响应 5（含最终），oracle 查询 4，扩展 10；构造 30 秒，子进程组 45 秒及 512 MiB，VM 生命周期目标 300 秒，T0+270 秒独立停机 watchdog。E0/E1/E2/重试均为 0。`--execute` 仅是防误触开关，不代表资源授权。

`bundle-manifest.json` 列出 72 项固定 Git blob/官方 ZIP 字节及大小、SHA-256。`rebuild_bundle.py` 采用旧包相同的 tar PAX 与 gzip mtime=0 配方；本目录包精确重建通过：9,237,625 字节，SHA-256 `49550ba410f732c2cc4032adca58765f33f76685a642280039455a18a958abb5`。离线安全解包核验 73 个成员，脚本 AST、控制器来源指纹回读和 7 项 fake 测试通过。`offline-check.json` 是本地预检收据，`execution-manifest.json` 记录本包文件哈希。

未验证云端依赖安装、真实编译/响应、Linux RSS 监督、实际下载和 VM 停止。运行会创建单次不可覆盖的控制器与证据回执；失败/未知不能重试或宣称探针成功。协调者需在独占资源窗口内另行决定是否执行。
