# 2026-09-23 紧急资料补齐与补读

本次补齐此前仅在队长电脑上的材料。两位成员应在保存当前工作后优先补读，回报影响；不重做已有正确成果，不把研究建议当成已经批准的新任务。

## 立即阅读

1. 根目录 `AGENTS.md`、`docs/TEAM_WORKFLOW.md`：最新协作、同步、分支/worktree 与来源边界。根目录已保留队长新增的外置盘维护规则，修正“Atlas 尚未初始化”的过期描述。
2. `AI chats/A题方法.md`：整体目标、三问不同语义、候选研究方向、机制验证与最终交付约束。FORM 提取需要形式化/反例检验的假设；E1/E2 检查近似边界和计时口径。未验证假设不升级为官方规则。
3. `AI chats/讲解A题调度.md`：完整题意讨论与评价器讨论，按段补读到末尾；遇到早期误解与后续修正要保留时间顺序。题面/源码行为仍以冻结文件独立核对。
4. `docs/a/contract-v1.md`、`docs/a/READ_AUDIT.imported.md` 以及本人 `tasks/a/` 任务卡：前两项与此次补入的 `AI chats/A_problem_evaluator_contract_v1.md`、`AI chats/READ_AUDIT.md` 原始字节相同，已完整读过且哈希一致无需重复全文读。

## 随后补齐

- `AI chats/选择建模题目策略.md`：选题与竞赛目标背景。它包含历史时点判断与待核查引文，不作为本轮实测成绩或最新赛事公告。
- `paper/README.md`、`paper/template-source.json`：论文模板已换为 `paper/template-2026/`；先读入口和来源，按需读正文模板。模板示例不是本队成果，正式要求仍以当届公告为准。
- `docs/a/ATLAS.md`、`docs/a/CANVAS.md`：本轮身份、可信通信和统一图谱的研究/成员两种视角。Windows 继续使用既定固定 runtime，不因更新资料覆盖已运行的服务。
- `output/pdf/` 的两份现有 PDF 一并补入供追溯。它们是队长现有输出，不能替代 `data/raw/a/problem.pdf` 的冻结原始身份；本次未重新生成或追加内容验收。

## 原始题目无需重复搬运

本机 `Problem A/` 的题面、114 个附件文件（含 100 个案例）已在任务包通过 `data/raw/a/problem.pdf`、`official/`、`official-cases.zip` 发布。本次再次逐文件哈希比对全部一致，不再重复提交一份 254 MB 的解压目录。运行 `python scripts/a_materials.py --extract` 可恢复并验证全部原始案例。

新增原文与现有 PDF 的字节清单见 `sync-materials-20260923.json`。个人工作区、依赖和 Atlas 私有状态不属于共享资料。

## 回报格式

在本人既有 Issue 回复：`资料 commit / 当前实现分支和 HEAD / 已读与未读 / 影响或无影响的依据 / 待队长决策项`。先快速给出核心材料的影响检查，随后补齐剩余全文；不要把只读摘要写成全部阅读完成。无需队长逐条重复授权，既有任务范围内直接继续。
