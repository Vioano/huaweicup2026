# Colab 两计划探针：准备阶段失败

2026-09-25T03:49:15.582Z 开始唯一 CPU Standard 实例的创建流程。准备脚本在 `bundle-verify` 阶段读取已经关闭的 TarFile，报 `OSError: TarFile is closed`，未进入 Python/uv 检查或探针执行。

- 冻结探针及源包：`d5cce3680dc2575a6de95690b09e999992840fb0`。
- 008/K5、095/K5 均未运行；实际 Task 编译、Fraction 响应、solver、E0/E1/E2 调用均为 0。没有云端重试。
- 从创建流程开始到证据下载、关闭及服务端回读，共 26.522484 秒。`stop` 返回 `Session terminated`，随后 `sessions` 返回 `No active sessions found on server`。
- 真实下载档 `evidence.tar.gz` 为 610 字节，SHA-256 为 `b806f03d11fc7be143a741b259b6859905eadb0d4f7ea8c552e3a748ce80f417`。清单中的一个原件及清单本身均已核验。下载成功不代表探针成功。
- 远端 Python/uv 版本、本次峰值内存及 CU 消耗未测得，不沿用历史 VM 的数字。原批准上限为 20 次 Task 编译、2 次响应、30 秒/512 MiB；这些是未执行探针的预算，不是实际调用或消耗。

`executed-remote-setup.py` 保存实际执行的有错脚本，哈希与启动前 `execution-scripts-manifest.json` 一致，不原地修正。`setup.json` 是远端失败原件，`collection-receipt.json` 是下载和停止回执，`source-bundle-manifest.json` 保存固定输入及依赖锁文件的字节清单。原始 Mac 控制脚本与完整日志保留于本机任务输出目录，清单只记录其原始 SHA；它不是本目录中的可移植重放入口。

VM 创建之前另有一次本机预检因控制脚本缺少 `sys` 导入停止；修复后才发起上述唯一 VM。该预检没有创建实例或运行探针，未隐藏为算法重试。根代理接收和复核准备脚本后未发现此次 TarFile 生命周期错误，按本侧准备故障记录。

本目录不提交成绩台分数，不改变旧完整批次的 4.025907473836023 五核均值，也不判定这两个候选方案失败。当前只知道探针尚未运行。资源已交回总调度；下一次执行须重新获得明确窗口，不能因为本次调用为零而自行再开 VM。
