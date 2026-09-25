"""Only arithmetic/metadata tests; zero official compilation or responses."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor'))
from archived_recognizer import views
from reuse_prekey import release_word
from edge_envelope import Resources,value,F

reports=[];count=0
# Predetermined abstract resource examples, not measured graph scores.
examples=[(Resources(11,17,11,8,5,10,(9,9),100),0,0,(1,7,0,7)),
          (Resources(11,17,11,8,5,10,(9,9),100),2,1,(1,5,0,5)),
          (Resources(3,23,7,14,9,19,(8,7,7),100),3,2,(1,4,0,4))]
for model,n,r,box in examples:
    record=model.box(n,r,box);edge,tail=model.forms(n,r)
    vals=[]
    for q in range(box[0],box[1]+1):
        for s in range(box[2],min(q,box[3])+1):
            x=max(value(a,F(q),F(s)) for a in edge)+max(value(a,F(q),F(s)) for a in tail)
            assert record['integer_lower_bound']<=x
            vals.append(int(x));count+=1
    record['integer_minimum_exhaustive_for_small_test']=min(vals)
    reports.append(record)
probe=ROOT/'results/set_order_probe'
g0=json.loads((probe/'graph_0.json').read_text());g7=json.loads((probe/'graph_7.json').read_text())
nodes=[o['id'] for o in g0['ops'] if o['op'] not in ('COPY_IN','COPY_OUT')]
w0=release_word(views(g0),nodes);w7=release_word(views(g7),nodes)
assert w0!=w7
result={'kind':'pure-metadata-arithmetic-tests_NOT_response_NOT_E0',
        'refined_release_keys_differ':True,'release_words':[w0,w7],
        'box_tests':reports,'integer_points_checked':count,
        'calls':{'official_static_task_compiles':0,'response_simulations':0,'E0':0,'E1':0,'E2':0}}
(ROOT/'results/metadata_tests.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('box_tests','release_words')},indent=2))
