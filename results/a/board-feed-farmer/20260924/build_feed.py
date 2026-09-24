"""board-submission-v1 feed builder for farmer P1 v3 results (0 solver/E0 calls).

Reads the frozen v3 batch products from the three parallel workspaces and emits a
board feed plus the referenced artifacts (plan / result / run / baseline result).
Nothing here runs a solver or an evaluator; it only copies bytes and hashes them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

WS = [
    Path("C:/Users/Dora/Desktop/数学建模/Workbuddy/_a-r1/worktree"),
    Path("C:/Users/Dora/Desktop/数学建模/a-amend-ad1a2c5"),
    Path("C:/Users/Dora/Desktop/数学建模/a-materials-1823040"),
]
BATCH = "results/a/review/accel-100-20260924"
OFFICIAL_SHA256 = "de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0"
SOLVER_COMMIT = "4dff90ef699fd51845cf482951e8477066f5f566"
# 冻结官方代码最后一次变更的仓库提交（内容以 official_sha256 为准）
EVAL_COMMIT = "acfece680d8fa8471b4cf06e65ab0122e71999c8"
# 冻结官方代码最后一次变更的仓库提交（内容以 official_sha256 为准）
EVAL_COMMIT = "acfece680d8fa8471b4cf06e65ab0122e71999c8"
REPO = "huaweibei123/huaweicup2026"
RUN_ID = "farmer-q1-v3-20260924"
TASK_URL = "https://github.com/huaweibei123/huaweicup2026/issues/14"
PRODUCER = "farmeruncle123/s-e7e5e4b76974459f9f6757cfdc31a84a"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def locate(case: str, sub: str) -> Path | None:
    for w in WS:
        p = w / BATCH / f"case{case}" / sub
        if p.is_dir():
            return p
    return None


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_record(case: str, cores: int, art_root: Path, rel_root: str, missing: list,
                 full: bool = True) -> dict:
    unit = locate(case, f"c{cores}")
    base = locate(case, "c1official")
    attempt_id = f"farmeruncle123-P1-{case}-k{cores}-seed0-repeat0-v3"
    rec = {
        "attempt_id": attempt_id,
        "revision": 1,
        "run_id": RUN_ID,
        "algorithm_id": "q1-propose-e0",
        "algorithm_name": "候选提议 + 冻结官方 E0 选择（≤32 候选 / 60s 预算）",
        "variant": "propose-e0",
        "solver_commit": SOLVER_COMMIT,
        "parameters": {
            "candidate_limit": 32,
            "wall_seconds": 60,
            "e0_timeout_seconds": 30,
            "backend": "E0",
            "stop_policy": "32 候选或 60s 墙钟（含内部 E0）；incumbent 取 makespan 最小",
            "seed": None,
        },
        "problem": "P1",
        "case_id": case,
        "cores": cores,
        "runtime_id": "dora-win-python3.13",
        "observed_at": None,
        "source_url": TASK_URL,
        "notes": [
            "v3 官方单核分母口径（singlecore_evaluate.py）；v2 stub 分母原件保留但不引用",
            "60s 预算包含单元内全部官方 E0 评价，solver wall 与 evaluation wall 不相加",
        ],
    }

    # ---- baseline (official singlecore, 30s timeout on this batch) ----
    baseline = None
    if base is not None:
        bsum_p = base / "summary.json"
        bres_p = base / "singlecore-result.json"
        if bsum_p.exists() and bres_p.exists():
            bsum = read_json(bsum_p)
            rc = bsum.get("rc")
            if bsum.get("makespan") and rc == 0:
                if full:
                    dst = art_root / f"case{case}" / "c1official"
                    dst.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(bres_p, dst / "result.json")
                    baseline = {
                        "graph_sha256": graph_sha(case),
                        "config_sha256": config_sha(),
                        "official_sha256": OFFICIAL_SHA256,
                        "route": "E0",
                        "entrypoint": "singlecore_evaluate.evaluate_singlecore",
                        "result": {
                            "path": f"{rel_root}/case{case}/c1official/result.json",
                            "sha256": sha256_file(dst / "result.json"),
                        },
                    }
                else:
                    baseline = None
                    missing.append(
                        f"case{case}: baseline result 原件未入本提交（报告级），sha256 见 PR88 MANIFEST"
                    )
            else:
                missing.append(
                    f"case{case}: 单核分母 30s 超时（rc={rc}），无官方 baseline 原件"
                )

    graph = graph_sha(case)
    cfg = config_sha()

    artifacts = {}
    miss = {}

    if unit is None or not (unit / "summary.json").exists():
        rec["status"] = "timeout"
        rec["metrics"] = {
            "makespan_cycles": None,
            "solver_wall_seconds": None,
            "evaluation_wall_seconds": None,
            "ddr_bytes": None,
            "extra_ddr_bytes": None,
            "spill_bytes": None,
            "cache_hit_rate": None,
        }
        rec["timing"] = {
            "solver_includes_evaluation": True,
            "evaluation_precision": None,
            "utc": None,
        }
        rec["evaluator"] = {
            "route": "E0",
            "commit": None,
            "entrypoint": "multicore_cut_evaluate_problem_1.py",
        }
        rec["identity"] = {
            "graph_sha256": graph,
            "config_sha256": cfg,
            "official_sha256": OFFICIAL_SHA256,
            "plan_sha256": None,
        }
        rec["artifacts"] = {}
        rec["provenance"] = provenance(attempt_id, None, None, miss)
        rec["provenance"]["measurement"]["failure"] = {
            "stage": "sweep",
            "reason": "60s 单元预算内无候选完成官方 E0（大图单次 E0 超 30s），NO-BEST",
            "exit_code": None,
            "elapsed_seconds": None,
        }
        rec["provenance"]["missing_reasons"].update(
            {
                "provenance.measurement.started_at": "旧收据未记录，不用文件 mtime 推算",
                "provenance.measurement.finished_at": "旧收据未记录，不用文件 mtime 推算",
                "provenance.environment.cpu": "旧收据未记录",
                "provenance.environment.ram_bytes": "旧收据未记录",
                "provenance.environment.peak_rss_bytes": "本轮未采样",
                "provenance.runner.source": "驱动尚未发布，本次交付同一提交含驱动文件，SHA 发布后回填",
                "evaluator.commit": "官方冻结代码以 official_sha256 标识，无 git commit",
                "provenance.measurement.calls.E0": "60s 内无候选完成官方 E0，超时候选的实际启动次数收据未逐次记录",
                "provenance.measurement.failure.exit_code": "sweep 为驱动内部超时终止，未记录独立子进程退出码",
                "provenance.measurement.failure.elapsed_seconds": "单元总墙钟未写入收据",
                "identity.plan_sha256": "无有效方案落盘",
            }
        )
        if baseline:
            rec["baseline"] = baseline
        return rec

    summary = read_json(unit / "summary.json")
    makespan = summary.get("makespan")
    plan_p = unit / "best_plan.json"
    result_p = unit / "best-result.json"
    result = read_json(result_p) if result_p.exists() else {}
    dm = result.get("data_movement_bytes", {}) or {}

    dst = art_root / f"case{case}" / f"c{cores}"
    artifacts = {}
    miss_art = {}
    if full:
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(plan_p, dst / "plan.json")
        shutil.copy2(result_p, dst / "result.json")
        shutil.copy2(unit / "summary.json", dst / "run.json")
        artifacts = {
            "plan": {"path": f"{rel_root}/case{case}/c{cores}/plan.json", "sha256": sha256_file(dst / "plan.json")},
            "result": {"path": f"{rel_root}/case{case}/c{cores}/result.json", "sha256": sha256_file(dst / "result.json")},
            "run": {"path": f"{rel_root}/case{case}/c{cores}/run.json", "sha256": sha256_file(dst / "run.json")},
        }
    else:
        # 报告级：原件 sha256 仍如实计算，但路径指 PR88 MANIFEST 固定索引，不入本提交
        for name, fp in (("plan", plan_p), ("result", result_p), ("run", unit / "summary.json")):
            miss_art[f"artifacts.{name}"] = (
                f"原件未入本提交；sha256={sha256_file(fp)}；字节与路径见 PR88 MANIFEST "
                "(codex/q1-full-benchmark-farmer-20260924 @ a4f421e)，分卷方式待维护者确认"
            )

    rec["status"] = "ok" if makespan else "failed"
    rec["metrics"] = {
        "makespan_cycles": makespan,
        "solver_wall_seconds": summary.get("elapsed_s"),
        "evaluation_wall_seconds": None,
        "ddr_bytes": dm.get("scheduled_copy_bytes"),
        "extra_ddr_bytes": dm.get("added_copy_bytes"),
        "spill_bytes": result.get("spill_added_copy_bytes", dm.get("spill_added_copy_bytes")),
        "cache_hit_rate": None,
    }
    rec["timing"] = {
        "solver_includes_evaluation": True,
        "evaluation_precision": None,
        "utc": None,
    }
    rec["evaluator"] = {
        "route": "E0",
        "commit": EVAL_COMMIT,
        "entrypoint": "multicore_cut_evaluate_problem_1.py",
    }
    rec["identity"] = {
        "graph_sha256": graph,
        "config_sha256": cfg,
        "official_sha256": OFFICIAL_SHA256,
        "plan_sha256": sha256_file(plan_p),
    }
    rec["artifacts"] = artifacts
    rec["provenance"] = provenance(attempt_id, summary, cores, miss)
    rec["provenance"]["missing_reasons"].update(
        {
            "provenance.measurement.started_at": "旧收据未记录，不用文件 mtime 推算",
            "provenance.measurement.finished_at": "旧收据未记录，不用文件 mtime 推算",
            "provenance.environment.cpu": "旧收据未记录",
            "provenance.environment.ram_bytes": "旧收据未记录",
            "provenance.environment.peak_rss_bytes": "本轮未采样",
            "provenance.runner.source": "驱动尚未发布，本次交付同一提交含驱动文件，SHA 发布后回填",
            "evaluator.commit": "官方冻结代码以 official_sha256 标识，无 git commit",
        }
    )
    if baseline:
        rec["baseline"] = baseline
    else:
        missing.append(f"case{case}/c{cores}: 缺官方 baseline（分母超时）")
    return rec


_cache: dict = {}


def graph_sha(case: str) -> str | None:
    key = f"graph:{case}"
    if key in _cache:
        return _cache[key]
    for w in WS:
        p = w / "data/raw/a/official/data" / f"case_{case}.json"
        if p.exists():
            _cache[key] = sha256_file(p)
            return _cache[key]
    _cache[key] = None
    return None


def config_sha() -> str | None:
    if "config" in _cache:
        return _cache["config"]
    for w in WS:
        p = w / "data/raw/a/official/data/config.txt"
        if p.exists():
            _cache["config"] = sha256_file(p)
            return _cache["config"]
    _cache["config"] = None
    return None


def provenance(attempt_id: str, summary, cores, miss: dict) -> dict:
    return {
        "producer_session": PRODUCER,
        "task_url": TASK_URL,
        "solver": {
            "source": {
                "repo": REPO,
                "commit": SOLVER_COMMIT,
                "path": "src/q1/search.py",
                "entrypoint": "propose",
            },
            "authors": ["farmeruncle123"],
            "method": "进程内复用官方冻结 propose 候选生成（种子候选 + move/swap/split 邻域），"
            "每个候选由冻结官方 E0 评价，incumbent 取 makespan 最小",
            "references": [
                "https://github.com/huaweibei123/huaweicup2026/issues/14#issuecomment-5812757302"
            ],
            "upstream": [],
            "selected_algorithm_id": None,
            "selected_solver_commit": None,
        },
        "runner": {
            "source": None,
            "argv": [
                "python",
                "-B",
                "results/a/review/accel-100-20260924/v3/accel100_v3.py",
                "sweep",
                "<case ids>",
            ],
            "working_directory": None,
        },
        "environment": {
            "os": "windows",
            "cpu": None,
            "gpu": "none",
            "ram_bytes": None,
            "python": "3.13.12",
            "dependencies": None,
            "threads": 1,
            "workers": 1,
            "peak_rss_bytes": None,
        },
        "measurement": {
            "started_at": None,
            "finished_at": None,
            "seed": None,
            "repeat_index": 0,
            "cold_start": None,
            "solver_scope": "单元计时自候选生成起至最优方案落盘与 summary 写出止，含单元内全部官方 E0 子进程",
            "evaluation_scope": "单元内每次候选评价均为冻结官方 E0 子进程，已计入 solver wall，不另计",
            "budget": {
                "wall_seconds": 60,
                "candidate_limit": 32,
                "stop_reason": "32 候选或 60s 墙钟（含内部 E0）",
            },
            "calls": {
                "solver": 1,
                "E0": (summary or {}).get("evaluations"),
                "E1": 0,
                "E2": 0,
            },
            "offline_costs": "none",
            "failure": None,
        },
        "missing_reasons": {
            "provenance.runner.source": "驱动尚未发布，本次交付同一提交含驱动文件，SHA 发布后回填",
            "provenance.runner.working_directory": "三个并行工作区各自在仓库根运行，不写个人绝对路径",
            "provenance.environment.cpu": "旧收据未记录",
            "provenance.environment.ram_bytes": "旧收据未记录",
            "provenance.environment.peak_rss_bytes": "本轮未采样",
            "provenance.environment.dependencies": "无第三方依赖，官方冻结程序为纯标准库调用",
            "provenance.measurement.started_at": "旧收据未记录，不用文件 mtime 推算",
            "provenance.measurement.finished_at": "旧收据未记录，不用文件 mtime 推算",
            "provenance.measurement.seed": "propose 候选生成随机性由官方种子流程决定，收据未记录具体种子",
            "provenance.measurement.cold_start": "旧收据未记录冷热状态",
            "evaluator.commit": "官方冻结代码以 official_sha256 标识，无 git commit",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True, help="逗号分隔的 case 编号，或 all")
    ap.add_argument("--out", required=True, help="输出目录（仓库相对或绝对）")
    ap.add_argument("--rel-root", required=True, help="artifacts 的仓库相对根路径")
    ap.add_argument("--full-cases", default="", help="完整入库原件的 case 编号，逗号分隔；其余为报告级")
    args = ap.parse_args()

    out = Path(args.out)
    art = out / "artifacts"
    art.mkdir(parents=True, exist_ok=True)

    if args.cases == "all":
        cases = ["%03d" % i for i in range(1, 101)]
    else:
        cases = [c.strip().zfill(3) for c in args.cases.split(",") if c.strip()]

    full_cases = {c.strip().zfill(3) for c in args.full_cases.split(",") if c.strip()}
    missing: list = []
    records = []
    for case in cases:
        for cores in (2, 3, 4, 5):
            records.append(build_record(case, cores, art, args.rel_root, missing,
                                        full=case in full_cases))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    feed_path = out / f"board-feed-{stamp}-farmer-p1-v3.json"
    feed = {
        "schema_version": 1,
        "submission_version": 1,
        "records": records,
    }
    feed_path.write_text(json.dumps(feed, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "generated_at_utc": stamp,
        "run_id": RUN_ID,
        "cases": cases,
        "records": len(records),
        "status_counts": {
            s: sum(1 for r in records if r["status"] == s)
            for s in sorted({r["status"] for r in records})
        },
        "official_sha256": OFFICIAL_SHA256,
        "solver_commit": SOLVER_COMMIT,
        "notes": missing,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"feed": str(feed_path), **{k: v for k, v in manifest.items() if k != "notes"},
                      "missing_note_count": len(missing)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
