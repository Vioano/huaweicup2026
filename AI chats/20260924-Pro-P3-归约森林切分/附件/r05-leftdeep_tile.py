"""Static, owner-preserving left-deep Cartesian tiling. No official evaluator calls.

The computed-output/no-intra-layer-input-spill statement is conditional on the
frozen Step2 Belady rule and singleton bucket reconstruction in the report.
No zero-total-spill or Makespan claim is made by this module.
"""
from __future__ import annotations
import argparse, json, hashlib, heapq
from collections import defaultdict, deque, Counter
from pathlib import Path

class Unsupported(ValueError): pass

def need(ok, text):
    if not ok: raise Unsupported(text)

def ceildiv(a,b): return (a+b-1)//b

def recognize(g):
    O={o['id']:o for o in g['ops']}; T={t['id']:t for t in g['tensors']}
    need(len(O)==len(g['ops']) and len(T)==len(g['tensors']) and not(set(O)&set(T)), 'IDs')
    comp={u:o for u,o in O.items() if o['op'] not in ('COPY_IN','COPY_OUT')}
    I=defaultdict(list); U=defaultdict(list); prod=defaultdict(list); readers=defaultdict(list)
    for e in g['edges']:
        x,y=e['source'],e['target']
        if x in O and y in T: U[x].append(y);prod[y].append(x)
        elif x in T and y in O: I[y].append(x);readers[x].append(y)
        else: raise Unsupported('requires original tensor-mediated ports')
    need(all(len(v)==1 for v in prod.values()),'unique original producers')
    pred={u:{p for t in I[u] for p in prod[t] if p in comp} for u in comp}
    succ={u:set() for u in comp}
    for v,ps in pred.items():
        for u in ps: succ[u].add(v)
    need(all(len(s)<=1 for s in succ.values()),'not a forest')
    roots=sorted(u for u in comp if not succ[u]); cells=[]; seen=set()
    for root in roots:
        back=[]; joins=[]; u=root
        while True:
            need(comp[u]['op']=='ADD' and comp[u]['pipe']=='PIPE_V' and len(pred[u])==2,'not binary left-deep ADD')
            ps=sorted(pred[u]); ms=[v for v in ps if comp[v]['op']=='MATMUL']; ads=[v for v in ps if comp[v]['op']=='ADD']
            joins.append(u)
            if len(ms)==2:
                base=ms;break
            need(len(ms)==len(ads)==1,'ADD spine is not left deep')
            back.append(ms[0]);u=ads[0]
        leaves=base+list(reversed(back)); adds=list(reversed(joins))
        nodes=set(leaves+adds)
        need(not(nodes&seen),'overlapping original trees');seen|=nodes
        cells.append({'root':root,'base':base,'leaves':leaves,'adds':adds,'nodes':nodes})
    need(seen==set(comp) and len(cells)>0,'cover')
    c_of={u:h for h,c in enumerate(cells) for u in c['nodes']}
    ext=set(); output_sizes=set(); msizes=set(); vsizes=set(); lengths=set()
    for c in cells:
        lengths.add(len(c['leaves']))
        for u in c['nodes']:
            need(len(U[u])==1 and len(I[u])==2,'exact compute ports')
            ot=U[u][0];need(T[ot]['pos']=='L1','prototype requires every compute output in L1')
            output_sizes.add(T[ot]['size'])
            if u in c['leaves']:
                need(comp[u]['pipe']=='PIPE_M' and not pred[u],'leaf pipe / predecessors')
                msizes.add(comp[u]['cycles']);ext.update(I[u])
                for t in I[u]: need(T[t]['pos']=='L1' and not any(p in comp for p in prod[t]),'leaf external input')
            else: vsizes.add(comp[u]['cycles']);need(set(pred[u])=={prod[t][0] for t in I[u]},'extra ADD port')
            if u==c['root']:
                rr=readers[ot];need(len(rr)==1 and O[rr[0]]['op']=='COPY_OUT','root needs one COPY_OUT')
            else: need(set(readers[ot])==succ[u] and len(readers[ot])==1,'hidden internal consumer')
    need(len(lengths)==len(output_sizes)==len(msizes)==len(vsizes)==1,'homogeneous tree signature')
    L=next(iter(lengths));s=next(iter(output_sizes));mu=next(iter(msizes));nu=next(iter(vsizes))
    need(L>=2 and min(s,mu,nu)>0,'positive parameters')
    copies=set()
    for t in ext:
        pp=prod[t];need(len(pp)==1 and O[pp[0]]['op']=='COPY_IN','input backing')
        cp=pp[0];copies.add(cp)
        need(U[cp]==[t] and len(I[cp])==1 and T[I[cp][0]]['pos']=='DDR' and T[I[cp][0]]['size']==T[t]['size'],'COPY_IN ports')
    for c in cells:
        t=U[c['root']][0];cp=readers[t][0];copies.add(cp)
        need(I[cp]==[t] and len(U[cp])==1 and T[U[cp][0]]['pos']=='DDR' and T[U[cp][0]]['size']==s,'COPY_OUT ports')
    need(copies==set(O)-set(comp),'unrecognized copies')
    masks=defaultdict(list)
    for t in sorted(ext):
        need(all(u in comp and comp[u]['op']=='MATMUL' for u in readers[t]),'input consumers')
        masks[tuple(sorted({c_of[u] for u in readers[t]}))].append(t)
    group=list(masks.values()); gt={t:h for h,x in enumerate(group) for t in x}
    members={}
    for h,c in enumerate(cells):
        gs={gt[t] for u in c['leaves'] for t in I[u]};need(len(gs)==2,'two groups per cell');members[h]=gs
    adj={h:set() for h in range(len(group))}
    for x,y in (sorted(gs) for gs in members.values()):adj[x].add(y);adj[y].add(x)
    color={0:0};qq=deque([0])
    while qq:
        x=qq.popleft()
        for y in adj[x]:
            if y not in color:color[y]=1-color[x];qq.append(y)
            need(color[y]!=color[x],'bipartite')
    need(len(color)==len(group),'connected input reuse grid')
    axes=[[h for h in range(len(group)) if color[h]==v] for v in (0,1)]
    # Name the heavier per-position input axis A; names do not alter any graph edge.
    aw=[sum(T[t]['size'] for t in group[x]) for x in axes[0]]
    bw=[sum(T[t]['size'] for t in group[x]) for x in axes[1]]
    need(len(set(aw))==len(set(bw))==1,'uniform group bytes on each axis')
    if aw[0]<bw[0]:axes.reverse()
    coords={};rank=[{g:r for r,g in enumerate(axis)} for axis in axes]
    for h,gs in members.items():
        x=next(iter(gs&set(axes[0]))); y=next(iter(gs&set(axes[1])))
        ij=(rank[0][x],rank[1][y]);need(ij not in coords,'duplicate cell');coords[ij]=h
    m,n=map(len,axes);need(len(coords)==m*n,'complete grid')
    # Resolve the two symmetric seed leaves by their input-pair connected components.
    seedadj=defaultdict(set)
    for c in cells:
        for u in c['base']:
            x,y=I[u];seedadj[x].add(y);seedadj[y].add(x)
    seedclass={};classes=[]
    for root in sorted(seedadj):
        if root in seedclass:continue
        q=[root];nodes=set()
        while q:
            u=q.pop()
            if u in nodes:continue
            nodes.add(u);q.extend(seedadj[u]-nodes)
        cid=len(classes);classes.append(nodes)
        for u in nodes:seedclass[u]=cid
    need(len(classes)==2,'seed input positions do not align across cells')
    At={};Bt={}; used_inputs=set()
    for (i,j),h in coords.items():
        c=cells[h];c['leaves'][:2]=sorted(c['base'],key=lambda u:seedclass[I[u][0]])
        for t,u in enumerate(c['leaves']):
            ins=I[u];aa=[x for x in ins if gt[x] in rank[0]];bb=[x for x in ins if gt[x] in rank[1]]
            need(len(aa)==len(bb)==1,'one A and one B per leaf')
            for d,key,value in ((At,(i,t),aa[0]),(Bt,(j,t),bb[0])):
                need(key not in d or d[key]==value,'same chain position uses inconsistent input key');d[key]=value
            used_inputs|=set(ins)
        for t,u in enumerate(c['adds'],1):
            expected={c['leaves'][0],c['leaves'][1]} if t==1 else {c['adds'][t-2],c['leaves'][t]}
            need(pred[u]==expected,'original ADD association changed')
    need(len(set(At.values()))==m*L and len(set(Bt.values()))==n*L and not(set(At.values())&set(Bt.values())),'aliased chain-position keys')
    need(used_inputs==ext,'input cover')
    avec={T[t]['size'] for t in At.values()};bvec={T[t]['size'] for t in Bt.values()}
    need(len(avec)==len(bvec)==1,'uniform leaf input sizes')
    a=next(iter(avec));b=next(iter(bvec))
    need(all(len(group[x])==L for axis in axes for x in axis),'L tensors per group')
    return dict(m=m,n=n,L=L,s=s,mu=mu,nu=nu,a=a,b=b,cells=cells,coords=coords,
                ops=comp,tensors=T,inputs=I,outputs=U,pred=pred,external=ext,At=At,Bt=Bt)

def owner_from_plan(model,plan):
    mapping={int(u):sg for u,sg in plan['node_to_subgraph'].items()}
    need(set(mapping)==set(model['ops']) and len(set(mapping.values()))==len(mapping),'singleton mapping required')
    sgowner={}
    for c,word in enumerate(plan['core_schedules']):
        for sg in word:
            need(sg not in sgowner,'duplicate singleton');sgowner[sg]=c
    need(set(sgowner)==set(mapping.values()),'schedule cover')
    k=len(plan['core_schedules']);need(1<=k<=5,'core count')
    co={}
    for ij,h in model['coords'].items():
        oo={sgowner[mapping[u]] for u in model['cells'][h]['nodes']};need(len(oo)==1,'baseline splits an original tree');co[ij]=next(iter(oo))
    return co,mapping,k

def tiles(model,co,k,p,q):
    out=[[] for _ in range(k)]
    for i0 in range(0,model['m'],p):
        for j0 in range(0,model['n'],q):
            for c in range(k):
                cells=[(i,j) for i in range(i0,min(i0+p,model['m'])) for j in range(j0,min(j0+q,model['n'])) if co[i,j]==c]
                if cells:out[c].append(cells)
    return out

def tile_word(model,cells,mode='stagger'):
    pending=None;word=[]
    for t in range(model['L']):
        if mode=='batch':
            word.extend(model['cells'][model['coords'][ij]]['leaves'][t] for ij in cells)
            if t:word.extend(model['cells'][model['coords'][ij]]['adds'][t-1] for ij in cells)
        else:
            for ij in cells:
                c=model['cells'][model['coords'][ij]]
                word.append(c['leaves'][t])
                if pending is not None:word.append(pending)
                pending=c['adds'][t-1] if t else None
    if mode!='batch' and pending is not None:word.append(pending)
    return word

def protection_peak(model,word):
    """Exact sequential current-tile protected peak, not actual occupancy."""
    pos={u:i for i,u in enumerate(word)};lo={};hi={}
    for u in word:
        for t in model['inputs'][u]+model['outputs'][u]:
            lo[t]=min(lo.get(t,len(word)),pos[u]);hi[t]=max(hi.get(t,-1),pos[u])
    plus=defaultdict(int);minus=defaultdict(int)
    for t in lo:
        plus[lo[t]]+=model['tensors'][t]['size'];minus[hi[t]]+=model['tensors'][t]['size']
    x=peak=0
    for i in range(len(word)):x+=plus[i];peak=max(peak,x);x-=minus[i]
    need(x==0,'interval closure')
    return peak

def choose_shape(model,co,k,C=524288,B=60):
    need(model['mu']>=model['nu'],'this M-dominant stagger template requires mu >= nu')
    a,b,s,L=model['a'],model['b'],model['s'],model['L']
    W=[sum(c==h for c in co.values())*L*model['mu'] for h in range(k)]
    candidates=[]
    for p in range(1,model['m']+1):
        for q in range(1,model['n']+1):
            ts=tiles(model,co,k,p,q);cp=[];ok=True;readB=[];phi=[];Q=[]
            for c,tt in enumerate(ts):
                read=units=peak=0
                for tile in tt:
                    d=len(tile);r=len({i for i,j in tile});z=len({j for i,j in tile})
                    # Exact future-use envelope also counts already-resident upcoming-layer inputs.
                    qb,_ = future_use_envelope(model, tile_word(model,tile))
                    peak=max(peak,qb);ok &= qb<=C
                    # Separate reserved-buffer model guard, not an E0 occupancy bound.
                    ok &= (d+3)*s+r*a+z*b+a+b <= C
                    read += L*(r*a+z*b)
                    units += L*(r*ceildiv(a,B)+z*ceildiv(b,B))
                roots=sum(len(t) for t in tt)
                readB.append(read);Q.append(peak)
                # Conditional no-extra-credit-stall service envelope, NOT an E0 bound.
                phi.append(W[c]+2*k*(units+roots*ceildiv(s,B))+len(tt)*model['nu'])
            if ok:candidates.append(dict(p=p,q=q,read_bound=readB,protected_bound=Q,
                        conditional_service_envelope=phi,tile_counts=list(map(len,ts)),
                        key=(max(phi,default=0),sum(readB),max(Q,default=0),p,q)))
    need(candidates,'no protected template fits')
    best=min(candidates,key=lambda x:x['key'])
    return best,candidates

def construct(g,base,C=524288,B=60):
    md=recognize(g);co,mapping,k=owner_from_plan(md,base)
    best,candidates=choose_shape(md,co,k,C,B);ts=tiles(md,co,k,best['p'],best['q'])
    words=[[] for _ in range(k)];peak=[]
    for c,tt in enumerate(ts):
        vals=[]
        for tile in tt:
            w=tile_word(md,tile);words[c].extend(w);vals.append(protection_peak(md,w))
        peak.append(max(vals,default=0))
    for c,word in enumerate(words):
        ranks={u:i for i,u in enumerate(word)}
        for u in word:
            need(all(v in ranks and ranks[v]<ranks[u] for v in md['pred'][u]),'raw precedence')
    need(sum(map(len,words))==len(md['ops']) and len({u for w in words for u in w})==len(md['ops']),'cover')
    new={'node_to_subgraph':base['node_to_subgraph'], 'core_schedules':[[mapping[u] for u in word] for word in words]}
    first_input=sum(sum(md['tensors'][t]['size'] for t in {t for ij in co if co[ij]==c for u in md['cells'][md['coords'][ij]]['leaves'] for t in md['inputs'][u]}) for c in range(k))
    # Original once-per-graph inputs vs per-Task initial copies are separate quantities.
    original_input=sum(md['tensors'][t]['size'] for t in md['external'])
    meta={'parameters':{x:md[x] for x in ('m','n','L','a','b','s','mu','nu')},
          'selected':best,'algebraic_feasible_shapes':len(candidates),
          'current_tile_live_peak_by_core':peak,
          'protection_certificate':'future-use envelope in selected.protected_bound, not the current-tile peak',
          'task_first_input_bytes':first_input,'original_input_bytes':original_input,
          'conditional_input_copy_bound_bytes':sum(best['read_bound']),
          'step2_input_reload_bound_bytes':sum(best['read_bound'])-first_input,
          'conditional_total_extra_copy_bound_bytes':sum(best['read_bound'])-original_input,
          'raw_node_count':len(md['ops']),'same_original_owner':True,
          'raw_static_precedence_and_cover':True,
          'official_derivation_called':False,'task_builds':0,'step2_calls':0,'step3_calls':0,'e0_calls':0,
          'claim_scope':'Step2 bound needs specified singleton reconstruction/Belady guards; no E0 makespan claim',
          'all_shape_records':candidates}
    return new,meta,md,words

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('graph',type=Path);p.add_argument('baseline_plan',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--capacity',type=int,required=True);p.add_argument('--bandwidth',type=int,required=True)
    a=p.parse_args();need(not a.output.exists(),'output must not exist')
    plan,meta,_,_=construct(json.loads(a.graph.read_text()),json.loads(a.baseline_plan.read_text()),a.capacity,a.bandwidth)
    a.output.mkdir(parents=True);(a.output/'plan.json').write_text(json.dumps(plan,separators=(',',':'))+'\n');(a.output/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')

# Deliberately defined separately: the simple current-layer peak above is NOT
# sufficient to protect accumulators from already-resident future-layer inputs.
def future_use_envelope(model, word):
    """Worst resident input mass ahead of protected original-output consumers.

    Returns an upper bound for the Step2-protected set. Counts distinct external
    keys in each closed compute interval [j,H(j)], not just already-first-used
    inputs. Original root COPY_OUT is in the root singleton bucket.
    """
    pos={u:i for i,u in enumerate(word)};lo={};hi={}
    for u in word:
        for t in model['inputs'][u]+model['outputs'][u]:
            lo[t]=min(lo.get(t,len(word)),pos[u]);hi[t]=max(hi.get(t,-1),pos[u])
    new=defaultdict(list);ends=defaultdict(list)
    for t in lo:new[lo[t]].append(t);ends[hi[t]].append(t)
    alive_out=0;heap=[];counts=Counter();input_bytes=0;right=-1;peak=0;witness=None
    external=model['external'];T=model['tensors']
    for j,u in enumerate(word):
        for t in new[j]:
            heapq.heappush(heap,(-hi[t],t))
            if t not in external:alive_out+=T[t]['size']
        while heap and -heap[0][0]<j:heapq.heappop(heap)
        h=max(j,-heap[0][0] if heap else j)
        while right<h:
            right+=1
            for t in model['inputs'][word[right]]:
                if t in external:
                    if counts[t]==0:input_bytes+=T[t]['size']
                    counts[t]+=1
        if alive_out+input_bytes>peak:
            peak=alive_out+input_bytes;witness={'position':j,'horizon':h,'op':u,
                                                'output_bytes':alive_out,'future_input_bytes':input_bytes}
        for t in model['inputs'][u]:
            if t in external:
                counts[t]-=1
                if counts[t]==0:input_bytes-=T[t]['size']
        for t in ends[j]:
            if t not in external:alive_out-=T[t]['size']
    need(alive_out==input_bytes==0,'envelope closure')
    return peak,witness

if __name__=='__main__':main()
