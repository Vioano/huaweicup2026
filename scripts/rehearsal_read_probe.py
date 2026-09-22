"""Bounded, read-only CLI/HTTP measurements for the synthetic rehearsal model.

This checks interface mechanics, not whether an Agent understood the output.
No GitHub writes, identities, synchronization, tokens, or model mutations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / ".agents/skills/system-atlas/bin/system-atlas.mjs"


def probe(state: Path, output: Path, actor: str, url: str | None = None, after: int | None = None):
    output.mkdir(parents=True, exist_ok=False)
    measurements, failures, results = [], [], {}

    def record(name, raw, elapsed, code):
        value = json.loads(raw)
        measurements.append({"name": name, "response_bytes": len(raw), "elapsed_ms": round(elapsed * 1000, 1),
                             "exit_code": code, "cursor": value.get("cursor"),
                             "from_cursor": value.get("fromCursor"), "to_cursor": value.get("toCursor"),
                             "records": len(value.get("records", [])),
                             "record_bytes": value.get("page", {}).get("recordBytes"),
                             "complete": value.get("complete"), "has_more": value.get("page", {}).get("hasMore")})
        # Save query responses, never team state/session/key material.
        (output / (name + ".json")).write_bytes(raw)
        results[name] = value
        return value

    def cli(name, command, *args, expected_error=None):
        if len(measurements) >= 32:
            raise RuntimeError("Probe call budget reached; preserve partial results")
        start = time.perf_counter()
        p = subprocess.run(["node", str(CLI), "team", command, "--state", str(state), *map(str, args)],
                           capture_output=True, cwd=ROOT, timeout=45)
        value = record(name, p.stdout if p.returncode == 0 else p.stderr, time.perf_counter() - start, p.returncode)
        if expected_error:
            if p.returncode == 0 or value.get("code") != expected_error:
                failures.append(name + ": expected " + expected_error)
        elif p.returncode:
            raise RuntimeError(name + ": " + str(value.get("code", "command failed")))
        return value

    manifest = cli("manifest", "manifest")
    cursor = manifest["cursor"]
    if manifest.get("counts", {}).get("entities") != 6:
        raise ValueError("Expected the six-module rehearsal fixture; do not benchmark a real model with this oracle")

    def query(name, *args, **kwargs):
        return cli(name, "query", "--cursor", cursor, "--limit", 100, "--max-bytes", 8192, *args, **kwargs)

    def ids(value, record_type="entity"):
        return {r["value"]["id"] for r in value["records"] if r["type"] == record_type}

    def check(condition, message):
        if not condition:
            failures.append(message)

    overview = query("overview", "--mode", "overview", "--depth", 0)
    check(ids(overview) == {"data", "analysis", "delivery"}, "overview top-level identities")
    local = query("local", "--mode", "local", "--target", "analysis", "--depth", 1, "--hops", 0)
    check(ids(local) == {"analysis", "baseline", "residuals", "revision"}, "local descendants")
    check({r["value"]["externalEntity"] for r in local["records"] if r["type"] == "boundary"}
          == {"data", "delivery"}, "local crossing boundaries")
    reach = query("reach", "--mode", "reach", "--target", "data", "--direction", "out", "--kinds", "dataflow")
    check(ids(reach) == {"data", "analysis", "delivery"}, "reach must not traverse containment")
    path = query("path", "--mode", "path", "--from", "data", "--to", "delivery", "--kinds", "dataflow")
    check(path.get("path") == ["data", "analysis", "delivery"], "shortest path witness")
    absent = query("no-path", "--mode", "path", "--from", "data", "--to", "baseline", "--kinds", "dataflow")
    check(absent.get("path") == [], "no invented cross-level path")
    cycles = query("cycles", "--mode", "cycles", "--kinds", "dataflow,feedback")
    check([r["value"]["members"] for r in cycles["records"] if r["type"] == "group"]
          == [["baseline", "residuals", "revision"]], "cyclic region")
    acyclic = query("cycles-dataflow", "--mode", "cycles", "--kinds", "dataflow")
    check(not acyclic["records"], "dataflow-only graph should be acyclic")
    view = query("view", "--mode", "view", "--view", "overview", "--expanded", "analysis")
    check(ids(view) == {"data", "analysis", "delivery", "baseline", "residuals", "revision"}, "expanded Human view")
    board = query("board", "--mode", "board", "--assignee", actor, "--detail", "full")
    check(bool(board["records"]) and all(actor in r["value"]["assignees"] for r in board["records"]),
          "board needs a real assigned rehearsal task; pass an enrolled assignee")
    query("local-full", "--mode", "local", "--target", "analysis", "--depth", 0, "--hops", 0, "--detail", "full")
    full = query("full", "--mode", "full", "--detail", "full", "--max-bytes", 32768)
    check(ids(full) == ids(view), "full/view entity coverage")
    check(ids(board, "task") == {r["value"]["id"] for r in full["records"]
                                if r["type"] == "task" and actor in r["value"]["assignees"]}, "board/full task equivalence")
    for name in ("overview", "local", "reach", "path", "no-path", "cycles", "cycles-dataflow", "view", "board", "local-full", "full"):
        check(results[name]["complete"] and not results[name]["page"]["hasMore"], name + ": unexpected truncation")

    # Force pagination on a small query, then test a query-bound token's rejection.
    paged, token, page_index = [], None, 0
    while True:
        args = ["--mode", "full", "--detail", "full", "--limit", "2", "--max-bytes", "32768"]
        if token:
            args += ["--page", token]
        part = query("page-" + str(page_index), *args)
        check(part["cursor"] == cursor, "mixed page cursors")
        paged.extend(part["records"])
        if not part["page"]["hasMore"]:
            break
        if page_index == 0:
            check(not part["complete"] and part["selectionComplete"], "partial page must not claim completeness")
            query("wrong-page", "--mode", "full", "--detail", "summary", "--limit", 2, "--max-bytes", 32768,
                  "--page", part["page"]["next"], expected_error="query/page")
        token = part["page"]["next"]
        page_index += 1
    check(paged == full["records"], "pagination omissions or duplicates")

    if url:
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ValueError("Use the local serve HTTP origin without secrets or path")
        params = {"mode": "view", "view": "overview", "expanded": "analysis", "cursor": cursor, "maxBytes": 8192}
        start = time.perf_counter()
        with urlopen(url.rstrip("/") + "/api/query?" + urlencode(params), timeout=30) as response:
            raw = response.read(1024 * 1024)
        http = record("http-view", raw, time.perf_counter() - start, 0)
        check(http["cursor"] == view["cursor"] and http["records"] == view["records"], "HTTP/CLI view mismatch")
        if after is not None:
            params = {"after": after, "cursor": cursor, "limit": 100, "maxBytes": 8192}
            start = time.perf_counter()
            with urlopen(url.rstrip("/") + "/api/diff?" + urlencode(params), timeout=30) as response:
                raw = response.read(1024 * 1024)
            diff = record("http-diff", raw, time.perf_counter() - start, 0)
            check(diff["fromCursor"] == after and diff["toCursor"] == cursor and diff["complete"], "diff version/completeness")
            check(bool(diff["records"]) and all(r["collection"] == "tasks" for r in diff["records"]),
                  "expected isolated task change in R2")
    elif after is not None:
        raise ValueError("--after requires the local HTTP --url")

    by_name = {row["name"]: row for row in measurements}
    report = {"ok": not failures, "scope": "synthetic query mechanics; not human/Agent comprehension or billing",
              "cursor": cursor, "actor": actor, "failures": failures, "measurements": measurements,
              "calls": len(measurements), "response_bytes_total": sum(row["response_bytes"] for row in measurements),
              "http_view_checked": bool(url), "http_diff_checked": after is not None,
              "human_viewer": "NOT TESTED", "agent_comprehension": "NOT TESTED",
              "actual_input_tokens": None, "actual_output_tokens": None, "actual_cost": None,
              "steady_state_local_to_full_bytes_ratio": round(by_name["local-full"]["response_bytes"] / by_name["full"]["response_bytes"], 4),
              "cold_start_local_bytes": sum(by_name[n]["response_bytes"] for n in ("manifest", "overview", "local-full"))}
    (output / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--url", help="Optional own local serve origin, never another person's localhost")
    parser.add_argument("--after", type=int, help="Optional cursor before one isolated task-only change (R2)")
    options = parser.parse_args()
    report = probe(options.state, options.out, options.actor, options.url, options.after)
    print(json.dumps({key: value for key, value in report.items() if key != "measurements"}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)
