"""Reproduksi audit offline. Tidak mengubah source atau fixtures proyek.
Usage: python3 repro-base-audit-2026-11-22.py /path/to/base-prototype
"""
import copy
import datetime
import json
import pathlib
import socket
import sys
import tempfile
import urllib.request


def deny_network(*args, **kwargs):
    raise RuntimeError("Network disabled for offline audit")


socket.socket.connect = deny_network
urllib.request.urlopen = deny_network
root = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
import pipeline

base = json.loads((root / "fixtures/snapshot_live_20261122_NVDAc.json").read_text())


def evaluate(snapshot):
    return pipeline.explain(pipeline.decide(pipeline.assess_snapshot(snapshot)))


def summary(snapshot):
    return {key: snapshot[key] for key in ("decision", "decision_reasons", "proposal", "assessment")}


results = {}
for name, quote in (("A_null_quote_control", None), ("A_empty_quote", {})):
    sample = copy.deepcopy(base)
    fetched = datetime.datetime.fromisoformat(sample["fetched_at"].replace("Z", "+00:00"))
    sample["reference"].update(
        age_seconds=1,
        nav_price_updated_at=(fetched - datetime.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        session_status="active",
        session_status_basis="controlled_fresh_nav_fixture",
    )
    sample["exit_quote"] = quote
    results[name] = summary(evaluate(sample))

sample = copy.deepcopy(base)
for pool in sample["pools"]:
    pool["fetched_at"] = "2026-01-01T00:00:00Z"
    pool["source_updated_at"] = "2026-01-01T00:00:00Z"
results["B_stale_pool_timestamps"] = summary(evaluate(sample))

sample = copy.deepcopy(base)
sample["reference"].update(nav_price_updated_at=None, age_seconds=None, session_status="unknown")
results["B_missing_nav_timestamp"] = summary(evaluate(sample))

sample = copy.deepcopy(base)
sample["asset"]["chain"] = "ethereum"
results["C_wrong_chain"] = summary(evaluate(sample))

sample = copy.deepcopy(base)
sample["pools"] = sample["pools"][:1]
sample["coverage"].update(independent_pool_count=2, independent_venue_count=1)
results["C_one_pool_claiming_two"] = summary(evaluate(sample))

sample = copy.deepcopy(base)
sample["pools"] = sample["pools"][:2]
for pool in sample["pools"]:
    pool["dex"] = "aero"
sample["coverage"].update(independent_pool_count=2, independent_venue_count=1)
results["C_two_pools_one_venue"] = summary(evaluate(sample))

with tempfile.TemporaryDirectory(prefix="base-audit-") as directory:
    seen_path = str(pathlib.Path(directory) / "missing-parent" / "seen.json")
    sample = evaluate(copy.deepcopy(base))
    first = pipeline.emit_alert(sample, "TEST/REPLAY", seen_path)
    second = pipeline.emit_alert(sample, "TEST/REPLAY", seen_path)
    results["D_dedup_persistence_failure"] = {
        "first_duplicate": first["duplicate"],
        "second_duplicate": second["duplicate"],
        "same_alert_id": first["alert_id"] == second["alert_id"],
        "dedup_file_exists": pathlib.Path(seen_path).exists(),
    }

print(json.dumps(results, indent=2, sort_keys=True))
