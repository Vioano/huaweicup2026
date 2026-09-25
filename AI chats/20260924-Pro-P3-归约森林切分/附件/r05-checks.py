"""Small abstract checks only; not official scoring or local Step3."""
import json
from pathlib import Path
from m_debt_certificate import certificate

def model(which,n=7,mu=100,nu=10):
    nodes={};edges={}
    def edge(u,v,reason):edges[(u,v)]={'lag':0,'reasons':{reason}}
    for i in range(n):nodes[f'M{i}']={'lower':mu,'upper':mu}
    for i in range(1,n):
        nodes[f'A{i}']={'lower':nu,'upper':nu};edge(f'M{i}',f'A{i}','raw')
        edge('M0' if i==1 else f'A{i-1}',f'A{i}','raw')
    for i in range(n-1):edge(f'M{i}',f'M{i+1}','M_fifo')
    if which=='short':
        for i in range(1,n-1):edge(f'A{i}',f'M{i+1}','memory_reuse')
    else:
        for i in range(1,n-2):edge(f'A{i}',f'M{i+2}','memory_reuse')
        if which=='reader_lock':
            for i in range(1,n-2):edge(f'M{i+1}',f'A{i}','memory_reader_lock')
    obj=certificate(nodes,edges,{0:[f'M{i}' for i in range(n)]})
    return obj

if __name__=='__main__':
    results={x:model(x) for x in ('short','delayed','reader_lock')}
    assert results['short']['cores'][0]['upper_model_gap_sum']==50
    assert results['delayed']['cores'][0]['upper_model_gap_sum']==0
    assert results['reader_lock']['cores'][0]['upper_model_gap_sum']==40
    # Larger, repeated small gaps beat one large gap as a failure, not a success.
    assert results['reader_lock']['cores'][0]['upper_model_gap_max']==10
    p=Path(__file__).parent/'abstract_wait_checks.json';p.write_text(json.dumps(results,indent=2)+'\n')
    print({k:(v['cores'][0]['upper_model_gap_sum'],v['upper_makespan']) for k,v in results.items()})
