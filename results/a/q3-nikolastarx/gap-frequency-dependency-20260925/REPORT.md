# 097/k1：累计 M 间隙的直接依赖诊断

固定源码 `dd386a1cbd4d0c86544c7000b00bcf6ed5194439`。两份现有计划和 E0 原件逐字节对照固定发布提交，执行的是未改官方 Task/Step3 重建，不是新的 P3 评分。实际 **2 次 Task 构造、2 次本地 Step3、0 次新多核 E0、0 次 solver、0 重试**；整批 2.958091 秒，单 worker，采样进程组 RSS 峰值 179814400 B（约 171.48 MiB），低于事前 512 MiB 停机线。启动前 pressure=2、两次物理 unused 1155/1383 MiB、两次 swapout 增量0，见 resource-preflight.json。该资源窗口不包括新候选评分或全500。

| 直接紧前驱 | 旧 forest：次数 / 间隙周期 | 新 band+lookahead：次数 / 间隙周期 |
|---|---:|---:|
| ADD → M 的内存复用边 | 320 / 373728 | 7 / 2856 |
| COPY_IN → M 的数据边 | 77 / 68145 | 1897 / 908005 |
| 合计 | 397 / 441873 | 1904 / 910861 |

共 6656 个 M 的开始时刻逐个满足 `start=max(previous_M_end, every_actual_predecessor_end)`。操作覆盖、每核各 Pipe 完整投影、官方搬运统计和 Step3 内存边数均与固定结果匹配。两方案 M busy=10303488、首个 M 起点172、尾部613，累计间隙差468988完全等于既有 Makespan差（10746146→11215134）。重建结果只复核既有时序的直接依赖，不是改边后的反事实模拟。

**不能把第二行直接改称“带宽瓶颈”或“已排除内存影响”。** 新方案1897条紧 COPY 的开始时刻全部比前一个 M 的结束晚408周期；其服务时长分别为69（1848次）、103（7次）、138（42次），皆走DDR。这说明真正决定 COPY 就绪/排队的上游仍需检查，恰好408也等于本图ADD时长，但仅靠相等不能断定具体上游依赖。当前重建器没有输出这些 COPY 的完整祖先边，预算已结束，未再构造 Task 补数据。

因此“减少直接 ADD→M 阻塞”“缩短最大间隙”“减少 COPY 字节”都不能单独作为算法接受规则。下一构造应同时检查全部 M 间隙、上游 COPY 就绪与官方 Makespan。逐叶 tile 原型已做静态合法性检查，尚无正式评分；Pro R5正在研究相应条件证书，此结果未中断其生成或自动追加提问。

原始派生证据见 old_forest/dependency.json 与 new_band_lookahead/dependency.json；run.json保存原件SHA、调用账和子进程信息，summary.json由以下零评分命令生成：

```sh
python3 results/a/q3-nikolastarx/gap-frequency-dependency-20260925/reproduce_summary.py
```

这不是完整评价器等价认证，也不证明任何修改后的候选改善。要追踪COPY上游，需独立预算与更完整依赖导出，不覆盖这次原件。
