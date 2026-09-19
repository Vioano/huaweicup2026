# 建仓验证记录

日期：2026-09-19。本记录描述初始化时实际做过的验证，后续修改需重新核对。

## 本机已验证

- 项目目录符合课件要求，README 的项目内链接检查通过。
- `uv sync --locked` 通过；Python 3.12.13，NumPy 2.5.3、SciPy 1.18.1、pandas 3.0.6、Matplotlib 3.11.2，完整依赖在 `uv.lock`。
- ExFAT 上首次安装受到 AppleDouble `._*` 影响。对本项目执行普通 `dot_clean` 后，环境同步和示例运行成功；未对整盘或源资料项目清理。
- `uv run python src/demo.py` 实际生成 3 份 CSV、运行 JSON、PNG 和 PDF；PNG 已打开检查，坐标单位与图例可读。
- `--noise-std 0 --outliers 0` 下两个求解器恢复 `R=18`、`beta=0.8`、`C=220`，参数绝对误差低于 `1e-8`，真值 RMSE 约 `4.43e-14 mm`。
- 默认参数重复运行后，input/predictions/metrics 三份 CSV 的 SHA-256 逐字节一致。运行记录中的输入、源码、锁文件和输出哈希核对通过；带时间戳的 JSON/PDF 不宣称逐字节复现。

默认种子 `2026`、240 个合成点、噪声标准差 `0.8 mm`、18 个偏移 `20 mm` 的离群点：

| 方法 | R / mm | beta / rad | C / mm | 对真值 RMSE / mm | 对观测 RMSE / mm |
| --- | --- | --- | --- | --- | --- |
| OLS | 18.179255 | 0.823095 | 221.556802 | 1.589642 | 5.291942 |
| Soft-L1 | 17.963030 | 0.803954 | 220.182218 | 0.190824 | 5.475155 |

这是固定周期、单个合成种子的演示；真实未知真值不能计算“对真值 RMSE”，也不能用这组结果宣称某模型在真实赛题上更好。

## 通信 Skill

- 完整 9 个上游文件与固定提交 `77581d4` 内容一致。
- 上游自带 21 项 unittest 全部通过（本机系统 Python 3.14）。测试使用模拟 GitHub 响应和临时 Git 仓库。
- 在 `huaweibei123/huaweicup2026` 上以 `NikolaStarx` 身份实际执行 `init` 与 `check --full` 成功；已读返回索引，0 个话题、0 条评论、0 个当前指派任务。
- Issues 已启用；未安装 Hook，未发送消息，未启用自动回信。
- 尚未完成两个队友账号之间的实际消息往返或各客户端自动发现验证。

## LaTeX

- 课堂归档内 7 个模板文件完整解压，SHA-256 来源清单在 `paper/template-source.json`。
- 在临时副本执行 XeLaTeX，因本机缺少 `SimSun` 退出 1，无页面输出；未改动原模板。
- 归档的 `MathModel.pdf` 为旧示例，不能作为本次编译证据。尚未做 2026 正式格式验收。

## 远端检查

仓库提供 `.github/workflows/smoke.yml`，在 Linux、Windows、macOS 执行锁定环境同步、合成示例及通信 Skill 的现有测试，并保存示例产物。实时结果以 [GitHub Actions](https://github.com/huaweibei123/huaweicup2026/actions) 为准；本机通过不等于远端或队友电脑通过。
