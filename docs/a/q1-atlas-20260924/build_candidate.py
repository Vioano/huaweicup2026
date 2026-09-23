"""Build a Q1-only Atlas patch; never writes the live authority model."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'output/q1-atlas-authoring/base-bundle.json'
SOURCE_COMMIT = '13d6b0298f944d3c0bfdf3172191f1ac25a50379'


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(data):
    return hashlib.sha256(data).hexdigest()


base = json.loads(BASE.read_text())['snapshot']
model = copy.deepcopy(base['model'])
# Published bundles include evaluated status fields; authoring JSON does not.
# Remove only those derived annotations from this local validation copy.
for row in model['entities']:
    for claim in row['maturity'].values():
        claim.pop('effective', None)
        claim.pop('evidenceStatus', None)
for row in model['evidence']:
    row.pop('checks', None)
    row.pop('status', None)
entities, relations, views, evidence = [], [], [], []
provenance = []


def bind(name, path, kind='source', scope='固定交付源码；文件存在不代表全模块验收。'):
    source = ROOT / path
    target = OUT / 'evidence' / ('source' if kind == 'source' else 'results') / source.name
    target.write_bytes(source.read_bytes())
    entry = {'id': 'q1-atlas-' + name, 'kind': kind, 'path': str(target.relative_to(ROOT)),
             'sha256': digest(target.read_bytes()), 'label': name, 'scope': scope}
    evidence.append(entry)
    provenance.append({'id': entry['id'], 'originCommit': SOURCE_COMMIT, 'originPath': path,
                       'path': entry['path'], 'sha256': entry['sha256']})
    return entry['id']


src = {name: bind(name, 'src/q1/' + name + '.py') for name in
       ['prototype', 'structure', 'search', 'neighborhood', 'profile_candidates',
        'profile_refine', 'trace_priority', 'prospective_priority']}
reports = {}
for name, path in {
    'construction-report': 'docs/a/Q1_PROTOTYPE_START.md',
    'move-report': 'docs/a/Q1_GUIDED_MOVES.md',
    'profile-report': 'docs/a/Q1_PROFILE_REFINE.md',
    'trace-report': 'docs/a/Q1_TRACE_EXPLANATION.md',
    'prospective-report': 'docs/a/Q1_TRACE_PROSPECTIVE.md',
    'e2-pro-report': 'docs/a/Q1_E2_PRO_NEXT.md',
}.items():
    reports[name] = bind(name, path, 'design', '既有阶段报告，注明开发例、代码身份与计时边界；本轮只读归档。')


def entity(id, label, purpose, steps, sources=(), reports_=(), parent='q1-construction',
           type='backend', sub='', issues=(), inputs=(), outputs=(), implemented=True):
    ids = [src[x] for x in sources] + [reports[x] for x in reports_]
    maturity = {'design': {'value': 'proposed'},
                'implementation': {'value': 'implemented' if implemented and sources else 'unknown'},
                'verification': {'value': 'unknown'}, 'integration': {'value': 'unknown'}}
    if sources:
        maturity['implementation']['evidence'] = [src[x] for x in sources]
    row = {'id': id, 'parent': parent, 'type': type, 'label': label, 'sublabel': sub,
           'purpose': purpose, 'inputs': list(inputs), 'outputs': list(outputs), 'steps': list(steps),
           'openIssues': list(issues), 'evidence': ids, 'maturity': maturity}
    entities.append(row)
    return id


def edge(id, a, b, label='', kind='dataflow', variant=None):
    row = {'id': id, 'from': a, 'to': b, 'kind': kind, 'label': label}
    relations.append(row)
    result = {'relation': id}
    if variant:
        result['variant'] = variant
    return result


def placement(id, x, y, sub=None, tag=None):
    p = {'entity': id, 'pos': [x, y], 'size': [240, 110]}
    if sub:
        p['sublabel'] = sub
    if tag:
        p['tag'] = tag
    return p


entity('q1-input', '原始图与固定配置', '情况 A / 第一问的固定输入；不改变官方执行语义。',
       ['读取计算图 JSON、核心数、官方固定配置。', '决策空间是非 COPY 算子的 Task 分区、分核、核内 Task 顺序。',
        'Task 内部 Step1/2/3 与事件模拟由官方程序决定。'], sources=['prototype'], type='external',
       sub='图 JSON · 核数 · 配置', outputs=['待构造的原始图及资源限制'])
entity('q1-seed', '结构化初始构造', '利用非分叉链与依赖图产生合法初始方案；Pro 第一路是链包与 cover 合并的重要思想来源。',
       ['非分叉链打包，另保留弱连通分量与固定分块等有限候选。',
        '按拓扑关系与官方局部编译时长安排核心；局部时长仅用于提议。',
        '同核相邻合法 cover 合并，分别保留出口保护与不保护候选。'],
       sources=['structure', 'prototype'], reports_=['construction-report'],
       sub='链包 → 分核 → 合法合并', issues=['共享 DDR 使局部时长不等于真实全局工期。'])
entity('q1-improve', '结构化有限改进', '已经实现的多个实验入口；从已确认父计划提出有限邻域，不声称已集成为统一端到端求解器。',
       ['固定分区：计算 Task 合法插入区间。', '分区调整：从真实 Task 剖面提出少量拆分/合并。',
        '每轮固定父计划，真实评分后保留更优方案；不能靠代理硬剪枝。'],
       sources=['neighborhood', 'profile_candidates'], reports_=['move-report', 'profile-report'],
       sub='合法移动 · Task 拆分/合并', issues=['当前候选覆盖与合并排序仍有明显改进空间。'])
entity('q1-select', '在线评分与选优', '候选经固定 E1 精确评价，以 Makespan 优先、同分比较搬运量，保留可恢复的已确认方案。',
       ['E1 固定提交 5bfe53a；改变分区后重新官方编译。', '记录预算、派发/返回、超时和失败；失败保留已有合法方案。',
        '在线使用 E0 确认时，其时间也属于求解耗时。'], sources=['search', 'profile_refine'],
       reports_=['profile-report'], sub='固定 E1 · 保留 incumbent',
       issues=['E2 尚未接入本版本 Q1 默认路径。', '并不是所有改进模块都已接入同一自适应循环。'])
entity('q1-plan', '官方格式方案', '可以交给未修改官方 evaluator 的方案文件；不是评价结果文件。',
       ['顶层只有 node_to_subgraph 与 core_schedules。', '全部非 COPY 算子恰好覆盖、每个 Task 恰好在一核出现。',
        '最终确认后原子提升 confirmed_plan；provisional 与 confirmed 分开。'],
       sources=['profile_refine'], reports_=['profile-report'], type='database', sub='分区 · 核归属 · 核序',
       outputs=['<case>_multicore_res.json'], issues=['计划文件存在不是全例终验。'])
entity('q1-results', '两条成果轴', '方案质量与求解效率分开报告；已有正式开发例 E0 成绩，尚无最新组合求解器统一冷启动测量。',
       ['Makespan 单位 cycles：最重要官方指标，兼顾额外 DDR bytes。',
        '求解 wall 从启动/读图到合法方案落盘和必要收尾，在线预处理、评价/复核都计入。',
        '5～10 分钟为推荐，不是硬 600 秒或本队效率终点。'],
       reports_=['profile-report', 'move-report', 'prospective-report'], type='database',
       sub='官方 cycles ≠ 求解 wall', issues=['未完成全 100 图、1～5 核、公平强基线与尾部时延验收。'])
entity('q1-research', '研究与未接入项', '独立于已实现主流程的可证伪研究，不能画成已完成运行路线。',
       ['入口提前量排序在三个新池没有质量收益，暂缓默认接入。',
        'E2 有专项交付，但本 Q1 版本仍用固定 E1。',
        'Pro route1 数学问题已发送；本次不轮询、不重发、不把在途请求当成果。'],
       reports_=['prospective-report', 'e2-pro-report'], sub='负结果 · E2 · 数学研究',
       issues=['在途状态以原发送会话读取为准；本图为固定版本事实。'])

main_links = [edge('q1-flow-input-seed', 'q1-input', 'q1-seed', '读图'),
              edge('q1-flow-seed-improve', 'q1-seed', 'q1-improve', '方案'),
              edge('q1-flow-improve-select', 'q1-improve', 'q1-select', '候选'),
              edge('q1-e1-score', 'exact-evaluator', 'q1-select', '评分'),
              edge('q1-flow-select-plan', 'q1-select', 'q1-plan', '选优'),
              edge('q1-plan-e0', 'q1-plan', 'official-evaluator', '复评'),
              edge('q1-e0-results', 'official-evaluator', 'q1-results', '结果')]
# Renderer diagnostics identified two vertical label/component overlaps.
main_links[3]['labelAt'] = [1090, 190]
main_links[4]['labelAt'] = [1090, 415]
views.append({'id': 'inside-q1-construction', 'scope': 'q1-construction',
              'title': 'Q1 / 情况 A · 已实现算法与验证', 'viewBox': [1290, 680],
              'placements': [placement('exact-evaluator', 970, 30, 'P1 精确批评估 · 已接入', '固定 5bfe53a'),
                placement('q1-input', 40, 240), placement('q1-seed', 350, 240, tag='已实现'),
                placement('q1-improve', 660, 240, tag='阶段原型'), placement('q1-select', 970, 240),
                placement('q1-research', 40, 480, tag='非运行路线'), placement('q1-results', 350, 480, tag='局部证据'),
                placement('official-evaluator', 660, 480, '未修改官方程序 · 正式复评', '官方 E0'),
                placement('q1-plan', 970, 480)], 'relations': main_links,
              'cards': [{'dot': 'cyan', 'title': '读取方式', 'items': ['主线展示已实现阶段的接口关系；并非一次完整运行的实测轨迹。', '展开构造、改进、成果与研究节点，查看来源、边界和数值。']},
                        {'dot': 'amber', 'title': '两类时间', 'items': ['Makespan 是模拟 cycles；wall 是求解程序真实耗时。', '在线 E0 计入求解时间，求解结束后的独立正式 E0 另列。']}],
              'guidedViews': [{'id': 'q1-main-path', 'label': '已实现主线', 'focus': ['q1-input','q1-seed','q1-improve','q1-select','q1-plan'],
                               'note': '构造、改进、选优均有实现；当前是多个阶段实验入口。'},
                              {'id': 'q1-result-proof', 'label': '官方确认与两轴成果', 'focus': ['q1-plan','official-evaluator','q1-results'],
                               'note': '计划交 E0 复评；展开成果查看实测数值和计时范围。'}]})

entity('q1-chain', '非分叉链打包', '优先沿无分叉依赖链聚合计算算子，减少不必要的 Task 边界。',
       ['来源：第一路 Pro 的结构化构造建议，随后独立实现。', '保留固定分块、弱连通分量等有限构造以应对图结构差异。'],
       ['structure'], ['construction-report'], 'q1-seed', sub='Pro 思路 → 独立实现')
entity('q1-placement', '拓扑组织与分核', '在合法拓扑关系下使用预计完成时间安排核心。',
       ['使用官方局部编译时长与等待参数提议核归属。', '局部代理不含完整共享 DDR 竞争，所有候选再作精确评价。'],
       ['structure','prototype'], ['construction-report'], 'q1-seed', sub='局部时长只作提议')
entity('q1-cover', '合法 cover 合并', '在完整数据依赖＋各核链的增广 DAG 中合并同核相邻 Task。',
       ['删除相邻直连边后不存在替代 A→B 路径时，收缩不会引入环。',
        '保留出口保护/不保护两种候选；051不保护退化，002不保护反而更好。'],
       ['structure'], ['construction-report'], 'q1-seed', sub='合法性条件＋出口保护',
       issues=['出口保护是启发式，不是收益定理。'])
views.append({'id':'inside-q1-seed','scope':'q1-seed','title':'Q1 · 初始构造来自哪里','viewBox':[1000,480],
              'placements':[placement('q1-chain',40,180),placement('q1-placement',380,180),placement('q1-cover',720,180)],
              'relations':[edge('q1-seed-chain-place','q1-chain','q1-placement','链包'),edge('q1-seed-place-cover','q1-placement','q1-cover','核序')],
              'cards':[{'dot':'emerald','title':'结构构造的 E0 成绩 / cycles','items':['002：随机示例269157 → 链包119687 → 合并组合最佳92089。','008：随机示例443533 → 链包369908 → 合并组合最佳113686。','同4核开发例；不是强基线消融，也不是相对官方单核基线的加速比。']}]})

entity('q1-legal-move','合法移动区间','固定分区与父计划，用祖先/后继界定 Task 的合法插入位置，减少非法提议。',
       ['先移除待移动 Task 的核链位置并连接前后项，保留数据依赖。','目标核上最后祖先之后、最早后继之前构成合法区间。','已核对20480个有限槽位；一般性依据为图论证明。'],
       ['neighborhood'],['move-report'],'q1-improve',sub='祖先 / 后继 → 插入区间',
       issues=['只保证 Task-order 合法性，不保证内存、FIFO或收益。'])
entity('q1-task-profile','真实 Task 剖面','读取官方构建的完整 Step1/COPY、局部pos、backing与spill，作为候选依据。',
       ['第四路勘误审计帮助校准语义；复用按Task，不按core。','已有DDR backing时可不新增COPY_OUT；零spill不保证更快。'],
       ['profile_candidates'],['profile-report'],'q1-improve',sub='COPY · backing · 压力 · 远端入口')
entity('q1-split-merge','有限拆分与合并','围绕真实剖面构造少量候选；分区改变后重新官方编译。',
       ['两轮各最多4候选，通常2拆分＋2合并。','每轮同一父计划；首轮无改善可跳过已见候选继续下一轮。','051胜出拆分把不必等晚到输入的前缀提前执行；不等于总工作量减少。'],
       ['profile_candidates','profile_refine'],['profile-report','trace-report'],'q1-improve',sub='切点与 cover → 完整重编译',
       issues=['边界字节节约只排序，不替代真实makespan。'])
views.append({'id':'inside-q1-improve','scope':'q1-improve','title':'Q1 · 两类已实现有限改进','viewBox':[1000,560],
              'placements':[placement('q1-legal-move',40,100),placement('q1-task-profile',40,350),placement('q1-split-merge',570,350)],
              'relations':[edge('q1-profile-candidates','q1-task-profile','q1-split-merge','生成候选')],
              'cards':[{'dot':'amber','title':'方法边界','items':['合法移动与剖面拆分合并是两类阶段入口，不能把并排模块读成每次都顺序执行。','有界次数不自动满足避免暴力搜索要求；保留结构依据、复杂度、停止条件及实际收益。']}]})

entity('q1-quality','官方方案质量 / cycles','以下是固定4核预算的正式开发例、未修改E0复评结果；对照为官方随机stub。',
       ['002：269157 → 88188，降低67.24%。','008：443533 → 113686，降低74.37%。','051：645287 → 336057，降低47.92%。',
        '044：137207 → 114443，降低16.59%。','014：11866986 → 4537232，降低61.77%。',
        '003新父654160 → 653263；897改善来自原有merge，不是trace排序。'],
       reports_=['construction-report','move-report','profile-report','prospective-report'],parent='q1-results',type='database',sub='官方 E0 已确认开发例',
       issues=['不是强基线排名、官方单核加速比、全例结果或全局最优性证明。'])
entity('q1-wall','求解效率 / wall 秒','时间必须覆盖从程序启动到合法方案落盘与必要收尾；当前保留各阶段测量范围。',
       ['早期有预算搜索：普通例4.20～6.13秒，014为92.44秒；部分继承已有初始方案。',
        '后续局部改进：044为1.361秒、051为2.479秒、002为1.857秒，含本阶段启动与两次E0。',
        '这1～2.5秒不是从原始图得到当前最佳方案的全部成本。',
        '三例双策略前瞻23.674秒是监督实验时间，不能当单个求解器端到端时间。',
        '下一步应同质量比时间、同时间比质量，记录冷启动/图规模/P50/P95/最慢及资源；不因低于10分钟停止优化。'],
       reports_=['profile-report','prospective-report'],parent='q1-results',type='database',sub='已有阶段计时 · 全链尚待统一测量',
       issues=['本机单次计时，未完成重复统计、跨平台及最新组合算法统一冷启动。'])
views.append({'id':'inside-q1-results','scope':'q1-results','title':'Q1 · 成果与测量边界','viewBox':[960,470],
              'placements':[placement('q1-quality',90,160),placement('q1-wall',630,160)],'relations':[],
              'cards':[{'dot':'emerald','title':'方案质量','items':['002 / 008 / 051 / 044 / 014 的 E0 最佳值均有固定计划和归档。','随机stub是接口示例，不能据此宣称接近最优。']},
                       {'dot':'cyan','title':'求解效率','items':['1.36～2.48秒是已有计划的局部改进阶段，不包括历史初始构造。','Makespan与完整求解wall同时优化；不以评分内核倍数替代。']}]})

entity('q1-trace-priority','入口提前量排序','已实现的实验特征；冻结父时间线只在已有split槽位间重排，不用于硬剪枝。',
       ['旧051候选池回看使最好split从第3次提前到第1次，属于开发回看。','新008/003/044三个池中六个split提前量均为0，顺序与质量均未改变。','按预先决策规则暂缓默认接入，保留负结果。'],
       ['trace_priority','prospective_priority'],['prospective-report'],'q1-research',sub='已实验 · 三个新池无质量收益',
       issues=['未证明非零提前量场景普遍无效。'])
entity('q1-pro-math','Pro 数学研究在途','固定13d6b02记载route1追问已经发送；本次不重新读取生成状态。',
       ['问题：从外部输入释放时间构造向下闭合的切分集合。','探索阈值理想集、最大权闭包或超图割；要求证明/反例/伪代码。','消息ID e03ba69e-151c-4b48-af23-499aa399441f，发送归属fork s-8ee33…。'],
       reports_=['e2-pro-report'],parent='q1-research',type='external',sub='待收取 / 待验证 · 非算法成果')
views.append({'id':'inside-q1-research','scope':'q1-research','title':'Q1 · 未接入与负结果','viewBox':[1000,480],
              'placements':[placement('q1-trace-priority',40,180,tag='暂缓默认启用'),
                placement('approximate-evaluator',380,180,'E2 专项已有交付 · Q1尚未接入','非当前运行路线'),
                placement('q1-pro-math',720,180,tag='固定版本在途记录')], 'relations':[],
              'cards':[{'dot':'amber','title':'研究不等于已完成','items':['共享E2实体保持原状态，本视图只说明其与当前Q1的接入关系。','不重发Pro问题，不用候选设想或作者自报倍数冒充Q1实测收益。']}]})

old = next(e for e in model['entities'] if e['id'] == 'q1-construction')
updates = {
    'sublabel':'阶段原型已实现 · E0开发例确认 · 可展开',
    'purpose':'情况A第一问：图结构构造、合法Task移动和真实Task剖面拆分合并已有代码与E0开发例证据。事实锚点13d6b02；不是全例终验或统一端到端求解器验收。算法/Pro单写已交fork s-8ee33…；此图由原会话单独整理，任务状态仍由协调者维护。',
    'inputs':['原始计算图JSON、核数、官方固定配置；可选已有合法初始方案。'],
    'outputs':['官方两字段方案JSON、E0复评结果、带明确范围的求解耗时。'],
    'steps':['展开主视图查看已实现构造与评价关系。','展开成果查看官方Makespan与求解wall两类指标。','展开研究查看未接入项和负结果，不把它们读成执行路径。'],
    'openIssues':['全100图、多核数、强基线、统一端到端冷启动和尾部统计尚未完成。','本图不修改Board任务状态，也不代表实时进程在线。'],
    'evidence':[reports['construction-report'],reports['profile-report'],reports['prospective-report'],reports['e2-pro-report']],
}
patch = {'schema':'q1-atlas-scoped-additions-v1','sourceCommit':SOURCE_COMMIT,
         'baseCursor':base['cursor'],'baseRevision':base['revision'],
         'scope':'Only q1-construction descriptive fields and its new child entities/relations/views; no tasks or other view edits.',
         'preserve':['all tasks','all pre-existing view placements/relations','all other entities including shared E0/E1/E2','q1-construction id/type/parent/label/maturity'],
         'updateEntities':[{'id':'q1-construction','expected':{k:old[k] for k in updates},'set':updates}],
         'addEntities':entities,'addRelations':relations,'addViews':views,'addEvidence':evidence}
dump(OUT/'q1.patch.json',patch)
old.update(updates)
for key,items in [('entities',entities),('relations',relations),('views',views),('evidence',evidence)]:
    model[key].extend(items)
dump(OUT/'candidate.system.json',model)
dump(OUT/'evidence-manifest.json',{'sourceCommit':SOURCE_COMMIT,'files':provenance,
      'scope':'Frozen copies for portable Atlas evidence. No new algorithm experiment; imported source or report is not independent acceptance.'})
print(json.dumps({'baseCursor':base['cursor'],'entitiesAdded':len(entities),'relationsAdded':len(relations),'viewsAdded':len(views),'evidenceAdded':len(evidence)}))
