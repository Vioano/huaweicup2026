# FORM 固定用例（独立回跑入口）

本目录是 A 题 FORM 任务的**固定件**，由 `src/adversarial/verify_fixtures_r1.py` 统一复验。
任何独立环境（LYX / 队长）都可以用下面**一条命令**回跑全部用例并取得机械判据。

## 回跑

```sh
# 在 FORM 分支的工作区根目录执行
python src/adversarial/verify_fixtures_r1.py
```

- **通过** ⇒ 末行 `ALL FIXTURES REPRODUCED: True`，**退出码 0**。
- **任一不成立** ⇒ 退出码非 0，并在 `results/a/form/r1-20260923-farmeruncle123/fixtures-observations.json`
  中给出逐条判据。

冻结常量取自 `data/raw/a/official/data/config.txt`（bandwidth=60、L1=524288、UB=131072），
**未修改官方任何文件**。

## 三个固定件

| 文件 | 内容 | 判据 |
|---|---|---|
| `ranking-inversion-pair.json` | E2 排序反转：两个候选搬运统计**逐字节相同**（256 / 768），官方 makespan **1052 vs 152** | 复算两个 makespan 与三个搬运字段，并核 `delta=900` 与字段逐字节相同 |
| `fplan-005-quotient-cycle.json` | 原图是 DAG，但把 op 1 与 3 并入同一子图后**商图成环** → 划分级拒绝 | 核 `graph_sha256`/`plan_sha256`；`validate_graph` 通过；`derive_multicore_plan` 拒绝且错误消息逐字符一致 |
| `dev-samples.jsonl` | 10 条开发反例（正例 / 边界 / 对抗，三条机制组） | 核每条 `graph_sha256`/`plan_sha256`，并用官方入口**重放** `observed` 逐字段比对 |

## 哈希口径

固定件中的 `graph_sha256` / `plan_sha256` 均为

```python
hashlib.sha256(
    json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
```

`fixtures-observations.json` 另记录每个固定件的 `fixture_sha256`（文件字节哈希），便于核对**文件本身**是否一致。

## 一条实现口径（避免假失败）

官方 `derive_multicore_plan` 返回的 `dependency_pairs` 是 Python `tuple`，而 jsonl 经序列化后是 `list`。
本复验脚本在比较前做 **JSON 往返归一化**，否则会出现与语义无关的失败。

## 边界

- 全部为**微型构造图**，不是正式 100 个 case，结论**不可外推**。
- 只调用**冻结官方函数**取原始输出；**未调用队长的 oracle 适配层**，**未做 E0 评分**，
  **不构成任何验收结论**（验收不能由实现者或复核者代签）。
- `S-ROUND-SIZE-0`、`S-PLAN-ID-LEADING-ZERO` 等属**非正式输入域**，标注为对抗/边界，不代表正式域行为。
- 复验只证明这些固定件**可被重放**，不证明它们代表官方候选池的真实分布。
