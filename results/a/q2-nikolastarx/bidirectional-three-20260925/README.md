# P2 三格真实在线选择验证

固定统一求解器 `15d86e13b4a8abb4bce445ac241aecac13f553bf`，入口 adaptive_bidirectional_guarded；E2 `603b0741e21c449d3db652ebd67c94f2dc014cc9`。本次不是新的全量500格成绩，也不能与历史赢家拼接为主成绩。

| 图/核 | 原工期 | 新工期 | 原额外DDR B | 新额外DDR B | 冷solver s | 自动选择 |
|---|---:|---:|---:|---:|---:|---|
|005/K5|33515|33515|1410582|1410582|3.613|旧方案；拒绝43881的反向候选|
|069/K5|11962|10577|321938|452436|1.468|反向；工期降11.58%，DDR升40.54%|
|071/K2|9261|9153|235654|235462|1.182|反向；工期降1.17%|

总计3solver、12 E2 API且12 native、3独立官方E0，0fallback/unknown/retry；批墙钟7.272s。Python3.12.13/macOS arm64共享主机，观察者与进程合计峰值207503360 B。每个候选完整计划在评分前保存；最终选中计划hash对应唯一评分请求，M、五项DDR和cross_task_traffic与独立E0完全相等。六个子进程exit0、survivors空，收尾扫描无评分进程。

旧12:10:17Z门禁因动态swap free小于1GiB未通过，0调用，原件保留。总调度R2改以真正空闲物理内存≥6GiB及无明显内存压力准入；实际T0为12:14:52Z，物理free约9.92GiB，memory_pressure系统free86%。单worker/RSS512MiB/每solver60s、E030s、批300s，预算没有增加。两份门禁不能合并为两次评分。

`run-originals.zip` 保留全12候选、三个最终计划、solver/E2账、官方结果/trace/log、进程命令/墙钟/清理原件。`parent-readback.json` 是本机独立逐文件读回，`execution-receipt.json` 是执行者收据。附runner和LOCAL_README是当次工作目录的历史原件，含当时绝对路径；不是归档目录下直接重跑入口。原始文件哈希见files.json。正式主成绩仍为c66559a6全500，K5平均4.549756996698352。
