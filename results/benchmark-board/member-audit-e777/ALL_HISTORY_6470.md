# 全历史续验：6470 → 6472

执行者 `yuanzhifang30-sudo/s-e777d827b5af4adfafd148ff3a4fae8b`。这次是对[队长5962检查点](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5819724407)和[c909的6468检查点](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5819870868)的有限续验，不重复启动实验，不修改生产服务。

## 独立验证结果

- `all-history-6470.json`：全部6470条HTTP记录与当前队长Ed25519签名快照逐条canonical相同；142批次，P1/P2/P3为38/79/25。历史5962条、6468条均逐ID/内容完整保留，各新增508、2条。
- `all-history-6472.json`：随后真实P1提交新增2条，全部6472条再次逐条通过，144批次为40/79/25。HTTP读取前后同一快照 `94ee4f369d9d6446a4d0235189a42fc0c6cb45bf89dcc41ee0c53835475e0591`；record SHA `888e29bb6a9baf28e854061ab8a2301283a7a23e792aa169886c22639f79e9a7`，IDs SHA `2a23423a33b78a897ff29a3756d1b0911f564bfe559e5a0bd682c637eef7e200`。13页全部历史与144批次均缺0、多0、内容/数量差0。
- 当前代码 `922c3c38ef89142e2ebb38697519958f554a685a`，签名发布 `a2cbb0c80c4fb536df7b936591f5ae9370a1073923624ea1a34af1277b075ab9`：33个安装文件hash/size逐项相同，4个实际HTTP静态资源逐字节相同，runtime版本/健康/UI指纹和快照中央publisher代码相同。
- 独立选择器重算的1500格完整body与HTTP相同。四个原有IAB标签没有手动reload或导航，自然从6470→6472；总览1500加三页各500显示值共3000元组hash均与独立计算相同，UI均为 `64c3539c565fab3ff7c2a09b3d24cf9ebf98f747e311112ce206d093eb883032`。P3本次显示2/25张卡，前次显示25/25，保留当时界面选择，不将过滤后的显示数量当丢批。页面证据分别见两份 `browser-all-history-*.json`。
- P3真实500个attempt均含revision1和2，原记录都保留，latest折叠仅计最新版本。逐对检查metrics完全相同、status均ok；变化为来源/备注/参数及记录元数据。这是来源补充，不能说成加速。
- 初次后续扩展检查跨越6470→6472更新而中止，未算通过，见 `all-history-interrupted.json`。原6470签名/全历史通过记录保留；其离线DOM期望格式从2位修正到页面实际3位后核同。新代码完整运行在6472固定窗口通过。

## 延迟与范围

6470快照生成→本机verified差29.934765秒，属于同内容重发布观察，不是新增首达时间。6472对应差23.231027秒。c909另外报告此次P1 Stage H：18:42:41.528675Z排队、18:43:09.131063Z中央签名接受add2、18:43:16.556913Z生成、18:43:39.787940Z本机验收，总58.3秒；其中排队/回执时间是部署会话报告，本次未独立重新验签该回执。未计量网页首帧，也未消除双机时钟偏差。不能宣称瞬时或保证固定上界。

本次批次审计覆盖所有最高revision后的run集合、逐批record_count、k5范围attempt/status数量；不重新认证新版全题资格、全部排名规则或其他核数排名。历史旧快照的封套未单独取得，使用原Issue固定hash及新签名快照逐条不变包含证明；当前封套已独立Ed25519验证。原件/E0不重评，页面中的历史最优均值不替代同一固定算法全500正式成绩。旧完整版排名、异常/回退及原872账本证据继续见先前报告，不能将它们冒充新版本所有功能复测。

## 复现与阅读记录

`python -X utf8 -B src/member_board_sync/history.py --sync-state <现有正式状态目录> --url <已有服务URL> --key-sha256 30ad22b72b3d2d3f291135cd43a640e2704c8fc22990249822d28ef457ccd439 --output <新报告>`。不导入生产模块；分页最多4个并行只读GET。持续写入跨检查窗口时应记录inconclusive，不能冻结生产或捏造同快照。

Windows/Python现有环境；独立验签/反例测试 `python -X utf8 -B -m unittest discover -s tests/member_board_sync -q` 实际10/10通过（0.028秒），不声称这10项覆盖全部新程序。无新增solver/E0调用、无Actions、无子Agent。本次check --full已抓475条，但实际按本任务阅读上述Issue33原文和相关部署消息，不代签全账号已读。

已读子Agent策略固定 `0a97785fae0df0354424c5d760914c7c9ae2d3ac:AGENTS.md` 的新增节：常规补格/哈希Luna medium、一般实现Sol、关键难点按需Astra；本会话此次不派子Agent、不增加评价预算、不重跑实验，也不宣称硬token上限。后续若实际派工再记录软/硬预算、上下文与停止条件。
