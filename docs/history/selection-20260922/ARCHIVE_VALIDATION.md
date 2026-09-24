# 归档验证记录

日期：2026-09-24；平台：本机 macOS；基线：`3f0004815ca1c8f1af14b4f77db652caa98b37ac`。

- 21 个既存文件逐项与旧留存副本比较大小/SHA-256，通过；总计 1,106,485 字节。
- 原脚本 SHA-256 `5a9cb0d4bd394b46e314989d5000c5eb438e78e26bcf54cc3ebf7fbb62837852` 与旧 run.json 相同。
- 原报告 SHA-256 `31a673b2e972915e96789610b3b3a75648ed0841549d084ef6df6f7eadf4f6c4` 与旧 run.json、主库已有 PDF 相同。
- JSON 全部解析通过；CSV 列数一致；Python 用 `ast.parse` 静态解析通过，未 import/执行历史脚本。
- 检查文本/SVG中的个人绝对路径、常见 GitHub token 和私钥标记，无命中；不存在 `tmp`、AppleDouble、`.DS_Store` 或私有运行状态。此为有明确范围的内容检查，不是通用安全证明。
- 10 个旧输入中 2 个与仓库既有原字节一致、8 个原件当前不可取得，详见 archive-manifest.json。未将输入缺失记作完整复现。
- `pdfinfo docs/history/selection-20260922/output/pdf/HuaweiCup_Selection_Report.pdf`：2 页 A4，236,520 字节。PDF是原字节归档，没有重新排版；9月22日已有逐页渲染检查，本次未声称重新视觉验收。
- 原件中的提取文本/SVG含尾随空白，CSV使用CRLF；首次暂存发现Git会规范化CSV行尾。归档目录现以局部 `.gitattributes` 禁止文本换行转换，并只对原件文本/SVG/CSV豁免空白警告，随后核对Git暂存blob大小/SHA与清单一致；没有清洗历史字节。新增说明文件仍检查空白。未修改当前 AGENTS、源题、评价器、任务预算或云端服务。

范围：只验证归档身份与可分享性；不重算评分、不运行算法/评估器、不复核原报告科学正确性，不宣称跨平台重绘或队友已读。GitHub Actions按免费策略停用。
