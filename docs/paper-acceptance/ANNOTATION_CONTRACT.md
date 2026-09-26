# 人工实例到全文同类检查：数据约定 v2

真实首轮样本见 `annotation-workflow.json`，它与页面、Agent接口使用同一原件。当前17条人工批注来自原写作任务交回的CP02批注JSON；前7条已核固定097240c3原件，新增10条收到工作稿，来源状态逐批区分。用户原话、作者理解和本台归类分开保存。批注文件自己的固定提交取得前，其来源回执明确记本地工作稿与字节哈希，不能把论文PDF所在提交冒充批注文件提交。

## 稳定事件

`events[]` 必需字段：`annotation_id`、`event_key`、`source_commit`、`paper_sha256`、`pdf_path`、`page`、`rect`、`original`、`user_comment_verbatim`、`source_type`。`event_key` 为 `PDF哈希:批注ID`。相同键再次收到时核对原文与用户批注，完全相同则复用；内容改变视为新修订并保留旧版，不能覆盖后冒称初始原话。

`artifact_commit` 是PDF原件所在提交，不一定等于正文SHA；批注文件的发布身份单独在 `source_receipt`。同一句跨行产生的不同批注ID都保留，通过`occurrence_groups`关联到同一位置，不计作两个独立问题。每条`annotation_commit`单独记录批注原件发布状态，顶层回执可同时含固定批次与待发布批次。

PDF坐标始终带页尺寸及原点，不能套到重排后的页。转述必须使用 `user_comment_summary` 并标明不是原话，不得填进verbatim字段。

## 问题类别

`issue_classes[]` 必需字段：`id`、`annotation_ids`、`title`、`mechanism`（共同缺陷）、`scope`、`positive_example`（应查实例）、`negative_example`（不应误报实例）、`facts_to_verify`、`rules`、`finding_ids`、`coverage_status`。类别的来源必须回指人工事件；用户的一句例子可关联全文许多位置，也允许实际找不到其他同类。例子是判别依据，不是字符匹配规则。

先由两任务核对少量已有样本以校准边界，再在固定版本和有限范围内展开；不要求用户逐条批准。复用已完成且来源相同的审阅，只有新的缺陷类型或新稿变化需要额外检查。新稿已替换且没有历史对照价值时停止旧稿新派工。

## 扫描与具体发现

`scan_runs[]` 记录唯一任务ID、源稿SHA、标准版本、类别/范围、模型与预算、实际覆盖及未核范围。去重至少比较 `source_commit + 类别 + 范围 + 标准版本`；相同工作已完成时引用现有记录，不重复生成问题。

`semantic-audit.json` 保存 `findings[]` 与每个源文块的 `coverage[]`。每条发现包含稳定问题ID、类别ID、源稿SHA、精确原句、路径/行号、同类理由、修改要求和复核状态。`pending` 为未核提议，`confirmed` 为语言问题理由已核，`needs_context` 为待作者解释/提供依据，`dismissed` 为误报或不采用；这些都不是最终通过。

原句须是固定源单元的连续子串，行号在该单元范围内。覆盖清单必须对应全部给定单元，不遗漏、不重复；缺上下文就标出。`reviewed_no_finding`只表示本轮未发现问题。单元可为多句段落、表格、公式或标题，不能把数量冒称句数。图内文字需单独实际查看，不由源文初审代签。

## 作者回交

当前正文负责人Antigravity通过资料与审核任务交付，在约定的 `paper/manuscript-v1/review/` 保存响应JSON，再发固定SHA和路径。顶层字段：`schema_version:2`、`source_commit`（被审94dae）、`target_commit`（新稿）、`entries`。每条：

```json
{
  "finding_id": "SA-A-001",
  "annotation_ids": ["USER-CP02-03"],
  "class_ids": ["CLASS-03"],
  "disposition": "revised",
  "target_path": "paper/manuscript-v1/chapters/00-abstract.md",
  "target_line": 5,
  "replacement": "实际改文，不填示意",
  "explanation": "怎样消除共同缺陷，科学含义是否变化",
  "evidence": [],
  "remaining": []
}
```

`disposition` 允许 `revised`（已改）、`explained`（提供定义/已有位置）、`disputed`（提出异议）或 `unresolved`。改写、合并、拆分或删除均说明去向；删除不省略原因。证据用固定出处。作者不能填写accepted替代验收者回读。

监督与审核任务核对新原文、语义及影响后交回处理结果，验收台记录并展示；类级关闭还要求该类覆盖完整且无未解决问题，不能以一条改好关闭一整类。当前接口仅提供读取与既有审阅发布，导入报告不自动改状态、不自动运行扫描、更不提供不存在的后台唤醒。
