"""Read the saved R6 Task artifacts once; issue no scheduling/evaluator calls."""
import argparse
from pathlib import Path

from .construct import ROOT
from .feedback_benchmark import digest, read, verify_source, write
from .static_task_bound import analyze

STATIC = ROOT / 'results/a/q3-nikolastarx/pipeline-prefix-static-20260925'
SUMMARY_SHA = '6f8d0680ca8ebcdf8b35269961881d6d13e7c0524cdea235bd341f4608906b10'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    official, inputs = verify_source(args.source, {'044'})
    if digest(STATIC / 'summary.json') != SUMMARY_SHA:
        raise ValueError('static identity mismatch')
    summary = read(STATIC / 'summary.json')
    if summary['status'] != 'complete':
        raise ValueError('static certificate is incomplete')
    for filename, sha in summary['artifacts'].items():
        if Path(filename).name != filename or digest(STATIC / filename) != sha:
            raise ValueError('static artifact identity mismatch')
    # A newer analysis commit may add files but cannot silently alter the old
    # constructor, official source, graph, or config used by the saved snapshot.
    for filename, sha in summary['source_input_sha256'].items():
        if digest(ROOT / filename) != sha:
            raise ValueError('saved static source identity changed')
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    from multicore_cut_evaluate_problem_3 import read_cache_config
    cfg = ROOT / 'data/raw/a/official/data/config.txt'
    config = read_evaluation_config(cfg)
    settings = {'capacity': config['capacity'], 'ddr_bandwidth': config['bandwidth'],
                'cache_bandwidth': read_cache_config(cfg)['cache_bandwidth_bytes_per_cycle'],
                'cross_core_delay_cycles': read_scene_b_config(cfg)['cross_core_copy_delay_cycles']}
    out = args.output.resolve()
    out.relative_to(ROOT / 'results/a/q3-nikolastarx')
    out.mkdir(exist_ok=False, parents=True)
    snapshots = read(STATIC / 'snapshots.json.gz')
    state = {'source_commit': args.source, 'official_code_sha256': official,
             'source_input_sha256': inputs, 'static_summary_sha256': SUMMARY_SHA,
             'calls': {'Task_builder': 0, 'Step1': 0, 'Step2': 0, 'Step3': 0, 'E0': 0},
             'scope': 'two already saved fixed plans; no new candidate or scheduling',
             'status': 'running', 'analyses': {}}
    write(out / 'summary.json', state)
    try:
        for name in ('anchor', 'candidate'):
            tasks = {}
            for key, data in snapshots[name].items():
                if name == 'anchor':
                    ranks = {sg: i for i, sg in enumerate(data['subgraph_order'])}
                    # Reconstruct the already specified stable bucket word, not
                    # a new Step1 schedule. _interval_peaks checks its topology.
                    word = sorted(data['raw_seq'], key=lambda u: ranks[data['op_subgraph'][str(u)]])
                else:
                    word = data['pre_step2_word']
                tasks[int(key)] = {'graph': data['graph'], 'pre_step2_word': word}
            result = analyze(tasks, snapshots['cross_links'], **settings)
            write(out / f'{name}.json', result)
            state['analyses'][name] = {
                'sha256': digest(out / f'{name}.json'),
                'lower_bound_cycles': result['lower_bound_cycles'],
                'copy_count': result['copy_count'],
                'sole_copy_in_key_count': result['sole_copy_in_key_count']}
        state['status'] = 'complete'
    except BaseException as error:
        state.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        write(out / 'summary.json', state)
    print(state['analyses'])


if __name__ == '__main__':
    main()
