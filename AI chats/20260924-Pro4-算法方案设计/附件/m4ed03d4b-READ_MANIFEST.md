# 第四路实际读取清单 / D-READ-v1

**本清单是D自己的阅读登记，不把A/B/C的READ_MANIFEST当作D已读的代签。** 新E0/E1/E2/native、作者脚本、训练和Goal均为0；只做字节/JSON回读与综合。

## 1. 六份原件与完整回答

| 文件 | bytes | SHA-256 | 读取 |
|---|---:|---|---|
| `00_READ_FIRST.md` | 8962 | `dd469065018d1a00dbb6195f5a9c0d593d83d68de48f49c72dc452fbfd5e967c` | full supplied navigation/glossary/original prompts + ALL three latest complete web answers |
| `01_GLOSSARY_V1_SOURCE.md` | 29626 | `bf26e989a8d6609257eda91c9b363ebeed65f39a6a79d7bab42f6d15767852d4` | full supplied navigation/glossary/original prompts + ALL three latest complete web answers |
| `02_ABC_LATEST_FULL.md` | 162759 | `13a9567a74743b1d23608790725ffb012d4d06f77a6e793969868df7cfec410e` | full supplied navigation/glossary/original prompts + ALL three latest complete web answers |
| `r11-Official_Mapping_Architecture.zip` | 688571 | `c9e43f7f3800d95d489af7e2d33a23e187e9ec0bbbf61419e02f8299853a6504` | all members integrity checked; per-member semantic reading below |
| `r06-ProB_Peak_Mechanism_CRGv1_Research_Package.zip` | 70961 | `812dc18d4a5275db127b65c43d2f05df5f86b87aba6a6c4bca694d9fc25d4c03` | all members integrity checked; per-member semantic reading below |
| `r06-pro_c_operations_20260924.zip` | 35127 | `0f610e8c90a160b20452ec5c3ece4e8b0b663941cc83bb0ecdd3149638b60597` | all members integrity checked; per-member semantic reading below |

A/B/C最新完整回答ID：`66f7a7d8-8a56-47db-bd86-8b14fce276fa`、`dcf7fafc-9f17-404c-aca4-39003b2c3035`、`95635808-9873-4204-bacd-814c44930fc2`。三份原专题提问也已完整阅读；没有以ZIP简版替代网页全文。

## 2. 原ZIP完整性与语义读取分开

A 88成员/87 payload；B 19/18；C 9/8。全部116成员CRC、113 payload大小/SHA通过。本清单JSON逐member列出`content_review`。完整性核验不意味着每份文件都完成逐行理论审查。

D完整解析A的两张原图、5组CLI result/trace和24份函数result/plan；重新比对ledger/source/plan/result哈希、Q2/Q3共同op时刻、Cache事件、逻辑计划恢复及资源工作量。B的PREFIX_ONLY保持部分性质；C结构统计只回读/重数原JSON，不运行检查程序。

## 3. 定点源码阅读

| 官方文件（A包原字节） | 范围 |
|---|---|
| `contest_io.py` | whole-file function/index scan; byte identity; output-wrapper points; not full semantic review |
| `evaluation_validation.py` | selected source, especially 120–243 (combined graph/task/execution checks); earlier definitions indexed, not full formal verification |
| `multicore_cut_evaluate_problem_1.py` | 60–531: local builder, Step1–3 inputs, event advancement, output assembly; helpers before60 indexed |
| `multicore_cut_evaluate_problem_2.py` | 1–350 and487–606: builder, validation/initialization, ending event section and result; 351–486 not claimed fully read |
| `multicore_cut_evaluate_problem_3.py` | 350–729 event/cache/result; complete builder and priority functions compared statically with Q2; other prefix sections indexed |
| `schedule_step1.py` | function/index scan and selected ordering interfaces; entire byte hash checked, not full line-by-line proof |
| `schedule_step2.py` | 60–471: lifecycle, victim filtering, alloc/check/free, backing, incarnation and rewiring; remaining sections indexed |
| `schedule_step3.py` | 1–116,675–703; execution/dependency output locations indexed; not full memory-allocation proof |
| `singlecore_evaluate.py` | full108-line source read; fixed single Task baseline construction |
| `stub_multicore_cut_and_schedule.py` | 120–295: plan coverage/ID parsing/quotient/core orders; other functions indexed |

十份官方源码集合hash重新核对：`de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。不是全体源码形式验证。

## 4. 授权镜像补读

| 固定提交 | 文件 | 实际范围 |
|---|---|
| `eaa15af9dde7365722e3b497df2fb869ff6e1c1e` | `docs/a/research/20260924-coherent-pro/README.md` | full |
| `eaa15af9dde7365722e3b497df2fb869ff6e1c1e` | `docs/a/OFFICIAL_OBJECTIVES.md` | initial full request truncated in section5; source60–150 follow-up completed tail; combined content read |
| `eaa15af9dde7365722e3b497df2fb869ff6e1c1e` | `docs/a/source-manifest.json` | source1–127 only; full10-code list/hash and case008; not all100-case manifest revalidation |
| `a4e7ee13310d693ec4fb5cc236669ceb3b172d1f` | `src/q3/construct.py` | source1–185, core constructor/guards; remaining CLI tail not claimed read |
| `603b0741e21c449d3db652ebd67c94f2dc014cc9` | `research/a/e2_search/P23_HANDOFF.md` | full returned text; performance assertions remain developer reports |
| `603b0741e21c449d3db652ebd67c94f2dc014cc9` | `research/a/e2_search/scene_b.py` | source1–190 requested; adapter/native/cache/evaluate_record routing read through return; native C++ not read |
| `eaa15af9dde7365722e3b497df2fb869ff6e1c1e` | `AGENTS.md` | requested1–155, response truncated; visible workflow/session/objectives/Pro consultation/archive prefix read; remainder NOT claimed read |

完整URL、Git blob SHA和引用标记见JSON。OFFICIAL_OBJECTIVES截断尾已补读；AGENTS后部没有标为已读。链接可达、文件哈希和实际阅读分别记录。

## 5. 本轮仍保留的缺口

- No new E0/E1/E2/native run or attached-code execution; no full100 graph performance matrix.
- No independent current-runtime or cross-platform rerun of A fiveCLI/24function results; source integrity is not runtime acceptance.
- B originally read zero full G and only compressed prefixes. D now has full008/044 G and A word results, but never rewrites B original evidence status.
- Q1 coarse113686, Q1 051/044 macro performance, Q3 080 ranking inversion remain AUTHOR-REPORT in this synthesis unless specifically identified as complete readback; full corresponding raw archives not reread.
- No complete formal acceptance of all frozen code or FORM; precise static-source ranges above.
- No original PDF rerender in this turn; official objectives taken from authorized source-backed OFFICIAL_OBJECTIVES plus full supplied context.
- No fresh DOM/browser visit or all-history Chat Folder reconstruction; complete latest web answers supplied by user read in full.
- No full C++ native review or current availability guarantee; P23 adapter routing read, developer performance remains AUTHOR-REPORT.
- Remote source-manifest partial, AGENTS tail truncated; next executing session must read required workflow fully.
- Historical old295 outcomes or other prior Pro missing artifacts not retroactively recovered.
- Initial generic filesystem inventory also listed/hashed some older mounted artifacts; this does not constitute semantic reread or additional evidence for this task.

## 6. 清单和摘要的对应关系

- `INTEGRITY_AUDIT.json`：六原件和113 payload逐字节检查。
- `EVIDENCE_READBACK.json`：D实际对既存结果做的字段/身份静态核对。
- `READ_MANIFEST.json`：每member阅读方式、源范围、远端固定引用和缺口。
- `SYNTHESIS_REPORT.md`：结论的证据等级、证明适用域与去重设计。

原文件没有被覆盖；D的新文档、图和任务卡在独立目录。
