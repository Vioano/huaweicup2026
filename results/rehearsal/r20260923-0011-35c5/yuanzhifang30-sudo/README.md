# 合成直线拟合交付

负责人：@yuanzhifang30-sudo。任务：`fit-yuanzhifang30-sudo`。
分支：`codex/rehearsal-r20260923-0011-35c5-yuanzhifang30-sudo`。
控制帖：https://github.com/huaweibei123/huaweicup2026/issues/5
计算分配：https://github.com/huaweibei123/huaweicup2026/issues/5#issuecomment-5780065751

1. **任务目标**：以带截距普通最小二乘基线拟合 `distance_m = slope * time_s + intercept`，验证无噪声参数恢复。
2. **输入文件**：`tests/rehearsal/observations.csv`，仓库人为构造的五行合成数据；时间单位 s、距离单位 m。输入 SHA-256 见 `result.json`。全部样本用于拟合，仅检查样本内恢复，无训练/测试性能比较。
3. **输出要求**：本人脚本 `src/rehearsal/r20260923-0011-35c5/yuanzhifang30-sudo.py`、本目录 `result.json` 和说明。JSON 记录逐行预测、残差、单位、命令、环境、输入/脚本/锁文件哈希及脚本提交版本。
4. **限制条件**：使用已锁定环境中的 Python 标准库；确定性算法，`seed=null`；从 CSV 实际计算系数，不硬编码答案。截止前交付，不改原件、不合并 PR。
5. **验收标准**：n=5、斜率 2 m/s、截距 1 m、MSE≤1e-20 m²；给出最大绝对残差；队长独立重跑并验收 PR。该阈值仅用于本轮无噪声样例。
6. **截止时间**：2026-09-23T00:56:45+08:00。

## 复现

从项目根目录执行：

```sh
uv sync --locked
uv run python src/rehearsal/r20260923-0011-35c5/yuanzhifang30-sudo.py --input tests/rehearsal/observations.csv --output results/rehearsal/r20260923-0011-35c5/yuanzhifang30-sudo/result.json
```

脚本先提交、后运行，再单独提交结果，避免结果嵌入自身最终提交 SHA。重跑时生成时间和 checkout 提交可能变化，比较输入/脚本哈希、算法及全部数值，不要求 JSON 字节完全相同。

## 范围和未测项

这是合成无噪声基线检查，不证明真实赛题性能、抗噪能力或外推能力；本轮任务不要求图表。成员实际运行及代码审查结果与队长独立重跑分开记录。

本机为原生 Windows，未安装 WSL/Linux。按联测入口，Atlas 0.5.0 阶段阻塞；未初始化私有身份、未获得成员 grants、未读取签名 board 或字段版本、未提交 doing/review/deliverables 请求。队长允许独立计算交付，此 PR 不代替 Atlas accepted 回执或状态闭环。网页未打开，同 cursor Human/Agent、设计字段/批注、原子拒绝、旧版本冲突、离线恢复均未测。
