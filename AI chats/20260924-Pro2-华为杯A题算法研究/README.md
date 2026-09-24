# Pro2 · 华为杯A题算法研究

最新：[完整问答-20260924T103700Z.md](完整问答-20260924T103700Z.md) · [消息校验-20260924T103700Z.json](消息校验-20260924T103700Z.json) · [Coherent本轮完整回答](本轮回答-20260924T103700Z.md)

本轮共10条公开消息，网页核对10条；0条仅原生清单可读并逐条标源。全部达到20000字符上限的消息均由网页补齐。历史版本与原附件保留。

本轮AI附件（来自最新回答）：

- [ProB_Peak_Mechanism_CRGv1_Research_Package.zip](附件/r06-ProB_Peak_Mechanism_CRGv1_Research_Package.zip)
- [REPORT.md](附件/r06-REPORT.md)
- [GOALS.md](附件/r06-GOALS.md)
- [GOALS.json](附件/r06-GOALS.json)
- [audit_results.json](附件/r06-audit_results.json)
- [PROPOSED_COUNTERFACTUAL.json](附件/r06-PROPOSED_COUNTERFACTUAL.json)
- [READ_MANIFEST.json](附件/r06-READ_MANIFEST.json)

完整包CRC通过，包内作者清单18项逐一核对字节/哈希；未执行包内脚本。

以下为此前归档说明与附件入口，描述对应历史版本：

[完整问答](%E5%AE%8C%E6%95%B4%E9%97%AE%E7%AD%94-20260923T195552Z.md) · [消息核对](%E6%B6%88%E6%81%AF%E6%A0%A1%E9%AA%8C-20260923T195552Z.json) · [原会话](https://chatgpt.com/g/g-p-6ab2d820c86081918067a0c6d5eb1ab6-huaweicup/c/6ab39af5-bcf4-83e8-a5ec-a093f60f2039)

完整保存当前分支的提问与公开回答，按消息 ID/角色/顺序与独立会话清单对齐。三个首轮超长回答越过读取接口的 20000 字符上限，使用完整网页补齐；摘要不代替原文。原生引用标记如无法映射，原样保留并附网页实际来源链接。

用户上传材料只保留名称/上下文，不另下载。下方只收 AI 生成附件；ZIP 内附带的输入原件作为原包组成保留。所有程序均未因归档而执行；字节/CRC 校验不等于研究结论通过。历史 295 份 result.json 缺口没有被这次归档补造。

本次是首次完整快照；之前分散的摘要/研究原件继续保留。后续追问或修订追加 UTC 文件与 versions 记录，不能覆盖本快照；README 可更新最新入口。未导出隐藏推理、删除消息、未选中的其他分支。

## AI 生成附件

| 原轮次 / 名称 | 本地原件 | 取得方式 |
| --- | --- | --- |
| r01 / RESEARCH_MEMO_20260923.md | [文件](%E9%99%84%E4%BB%B6/r01-RESEARCH_MEMO_20260923.md) | original bytes extracted from downloaded AI ZIP |
| r01 / huaweicup_A_independent_research_20260923.zip | [文件](%E9%99%84%E4%BB%B6/r01-huaweicup_A_independent_research_20260923.zip) | original downloaded ZIP bytes |
| r02 / RESEARCH_MEMO_ROUND2.md | [文件](%E9%99%84%E4%BB%B6/r02-RESEARCH_MEMO_ROUND2.md) | original bytes extracted from downloaded AI ZIP |
| r02 / HuaweiCup_A_Round2_Prototype.zip | [文件](%E9%99%84%E4%BB%B6/r02-HuaweiCup_A_Round2_Prototype.zip) | original downloaded ZIP bytes |
| r02 / HuaweiCup_A_Round2_Full_E0_Evidence.zip | [part000](%E9%99%84%E4%BB%B6/r02-HuaweiCup_A_Round2_Full_E0_Evidence.zip.part000) / [part001](%E9%99%84%E4%BB%B6/r02-HuaweiCup_A_Round2_Full_E0_Evidence.zip.part001) / [part002](%E9%99%84%E4%BB%B6/r02-HuaweiCup_A_Round2_Full_E0_Evidence.zip.part002) / [part003](%E9%99%84%E4%BB%B6/r02-HuaweiCup_A_Round2_Full_E0_Evidence.zip.part003) | original downloaded ZIP bytes |

补收：首轮长答末尾的[原始数学验证结果](附件/r01-probe_results.json)，单独下载与原 ZIP 成员逐字一致。

轮次 rNN 对应原会话第 NN 个用户提问；同轮多条回答分别保留 message_id。同名文件用轮次前缀区分，清单保留准确 sandbox 原路径、来源回答和 SHA-256。

超过 48 MiB 的原 ZIP 只按字节切片，未重新压缩；按 part000、part001…拼接即可恢复同一 ZIP。可在仓库根使用 `python3 scripts/export_chatgpt_archive.py restore <新ZIP路径> --sha256 <manifest原ZIP哈希> <按序排列的part路径...>`，还原后会校验原 SHA-256。不自动解压或执行附件。
