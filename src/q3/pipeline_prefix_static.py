"""Reproduce one R6 prefix proposal without Step2, Step3 or scoring.

This is a fixed mechanism diagnostic, not a full-suite solver. The general
constructor lives in pipeline_prefix and does not depend on the case number.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

from .construct import Index, ROOT
from .feedback_benchmark import digest, read, utc, verify_source, write
from .safe_solve import encoded
from .shared_pipeline_capacity import construct as capacity_anchor

ARCHIVE = Path('AI chats/20260924-Pro-P3-归约森林切分/附件')
ANCHOR = Path('results/a/q3-nikolastarx/pipeline-capacity-two-shot-20260925')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    official, inputs = verify_source(args.source, {'044'})
    out = args.output.resolve()
    out.relative_to(ROOT / 'results/a/q3-nikolastarx')
    out.mkdir(parents=True, exist_ok=False)
    ledger = {'capacity_anchor_derive': 0}
    start = time.perf_counter()
    report = {'status': 'running', 'source_commit': args.source,
              'started_at': utc(), 'official_code_sha256': official,
              'source_input_sha256': inputs, 'calls': ledger,
              'scope': 'one seen-case static reconstruction; no new official score'}
    write(out / 'summary.json', report)
    try:
        from evaluation_validation import read_evaluation_config
        from .pipeline_prefix import build_candidate
        cfg = read_evaluation_config(ROOT / 'data/raw/a/official/data/config.txt')
        graph = read(ROOT / 'data/raw/a/official/data/case_044.json')
        index = Index(graph)
        ledger['capacity_anchor_derive'] += 1
        anchor, anchor_meta = capacity_anchor(index, 5)
        anchor_bytes = encoded(anchor)
        assert anchor_bytes == (ROOT / ANCHOR / 'case_044_multicore_res.json').read_bytes()
        plan, meta, snapshots = build_candidate(
            index, anchor, anchor_meta['cuts'], **cfg, ledger=ledger)
        raw = encoded(plan)
        author_bytes = (ROOT / ARCHIVE / 'r06-case044_bucket_candidate.json').read_bytes()
        report['matches_author_plan_bytes'] = raw == author_bytes
        # A mismatch is a diagnostic failure, not a reason to modify the selector.
        assert raw == author_bytes, 'independent reconstruction differs from author artifact'
        assert set(plan) == {'node_to_subgraph', 'core_schedules'}
        (out / 'case_044_multicore_res.json').write_bytes(raw)
        packed = json.dumps(snapshots, ensure_ascii=False, separators=(',', ':')).encode()
        (out / 'snapshots.json.gz').write_bytes(gzip.compress(packed, mtime=0))
        write(out / 'certificate.json', meta)
        report.update(status='complete', metadata=meta,
                      anchor_sha256=hashlib.sha256(anchor_bytes).hexdigest(),
                      author_plan_sha256=hashlib.sha256(author_bytes).hexdigest(),
                      artifacts={n: digest(out / n) for n in (
                          'case_044_multicore_res.json', 'snapshots.json.gz', 'certificate.json')})
    except BaseException as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        report.update(finished_at=utc(), wall_seconds=time.perf_counter() - start)
        write(out / 'summary.json', report)
    print(json.dumps({'status': report['status'], 'calls': ledger,
                      'matches_author_plan_bytes': report['matches_author_plan_bytes'],
                      'wall_seconds': report['wall_seconds']}))


if __name__ == '__main__':
    main()
