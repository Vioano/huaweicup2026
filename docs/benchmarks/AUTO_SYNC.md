# 方案成绩台：双向自动同步 v1

用户授权：队长与 Fang 的数据、UI 自动同步，双方继续研发并提交 benchmark；正常同步不调用模型。维护 session `nikolastarx/s-c04feaf0736b49fa838f7fed36c9f5a2`；网页/中央接收器由 s-7c98 维护。

## 数据路径

```text
队长各研发 worktree ─┐                              ┌─ 队长成绩台
                    ├→ 本人持久 outbox → 签名提交 → 中央校核账本 ┤
Fang 各研发 worktree ─┘                              └─ 签名全历史快照 → Fang 成绩台
                                      ↑签名回执回到提交人
```

数据是双向生产、汇总后共享。只有中央账本决定准入；各端 SQLite 不相互覆盖或合并。成员视图保留全部成功/失败/待核/撤回历史和算法来源；显示“中央已核”，不伪称成员本机重跑或核过每个原件。原件固定 Git 链接按需打开。固定提交的目录树以最多16项LRU缓存保留，不因发布快照/回执清空，以免反复下载科研目录元数据。初始3154条快照约1MB；原件不因压缩快照被删除。

研究过程仍按 `SUBMISSION_PROTOCOL.md` 写 `board-feed*.json`，包含算法来源、实际固定代码版本、E0或已获准E1、端到端求解墙钟、外部评价墙钟和原件hash。自动发现只监看配置的本人仓库及其已登记 worktrees 中 `results/**/board-feed*.json` 的**已提交 Git 版本**，要求每条 `provenance.producer_session` 属于本人。原有正式历史ID全在快照中则跳过。未提交/临时写到一半的数据不发布；科研程序仍须按团队流程完成原件及 Git 提交。不自动运行求解器或修改研究分支。

提交完成后普通程序自动发现、校验完整字节、保留持久 outbox，必要时将固定提交非强制推到本人的唯一 `benchmark-delivery/<actor>/<id>` 引用，再将签名描述发布到 `benchmark-sync-v1`。原件路径先从固定提交树分组解析，再用 `git cat-file --batch` 有界分批读 blob 并逐项核对长度和 SHA-256，避免一个feed的每个原件都单独启动 `git show`；成员系统会检查实际队友仓库版本上的批量性能。其他用户分支和工作区不改。主库已存在的固定提交不重复推送研究历史。也可明确入队：

```sh
python -X utf8 -m src.benchmark_sync --config /outside-git/config.json enqueue --repo /research/repo --commit FULL_SHA --feed results/.../board-feed.json
```

新算法不需要维护者逐次修改来源分支白名单才能输送；仍须给完整协议和来源，算法科学验收不因输送成功而免除。

## 传输、信任和失败

- `benchmark-sync-v1` 是小对象 Git 分支，程序通过 GitHub REST 读固定 blob/tree；网页查看不克隆研究历史。只用既有免费 Git/REST，无 Actions、第三方收费设施或模型轮询。
- 每人使用自己已登录的 `gh` 身份。Ed25519 由已安装 Node 的内置 crypto 实现，无 npm 包。私钥、配置、队列、缓存、快照和运行状态在所有 Git 工作区之外。专用 benchmark 密钥与 Atlas 分开，不覆盖 Atlas 身份或权限。
- 中央公钥首次通过队长本人 Issue33 固定消息及 bootstrap 固定源码核对；成员公钥需由该成员本人 GitHub 身份登记一次，队长实际核对后加入 `trusted_keys`。来包不能自授信任。签名按 snapshot/release/submission/receipt 分域；公钥变化默认拒绝。
- 内容用 SHA-256，Git blob另校Git对象hash；固定提交、签名代数和全部旧记录分别核查。中央优先复用本机仓库已有的同一Git blob对象：对象ID仍来自远端固定tree，读取前限制大小，读取后同样核Git hash、长度和提交所列SHA-256。缺少对象才下载；不读工作文件、不fetch或切分支，也不要求成员克隆完整科研库。缺记录、历史改写、回退、相同代数不同内容均拒绝；保留最后可信页面。坏 outbox独立隔离，有效邻居仍处理。
- 每个submission用稳定内容ID，重试和入账后回执丢失不产生第二份历史。`accepted` 只表示中央接收完成，正式eligible/待核/失败另由已有接收器判定，不能把HTTP成功或签名成功当官方算法验证。
- 中央原件下载最多4路并发，每个文件单独校验并原子落盘；已完成文件断点复用，遇到限流统一保留最长退避时间。安全GET的瞬时断连最多尝试3次，证书错误、请求超时、HTTP拒绝与不确定写入不作瞬时重放。先完成各字节/hash，再原子发布 `inbox/<id>/request.json`；只有网站进程同一个 Ledger worker 接收入库。网络缺字节不能误落为永久reported。队长离线则成员排队，不能承诺两台机器离线仍实时。
- 接收器优先处理未有回执的提交，在8秒调度预算内持久轮转；本轮无回执提交超过4份时使用30秒有界处理窗口；中断的大包下次续传，其他待办仍获得处理机会。已验签的完成项只有提交blob、回执blob及受信公钥集合均不变才跳过重复验签；变化后重新核验。调度缓存损坏只重置调度提示，不改账本或快照。
- 每个已提交的完整feed进入持久outbox后即参与下一轮签名传输；在线时双方同步器最多每2秒检查一次远端及本地已提交worktree。每轮固定一个远端head用于数据接收/发布/回执扫描，完成轮次后按起始节拍等待；慢轮次不会再额外叠加整段2秒等待。`status.json` 持久报告当前同步阶段、阶段开始时间、各阶段最近耗时和整轮耗时；`runtime_stage` / `runtime_stage_timings_ms` 另显示接收网站release与检查已批准main代码，便于发现软件检查对数据轮询的阻塞。central 的 main 代码分支每5秒检查，只有SHA改变才fetch/构建签名release；打开的新版页面每5秒检查软件指纹，数据视图每1秒读取已验签快照，中央接收器仍每2秒排空本地inbox。没有“凑够500条再发送”门槛，也不要求每个科研run覆盖500个格：任意大小的完整feed按各自attempt/revision立即追加，后续补片继续追加，旧历史不会被覆盖。GitHub说明，正确授权的条件GET若返回304，不计入REST primary rate limit（[官方文档](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#use-conditional-requests)）。轮询间隔不是端到端硬保证：原件体积、验签/准入、网络、限流和离线会增加耗时；状态页分别显示最后成功时间、队列和错误。
- 高频空闲检查使用 GitHub REST 条件请求（ETag）；已对固定 `benchmark-sync-v1` ref 验证 `304 Not Modified`，可避免每轮都下载tree和快照。 有新 HEAD 时，快照/版本通道读取和条件写入只解析所需路径的非递归目录树，不随历史快照、增量对象及回执总数下载整个递归分支树。遇到更新才读取变化对象或写新签名快照；403/429、`Retry-After`及离线指数退避仍优先，失败不忙轮询、不降低验签要求。

#### 任意大小补片的低延迟路径

没有“凑够500条再发送”门槛，也不要求每个科研run覆盖500个格：任意大小的完整feed按各自attempt/revision立即追加，后续补片继续追加，旧历史不会被覆盖。队长同机同步器先验证本人签名、固定commit、producer身份及feed/原件SHA，再将同一submission ID的完整请求写入唯一中央inbox；远端签名传输同时继续。相同submission ID的本地与远端物化由per-ID锁串行，request marker始终最后原子发布。中央Ledger仍是唯一准入写者，本机快路径失败时远端通路继续。中央接收器每0.25秒检查本机已完整落盘的inbox。

远端收件优先处理最近首次发现的pending交付，每四个新件至少处理一个旧pending，持续新数据不会饿死旧队列。本机上传每轮先处理完整的新交付，再检查最多16个旧待回执项，并按上次检查时间轮转旧项；数百个旧回执不能独占上传线程。固定源仓库按commit root逐目录查询非递归Git tree，避免GitHub递归整树截断；固定commit和目录tree按SHA有界缓存。需分别测量E0完成到固定feed提交/入队、中央准入/签收、快照生成/发布、两端验签及双方原页面完整可见时间；轮询频率不代表端到端延迟保证。

中央在完整快照上传前先向独立 `channels/fast.json` 发布已签名的增量对象；它以最近已发布的完整快照为基点，携带新增的完整记录和当前来源状态。成员必须验签、核增量字节哈希、重建整份快照并核对签名中的完整未压缩内容哈希，再给本机压缩字节计算独立存储哈希，才原子替换 `accepted/current.json`；不同系统的 gzip 头部字节可以不同，旧记录仍不得改写或丢失。原 `channels/central.json` 完整快照继续发布，供首次连接、断线恢复和旧版本读取，增量失败也不修改已验收的当前视图。真实 50 格片从 11278→11328 条记录的样本中，完整 gzip 为 6,004,223 B，同内容增量为 102,814 B；这只是传输量比较，实际双端延迟仍以线上原页观察为准。

## 网站代码更新

网页/接收器/同步模块及必要小JSON/协议组成独立签名ZIP，不打包科研数据。中央发布器只跟踪审查合入的 main 相关文件；无关文件变化不会生成新release。成员先验签和每文件hash、限制展开范围/大小，再隔离启动候选、核对HTTP实际资源；通过后才切原端口。失败恢复上一可用版本，不删除原账本。正常服务启用后只能由同一supervisor管理，不能再手开另一个写库进程。

已打开页面比较实际UI资源指纹，发现部署变化后保留筛选/详情/滚动并重新载入。数据更新由同一页面读取新快照。软件desired是已收到候选，active/health=ok才是实际运行；二者不混同。

稳定 `start.py` 持有独立 `launcher.lock`，在原生登录任务的同一等待进程下接续监督器。监督器升级先检查候选监督器可导入及交接协议、候选页面和正式端口健康，再以退出码75交回父进程；退出前停止自己拥有的网站/worker并释放 `supervisor.lock`。父进程从已核准active启动新监督器，不调用Agent，不重新创建登录任务。新监督器在ready之前退出则将软件active退回previous并拒绝该候选，账本/快照/队列不回退。异常退出带退避；不同launcher不能并行拥有同一状态。

`software/supervisor.json` 单独报告实际进程PID、代码根目录、release/commit、启动时间、子进程PID与ready/handoff状态。它与网站active版本分别核对，不能用子进程已换版代替监督器自身换版。`software/launcher.json` 标明固定父进程PID和当前监督器PID。Windows/macOS同用这条交接链。

Windows短暂读句柄/杀毒软件占用引起WinError5/32/33时，原子替换最多10次，总等待2.62秒；期间保留旧目标，始终不先删目标、不改ACL。持续拒绝及其他I/O错误仍报错，保留可信旧状态；这不是绕过权限。监督器和worker使用同一实现，稳定launcher也含该实现。

**既有旧启动器的一次迁移**：旧版本只subprocess.call一次，更新磁盘start.py不会改变已运行父进程。两端唯一部署者在此补丁正式签名发布后，先保留旧start.py与进程树/软件状态；仅从已核验active release执行 `from src.benchmark_sync.install import launcher; launcher(state)` 更新start.py，再在原生服务已有入口执行一次受控停旧/启动。不得重复install覆盖Fang既有WScript等待包装、创建第二任务或手工拷贝未审核源码。确认launcher protocol=1与实际监督器路径/版本后，后续升级不再需要人工重启。测试需至少再经过一次真实签名版本自动切换才能称迁移验收，不把这次手工冷启动算成自动升级。

## 一次性接入

需要本人现成 Python3.12、Node、gh和Git；没有时先报告实际环境，不冒称已安装。队长会给 bootstrap.py 的固定提交链接，成员只取这一个文件，无需全库fetch：

```sh
python -X utf8 bootstrap.py --state D:/benchmark-sync --watch-repo D:/research/huaweicup2026
```

状态目录必须在Git之外，磁盘足够容纳轻量网站、完整压缩视图和本人待传批次。脚本不删原账本、不会杀52341现有进程，不会向Issue自动发消息。它下载并核验release/快照，生成本人的专用私钥，只输出公钥及指纹供登记。原872条等成员账本完整保留作原件核验记录；新页面在独立 member-board 状态中读取中央完整快照。

完成公钥登记后，维护者在本机一次性受控停止旧网站服务及旧重复导入控制器，保留它们的恢复入口；然后在已下载release的根目录执行：

```sh
python -X utf8 -m src.benchmark_sync.install --config D:/benchmark-sync/config.json --start
```

Windows为当前用户创建登录计划任务 `HuaweiCup-Benchmark-Sync`；macOS为当前用户创建 `com.huaweicup.benchmark-sync` LaunchAgent。不需要管理员或密码，不使用Codex自动化。未登录/电脑关闭属于离线，队列下次继续。`start.py`也可前台诊断。

队长使用leader配置，配置原ledger路径、同一inbox及发布代码源；必须先协商原服务受控交接，再启动同一端口监督器。禁止同时启动第二个中央写者。

## 状态与验收

`accepted/current.json`是已校验完整快照的原子指针；`status.json`含最后成功时间、数据版本/数量、软件实际版本、队列数量、本轮无回执提交数/处理窗口及阶段错误。网站使用 `serve --mirror <current.json> --sync-status <status.json>`；中央使用 `--sync-inbox` 和同状态文件。

上行传输可将最多16个已分别签名、具有独立submission ID的feed envelope放进同一个Git传输提交；源feed和原件仍分别按各自固定提交、路径及SHA256核验，每个submission仍有独立回执和准入结果。传输层合并提交只减少GitHub API分支更新次数，不合并成绩、不要求凑满记录数；队列里不足16个也立即发送。

常驻leader运行时，远端提交收件与前台签名快照轮询分开：一个单写者收件线程处理固定HEAD上的提交，主轮询仍可接收/验签新快照并发布已准入的ledger变化。`once`诊断模式保持同步收件；状态同时报告`receive_worker`阶段和收件错误。两条路径在Git引用上的并发更新仍使用同一CAS保护。

本机单测与GitHub读回不是双人Windows验收。最终验收必须分别记录：双方当前UI资源指纹、签名release ID、数据snapshot ID及全部记录ID集合；双方各一份真实既有benchmark的自动投递/签名回执/两端读回；断网重连、重复投递、UI升级失败回滚和真实Windows自启动。持续热更新验收还要实测一条feed从固定提交到中央准入签名、再到两端原浏览器可见的端到端时间；新记录ID/规范内容集合两端完全一致，未完成状态不可提前报已同步。实验成绩不得为了“测试同步”新增或伪造；可以重复投递现有固定feed，预期added=0。
