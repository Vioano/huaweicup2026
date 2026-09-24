# 成绩台独立成员端验收

执行者：`yuanzhifang30-sudo/s-e777d827b5af4adfafd148ff3a4fae8b`，Windows / Python 3.12.14。

本目录保留 **固定签名快照、真实运行发布与浏览器更新** 的分阶段证据；尚不宣称全部交付队列和最终双向同步验收完成。研发上下文已读，不宣称盲审，也未重新运行算法评估。

## 正式同步与网页自动换版（2026-09-24 16:02 UTC）

`formal-runtime-acceptance.json` 全项通过：签名快照 `200c47360d850d944a10cfae6769099e88d1282e5668623ad4894c9df551e1da` 的全部 3626 条历史与事件逐字段相等；正式/报告预览各 1500 格独立重算一致。原 3209 条记录完整保留，增加 417 条；原本机 872 条与备份逐行相等，全部 ID 确实在中央快照中。签名软件 release `fbc1b27c4154495605179cfe3d70787c2808897a5d9f66058f09dca3b4d4e434` 与中央发布者均对应完整代码 `a36cbcab441ece5df55f104c983e3341265f9f4e`；全部发布文件经 Git blob 核对，4 个 HTTP 静态资源含动态注入 HTML 指纹均相等，实际软件 health=ok。

此次使用 `--sync-state $State --projection-scope overview`，38 次 HTTP，约 27 秒；overview 省略逐算法/批次重复投影，但不省略全部历史、事件或默认 1500 格的两模式验收。此前 138/156 种过滤投影的完整报告仍保留。验收要求全过程快照稳定；之前遇到快照或软件自动变更的尝试没有算通过，见 `formal-first-attempt-inconclusive.json`。

已有 IAB 标签在首次接入正式程序的一次受控刷新后，**没有再次手动刷新**，其已加载 meta 指纹实际从 `ec5afa…` 自动变为 `9c7fd660d2511538b58dc44db6739693224b60235a20668c6f78616f92008588`，与已签名发布/HTTP 完全一致。`browser-3626-auto-ui-update.json` 的全部 1500 显示值及 15 个均值，与独立报告逐项吻合。此标签未设置非默认过滤、未打开 Cache；另一会话的非默认筛选保留不能算成本标签独立观察。

真实网络 TLS EOF 期间浏览器保留 3622 条，见 `browser-3622-network-offline.json`。随后程序自然恢复并更新至 3626；本会话未断用户网络、禁用 TLS 或重启生产。回执和往返延迟仍另核；不能用上述静态通过代替全部队列清空或另一端实际已读。

### PR118 Windows 独立复核暴露关闭端口误判

固定 `480f4a8cc16965984c9b52c69270b93dde539a6c` 的 44 个源码/测试文件，逐 Git blob 与长度校验后在隔离副本运行 `python -X utf8 -B -m unittest discover -s tests/benchmark_sync -v`：**26 项，25 通过、1 错误**。新公平队列、跨重启轮转、信任/blob 变化重验均通过；失败是 `test_handoff_distinguishes_closed_connections_from_live_listener`，`ensure_no_listener(timeout=1)` 在已经关闭的 Windows 回环端口收到 TimeoutError。

`pr118-windows-port-result.json` 保存实际补充探针：真实监听连接约 0.015 秒成功；同一已关闭端口两轮 timeout=1 均超时，timeout=3 均约 2.047 秒返回 WinError10061 / ConnectionRefusedError。原函数仍错误拒绝已关闭端口。本机自动换版已成功，并不能消除此后的冷启动/交接风险。探针仅用隔离临时端口，没有修改生产端口、TLS 或网络设置；未将超时视为安全空闲，修复归正式同步器单写者。

### 独立签名回执与实际耗时

**PR121 修复复核**：固定 `a51b49233f22ec361012c8efb54a739309ebb156` 的45文件逐Git blob校验后，同一Windows/Python3.12环境实跑同步32项，52.235秒全部通过。前次关闭端口/TIME_WAIT失败现已通过，真实占用端口仍拒绝，未知超时仍拒绝；并发读取完整性、限流最长退避、断点复用、缓存界限和安全GET重试均通过。详见 `pr121-windows-tests.json`。这是隔离运行复核；不将其冒充生产吞吐或登录启动实测。

`receipts-first-two.json` 在固定通道提交 `cec6907fdcd995aa694e1f14d0bfb9bb764b2a1e` 独立读取中央原始 Ed25519 回执，不信任本机 `accepted` 字样替代验签。1262…（active）和 10f630…（pipeline）两份的可信根/域/身份/提交内容ID/签名、Git blob 以及本机回执逐字段相等均通过；各有2条来源记录出现在当时3630条的签名快照中。其余5份仍无回执，明确保留 pending。

队列入队至中央回执所列时间分别为606.808秒和519.884秒，包括初始积压、开发换版与自然断连；两个时间来自不同机器，不等于精确网络耗时，也没有包含尚未准确观测的回到本机/页面时刻。不能据默认15秒轮询声称端到端15秒实时。新吞吐修复的收益另以实际持续任务验证。

新增 `src/member_board_sync/receipts.py --sync-state $State --key-sha256 $PinnedFingerprint --output $Report` 可复核固定通道上的现有回执；只读，不上传、重试任务或改状态。独立对抗测试现共10项通过，包含有效签名但错误actor/id/state/domain及签后篡改的拒绝。PR119固定 `faf44fc99b3ee6f8cc1d09ee617abbdda10b4391` 的 Cache 回归另在Windows/Node实际7项通过、`node --check`通过，仍区分函数夹具与真实双机更新。

## 第二次数据更新复核

`snapshot-3209.json` 对 generation 7、快照 `e9dad2e568c23d3d35a55044052503494067ecc94fa028953d58ab47607f67e7` 的复核通过：3209 条全历史、156 种投影、188 次 HTTP、1500 正式格及分母、26 个赢家 Cache 配对。独立核定前一快照的全部 3154 条记录逐字段保留，新增 55 条；原本机 872 条仍与备份完全相同。

已打开的 IAB 未重新加载页面，自动显示 3209 条以及新成绩；1500 个显示值 SHA256 `a23e622e525194e33f152bc75075aaf9ddbcd958f7b41ab2c83e0cff64564c83` 与 15 个均值均和独立计算相符。26 个赢家 Cache 配对与上次 27 个的差别来自赢家变化；历史记录完整保留，不能把赢家配对数下降说成历史丢失。

本次由部署者显式拉取并安装签名快照；证据证明数据安装后的页面自动刷新，不冒称传输已常驻，也没有解决旧标签的代码版本更新。追加历史删除/改写/回退反例后，独立测试共 9 项通过。复现第二报告时用 `--browser-observation .../browser-3209-before-first-reload.json --previous-report .../snapshot-3154.json`，输出另存 `snapshot-3209.json`；旧报告保留。

## 固定输入

- 信任根：[队长本人发布的 PEM](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5816627045)，SHA256 `30ad22b72b3d2d3f291135cd43a640e2704c8fc22990249822d28ef457ccd439`。
- 通道提交：`9354f92a96f3645d63e57884d57a756103bd6a75`，`channels/central.json`，签名 generation 1。
- 快照：`f8ae9d66a149c8994d10935d858f1f51b571396a5566a63e911ee1853362846d`，3154 条；压缩 1,234,265 字节，SHA256 `01cabc5423221eddfa88b2080a4f68c5962c6df44d19c8c3a29071873dc11563`。
- 本机便携网页发布：`c3d43916f7ca54e5760d124c39b69bd22c66939a`；快照发布者记录的中央代码为 `64f26d6fb7da6e7c62f7300ef9953a784a538881`。这两个是不同角色的版本，不能冒称已相同。
- 本机原有 872 条记录账本及切换前 SQLite 备份均以只读模式打开。

## 已测结果

`snapshot-3154.json` 由独立验收程序生成；该程序不导入生产 snapshot/selector 实现。

| 检查 | 结果 |
| --- | --- |
| 签名身份、域、可信根、压缩包及展开内容 | 通过 |
| HTTP 分页全部历史 | 3154 条完整 canonical JSON 相等，包括指标、状态、准入、来源、revision |
| 全部算法/批次与总表，正式/预览各一次 | 138 种投影逐 1500 格相等：赢家完整字段、attempts、状态、缺件提示 |
| 正式总表 | 1500 有效格、1500 已核官方分母、27 个赢家 Cache 配对 |
| 全部事件 | 3154 条相等，cursor 3154 |
| 旧本机账本 | 872 条与备份逐记录相等；SQLite quick_check=ok；全部 ID 存于中央快照 |
| 便携发布 | 24 文件与固定 Git tree/blob 一致；4 个静态 HTTP 资源字节一致 |
| 既有 IAB 页面数值 | 1500 个 `(题目,算例,核数,显示值)` 序列 SHA256 与独立预期一致 |
| 独立反例测试 | 8 项通过：撤回、跨修订过滤、报告不替代正式、身份不符、平分、篡改签名、错误域/密钥、压缩损坏 |

数值 DOM SHA256 为 `7d1a390aa19c7bf2967466747def0c1a3e5e3c91d54ea7d6496b339a4632d7a8`。它只描述默认相对官方单核指标，不代表全部 UI 行为通过。

## 发现的前端更新缺口

`browser-before-first-reload.json` 保存已有 IAB 页面的只读观察：新数据已显示，但仍运行旧版 HTML/JS；`mode-banner` 不存在，旧文案仍为“有原件的有效格”。静态资源 HTTP 已是新版本，也不能证明用户已打开的页面已升级。

此发现已直接通知本机唯一部署会话 s-c909；正式同步程序需要运行版本探测及保留筛选状态的页面刷新。首次受控刷新可以接入新版本，但后续自动热更新仍须真实发布验证。原始观察在验收期间保留，不靠主动刷新抹去缺口。

## 复现

使用既有 Python 3.12、cryptography 和已认证 gh。程序只读取上述本机现有输入；不会重新下载原件、写账本、重启服务、运行 solver/E0 或触发 Actions。

```powershell
python -X utf8 -B -m unittest discover -s tests/member_board_sync -v
# 四个输入路径指向已有 bootstrap、便携发布、原备份和原账本。
python -X utf8 -B src/member_board_sync/audit.py `
  --bootstrap $Bootstrap --release $Release --backup $Backup --local-db $Ledger `
  --url http://127.0.0.1:52341 `
  --key-sha256 30ad22b72b3d2d3f291135cd43a640e2704c8fc22990249822d28ef457ccd439 `
  --browser-observation results/benchmark-board/member-audit-e777/browser-before-first-reload.json `
  --output results/benchmark-board/member-audit-e777/snapshot-3154.json
```

如果页面/快照已更新，旧 DOM 观察不得复用；重新采集观察或不传该选项。程序要求审计全过程 snapshot ID 稳定，有更新则本次失败后按新固定快照复核。

## 尚未验收

正式控制器和双方真实部署、成员新提交到中央签名回执再回到页面、中央新记录到成员页面、连续两次版本热更新、网络断开恢复、重复交付不增记、坏签名/历史回滚拒绝及持久防回退、软件更新失败回滚、Windows 登录自启动。静态报告 `passed` 仅限它声明的固定快照范围。

P1 完整固定64统计是此前独立交付 [PR101](https://github.com/huaweibei123/huaweicup2026/pull/101)，本次没有新增求解或科学复跑。

## 另发现 PR112 接收队列饥饿反例

固定 `577a9a6130279acc93db8b386949a7445e22eb5b` 的 `src/benchmark_sync/engine.py`，SHA256 `484d22eed2f54449301ac4a5f29fed9d819a18917e69554ea0f7a74ac302b82b`。`receive_submissions` 每轮从相同排序开头重新验签已经有回执的提交，8 秒预算到期后直接 break，没有记录续扫位置。

独立最小复现抽取并执行该固定函数，使用纯内存远端、虚拟时钟和 64 条模拟传输信封（63 个已完成回执，最后一个待处理）。每次信封读取/校核模拟 2 秒，连续 3 轮都只读相同前 3 个已完成提交；最后一个永远没被读取，errors 仍为空。**这是调度反例，不是真机传输延迟测量，也没有写入任何科研成绩。** 具体原始输出为 `receive-starvation-577a9a61.json`。

```powershell
python -X utf8 -B tests/member_board_sync/reproduce_receive_starvation.py --engine $ReviewedEnginePy
```

脚本严格核对源码 SHA，不会对其他版本冒称同一复现。建议实现带持久位置的公平续扫，或经过验签的完成项按不可变 blob 身份缓存跳过；不能仅提高单轮时间预算。修复后还应保证网络慢/大批次不能饿死其他成员提交。

## 已打开 Cache 面板没有随数据刷新

固定主库 `c22708c5ae52a6046bbb252853d5884464b8420e` 的 `src/benchmark_board/web/app.js`，SHA256 `723f2f980eb3c1131072343fc1d85f89b5c169d65dab40d78c6f7673637a05c9`。`refresh` 在收到新 snapshot 后只重绘主表和详情，未重绘已经打开的 Cache 对话框；该对话框仅由打开、切换页签、手动刷新或软件重载恢复触发绘制。

`tests/member_board_sync/reproduce_cache_refresh.cjs` 抽取该原始 refresh 函数，使用隔离 Node VM 的 HTTP/DOM 替身。cursor 从 1 更新到 2 后，主表为 2、打开的 Cache 面板仍为 1。原始输出在 `cache-panel-staleness-c22708c5.json`。**这是函数级反例，不是真实浏览器或传输延迟实测，不向生产导入模拟成绩。** 应在数据变化时更新打开的面板并保留模式/滚动位置。

```powershell
node tests/member_board_sync/reproduce_cache_refresh.cjs $ReviewedAppJs
```

正式安装后的只读验收入口已准备为 `audit.py --sync-state $State`：独立验签数据和 active 软件、核全部 Git 文件、确定性 HTML/meta 与 runtime UI 指纹；其真实部署执行结果待安装完成后追加，不以工具已写好代称已通过。
