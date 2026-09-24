# 方案成绩台双向同步与热更新：本轮验收

本轮功能验收完成。两端采用同一正式签名软件，成员原浏览器自动取得新版UI；稳定启动器保持，管理进程和网站/同步子进程实际自动换版。以下结论固定到具体检查点，不把持续产生的新科研提交冒称已全部即时签收。

| 项目 | 实际结果 | 证据 |
| --- | --- | --- |
| 正式代码 | 两端 `6fcec11ccc472a1a652b21feb6fccf85a4555598`，release `846b6b324d7cf9b306fb60f5736b9cfb14637f8c69050b1742a933120430e106` | formal-runtime-focused-ui.json；队长Issue33评论5818746330 |
| 完整数据 | 成员3794条canonical记录、3794事件与签名包逐项相同；数据hash `a6850587cf94a9250da8b5e80155364a707e6e7db16c038361cff39f75acedde` | formal-runtime-focused-ui.json，17:21:37–17:22:56 UTC |
| 两端对应 | 队长实读3789条全部body与中央SQLite一致；其hash `d2c4d9b7cd84b915201cd3a32d612d9c878c19c95bd57fa804269efc10c6102f` 与成员保留检查点相同，且完整、不变地包含于成员3794 | captain-final-checkpoint-prefix.json |
| 历史保留 | 先前3633条逐记录未改，新增161；原本机872条与原备份完全一致，全部ID在中央，SQLite quick_check通过 | formal-runtime-focused-ui.json |
| 静态与数值 | 33发布文件与签名/hash/固定Git blob一致；4个HTTP资源一致；正式/报告预览各1500格与独立选择器相同 | formal-runtime-focused-ui.json |
| 实际页面 | 原标签无手动reload自动取得UI `30933be6e5092ca915cf40dfc54b4b6450cc26709f8fb5e746e918e7fb4f7cb2`；总览1500值与15均值吻合，三focus页各500格拼接逐值相同 | browser-focused-ui-3794.json |
| 新批次端点 | 3789固定签名输入，3题×5核×全100/001–025两范围，全部批次、来源、覆盖、失败状态、均值与排序共30组独立核对通过 | batches-focused-ui.json；batches.py不导入生产模块 |
| 实际后台换版 | WSH24612与launcher33652创建时间不变；sup37984→37464，实际新代码/路径6fcec/846，worker34460/site27876属新sup；旧sup与子进程退出 | supervisor-migration-baseline.json、supervisor-automatic-ui-upgrade.json |
| 双向与去重 | 原先11笔成员提交均已真实签收；StageC added24（23ok、1timeout、23eligible）及重复added0均独立验签/来源对应。最终扫描14份中央签名，13份已与本地accepted完全一致，1份中央accepted尚待本机持久回读；另1份新提交queued | receipts-stagec-accepted.json、receipts-final-ui-checkpoint.json |
| Windows修复 | PR127+122组合固定0eab全套43/43，0跳过；实际占用释放/持续占用、真实子进程换版与回退都执行 | pr127-merged-windows-tests.json |
| UI检查 | 新批次/focus9项及Node11项通过；P1完整批次切换、覆盖式详情前后表格几何不变、Esc回原格焦点、返回组合实查 | pr126-focus-windows-tests.json、browser-focused-ui-3794.json |

P1最新100×5格、完整精度均值、DDR、分别计时与固定来源已保存至 [p1-checkpoint-3794](p1-checkpoint-3794/README.md)。1–5核的均值依次为1.0240076820、1.7560468588、2.3996672623、3.0217155906、3.7074167462，每项100例。这是跨算法历史最优组合，未追加solver/E0；单一完整固定64批次的全量统计仍在PR101，二者不混算。

## 验收边界

- 同步程序独立常驻，健康空闲默认15秒轮询，页面5秒读取本机；大原件、网络、限流和离线会增加端到端时间。本轮修复后的三笔实签回执区间约73、82、104秒，跨机器时钟计时不是精确网络延迟或硬时限。新数据继续自动排队，不要求生产停住或队列永远为0。
- 旧启动器迁移是部署者的一次必要人工操作；它之后的正常新版UI发布才是本轮真实自动换版证据。没有用手动重启/刷新充作自动升级。
- 最新长时间全算法/run筛选巡检遇到3789之后的正常数据更新，按快照守卫中止，记录为inconclusive；最终3794核了全部raw记录/事件、默认两模式和所有数值，新增批次端点另有30组证据。早先138/156组全筛选结果仍按其历史版本保留，没有冒称最终长巡检全部通过。
- Windows网站44项中43个不同测试通过；1个既有symlink逃逸测试因本机不能创建该夹具（WinError1314）未执行。没有提升权限、修改断言或假报44/44；中央macOS结果由队长自身证据承担。
- 原Task已实际受控启动并保持真实等待链；未登出/重启电脑验证登录触发，不为此打断用户工作。成员镜像校验不等于本机逐原件重跑官方E0或科研结论终验。

完整目标的实际状态由本文件汇总；早期反例和待修描述保留在历史证据中，以对应固定版本理解。本人审计范围未修改生产服务、信任根、密钥、队列或账本；所有修复由原作者PR和正式签名通道交付。
