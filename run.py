"""Runner prototipe Base (lokal/offline).

Penggunaan:
  python3 run.py                  # satu pass live untuk semua token universe
  python3 run.py --token NVDAc    # satu token saja
  python3 run.py --replay fixtures/snapshot_live_20261122_NVDAc.json
                                  # replay snapshot (mode TEST/REPLAY)
  python3 run.py --daily          # run harian S1-D: semua token universe +
                                  # manifest run harian (out/daily_manifest_<tgl>_attempt<N>.json)
  python3 run.py --daily --dry-run   # gladi: manifest sama, trigger dry_run,
                                  # TIDAK dihitung ke 5 hari (26-30 Nov)
  python3 run.py --daily --run-date 2026-11-25
                                  # retry sesi: manifest diatribusikan ke
                                  # tanggal sesi asal (bukan tanggal WITA
                                  # saat retry jalan); dipakai run_daily.sh
                                  # saat attempt pertama gagal dan retry
                                  # jatuh setelah tengah malam WITA (§1.4b)
  bash run_daily.sh               # wrapper cron: lock + retry 2x + log
                                  # (lihat run_daily.sh; cron dipasang koordinator)

Output ditulis ke out/ (lokal saja):
  out/snapshot_<symbol>_<snapshot_id>.json
  out/decision_<symbol>_<snapshot_id>.json
  out/alert_<alert_id>.json            (bila alert baru; dedup via alerts_seen.json)
  out/paper_record_<symbol>_<snapshot_id>.json
  out/alerts_seen.json                 (dedup store lokal)
  out/run_manifest_<timestamp>.json    (manifest ringkas, semua mode)
  out/daily_manifest_<YYYY-MM-DD>_attempt<N>.json   (mode --daily saja)

Tidak ada yang dikirim ke Telegram produksi, tidak ada post publik, tidak
ada perubahan ke Radar produksi. Semua alert hanya file/console lokal.

S1-D (rencana Scope 1 v1.1 §1.4): manifest harian berisi scheduler config
(baris cron + zona waktu) + cuplikan log scheduler, run ID, commit hash,
versi skema, hash config, hash input (hash manifest universe, hash file
evidence), waktu mulai/selesai, status per sumber per token (ok/error),
status per token, dan market_session per token/hari (dari
snapshot["market_session"], S1-B — run 26 Nov Thanksgiving + 28-29 Nov
akhir pekan dilabeli off_hours dari kalender). Manifest ditulis ATOMIC
(file temp + rename). Exit code mode --daily: 0 bila minimum data usable
terpenuhi (>=1 token snapshot lengkap, lihat verify_daily_runs.py),
1 bila tidak — wrapper run_daily.sh memakai exit code ini untuk retry.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date as _date
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adapter
import config
import pipeline
from verify_daily_runs import is_complete_token_record

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "out")
SEEN = os.path.join(OUT, "alerts_seen.json")
DAILY_LOG = os.path.join(OUT, "daily_run.log")

# --- Konfigurasi scheduler S1-D (§1.4 v1.1; jam dikunci 23:00 WITA) --------
WITA = ZoneInfo("Asia/Makassar")
SCHEDULE_CRON_LINE = "0 23 * * *"
SCHEDULE_TIMEZONE = "Asia/Makassar"
SCHEDULE_COMMAND = "cd ~/workspace/base-exit-radar && bash run_daily.sh"
MANIFEST_SCHEMA_VERSION = "1"
MAX_ATTEMPTS = 3          # 1 run awal + maks 2 retry (§1.4)
RETRY_DELAY_SEC = 1800    # jeda retry 30 menit (§1.4)
KNOWN_TRIGGERS = ("cron", "manual", "dry_run")


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def _atomic_write(path, obj):
    """Tulis atomic (§1.4): file temp di direktori yang sama + rename.
    Pembaca tidak pernah melihat manifest setengah tertulis."""
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


def _sha256_file(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _git_commit():
    """Commit hash HEAD saat run (dicatat di manifest §1.4)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=BASE, capture_output=True,
            text=True, timeout=15)
        sha = (out.stdout or "").strip()
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha
    except Exception:  # noqa: BLE001 - git tidak tersedia != run gagal
        pass
    return "unknown"


def _input_hashes():
    """Hash input (§1.4): hash manifest universe + hash file evidence."""
    files = {
        "universe_manifest":
            os.path.join(BASE, "evidence",
                         "coinbase_tokenized_stocks_manifest.json"),
        "universe_evidence":
            os.path.join(BASE, "evidence",
                         "coinbase_tokenized_stocks_all.json"),
        "venue_census":
            os.path.join(BASE, "evidence", "venue_census_2026-11-24.json"),
    }
    evidence = {}
    for key, path in files.items():
        digest = _sha256_file(path)
        if digest is not None:
            evidence[key] = digest
    return {
        "universe_manifest": evidence.get("universe_manifest"),
        "universe_evidence": evidence.get("universe_evidence"),
        "venue_census": evidence.get("venue_census"),
        "evidence_files": evidence,
    }


def _scheduler_log_excerpt(max_lines=20):
    """Cuplikan log scheduler (§1.4): baris terakhir out/daily_run.log
    (ditulis wrapper run_daily.sh). None bila belum ada log (mis. run
    manual pertama sebelum wrapper pernah jalan) — dicatat apa adanya,
    bukan dipalsukan."""
    try:
        with open(DAILY_LOG, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        return "\n".join(lines[-max_lines:]) if lines else None
    except OSError:
        return None


def _wita_date(dt):
    return dt.astimezone(WITA).strftime("%Y-%m-%d")


def _run_date_type(s):
    """Tipe argparse untuk --run-date: YYYY-MM-DD kalender yang valid."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""):
        raise argparse.ArgumentTypeError(
            "--run-date harus YYYY-MM-DD, dapat %r" % s)
    try:
        _date.fromisoformat(s)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "--run-date bukan tanggal kalender: %r" % s)
    return s


def _resolve_run_date(run_date_arg, started_dt):
    """Tanggal atribusi manifest (§1.4b, aturan (b) sesi-aware).

    Tanpa override: tanggal WITA saat run mulai. Dengan --run-date
    (retry sesi): tanggal sesi asal — retry yang jalan setelah tengah
    malam WITA tetap milik hari sesi itu dimulai, bukan hari WITA
    berikutnya. Verifier (verify_daily_runs.py) menerima override ini
    HANYA bila tanggalnya sama dengan tanggal WITA saat sesi NYSE yang
    memuat run itu dibuka; tanggal lain DITOLAK di sana (fail-closed).
    """
    return run_date_arg if run_date_arg else _wita_date(started_dt)


def _next_attempt_number(run_date):
    """Nomor attempt berikutnya untuk tanggal WITA itu (1, 2, 3, ...)."""
    n = 0
    for path in glob.glob(os.path.join(
            OUT, "daily_manifest_%s_attempt*.json" % run_date)):
        m = re.search(r"_attempt(\d+)\.json$", path)
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def _run_live_token(symbol, coinbase=None, ingested=None):
    """Satu token live: ingest (bila belum) -> run_token -> tulis file out/.

    `ingested` (§1.4, dipakai mode --daily): hasil SATU kali
    pipeline.ingest_token() agar meta sumber (sources + errors) tersedia
    untuk manifest tanpa fetch ulang. Bila None, perilaku lama (run_token
    ingest sendiri). Kembalikan (snap, paths, ingested)."""
    if ingested is None:
        ingested = pipeline.ingest_token(symbol, coinbase=coinbase)
    snap = pipeline.run_token(symbol, ingested=ingested, coinbase=coinbase)
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
    return snap, paths, ingested


def _token_record(symbol, snap, paths, ingested, error=None):
    """Record per token untuk manifest harian (§1.4): status per token,
    status per sumber (ok/error), fetched_at + source, market_session,
    keputusan + coverage. `error` terisi bila token gagal (isolasi §1.2c)."""
    if error is not None:
        return {"symbol": symbol, "status": "error",
                "snapshot_id": None, "decision": None,
                "decision_reasons": [], "fetched_at": None,
                "source": None, "sources": {}, "market_session": None,
                "coverage": None, "files": {},
                "error": error, "complete": False}
    meta = (ingested or {}).get("meta") or {}
    sources_meta = meta.get("sources") or {}
    errors_meta = meta.get("errors") or {}
    sources = {}
    for name in ("coinbase", "dexscreener", "geckoterminal", "hyperliquid",
                 "block", "oracle_registry", "pool_factory", "quoter"):
        # Error ingest dicatat dgn key persis nama sumber; key turunan
        # (mis. quoter_pool_rejected:<addr>) BUKAN status sumber itu.
        err = errors_meta.get(name)
        sources[name] = {
            "status": "error" if err is not None else "ok",
            "source": sources_meta.get(name),
            "error": err,
        }
    rec = {
        "symbol": symbol,
        "status": "ok",
        "snapshot_id": snap["snapshot_id"],
        "decision": snap["decision"],
        "decision_reasons": snap["decision_reasons"],
        "fetched_at": snap["fetched_at"],
        # `source`: peta sumber -> identifier (URL/kontrak) per token;
        # verify_daily_runs mensyaratkan field ini ada + non-kosong.
        "source": dict(sources_meta),
        "sources": sources,
        # market_session (S1-B): detail kalender dari snapshot — BUKAN
        # dihitung ulang di sini; run 26 Nov (Thanksgiving) + 28-29 Nov
        # (akhir pekan) terlabel off_hours oleh pipeline.
        "market_session": snap.get("market_session"),
        "coverage": snap.get("coverage"),
        "files": {k: v for k, v in paths.items() if v},
        "error": None,
        "complete": False,  # diisi di bawah (butuh definisi verifier)
    }
    rec["complete"] = is_complete_token_record(rec)
    return rec


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
    ap.add_argument("--daily", action="store_true",
                    help="mode run harian S1-D: manifest harian lengkap + "
                         "exit 1 bila minimum data usable tidak terpenuhi")
    ap.add_argument("--dry-run", action="store_true",
                    help="gladi: seperti --daily tapi trigger dry_run; "
                         "manifest TIDAK dihitung ke 5 hari (26-30 Nov)")
    ap.add_argument("--trigger", choices=KNOWN_TRIGGERS, default=None,
                    help="asal run (cron/manual/dry_run); default: cron "
                         "bila --daily tanpa --dry-run, manual bila bukan "
                         "--daily, dry_run bila --dry-run")
    ap.add_argument("--run-date", metavar="YYYY-MM-DD", type=_run_date_type,
                    default=None,
                    help="override tanggal atribusi manifest (retry sesi, "
                         "§1.4b): manifest tetap milik tanggal sesi asal "
                         "bila retry jalan setelah tengah malam WITA; "
                         "default: tanggal WITA saat run mulai")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if args.replay:
        _replay(args.replay)
        return 0
    symbols = [args.token] if args.token else list(config.TOKENS)
    started_dt = datetime.now(timezone.utc)
    started = started_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
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
    token_records = {}
    for sym in symbols:
        # §1.2c (S1-A): exception isolation per token — satu token gagal
        # ingest TIDAK menggagalkan run; token itu dicatat gagal +
        # alasannya di manifest run, run lanjut ke token berikutnya.
        try:
            if args.daily:
                ingested = pipeline.ingest_token(sym, coinbase=shared_cb)
                snap, paths, ingested = _run_live_token(
                    sym, coinbase=shared_cb, ingested=ingested)
                token_records[sym] = _token_record(sym, snap, paths, ingested)
            else:
                _run_live_token(sym, coinbase=shared_cb)
            successes.append(sym)
        except Exception as e:  # noqa: BLE001 - isolasi per token
            failures.append({"symbol": sym,
                             "error": "%s: %s" % (type(e).__name__, e)})
            if args.daily:
                token_records[sym] = _token_record(
                    sym, None, {}, None,
                    error="%s: %s" % (type(e).__name__, e))
            print("[%s] FAILED (%s: %s) — run continues."
                  % (sym, type(e).__name__, e))
    finished_dt = datetime.now(timezone.utc)
    finished = finished_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
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
    if not args.daily:
        return 0

    # --- Manifest run harian S1-D (§1.4 v1.1) ---------------------------
    trigger = args.trigger
    if trigger is None:
        trigger = "dry_run" if args.dry_run else "cron"
    run_date = _resolve_run_date(args.run_date, started_dt)
    attempt = _next_attempt_number(run_date)
    run_id = "daily-%s-%s-a%d-%s" % (
        run_date.replace("-", ""),
        started_dt.astimezone(WITA).strftime("%H%M%S"),
        attempt,
        hashlib.sha256(("%s|%s|%d" % (started, run_date, attempt)).encode(
            "utf-8")).hexdigest()[:8])
    complete_syms = sorted(s for s, r in token_records.items()
                           if r.get("complete"))
    usable = len(complete_syms) >= 1
    daily_manifest = {
        # Format manifest (§1.4 v1.1).
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "run_date_wita": run_date,
        # --run-date dipakai (retry sesi) atau tidak: jejak audit agar
        # atribusi ke tanggal sesi asal bisa dilacak dari manifestnya.
        "run_date_override": bool(args.run_date),
        "trigger": trigger,
        "dry_run": bool(args.dry_run),
        # TIDAK ada input manual di jalur ini: semua data dari fetch
        # publik/RPC; tidak ada harga/keputusan yang diketik tangan.
        "manual_input": False,
        "input_mode": "automated",
        # Scheduler config (§1.4): baris cron + zona waktu + perintah,
        # + cuplikan log scheduler (dari out/daily_run.log bila ada).
        "scheduler": {
            "cron_line": SCHEDULE_CRON_LINE,
            "timezone": SCHEDULE_TIMEZONE,
            "command": SCHEDULE_COMMAND,
            "log_excerpt": _scheduler_log_excerpt(),
        },
        "git_commit": _git_commit(),
        "schema_version": config.SCHEMA_VERSION,
        "methodology_version": config.METHODOLOGY_VERSION,
        "policy_version": config.POLICY_VERSION,
        "config_hash": config.CONFIG_HASH,
        "universe_version": config.UNIVERSE_VERSION,
        "universe_total_tokens": config.UNIVERSE_TOTAL_TOKENS,
        "input_hashes": _input_hashes(),
        "run_started_at": started,
        "run_finished_at": finished,
        "run_started_at_wita": started_dt.astimezone(WITA).strftime(
            "%Y-%m-%dT%H:%M:%S+08:00"),
        "run_finished_at_wita": finished_dt.astimezone(WITA).strftime(
            "%Y-%m-%dT%H:%M:%S+08:00"),
        # Sesi pasar level run (§1.4b): SATU-SATUNYA sumber = pipeline
        # _market_session_detail (kalender NYSE), terpisah dari umur NAV.
        "run_market_session": pipeline._market_session_detail(started_dt),
        "attempt": attempt,
        "max_attempts": MAX_ATTEMPTS,
        "retry_delay_sec": RETRY_DELAY_SEC,
        "universe_version_manifest": config.UNIVERSE_VERSION,
        "symbols_attempted": symbols,
        "successes": successes,
        "failures": failures,
        "coinbase_shared": shared_cb is not None,
        "coinbase_error": shared_cb_error,
        # Status per token + status per sumber per token (§1.4).
        "tokens": token_records,
        "summary": {
            "attempted": len(symbols),
            "ok": len(successes),
            "error": len(failures),
            "complete_snapshots": len(complete_syms),
            "complete_symbols": complete_syms,
            # Minimum data usable per hari (§1.4): manifest lolos
            # verify_daily_runs.py DAN >=1 snapshot lengkap.
            "usable": usable,
        },
    }
    daily_path = os.path.join(
        OUT, "daily_manifest_%s_attempt%d.json" % (run_date, attempt))
    _atomic_write(daily_path, daily_manifest)
    print("Daily manifest (S1-D): %s" % daily_path)
    print("Daily manifest: run_id=%s attempt=%d usable=%s complete=%d/%d"
          % (run_id, attempt, usable, len(complete_syms), len(symbols)))
    if not usable:
        print("ALERT S1-D: run %s TIDAK usable (0 snapshot lengkap) — "
              "hari %s TIDAK dihitung sukses; wrapper akan retry bila "
              "masih dalam sesi NYSE yang sama." % (run_id, run_date))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
