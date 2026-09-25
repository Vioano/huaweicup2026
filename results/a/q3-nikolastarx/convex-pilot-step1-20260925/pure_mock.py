"""Two synthetic checks; no official import or archived 005 read."""
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
p=Path(__file__).with_name('step1_only.py')
spec=spec_from_file_location('step1_only',p);m=module_from_spec(spec);spec.loader.exec_module(m)
g={'ops':[{'id':1,'op':'COPY_IN'},{'id':2,'op':'MATMUL'}],
   'tensors':[{'id':3}], 'edges':[{'source':1,'target':3},{'source':3,'target':2},{'source':1,'target':2,'dependency':'MEMORY_REUSE'}], 'seq_ext':[1,2]}
t={'graph':g,'step3':{'memory_dependencies':[{'source':1,'target':2}]},'seq':[1,2]}
s={'new_ops':[],'new_tensors':[],'new_edges':[],'removed_edges':[], 'spill_records':[],
   'ext_edges':g['edges'][:2],'seq_ext':[1,2]}
restored,_,_=m.reconstruct({'task_return':({'0':t},),'step2':[s]})
assert restored['edges']==g['edges'][:2]
labels=m.copy_labels(restored,{2:20},{2:10},[20],[10],{1:20,2:20})
assert labels=={1:10,2:10}
print('2 pure mocks passed')
