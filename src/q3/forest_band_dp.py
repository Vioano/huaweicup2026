"""R4 (54a4a91e) integration adapter from archived certificate ZIP.


The author only syntax-checked the original attachment. Local bounded tests
also exercise recognition and static plan guards on the original 058/079 graphs.
No E0/Step2/Step3 is called. Whole trees and original DFS words are retained.
Default tree-order control matches forest_memory_order's component-ID rule.
"""
from .construct import derive_multicore_plan
from .forest_reuse_grid import recognize
from .forest_memory_order import construct as memory_order
from .grid_band_dp import construct_grid, row_block_word


def construct(index, cores, *, order_mode='component_id'):
    if order_mode not in {'component_id','pair_cache_model'}:
        raise ValueError('unknown tree-order mode')
    model=recognize(index)
    _,meta=memory_order(index,cores)  # existing raw-tree guard + unchanged DFS words
    dfs={rec['min_op_id']:rec['dfs_postorder'] for rec in meta['predicted_frontier']}
    axes=model['axes']
    a=[model['group_bytes'][g] for g in axes[0]]
    b=[model['group_bytes'][g] for g in axes[1]]
    result=construct_grid(a,b,cores)
    assignments=[];pair_predictions=[]
    for cells in result['parts']:
        if order_mode=='pair_cache_model':
            forward,cost0=row_block_word(cells,a,b)
            transposed,cost1=row_block_word([(j,i) for i,j in cells],b,a)
            reverse=[(j,i) for i,j in transposed]
            ordered,cost=(forward,cost0) if cost0<=cost1 else (reverse,cost1)
            jobs=[model['cells'][axes[0][i],axes[1][j]] for i,j in ordered]
            pair_predictions.append(cost)
        else:
            jobs=sorted((model['cells'][axes[0][i],axes[1][j]] for i,j in cells),
                        key=lambda cid:min(index.components[cid]))
        assignments.append(jobs)
    mapping={str(u):i for i,u in enumerate(index.order)}
    schedules=[[mapping[str(u)] for cid in jobs
                for u in dfs[min(index.components[cid])]] for jobs in assignments]
    plan={'node_to_subgraph':mapping,'core_schedules':schedules}
    derive_multicore_plan(index.graph,plan)
    details={k:v for k,v in result.items() if k!='parts'}
    details.update(strategy='forest_serpentine_band_quota_dp',
                   component_counts=[len(x) for x in assignments],
                   component_pipe_work=model['component_pipe_work'],
                   components_by_core=assignments,tree_order_mode=order_mode,
                   pair_cache_model_input_bytes=(sum(pair_predictions) if pair_predictions else None),
                   official_evaluations=0,
                   scope='D optimization within a path family; NOT official Makespan, spill, or hit optimization',
                   preserved='original ops, tensor ports, tree shape and existing per-tree DFS word')
    return plan,details
