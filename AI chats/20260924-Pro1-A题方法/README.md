# Pro1 · A题方法

[完整问答](%E5%AE%8C%E6%95%B4%E9%97%AE%E7%AD%94-20260923T195552Z.md) · [消息核对](%E6%B6%88%E6%81%AF%E6%A0%A1%E9%AA%8C-20260923T195552Z.json) · [原会话](https://chatgpt.com/g/g-p-6ab2d820c86081918067a0c6d5eb1ab6/c/6ab2d851-0348-83e8-ab24-02db57b01aea)

完整保存当前分支的提问与公开回答，按消息 ID/角色/顺序与独立会话清单对齐。三个首轮超长回答越过读取接口的 20000 字符上限，使用完整网页补齐；摘要不代替原文。原生引用标记如无法映射，原样保留并附网页实际来源链接。

用户上传材料只保留名称/上下文，不另下载。下方只收 AI 生成附件；ZIP 内附带的输入原件作为原包组成保留。所有程序均未因归档而执行；字节/CRC 校验不等于研究结论通过。历史 295 份 result.json 缺口没有被这次归档补造。

本次是首次完整快照；之前分散的摘要/研究原件继续保留。后续追问或修订追加 UTC 文件与 versions 记录，不能覆盖本快照；README 可更新最新入口。未导出隐藏推理、删除消息、未选中的其他分支。

## AI 生成附件

| 原轮次 / 名称 | 本地原件 | 取得方式 |
| --- | --- | --- |
| r03 / npu_static_audit.zip | [文件](%E9%99%84%E4%BB%B6/r03-npu_static_audit.zip) | original downloaded ZIP bytes |
| r03 / README.md | [文件](%E9%99%84%E4%BB%B6/r03-README.md) | original bytes extracted from downloaded AI ZIP |
| r04 / CODEX_HANDOFF.md | [文件](%E9%99%84%E4%BB%B6/r04-CODEX_HANDOFF.md) | original bytes extracted from downloaded AI ZIP |
| r04 / AUDIT_REPORT.md | [文件](%E9%99%84%E4%BB%B6/r04-AUDIT_REPORT.md) | original bytes extracted from downloaded AI ZIP |
| r04 / NPU_A_Strategy_Codex_Handoff.zip | [文件](%E9%99%84%E4%BB%B6/r04-NPU_A_Strategy_Codex_Handoff.zip) | original downloaded ZIP bytes |
| r05 / RESEARCH_MEMO.md | [文件](%E9%99%84%E4%BB%B6/r05-RESEARCH_MEMO.md) | original bytes extracted from downloaded AI ZIP |
| r05 / LITERATURE.md | [文件](%E9%99%84%E4%BB%B6/r05-LITERATURE.md) | original bytes extracted from downloaded AI ZIP |
| r05 / NPU_A_Math_Structures_R2.zip | [文件](%E9%99%84%E4%BB%B6/r05-NPU_A_Math_Structures_R2.zip) | original downloaded ZIP bytes |
| r05 / EVIDENCE_INDEX.md | [文件](%E9%99%84%E4%BB%B6/r05-EVIDENCE_INDEX.md) | original bytes extracted from downloaded AI ZIP |
| r06 / RESEARCH_MEMO.md | [文件](%E9%99%84%E4%BB%B6/r06-RESEARCH_MEMO.md) | original bytes extracted from downloaded AI ZIP |
| r06 / RESULTS.md | [文件](%E9%99%84%E4%BB%B6/r06-RESULTS.md) | original bytes extracted from downloaded AI ZIP |
| r06 / EVIDENCE_INDEX.md | [文件](%E9%99%84%E4%BB%B6/r06-EVIDENCE_INDEX.md) | original bytes extracted from downloaded AI ZIP |
| r06 / NPU_A_Structural_Prototypes_R3.zip | [文件](%E9%99%84%E4%BB%B6/r06-NPU_A_Structural_Prototypes_R3.zip) | original downloaded ZIP bytes |
| r06 / README.md | [文件](%E9%99%84%E4%BB%B6/r06-README.md) | original bytes extracted from downloaded AI ZIP |

轮次 rNN 对应原会话第 NN 个用户提问；同轮多条回答分别保留 message_id。同名文件用轮次前缀区分，清单保留准确 sandbox 原路径、来源回答和 SHA-256。

超过 48 MiB 的原 ZIP 只按字节切片，未重新压缩；按 part000、part001…拼接即可恢复同一 ZIP。可在仓库根使用 `python3 scripts/export_chatgpt_archive.py restore <新ZIP路径> --sha256 <manifest原ZIP哈希> <按序排列的part路径...>`，还原后会校验原 SHA-256。不自动解压或执行附件。
