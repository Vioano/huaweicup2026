# Fang / 成员方案成绩台全量同步

本包解决成员只导入主分支旧快照，遗漏其他已接收来源的问题。数据截止 **2026-09-24 13:50 UTC**：**2697条历史记录、1500个正式格位**。保留成功、失败、仅报告、旧revision和不同算法来源；不是2697个独立格位，也不是一次实验的全量成绩。

- [manifest.json](manifest.json)：13个已接收feed的固定提交、路径、SHA256、全部中央记录ID及核对指纹。
- [sync_snapshot.py](sync_snapshot.py)：通过网站现有校验器增量导入，保留本机额外记录，重复执行不重复入库。没有求解或评分调用。
- [验证记录](verification.json)：实际复建与核对范围。

## 网站代码也要更新

同步数据与更新网站代码是两个步骤。最低适用的已发布网站版本为 **a241394dc6bcde7dff41c1f7f4c333182436a759**，分支 `codex/benchmark-board-averages-20260924` / [PR96](https://github.com/huaweibei123/huaweicup2026/pull/96)。其中包括顶部布局、默认官方单核比、均值、UTF-8支持、新来源配置及官方JSON展开上限。后续UI仍在更新，`manifest.recommended_code_commit`记录本包交付时建议版本；新发布以网站维护者在[Issue33](https://github.com/huaweibei123/huaweicup2026/issues/33)给出的固定提交为准。仅跟旧main不能保证看到与中央相同的页面。

**先更新接收器，再导P1全量数据。** 旧64 MiB展开上限会把11条大结果存为仅报告；之后换代码不会自动重验已存的相同revision。本包脚本会在打开账本前检查128 MiB能力；如果旧版已经导入这些条目，回报精确attempt/revision给维护者安排可追溯处理，不删历史或改记录。

保留算法worktree和未提交修改，把网站代码放在独立运行checkout。使用原来的成员状态目录，不清库、不用别人的SQLite覆盖自己的记录。替换代码后，仅重启自己的网站服务，显式沿用原状态目录和端口；勿启动第二个重复轮询进程。后台Python不会因git fetch自动加载新版，浏览器缓存也需刷新。

## 导入完整快照

取得本包所在提交/分支和上述网站代码，保留本包目录中的manifest与脚本同层。在成员仓库中运行（Windows使用`python -X utf8`；路径按本人实际位置替换）：

```sh
python -X utf8 results/benchmark-board/member-sync-20260924/sync_snapshot.py --repo PATH_TO_UPDATED_WEBSITE_CHECKOUT --state PATH_TO_EXISTING_MEMBER_STATE
```

`--repo`是已更新网站代码的Git checkout；`--state`是成员原网站真正使用的状态目录。脚本仅在缺少固定提交时从本人组织仓库origin fetch，先核feed字节，再通过原Ledger校验原件和增量导入；不切换分支、不安装软件、不运行solver/E0/E1/E2。网络中断可重试；同revision内容冲突时保留现场并回复维护者，不能清库掩盖问题。

完成输出应满足`missing_snapshot_ids=[]`、`lost_existing_ids=[]`、`same_snapshot_admission_and_metrics=true`。本机拥有更多历史时，`extra_local_records_preserved`可大于零，总条数可超过2697；以中央快照全部ID存在为准。记录ID集合SHA256应为：

```
da222d10c50d133d7b0b88812cb1a105722dfe9f972f3cf802a6a19baff8b762
```

核对包含全部原始记录内容ID和固定的指标/准入投影；导入时间、事件游标、来源检查时间不要求一致。三条初版历史在现代校验器中会新增或规范化派生字段：两条新增`extra_ddr_bytes`，一条失败记录的缺失null字段变化。此差异已记录，不覆盖中央历史；核对投影按manifest所列指标将缺失值标准化为null，额外搬运派生字段不纳入这个跨旧版本指纹。Makespan、已核单核比、主要搬运/时间和准入身份仍逐记录核对。原件校验不等于独立重跑或科学终验。

## 完整来源

| 顺序 | 在中央新增历史数 | 固定feed |
| --- | ---: | --- |
| 1 | 8 | [17052ab873 / board-feed-initial-20260924.json](https://github.com/huaweibei123/huaweicup2026/blob/17052ab87301cc65c5340eb75873045c2ad892d7/results/benchmark-board/feeds/board-feed-initial-20260924.json) |
| 2 | 2 | [fac17a6e55 / board-feed-singlecore-first-20260924.json](https://github.com/huaweibei123/huaweicup2026/blob/fac17a6e559e41a8b327f3743bb4393d6400d196/results/benchmark-board/feeds/board-feed-singlecore-first-20260924.json) |
| 3 | 749 | [36dc69d065 / board-feed-lyx-partial-20260924T121711.json](https://github.com/huaweibei123/huaweicup2026/blob/36dc69d065fbb377ac141c99ed6bf640855f6cef/results/benchmark-board/feeds/board-feed-lyx-partial-20260924T121711.json) |
| 4 | 100 | [b1839b3130 / board-feed-full100.json](https://github.com/huaweibei123/huaweicup2026/blob/b1839b31300f69df6877241b20784552e7c6ad68/results/a/local-p2-k1-20260924/20260924T131640Z-s59ee/board-feed-full100.json) |
| 5 | 12 | [96ef2f1126 / board-feed-first12.json](https://github.com/huaweibei123/huaweicup2026/blob/96ef2f11263b2ca7aea8e800ae3a522c57812ef7/results/a/local-p2-multicore-20260924/20260924T1325Z-s59ee/board-feed-first12.json) |
| 6 | 13 | [f35b11ed02 / board-feed-20260924T132237Z-history13.json](https://github.com/huaweibei123/huaweicup2026/blob/f35b11ed029adface084044485b1e7fd23899c4d/results/a/q2-nikolastarx/board-export-20260924/board-feed-20260924T132237Z-history13.json) |
| 7 | 3 | [1e6ba3f527 / board-feed-20260924T132504.494191Z-c255fefc63ad-001.json](https://github.com/huaweibei123/huaweicup2026/blob/1e6ba3f527bea4adc83e8eb499461e788e44de2d/results/a/p123-multicore-20260924/submissions/20260924-first3/board-feed-20260924T132504.494191Z-c255fefc63ad-001.json) |
| 8 | 388 | [77dad8b5ce / board-feed-full400.json](https://github.com/huaweibei123/huaweicup2026/blob/77dad8b5ce1ea48616e9aa63bd9140bb5f6450d8/results/a/local-p2-multicore-20260924/20260924T1325Z-s59ee/board-feed-full400.json) |
| 9 | 400 | [247c6d8cab / board-feed-20260924T132554Z-farmer-p1-v3.json](https://github.com/huaweibei123/huaweicup2026/blob/247c6d8cab3be929ebea98bbba33543a7b2c3c76/results/a/board-feed-farmer/20260924/board-feed-20260924T132554Z-farmer-p1-v3.json) |
| 10 | 13 | [6a1f8e4455 / board-feed-20260924T133121Z-history13-r2.json](https://github.com/huaweibei123/huaweicup2026/blob/6a1f8e4455e8cadf53b60d9d7516e146684f68c3/results/a/q2-nikolastarx/board-export-20260924/board-feed-20260924T133121Z-history13-r2.json) |
| 11 | 500 | [ba99b74b52 / board-feed-full500.json](https://github.com/huaweibei123/huaweicup2026/blob/ba99b74b523f93a4002cd88970ec7164076d8008/results/a/local-p3-20260924/20260924T1331Z-s59ee/board-feed-full500.json) |
| 12 | 9 | [67c91f1834 / board-feed-stage-b-20260924.json](https://github.com/huaweibei123/huaweicup2026/blob/67c91f18348b31f713b0cf92def05eaebf4d5c37/results/a/q2-yuanzhifang/board-sync-20260924/board-feed-stage-b-20260924.json) |
| 13 | 500 | [6664a63adc / board-feed-full500.json](https://github.com/huaweibei123/huaweicup2026/blob/6664a63adc3464d28d1f835d907cdeaea23e6b35/results/a/local-p1-fixed64-20260924/20260924T1337Z-s59ee/board-feed-full500.json) |

官方单核100例原件同时随对应feed所引用的固定提交提供，不需要重跑。当前Fang P2/008/k4赢家尚缺单核分母引用，原件已核成绩可显示，单核比仍为NA；生产端按原attempt补revision2，包含002/008/044的匹配分母，不能填造或重跑。

## 持续联络与后续更新

本包是固定快照，不是后台服务。网站维护者负责发布代码/UI变更和稳定来源配置；成员沿本人已授权的现有轮询、工作间隙查信跟踪Issue33与正式版本，不再创建重复同步器。每次更新分开记录：网站运行SHA、来源配置SHA、实际数据截止时间及记录/正式格数。代码仅fetch、通知已发和浏览器已经更新是不同状态。

采用后在Issue33回：实际运行checkout/完整SHA（不用公开个人绝对路径）、导入核对摘要、页面1500格覆盖、网页JS/CSS版本与截图或实际UI检查结果；存在失败立即附具体错误/缺失feed。维护者发布新版本时及时同步并回读，发现页面或数据数量不同先核筛选条件、代码、来源列表与最新已接收批次。后续新增记录不在本快照指纹内，依更新后的来源配置继续接收。
