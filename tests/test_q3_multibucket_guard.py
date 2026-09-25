"""Pure multi-compute Task captures; no official constructor or evaluator."""
from copy import deepcopy
import unittest
from src.q3.layered_prepared_guard import check_layered_prepared, PreparedGuardError

PIPES=('PIPE_MTE2','PIPE_MTE3','PIPE_M','PIPE_V')
def op(u,kind,pipe):return {'id':u,'op':kind,'pipe':pipe,'cycles':1}
def t(u,size=1,pos='UB'):return {'id':u,'size':size,'pos':pos}
def e(u,v,**kw):return {'source':u,'target':v,**kw}

def fixture(memory=False):
    raw={'ops':[op(1,'MATMUL','PIPE_M'),op(2,'ADD','PIPE_V')],
         'tensors':[t(10),t(11,0),t(12)],
         'edges':[e(10,1),e(1,11),e(11,2),e(2,12)]}
    plan={'node_to_subgraph':{'1':0,'2':0},'core_schedules':[[0]]}
    ops=[op(100,'COPY_IN','PIPE_MTE2'),op(1,'MATMUL','PIPE_M'),
         op(2,'ADD','PIPE_V'),op(101,'COPY_OUT','PIPE_MTE3')]
    tensors=[t(10),t(11,0),t(12),t(1000,1,'DDR'),t(1001,1,'DDR')]
    pre=[e(1000,100),e(100,10),e(10,1),e(1,11),e(11,2),e(2,12),e(12,101),e(101,1001)]
    mem=[{'source':1,'target':2}] if memory else []
    graph={'ops':ops,'tensors':tensors,'edges':pre+([e(1,2,dependency='MEMORY_REUSE')] if memory else []),
           'seq_ext':[100,1,2,101]}
    pipe={p:[u for u in graph['seq_ext'] if next(o for o in ops if o['id']==u)['pipe']==p] for p in PIPES}
    task={'graph':graph,'seq':graph['seq_ext'],'op_by_id':{o['id']:o for o in ops},
          'tensor_by_id':{x['id']:x for x in tensors},'pipe_ops':pipe,
          'op_subgraph':{u:0 for u in graph['seq_ext']},
          'step3':{'memory_peak':{'L1':0,'UB':2},'memory_dependencies':mem,
                   'pipe_orders':deepcopy(pipe)}}
    step={'seq_ext':graph['seq_ext'],'spill_records':[],'overflow_log':[],
          'new_ops':[],'new_tensors':[],'new_edges':[],'removed_edges':[],
          'ext_edges':pre}
    capture={'task_return':[{0:task},[],0,{'original_graph_copy_bytes':0,
             'scheduled_copy_bytes':2,'added_copy_bytes':2,'spill_added_copy_bytes':0},{}],
             'step2':[step],'capacity':{'L1':2,'UB':2}}
    return raw,plan,capture

class MultiGuard(unittest.TestCase):
    def reject(self,all_args,code,**kwargs):
        with self.assertRaises(PreparedGuardError) as ctx:
            check_layered_prepared(*all_args,layers=0,allow_multi=True,crossing_limit=None,**kwargs)
        self.assertEqual(ctx.exception.code,code)

    def test_same_bucket_memory_and_zero_output(self):
        result=check_layered_prepared(*fixture(True),layers=0,allow_multi=True,crossing_limit=None)
        self.assertEqual(result['status'],'passed')
        self.assertIsNone(result['crossing_limit'])
        self.assertFalse(result['crossing_bound_certified'])
        self.assertEqual(result['complete_seq_closed_interval_peaks'][0]['UB'],1)

    def test_default_singleton_rejects_multi(self):
        with self.assertRaises(PreparedGuardError) as ctx:
            check_layered_prepared(*fixture(),layers=0)
        self.assertEqual(ctx.exception.code,'singleton_mapping')

    def test_complete_sequence_interval_capacity(self):
        a=list(fixture());a[2]['capacity']['UB']=1
        a[0]['tensors'][1]['size']=1
        task=a[2]['task_return'][0][0]
        task['graph']['tensors'][1]['size']=1
        task['tensor_by_id'][11]['size']=1
        task['step3']['memory_peak']['UB']=1
        self.reject(tuple(a),'closed_interval_capacity')

    def test_copy_must_precede_all_consumers(self):
        a=list(fixture());task=a[2]['task_return'][0][0]
        task['seq'][:]=[1,100,2,101]
        a[2]['step2'][0]['seq_ext']=task['seq']
        task['graph']['seq_ext']=task['seq']
        for p in PIPES:
            ids=[u for u in task['seq'] if next(o for o in task['graph']['ops'] if o['id']==u)['pipe']==p]
            task['pipe_ops'][p]=ids;task['step3']['pipe_orders'][p]=ids
        self.reject(tuple(a),'task_data_topology')

    def test_same_bucket_memory_cycle_rejected(self):
        a=list(fixture());task=a[2]['task_return'][0][0]
        task['step3']['memory_dependencies']=[{'source':2,'target':1}]
        task['graph']['edges'].append(e(2,1,dependency='MEMORY_REUSE'))
        self.reject(tuple(a),'union_cycle')

if __name__=='__main__':unittest.main()
