# 数模任务卡：huaweicup Project 聊天归档复核

负责人：@NikolaStarx（会话 `nikolastarx/s-fd4d197f9f6c4774bd20e2aebd99b8fd`）

分支：`codex/archive-pro-project-20260926`

沟通 Issue：[会话登记 #26](https://github.com/huaweibei123/huaweicup2026/issues/26)

1. **任务目标**：逐个复核 ChatGPT `huaweicup` project 当前可见聊天，将问答、附件原件、来源与缺口按 `docs/CHAT_ARCHIVE.md` 归档，供论文研究定位。
2. **输入文件**：该 project 当前选中分支的浏览器可见内容、`AI chats/` 既有快照与来源收据，以及项目其他工作树中已取得的原件；不改赛题与官方评估数据。
3. **输出要求**：`AI chats/PROJECT_INDEX_20260925.md`、逐会话稳定目录、版本快照、附件与 SHA-256 清单；提供校验命令和缺件列表。
4. **限制条件**：不将网页预览或同名本地文件冒充原件；不将 Pro 回答当成定理证明或实验成绩；保留旧快照、停止/无答复记录及勘误。仅在本分支写归档和核验文档/脚本。
5. **验收标准**：project 列表与目录一一对应，逐会话首末消息和轮次核对；已落盘文件 SHA-256 与 ZIP CRC 通过；不可取得的附件逐项列明且不宣布原件齐全。
6. **截止时间**：本次交付于 2026-09-26（Asia/Taipei）完成；网页后续新消息另追加快照。

## 交付记录

实际命令：`python3 scripts/verify_project_chat_archive.py`；`git diff --check`；对新增 ZIP 执行 CRC 检查。

代码提交与输入版本：见本分支最终提交 SHA；浏览器范围与首末 ID 见 `AI chats/PROJECT_AUDIT_20260925.json`。

结果与图表：逐会话索引与原文见 `AI chats/PROJECT_INDEX_20260925.md`；本任务无图表。

结论及限制：已核当前 project 列表的 15 个聊天；部分网页附件无法取得原字节，按目录清单保留缺口。

未验证项：服务端已删除历史、未选中的重新生成分支、缺失附件原字节及 Pro 数学结论的独立证明。

PR：[归档复核 #214](https://github.com/huaweibei123/huaweicup2026/pull/214)。
