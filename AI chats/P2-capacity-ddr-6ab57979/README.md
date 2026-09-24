# P2 容量 / DDR 专项 Pro 会话

- 来源：[P2容量DDR算法审计](https://chatgpt.com/g/g-p-6ab540961238819181aa53e685fdb456-huaweicup/c/6ab57979-aa78-83ee-bc0d-da8c426d737a)，位于用户本次指定的 huaweicup project，最高 Pro 档位。
- 负责人：session=yuanzhifang30-sudo/s-eb28fa11a5664fdfbdd29b3d6e38ca24；仅 P2。未复用或向 P1/P3 网页会话发问。
- 最新完整公开问答：[snapshot-20260924T202923Z.md](snapshot-20260924T202923Z.md)；包含 2 次用户提问、2 次公开最终回答。第一轮是研究，第二轮仅补交已有代码。保留上一快照，未导出折叠思考内容。
- 第一轮公开回答 ID：477e57c6-8e2c-4911-ab67-886b69336e52；第二轮：c9da08bb-2b0c-4060-bb3a-e3729f3fc031。read_thread 返回 hasMore=false；第一轮 message ID、首尾、章节及最终完成状态与浏览器 DOM 交叉核对。公开回答长度分别 15,351、12,979 字符，均小于接口每项 20,000 字符上限。
- 用户上传资料为已有 P2-capacity-ddr-evidence.zip（718,196 B，SHA256 bb50fbb4e69f3ad5acc2094f1ef93223644dca4545ec747b258312164015d4b4）；内容来自冻结官方45f647、solver384b6c2及归档结果，不重复下载/归档原始赛题。
- 两份脚本从第二轮完整公开代码块原样保存到 附件/，本地字节数、SHA256 与作者公布的值一致。它们是 Pro 作者原件，不能因入库就视为已审查生产实现。
- 原 ZIP 和其余附件的下载按钮可见，但本客户端未返回可用本地下载文件；page content export 不支持、download event 超时、pageAssets 不支持 other 类型。**ZIP 字节、报告 Markdown 和其他 25 个 ZIP 条目尚未取得**。页面报告预览已打开，但预览不冒充原文件。原 ZIP 自报566,335 B / SHA256 2af2e94a7a0cc55f7588504ffe67d745120dd87ad8e92423ccac88a15b26361a，尚未本地核验。
- 结论分层：四计划重放、两图 probe 与 L/U 数字当前仍为 Pro 环境报告。本地独立静态审阅见 [源码审计](../../docs/a/q2/PRO_CAPACITY_AUDIT_20260925.md)：COPY 计数与有条件 Step2 容量判据可用；无条件机器浮点严格 L/U 声明需收紧。尚不据此宣称均值提升或全局最优。
- 原始第一轮问题曾描述014/k5的30秒失败；之后固定60秒恢复预算下已有成功记录，这不覆盖旧失败，也不是作者回答已知事实。后续实现/实测以新的实验记录为准。

