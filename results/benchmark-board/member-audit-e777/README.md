# 成绩台独立成员端验收

执行者：`yuanzhifang30-sudo/s-e777d827b5af4adfafd148ff3a4fae8b`，Windows / Python 3.12.14。

本目录证明 **2026-09-24 的固定签名快照与本机接口一致**，不证明最终双向自动同步、代码热更新或算法重新评估已完成。研发上下文已读，不宣称盲审。

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
