"""Longest-path certificate over an ALREADY PREPARED official execution graph.
No Task/Step2/Step3 calls, cache simulation, or bandwidth event simulation.

Input format:
  {"tasks": {"0": prepared_task, ...}, "cross_links": [...], "delay":500,
   "bandwidth":60, "cache_bandwidth":250, "cache_capacity":1048576}
A prepared task must include graph, pipe_ops and the already exported
MEMORY_REUSE edges. The caller must validate preparation/plan provenance.
"""
from __future__ import annotations
import argparse,json,heapq
from collections import defaultdict
from pathlib import Path

def ceildiv(a,b):return (a+b-1)//b

def normalized(data):
    tasks=data['tasks'];k=len(tasks);BW=data['bandwidth'];CBW=data['cache_bandwidth'];CC=data['cache_capacity']
    nodes={};edges={};mwords={}
    def key(c,u):return f'{c}:{u}'
    def edge(x,y,lag,reason):
        if x==y:raise ValueError('self edge')
        z=edges.setdefault((x,y),{'lag':0,'reasons':set()});z['lag']=max(z['lag'],lag);z['reasons'].add(reason)
    for core,task in tasks.items():
        c=int(core);g=task['graph'];O={x['id']:x for x in g['ops']};T={x['id']:x for x in g['tensors']}
        ins=defaultdict(list);outs=defaultdict(list);producer=defaultdict(set)
        for e in g['edges']:
            u,v=e['source'],e['target']
            if u in O and v in T:outs[u].append(v);producer[v].add(u)
            elif u in T and v in O:ins[v].append(u)
            elif u in O and v in O:edge(key(c,u),key(c,v),0,e.get('dependency','direct'))
            else:raise ValueError('unknown endpoint')
        for v in O:
            for t in ins[v]:
                for u in producer[t]:edge(key(c,u),key(c,v),0,'tensor')
        for u,op in O.items():
            typ=op['op']
            if typ not in ('COPY_IN','COPY_OUT'):
                lower=upper=max(1,op.get('cycles',1))
            else:
                tids=outs[u] if typ=='COPY_IN' else ins[u]
                if not tids:raise ValueError('COPY without tensor endpoints is outside this checker')
                size=sum(T[t]['size'] for t in tids)
                ddr=max(1,ceildiv(size,BW));cache=max(1,ceildiv(size,CBW))
                uses_ddr=any(T[t]['pos']=='DDR' for t in ins[u]+outs[u])
                if typ=='COPY_IN':
                    # Safely optimistic for lower; oversize cannot hit.
                    lower=min(ddr,cache) if size<=CC else ddr
                    upper=max((2*k if uses_ddr else 1)*ddr,k*cache)
                else:
                    lower=ddr;upper=(2*k if uses_ddr else 1)*ddr
            nodes[key(c,u)]={'lower':lower,'upper':upper,'core':c,'op_id':u,'op':typ,
                              'original_M':op['pipe']=='PIPE_M' and typ not in ('COPY_IN','COPY_OUT')}
        orders=task['pipe_ops'];flat=[u for word in orders.values() for u in word]
        if len(flat)!=len(set(flat)) or set(flat)!=set(O):raise ValueError('bad pipe coverage')
        for pipe,word in orders.items():
            if any(O[u]['pipe']!=pipe for u in word):raise ValueError('pipe mismatch')
            for u,v in zip(word,word[1:]):edge(key(c,u),key(c,v),0,'pipe_fifo')
        mwords[c]=[key(c,u) for u in orders.get('PIPE_M',[]) if nodes[key(c,u)]['original_M']]
    for e in data.get('cross_links',[]):
        edge(key(int(e['source_core']),e['source_copy_out_id']),key(int(e['target_core']),e['target_copy_in_id']),data['delay'],'cross_release')
    return nodes,edges,mwords

def longest(nodes,edges,weight):
    degree=dict.fromkeys(nodes,0);succ=defaultdict(list);start=dict.fromkeys(nodes,0);prev={}
    for (u,v),e in edges.items():
        if u not in nodes or v not in nodes:raise ValueError('edge endpoint missing')
        degree[v]+=1;succ[u].append((v,e['lag']))
    ready=[u for u in nodes if not degree[u]];heapq.heapify(ready);finish={}
    while ready:
        u=heapq.heappop(ready);finish[u]=start[u]+nodes[u][weight]
        for v,lag in succ[u]:
            value=finish[u]+lag
            if value>start[v]:start[v]=value;prev[v]=u
            degree[v]-=1
            if not degree[v]:heapq.heappush(ready,v)
    if len(finish)!=len(nodes):raise ValueError('augmented cycle')
    return start,finish,prev

def certificate(nodes,edges,mwords):
    ls,lf,lp=longest(nodes,edges,'lower');us,uf,up=longest(nodes,edges,'upper')
    records=[]
    for c,word in mwords.items():
        if not word:continue
        work=sum(nodes[u]['lower'] for u in word)
        if any(nodes[u]['lower']!=nodes[u]['upper'] for u in word):raise ValueError('M work not fixed')
        first,last=word[0],word[-1]
        chain=[last]
        while chain[-1] in up:chain.append(up[chain[-1]])
        chain.reverse()
        prefix=0;debt=[]
        for u in word:
            debt.append({'node':u,'upper_start':us[u],'busy_prefix':prefix,'upper_debt':us[u]-prefix})
            prefix+=nodes[u]['upper']
        ugaps=[us[v]-uf[u] for u,v in zip(word,word[1:])]
        assert min(ugaps,default=0)>=0
        records.append({'core':c,'M_count':len(word),'M_busy':work,
            'startup_plus_gaps_lower':max(0,lf[last]-work),
            'startup_plus_gaps_upper':max(0,uf[last]-work),
            'internal_gaps_lower':max(0,lf[last]-work-us[first]),
            'internal_gaps_upper':max(0,uf[last]-work-ls[first]),
            'upper_model_gap_sum':sum(ugaps),'upper_model_gap_max':max(ugaps,default=0),
            'upper_model_positive_gap_count':sum(x>0 for x in ugaps),
            'upper_critical_path':chain,'upper_M_debt':debt})
    return {'scope':'constant-duration bounds on fixed prepared execution graph; no event simulation',
        'lower_makespan':max(lf.values(),default=0),'upper_makespan':max(uf.values(),default=0),
        'cores':records,'e0_calls':0}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('prepared_json',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    obj=certificate(*normalized(json.loads(a.prepared_json.read_text())))
    a.output.write_text(json.dumps(obj,indent=2)+'\n')
if __name__=='__main__':main()
