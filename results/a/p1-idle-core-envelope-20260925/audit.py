#!/usr/bin/env python3
"""Compute a retrospective idle-core Makespan envelope from one fixed feed."""
from __future__ import annotations
import hashlib
import json
import subprocess
import gzip
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
COMMIT = '0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297'
FEED = 'results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json'
OUT = Path(__file__).with_name('recomputed-summary.json')


def main() -> None:
    raw = subprocess.check_output(['git', 'show', f'{COMMIT}:{FEED}'], cwd=REPO)
    source_sha = hashlib.sha256(raw).hexdigest()
    feed = json.loads(raw)
    records = feed['records']
    table: dict[tuple[str, int], int] = {}
    baseline_ref: dict[str, dict] = {}
    for rec in records:
        case = str(rec['case_id']).zfill(3)
        cores = rec['cores']
        if rec['status'] != 'ok':
            raise ValueError(f'non-ok record {case}/k{cores}: {rec["status"]}')
        makespan = rec['metrics']['makespan_cycles']
        if type(makespan) is not int or makespan <= 0:
            raise ValueError(f'invalid Makespan {case}/k{cores}: {makespan!r}')
        key = (case, cores)
        if key in table:
            raise ValueError(f'duplicate cell {key}')
        table[key] = makespan
        ref = rec['baseline']
        if ref['route'] != 'E0' or ref['entrypoint'] != 'singlecore_evaluate.evaluate_singlecore':
            raise ValueError(f'baseline is not the official single-core E0 for {case}')
        old = baseline_ref.setdefault(case, ref)
        if old != ref:
            raise ValueError(f'baseline reference differs between K cells for {case}')
    expected = {(f'{i:03d}', k) for i in range(1, 101) for k in range(1, 6)}
    if set(table) != expected or len(records) != 500:
        raise ValueError(f'expected exactly 100x5 successful cells; got {len(table)} unique cells')

    baselines = {}
    for case, ref in sorted(baseline_ref.items()):
        compressed = subprocess.check_output(['git', 'show', f'{COMMIT}:{ref["result"]["path"]}'], cwd=REPO)
        if hashlib.sha256(compressed).hexdigest() != ref['result']['sha256']:
            raise ValueError(f'baseline compressed result SHA mismatch: {case}')
        baseline = json.loads(gzip.decompress(compressed))
        value = baseline['makespan']
        if baseline.get('scene') != 'A' or baseline.get('num_cores') != 1 or type(value) is not int or value <= 0:
            raise ValueError(f'invalid baseline result identity/value: {case}')
        baselines[case] = value
    if set(baselines) != {f'{i:03d}' for i in range(1, 101)}:
        raise ValueError('expected one referenced single-core baseline result per graph')

    per_core = {}
    speedup_summaries = {}
    per_graph = {}
    improved_counts = {}
    improved_total = 0
    best5 = []
    best_any = None
    source_counts = Counter()
    for k in range(1, 6):
        original = [table[(case, k)] for case in sorted({c for c, _ in table})]
        envelopes = []
        original_speedups = []
        envelope_speedups = []
        per_case_speedup_deltas = []
        n_improved = 0
        for case in sorted({c for c, _ in table}):
            choices = [(table[(case, j)], j) for j in range(1, k + 1)]
            envelope, source_core = min(choices)
            base = table[(case, k)]
            delta = base - envelope
            envelopes.append(envelope)
            original_speedups.append(baselines[case] / base)
            envelope_speedups.append(baselines[case] / envelope)
            per_case_speedup_deltas.append((baselines[case] / envelope - baselines[case] / base, case))
            source_counts[str(source_core)] += 1
            if delta > 0:
                n_improved += 1
                improved_total += 1
            item = {'case_id': case, 'cores_k': k, 'original_makespan_cycles': base,
                    'envelope_makespan_cycles': envelope, 'improvement_cycles': delta,
                    'envelope_source_cores': source_core,
                    'improvement_percent_of_original': 100.0 * delta / base}
            per_graph.setdefault(case, {})[str(k)] = item
            if k == 5:
                best5.append(item)
            if best_any is None or delta > best_any['improvement_cycles']:
                best_any = item
        per_core[str(k)] = {
            'original_makespan_arithmetic_mean_cycles': sum(original) / 100,
            'idle_core_envelope_arithmetic_mean_cycles': sum(envelopes) / 100,
            'mean_reduction_cycles': sum(original[i] - envelopes[i] for i in range(100)) / 100,
            'mean_reduction_percent_of_original_mean': 100.0 * (sum(original) - sum(envelopes)) / sum(original),
            'improved_graph_cells': n_improved,
            'graph_cells': 100,
        }
        speedup_summaries[str(k)] = {
            'original_arithmetic_mean_case_speedup': sum(original_speedups) / 100,
            'idle_core_envelope_arithmetic_mean_case_speedup': sum(envelope_speedups) / 100,
            'mean_speedup_increment': sum(envelope_speedups[i] - original_speedups[i] for i in range(100)) / 100,
            'largest_increment_contributor': {
                'case_id': max(per_case_speedup_deltas)[1],
                'speedup_increment': max(per_case_speedup_deltas)[0],
                'baseline_makespan_cycles': baselines[max(per_case_speedup_deltas)[1]],
                'original_makespan_cycles': table[(max(per_case_speedup_deltas)[1], k)],
                'envelope_makespan_cycles': per_graph[max(per_case_speedup_deltas)[1]][str(k)]['envelope_makespan_cycles'],
                'envelope_source_cores': per_graph[max(per_case_speedup_deltas)[1]][str(k)]['envelope_source_cores'],
            },
        }
        improved_counts[str(k)] = n_improved
    max5 = max(best5, key=lambda x: x['improvement_cycles'])
    result = {
        'kind': 'retrospective idle-core Makespan envelope; potential estimate only',
        'source': {'commit': COMMIT, 'feed_path': FEED, 'feed_sha256': source_sha,
                   'schema_version': feed.get('schema_version'), 'submission_version': feed.get('submission_version')},
        'method': {
            'cell_metric': "records[].metrics.makespan_cycles",
            'formula': 'for each graph and K, min of the already saved Makespan values at k=1..K',
            'means': 'arithmetic mean across the 100 graphs separately for each K',
            'improvement': 'original Makespan at K minus that graph K envelope; positive means lower Makespan in the envelope',
            'assumption': 'an already saved lower-core plan could be run with the remaining cores idle without changing its semantics or score',
            'status': 'No plan was transformed or evaluated. This envelope is not a new unified-algorithm score.'
        },
        'coverage': {'graphs': 100, 'cores': [1, 2, 3, 4, 5], 'successful_cells': len(table)},
        'per_core_summary': per_core,
        'official_primary_metric_summary': speedup_summaries,
        'baseline_source': {
            'reference': 'each record.baseline.result, deduplicated to one result per graph',
            'sha256_check': 'verified the compressed bytes against each feed reference before gzip decompression',
            'unique_results_read': len(baselines),
            'speedup_formula': 'per graph, baseline single-core Makespan / multi-core Makespan; arithmetic mean of 100 per-graph ratios for each K',
        },
        'improved_cells_by_K': improved_counts,
        'improved_cells_total_across_K': improved_total,
        'largest_improvement_any_K': best_any,
        'largest_improvement_at_K5': max5,
        'envelope_source_core_distribution_over_all_500_cells': dict(sorted(source_counts.items(), key=lambda x: int(x[0]))),
        'per_graph_cells': per_graph,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'feed_sha256': source_sha, 'output': str(OUT), 'per_core_summary': per_core,
                      'improved_cells_by_K': improved_counts, 'improved_cells_total': improved_total,
                      'largest_at_K5': max5,
                      'envelope_source_core_distribution_over_all_500_cells': dict(source_counts)},
                     ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
