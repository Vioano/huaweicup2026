# A 题原件的本机与 GitHub 对照

2026-09-24 队长针对本机 `Problem A/` 核对组织主库固定 `f637fc7045ece96476480245dfc71ff50da6af05`。本机原目录是留存副本，由本机 `.git/info/exclude` 排除；它的内容已以统一相对路径发布，不需要把同一批大 JSON 再提交一次。

| 本机原目录内容 | GitHub 中对应位置 | 本次结果 |
| --- | --- | --- |
| 题面 PDF | `data/raw/a/problem.pdf` | 字节一致 |
| 附件 README、code、docs、config 共14文件 | `data/raw/a/official/` 对应相对路径 | 14/14 字节一致 |
| 附件100个 case JSON | `data/raw/a/official-cases.zip` 中 `data/case_001.json`–`case_100.json` | 100/100 字节一致 |

共115文件无差异。PDF SHA-256 为 `2c0849000e137c978fb980b9c6855b2f1a23d6d4bbf46d80a6669e2249101dbe`；用例 ZIP SHA-256 为 `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528`。两者均与从上述远端提交取出的 Git blob 对比一致。

新克隆后运行 `uv run python scripts/a_materials.py --extract` 恢复100个原始用例，并按 `docs/a/source-manifest.json` 复核114个附件文件。解压出的 case 被忽略是避免重复存储，不是缺文件；不会修改原 PDF/ZIP/冻结源码。

此结论只覆盖题面与官方附件，不代表所有未提交的实验、私有状态或正在整理的聊天已经发布。实验与研发讨论按固定提交/各自归档清单同步，凭据与 Atlas 私有状态不入 Git。
