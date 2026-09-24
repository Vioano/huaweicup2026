"""Read-only 079 timeline audit. Usage: python3 script.py NEW_P3 OLD_P3 GRAPH OUT_PREFIX"""
import argparse, collections, gzip, json
from pathlib import Path

def read(p):
    p=Path(p)
    with gzip.open(p,'rt') if p.suffix=='.gz' else p.open() as f:return json.load(f)

def audit(name, result, graph, core_id):
    core=result['per_core_timeline'][core_id]; ops=core['ops']
    m=sorted((o for o in ops if o['pipe']=='PIPE_M'),key=lambda o:(o['start'],o['end']))
    incoming=collections.defaultdict(list); op_by_id={o['id']:o for o in graph['ops']}
    for e in graph['edges']:incoming[e['target']].append(e['source'])
    copies=collections.defaultdict(list)
    for o in ops:
        if o['op']=='COPY_IN' and 'cache_tensor_id' in o:copies[o['cache_tensor_id']].append(o)
    for cs in copies.values():cs.sort(key=lambda o:o['end'])
    gaps=sorted(((b['start']-a['end'],idx,a,b) for idx,(a,b) in enumerate(zip(m,m[1:]))),key=lambda x:(-x[0],x[1]))
    rows=[]
    for gap,idx,a,b in gaps[:3]:
        inputs=[]
        for tensor in incoming[b['op_id']]:
            producers=incoming[tensor]
            matching=[x for x in copies[tensor] if x['end']<=b['start']]
            last=matching[-1] if matching else None
            inputs.append({'tensor':tensor,'original_producer_ops':[{'id':p,'op':op_by_id[p]['op']} for p in producers if p in op_by_id], 'latest_visible_COPY_IN_before_M':None if last is None else {k:last.get(k) for k in ('op_id','start','end','memory_path','cache_hit')},'copy_end_to_M_start':None if last is None else b['start']-last['end']})
        overlap=[o for o in ops if o['pipe']!='PIPE_M' and o['start']<b['start'] and o['end']>a['end']]
        rows.append({'rank':len(rows)+1,'M_position':idx+1,'gap':gap,'gap_start':a['end'],'gap_end':b['start'],'preceding_M_op':a['op_id'],'following_M_op':b['op_id'],'following_M_start':b['start'],'inputs':inputs,'overlap_other_pipes':[{'op_id':o['op_id'],'op':o['op'],'pipe':o['pipe'],'start':o['start'],'end':o['end'],'subgraph_id':o['subgraph_id']} for o in overlap]})
    busy=sum(o['end']-o['start'] for o in m)
    assert all(a['end']<=b['start'] for a,b in zip(m,m[1:]))
    summary={'first_M_start':m[0]['start'],'last_M_end':m[-1]['end'],
             'busy_M':busy,'internal_M_gaps':sum(x[0] for x in gaps),
             'core_end':max(o['end'] for o in ops),
             'tail_after_M':max(o['end'] for o in ops)-m[-1]['end']}
    assert summary['first_M_start']+busy+summary['internal_M_gaps']+summary['tail_after_M']==summary['core_end']
    return {'name':name,'core':core_id,'makespan':result['makespan'],'summary':summary,'top_gaps':rows}

def main():
    p=argparse.ArgumentParser();p.add_argument('new_p3');p.add_argument('old_p3');p.add_argument('graph');p.add_argument('out_prefix');a=p.parse_args()
    g=read(a.graph);data={'new_pair':audit('new_pair',read(a.new_p3),g,0),'oldforest':audit('oldforest',read(a.old_p3),g,2)}
    Path(a.out_prefix+'.json').write_text(json.dumps(data,indent=2)+'\n')
    lines=['# 079-k5 最大 PIPE_M 间隙的局部证据','','只读统计；分别按各关键核 PIPE_M 执行序位排序，不跨 owner 按 op_id 强行配对。周期均为官方模拟时钟。','']
    for key,x in data.items():
        lines+=['## '+key+f"（核 {x['core']}，M={x['makespan']}）",'']
        for r in x['top_gaps']:
            lines += [f"- 第 {r['M_position']}→{r['M_position']+1} 个 PIPE_M：空隙 {r['gap']}，[{r['gap_start']}, {r['gap_end']}]；后继原图 op {r['following_M_op']}。"]
            for t in r['inputs']:
                ps=','.join(str(z['id'])+' '+z['op'] for z in t['original_producer_ops'])
                c=t['latest_visible_COPY_IN_before_M'];avail=('未找到可见 COPY_IN' if c is None else f"合成 op {c['op_id']} 在 {c['end']} 完成，早于后继 M {t['copy_end_to_M_start']} 周期")
                lines += [f"  - 输入张量 {t['tensor']}：原图直接生产者 {ps}；{avail}。"]
            lines += ['  - 空隙中可见其他 pipe：'+', '.join(f"{o['op']} {o['pipe']} [{o['start']},{o['end']}]" for o in r['overlap_other_pipes'])+'。']
        lines+=['']
    lines+=['图中直接生产者均为 COPY_IN；结果时间线不保留原 COPY_IN op_id 到合成 COPY_IN op_id 的直接映射。按张量 ID 匹配，旧 forest 最大两个空隙的某个输入 COPY 恰在后继 M 开始时完成，这是候选输入就绪边界；未匹配张量incarnation与完整内部依赖，不能证明这段 COPY 是整个间隙的唯一原因。新 pair 三个最大空隙的最近输入 COPY 均提前 63 周期完成，后继 M 同时与第三个 ADD 的结束时刻对齐；它们呈现不同的局部边界，是否由依赖、任务内排序或调度优先规则决定，单靠结果时间线无法确定。区间重叠不证明因果；没有重造 E0 调度器。']
    Path(a.out_prefix+'.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
