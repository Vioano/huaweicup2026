"""Score-free structural screening of the C04 port-packet constructor on P2 cases."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data/raw/a/official/code"))

from evaluation_validation import read_evaluation_config  # noqa: E402
from multicore_cut_evaluate_problem_2 import read_scene_b_config  # noqa: E402
from src.q2_nikolastarx.port_packet_adapter import (  # noqa: E402
    UnsupportedPortPacket, build,
)

INPUT = ROOT / "data/raw/a/official-cases.zip"
CONFIG = ROOT / "data/raw/a/official/data/config.txt"
OUT = ROOT / "results/a/q2-nikolastarx/c04-static-scan-20260926/summary.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    config = {**read_evaluation_config(CONFIG), **read_scene_b_config(CONFIG)}
    rows = []
    with zipfile.ZipFile(INPUT) as archive:
        names = [f"data/case_{case:03d}.json" for case in range(1, 101)]
        if any(name not in archive.namelist() for name in names):
            raise ValueError("official 100 graphs are incomplete")
        for case, name in enumerate(names, start=1):
            graph = json.loads(archive.read(name))
            for cores in range(1, 6):
                start = time.monotonic()
                row = {"case": case, "cores": cores}
                try:
                    plan, detail = build(graph, cores, config)
                    c = detail["constructor"]
                    row.update({"status": "static-pass",
                                "packet_count": c["packet_count"],
                                "pre_step2_copy_bytes": detail["physical_pre_step2_copy_bytes"],
                                "zero_spill_peak_bytes": detail["zero_spill"]["peaks"],
                                "canonical_plan_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True,
                                                   separators=(",", ":")).encode()).hexdigest()})
                except UnsupportedPortPacket as error:
                    row.update({"status": "abstain", "reason": str(error)})
                row["static_wall_seconds"] = round(time.monotonic() - start, 6)
                rows.append(row)
            print(f"case {case:03d} complete", flush=True)
    coverage = {str(k): sum(r["status"] == "static-pass" and r["cores"] == k
                             for r in rows) for k in range(1, 6)}
    reasons = dict(Counter(r["reason"] for r in rows if r["status"] != "static-pass"))
    doc = {"scope": "Static adapter guards only; zero E0/E1/E2 calls and no Makespan claim.",
           "source_sha256": {"adapter": sha(ROOT / "src/q2_nikolastarx/port_packet_adapter.py"),
                              "prototype": sha(ROOT / "AI chats/20260925-P2-零spill通信与流水联合构造/附件/c04-port_packet_stationary.browser-copy.py")},
           "official_zip_sha256": sha(INPUT), "official_config_sha256": sha(CONFIG),
           "width": 32, "coverage": coverage, "reasons": reasons, "rows": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"coverage": coverage, "reasons": reasons}, ensure_ascii=False))


if __name__ == "__main__":
    main()
