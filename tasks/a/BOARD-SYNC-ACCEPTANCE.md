# BOARD-SYNC-ACCEPTANCE：成员成绩台独立验收

负责人：@yuanzhifang30-sudo，session `s-e777d827b5af4adfafd148ff3a4fae8b`

分支：`codex/board-sync-audit-e777-20260924`

沟通 Issue：[方案成绩台 #33](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5816797523)

1. **任务目标**：独立验证成员端与队长签名快照的全历史、投影、前后端发布版本一致性；最终目标还包括双向自动更新与代码热更新，不用静态验收代替动态验收。
2. **输入文件**：Git 外现有 compact-bootstrap 的中央公钥、签名封套、current.json、压缩快照、release-files.json；旧本机 SQLite 备份与保留账本；运行中的只读 HTTP。可信公钥指纹以队长 [本人发布消息](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5816627045) 为根。
3. **输出要求**：`src/member_board_sync/audit.py`、独立反例测试与 `results/benchmark-board/member-audit-e777/` 证据；每次结果固定快照 SHA 与代码 SHA，注明未验收项。共享通过本分支 PR 与 Issue33。
4. **限制条件**：s-c909 是本机网站/状态唯一写者；本会话不重启、导入或覆盖其服务。不修改中央生产代码，不运行 solver/E0，不触发 Actions。只读验证原件一致性不等于算法科学验收。使用本机已有 Python3.12 与 cryptography，不新增依赖安装。
5. **验收标准**：签名域/身份/可信根、压缩哈希、全部历史内容、算法/批次正式与报告预览、事件流、原账本保留、HTTP 静态资源全部比对通过；已加载页面与签名发布版本单独检查。双向往返、真实发现到页面延迟、坏签名/回滚/断网恢复/重复交付、软件更新失败回退需正式同步程序接入后独立记录。
6. **截止时间**：按用户要求尽快，2026-09-24 开始；不虚报未完成事项。

## 交付记录

2026-09-25最终：本轮功能验收完成，实际范围与局限见 `results/benchmark-board/member-audit-e777/FINAL_ACCEPTANCE.md`。已核正式3794全部记录/事件、原872保留、两端固定检查点对应、33发布文件、浏览器1500值、30组新批次投影，以及同父启动器下监督器和子进程真实自动换版。最新P1全500已导出并共享；后续科研新增按常驻队列继续，不冒称队列永远为空。

独立程序不导入生产 `benchmark_board` 或 `benchmark_sync`。投影规则经生产源码和公开契约核对，属于独立实现复核，非盲审。

2026-09-25续验：针对队长5962、c909的6468检查点，以更新的6470条签名快照独立复核全历史、142批次、500对真实P3修订和自动更新的四个页面，见 `results/benchmark-board/member-audit-e777/ALL_HISTORY_6470.md`。仅新增范围，不重跑 solver/E0 或改写生产服务。新鲜数据首达延迟仍由生产维护者跟踪，不能以一次同内容重发布的30秒观察宣布即时同步。

实际命令、输入版本、结论与限制见结果目录 README；早期“等待正式控制器接入”为历史阶段，后续证据以注明的固定检查点为准。
