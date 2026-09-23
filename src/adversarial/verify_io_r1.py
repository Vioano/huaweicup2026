"""F-IO 探针：实际调用官方 CLI，观察默认路径、错误出口与退出码。

在系统临时目录内作业，绝不写入只读官方材料目录。
不做任何 E0 评分，不产出性能或质量结论。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL = ROOT / "data/raw/a/official"
CODE = OFFICIAL / "code"
OUT_DIR = ROOT / "results/a/form/r1-20260923-farmeruncle123"

sys.dont_write_bytecode = True


def run_cli(args, cwd):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(CODE)
    proc = subprocess.run(
        [sys.executable, str(CODE / "multicore_cut_evaluate_problem_1.py")] + args,
        cwd=str(cwd), capture_output=True, text=True, env=env, timeout=300)
    return proc


def main():
    records = []
    work = Path(tempfile.mkdtemp(prefix="atlas-io-probe-"))
    try:
        # 把官方 case 与 config 复制到临时目录（原件只读，不写入）
        case_src = OFFICIAL / "data/case_001.json"
        cfg_src = OFFICIAL / "data/config.txt"
        graph = work / "case_001.json"
        shutil.copy2(case_src, graph)
        shutil.copy2(cfg_src, work / "config.txt")

        # --- A) 缺省配置 + 缺省方案 + 缺省输出路径 ---
        # 先造一个最小合法方案，落到默认方案文件名
        ops = json.loads(graph.read_text(encoding="utf-8"))["ops"]
        non_copy = [o["id"] for o in ops if o["op"] not in ("COPY_IN", "COPY_OUT")]
        plan = {"node_to_subgraph": {str(i): 0 for i in non_copy},
                "core_schedules": [[0]]}
        (work / "case_001_multicore_res.json").write_text(
            json.dumps(plan, ensure_ascii=False), encoding="utf-8")

        proc = run_cli(["case_001.json"], work)
        observed = sorted(p.name for p in work.iterdir())
        records.append({
            "case": "A) all defaults (no --config, no -o, no plan positional)",
            "argv": ["case_001.json"],
            "returncode": proc.returncode,
            "stdout_head": proc.stdout.strip().splitlines()[:2],
            "stderr_head": proc.stderr.strip().splitlines()[:2],
            "files_after": observed,
            "expected_default_output": "case_001_problem_1_res.json",
            "expected_default_trace": "case_001_problem_1_trace.json",
            "expected_default_log": "case_001_problem_1_log.txt",
            "output_present": (work / "case_001_problem_1_res.json").is_file(),
            "trace_present": (work / "case_001_problem_1_trace.json").is_file(),
            "log_present": (work / "case_001_problem_1_log.txt").is_file(),
        })

        # --- B) 缺失配置：应硬失败，且不得回退内置默认值 ---
        work_b = work / "no_config"
        work_b.mkdir()
        shutil.copy2(case_src, work_b / "case_001.json")
        shutil.copy2(work / "case_001_multicore_res.json",
                     work_b / "case_001_multicore_res.json")
        proc_b = run_cli(["case_001.json"], work_b)
        first_err = next((l for l in proc_b.stderr.splitlines() if l.strip()), "")
        records.append({
            "case": "B) missing config.txt next to the graph",
            "argv": ["case_001.json"],
            "returncode": proc_b.returncode,
            "stderr_first_line": first_err,
            "stderr_contains_error_prefix": "[EVALUATION ERROR]" in proc_b.stderr,
            "stderr_contains_config_message": "configuration file not found" in proc_b.stderr,
            "exposes_traceback": "Traceback (most recent call last)" in proc_b.stderr,
            "files_after": sorted(p.name for p in work_b.iterdir()),
            "result_written": (work_b / "case_001_problem_1_res.json").is_file(),
        })

        # --- C) 显式 -o 落到指定路径 ---
        work_c = work / "explicit"
        work_c.mkdir()
        shutil.copy2(case_src, work_c / "case_001.json")
        shutil.copy2(cfg_src, work_c / "config.txt")
        shutil.copy2(work / "case_001_multicore_res.json",
                     work_c / "case_001_multicore_res.json")
        target = work_c / "my_result.json"
        proc_c = run_cli(["case_001.json", "-o", str(target)], work_c)
        records.append({
            "case": "C) explicit -o",
            "argv": ["case_001.json", "-o", "my_result.json"],
            "returncode": proc_c.returncode,
            "target_written": target.is_file(),
            "default_name_absent": not (work_c / "case_001_problem_1_res.json").is_file(),
        })

        payload = {
            "generator": "src/adversarial/verify_io_r1.py",
            "official_entry": "code/multicore_cut_evaluate_problem_1.py (CLI)",
            "workdir": "系统临时目录（未写入任何只读官方材料路径）",
            "observations": records,
            "limitations": [
                "只跑了问题 1 的 CLI；问题 2/3 的默认命名未单独验证。",
                "问题 1 的默认输出/trace/log 命名规则由源码 _common_paths 判定，本探针只抽样验证。",
                "未构造 --trace-output / --log-output 显式传参的运行。",
            ],
        }
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / "io-observations.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        for r in records:
            print(f"  {r['case']}")
            print(f"     rc={r['returncode']}  files={r.get('files_after')}")
            if "stderr_first_line" in r:
                print(f"     stderr: {r['stderr_first_line'][:120]}")
        print("evidence:", out.relative_to(ROOT))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
