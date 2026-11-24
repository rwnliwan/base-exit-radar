"""Runner prototipe Base (lokal/offline).

Penggunaan:
  python3 run.py                  # satu pass live untuk semua token universe
  python3 run.py --token NVDAc    # satu token saja
  python3 run.py --replay fixtures/snapshot_live_20261122_NVDAc.json
                                  # replay snapshot (mode TEST/REPLAY)

Output ditulis ke out/ (lokal saja):
  out/snapshot_<symbol>_<snapshot_id>.json
  out/decision_<symbol>_<snapshot_id>.json
  out/alert_<alert_id>.json            (bila alert baru; dedup via alerts_seen.json)
  out/paper_record_<symbol>_<snapshot_id>.json
  out/alerts_seen.json                 (dedup store lokal)

Tidak ada yang dikirim ke Telegram produksi, tidak ada post publik, tidak
ada perubahan ke Radar produksi. Semua alert hanya file/console lokal.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adapter
import config
import pipeline

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "out")
SEEN = os.path.join(OUT, "alerts_seen.json")


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def _run_live_token(symbol, coinbase=None):
    snap = pipeline.run_token(symbol, coinbase=coinbase)
    pub = pipeline.public_snapshot(snap)
    sid = snap["snapshot_id"]
    paths = {}
    paths["snapshot"] = _write(
        os.path.join(OUT, "snapshot_%s_%s.json" % (symbol, sid)), pub)
    decision = {
        "snapshot_id": sid, "asset": symbol, "decision": snap["decision"],
        "decision_reasons": snap["decision_reasons"],
        "policy_version": snap["policy_version"],
        "assessment": snap["assessment"],
        "proposal": snap["proposal"],
        "explanation": snap["explanation"],
        "fetched_at": snap["fetched_at"],
    }
    paths["decision"] = _write(
        os.path.join(OUT, "decision_%s_%s.json" % (symbol, sid)), decision)
    res = pipeline.emit_alert(snap, "live", SEEN)
    if not res.get("ok"):
        print("[%s] alert %s EMIT FAILED (%s): %s — NOT emitted, NOT deduped."
              % (symbol, res["alert_id"], res["error"]["stage"],
                 res["error"]["message"]))
        paths["alert"] = None
    elif res["duplicate"]:
        paths["alert"] = None
        print("[%s] alert %s DUPLICATE (already seen) - skipped."
              % (symbol, res["alert_id"]))
    else:
        snap["alert"] = res["payload"]
        paths["alert"] = _write(
            os.path.join(OUT, "alert_%s.json" % res["alert_id"]),
            res["payload"])
        print("[%s] alert %s emitted (live, local file only)."
              % (symbol, res["alert_id"]))
    rec = pipeline.paper_record(snap)
    paths["paper_record"] = _write(
        os.path.join(OUT, "paper_record_%s_%s.json" % (symbol, sid)), rec)
    print("[%s] decision=%s reasons=%s" % (
        symbol, snap["decision"], ",".join(snap["decision_reasons"]) or "none"))
    print("[%s] median=%s nav_gap=%s" % (
        symbol,
        snap["assessment"]["layer_a"]["median_price_usd"],
        (snap["assessment"]["layer_a"]["nav_gap_pct_labeled"] or {}).get("value_pct")))
    print("[%s] files: %s" % (symbol, {k: v for k, v in paths.items() if v}))
    return snap, paths


def _replay(path):
    with open(path, "r", encoding="utf-8") as f:
        snap = json.load(f)
    # Jalankan ulang assessment+decision+alert dari snapshot yang sama.
    # Snapshot dimuat apa adanya (tidak fetch ulang) agar replay deterministik.
    snap = pipeline.assess_snapshot(snap)
    snap = pipeline.decide(snap)
    snap = pipeline.explain(snap)
    res = pipeline.emit_alert(snap, "TEST/REPLAY", SEEN)
    if not res.get("ok"):
        print("[replay] alert %s EMIT FAILED (%s): %s — NOT emitted, NOT deduped."
              % (res["alert_id"], res["error"]["stage"], res["error"]["message"]))
    elif res["duplicate"]:
        print("[replay] alert %s DUPLICATE (already seen) - skipped."
              % res["alert_id"])
    else:
        snap["alert"] = res["payload"]
        p = _write(os.path.join(OUT, "alert_%s.json" % res["alert_id"]),
                   res["payload"])
        print("[replay] alert %s emitted (TEST/REPLAY, local file only): %s"
              % (res["alert_id"], p))
    print("[replay] decision=%s reasons=%s"
          % (snap["decision"], ",".join(snap["decision_reasons"]) or "none"))
    return snap, res


def main():
    ap = argparse.ArgumentParser(description="Base prototype runner (local/offline)")
    ap.add_argument("--token", choices=list(config.TOKENS),
                    help="satu token saja (default: semua token universe)")
    ap.add_argument("--replay", metavar="SNAPSHOT_JSON",
                    help="replay snapshot (mode TEST/REPLAY)")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if args.replay:
        _replay(args.replay)
        return 0
    symbols = [args.token] if args.token else list(config.TOKENS)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # §1.2c (S1-A): shared fetch cache per run — fetch_coinbase_tokens()
    # SATU kali, dipakai bersama semua token. Gagal -> fallback per-token
    # (ingest fetch sendiri) + dicatat di manifest run, bukan diam-diam.
    shared_cb = adapter.fetch_coinbase_tokens()
    shared_cb_error = None
    if not shared_cb.get("ok"):
        shared_cb_error = shared_cb.get("error")
        print("WARNING shared coinbase fetch failed (%s); falling back to "
              "per-token fetch." % shared_cb_error)
        shared_cb = None
    successes, failures = [], []
    for sym in symbols:
        # §1.2c (S1-A): exception isolation per token — satu token gagal
        # ingest TIDAK menggagalkan run; token itu dicatat gagal +
        # alasannya di manifest run, run lanjut ke token berikutnya.
        try:
            _run_live_token(sym, coinbase=shared_cb)
            successes.append(sym)
        except Exception as e:  # noqa: BLE001 - isolasi per token
            failures.append({"symbol": sym,
                             "error": "%s: %s" % (type(e).__name__, e)})
            print("[%s] FAILED (%s: %s) — run continues."
                  % (sym, type(e).__name__, e))
    finished = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "run_started_at": started,
        "run_finished_at": finished,
        "universe_version": config.UNIVERSE_VERSION,
        "config_hash": config.CONFIG_HASH,
        "symbols_attempted": symbols,
        "successes": successes,
        "failures": failures,
        "coinbase_shared": shared_cb is not None,
        "coinbase_error": shared_cb_error,
    }
    _write(os.path.join(
        OUT, "run_manifest_%s.json" % started.replace(":", "").replace("-", "")),
        manifest)
    print("Done. Output di %s (lokal saja)." % OUT)
    print("Run manifest: %d sukses, %d gagal: %s"
          % (len(successes), len(failures),
             [f["symbol"] for f in failures] or "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
