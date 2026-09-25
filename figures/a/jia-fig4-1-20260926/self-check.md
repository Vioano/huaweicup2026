# 图 4-1 自查记录（甲，v3，2026-09-26；响应工作台退回意见）

对照验收标准逐项：
1. 切图、分核、每核 Task 顺序三项决策齐全 → 通过（plan 节点列出 node_to_subgraph / core_schedules；note 注明提交者仅决定此三项）
2. 未赋予提交者直接控制官方 Pipe 顺序或等待时间的自由 → 通过（plan 标明"不含逐 Pipe 顺序"；下层容器标"提交者不可修改"；note2/note1 明示）
3. 在线 E1 评分与独立最终 E0 复评分开表示 → 通过（上层 e1 节点标注"E1…计入求解计时"；下层 e0 虚线节点标注"E0 独立最终复评…与在线 E1 分开表示"）
4. 研究模块未混入 v4 主线 → 通过（note3 注明变宽分组/错峰融合等研究扩展不在本主线；图中无研究模块节点）
5. 两个提交字段与两个评价出口 → 通过（金色 plan 节点含 node_to_subgraph、core_schedules；out1=Makespan cycles、out2=额外 DDR B）
6. 工具检查 → drawio-skill validate.py 0 error；draw.io CLI 导出（--disable-gpu --no-sandbox）
7. 版面 → PNG（scale=2）全宽目检：无缺字、无遮挡、无裁切；中文 Microsoft YaHei 正常渲染

有效/缺失数量：流程节点 13、连线 13，全部来自固定来源（见 audit.json sources）；无缺失输入。
未完成项：无（如整稿侧统一字体字号配色要求变更，按新规范重导）。

## v3 修订核对（逐条对应工作台退回意见）

1. 单候选分支 → 已加：dedup->single 节点（去重后仅 1 个候选直接选定输出，不启动在线 E1，仍由独立 E0 复评），与 unified.py solve/choose 的 len(candidates)==1 路径一致。
2. 箭头关系 → 已改：identify->candBox->dedup->(single | e1)->plan；删除 identify->dedup 直连；覆盖/依赖检查标注在各构造器内，plan_bytes 仅为字节去重。
3. 方案接口消歧 → 已改：plan 节点=官方方案文件严格仅两字段；新增 diag 旁支节点标 --diagnostics（求解器自留，不提交官方）。
4. audit 补件 → 已补：DELIVERY.md 纳入 notes 角色；nodes.csv stage 改用 required_stages 标准标记；sources 全部填真实 40 位 commit 与 64 位 SHA256。
5. 源文件缺陷 → 已修：46 行孤立闭合标签删除，标准 XML 解析通过；SVG/PNG 从修复后源重新导出，哈希同步更新。
