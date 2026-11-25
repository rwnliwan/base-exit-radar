"""Verifikasi manifest run harian — fail-closed (S1-D, rencana Scope 1 v1.1 §1.4).

Memeriksa, per manifest:
  * field wajib §1.4 ada: run ID, commit hash, versi skema, hash config,
    hash input (hash manifest universe + hash file evidence), waktu
    mulai/selesai, scheduler config (baris cron + zona waktu),
    status per sumber per token, status per token, market_session.
  * tiap record token yang sukses punya `fetched_at` + `source`.
  * tidak ada input manual (`manual_input` False, trigger dikenal).
  * manifest diatribusikan ke tanggal MULAI run (WITA) — aturan (b)
    sesi-aware (ACC 24 Nov 11:39): hari bursa buka, seluruh jendela
    [mulai, selesai] harus berada dalam SATU sesi NYSE (regular
    09:30-16:00 ET; early close 13:00 ET); hari libur/akhir pekan
    tetap valid, dicatat off_hours. Trigger dry_run dikecualikan dari
    containment (gladi, bukan hari yang dihitung).
  * retry sesi (revisi 25 Nov, §1.4): retry yang jalan setelah tengah
    malam WITA tetap milik tanggal sesi asal — atribusi diterima bila
    run_date_wita sama dengan tanggal WITA saat sesi NYSE yang memuat
    run itu DIBUKA (bukan hanya tanggal WITA saat run mulai); tanggal
    lain DITOLAK (fail-closed). Lihat `_session_start_wita_date()`.
  * minimum data usable per hari: >=1 token punya snapshot lengkap
    (keputusan + coverage + `fetched_at` + `source` ada, tanpa error
    ingest fatal untuk token itu).
  * versi skema + hash config + versi universe cocok dengan config.py.

Mode pemakaian:
  python3 verify_daily_runs.py                                  # jendela default 2026-11-26..2026-11-30, dir out/
  python3 verify_daily_runs.py --start 2026-11-26 --end 2026-11-30 [--dir out]
  python3 verify_daily_runs.py --manifest out/daily_manifest_2026-11-24_attempt1.json

Exit 0 bila SEMUA lolos; non-zero bila ada satu pun gagal (fail-closed).
Dipakai gate S1-D; JANGAN klaim hari sukses sebelum skrip ini lolos.

Manifest kosong/error TIDAK dihitung sebagai hari sukses.
"""

import argparse
import datetime as _dt
import glob
import hashlib
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "out")
WITA = ZoneInfo("Asia/Makassar")

MANIFEST_SCHEMA_VERSION = "1"
DEFAULT_START = "2026-11-26"
DEFAULT_END = "2026-11-30"
# Zona waktu sesi NYSE (aturan (b) sesi-aware, §1.4).
ET = ZoneInfo("America/New_York")
KNOWN_TRIGGERS = ("cron", "manual", "dry_run")
KNOWN_SOURCES = ("coinbase", "dexscreener", "geckoterminal", "hyperliquid",
                 "block", "oracle_registry", "pool_factory", "quoter")
# Error ingest fatal (§1.4 "tanpa error ingest fatal untuk token itu"):
# tanpa Coinbase record atau tanpa pool DexScreener, snapshot tidak punya
# data yang bisa dinilai — token itu TIDAK dihitung lengkap.
FATAL_SOURCES = ("coinbase", "dexscreener")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_complete_token_record(rec):
    """Snapshot lengkap (§1.4 minimum data usable): status ok + keputusan
    + coverage + `fetched_at` + `source` ada + `market_session` ada +
    tanpa error ingest fatal (coinbase/dexscreener) untuk token itu."""
    if not isinstance(rec, dict):
        return False
    if rec.get("status") != "ok":
        return False
    if not rec.get("fetched_at"):
        return False
    src = rec.get("source")
    if not src:
        return False
    if isinstance(src, dict) and not any(v for v in src.values()):
        return False
    if not rec.get("decision"):
        return False
    if not isinstance(rec.get("coverage"), dict):
        return False
    ms = rec.get("market_session")
    if not isinstance(ms, dict):
        return False
    if ms.get("strata") not in ("active", "off_hours", "unknown"):
        return False
    sources = rec.get("sources") or {}
    for name in FATAL_SOURCES:
        st = sources.get(name)
        if isinstance(st, dict) and st.get("status") == "error":
            return False
    return True


def _parse_iso(s):
    if not isinstance(s, str):
        return None
    try:
        t = s.replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(t)
        return dt if dt.tzinfo is not None else dt.replace(
            tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def _session_start_wita_date(started):
    """Tanggal WITA saat sesi NYSE yang memuat `started` DIBUKA.

    Satu-satunya sumber kebenaran = `pipeline._market_session_detail`
    (kalender NYSE; TIDAK ada jalur paralel):
    - hari bursa buka: tanggal WITA dari jam buka sesi hari ET itu
      (09:30 ET = 21:30 WITA hari yang sama; early close tetap buka
      09:30 ET, jadi rumusnya sama).
    - hari libur/akhir pekan: tidak ada jam buka — dipakai tanggal WITA
      dari tengah malam ET hari itu (00:00 ET = 12:00 WITA).
    Dipakai cek atribusi retry sesi: retry 00:05 WITA 26 Nov milik sesi
    25 Nov (dibuka 21:30 WITA 25 Nov) — bukan 26 Nov.
    """
    try:
        import pipeline as _pipeline
    except Exception:  # noqa: BLE001 - session logic tidak tersedia
        return None
    et = started.astimezone(ET)
    open_dt = et.replace(hour=9, minute=30, second=0, microsecond=0)
    det = _pipeline._market_session_detail(open_dt)
    if det.get("status") == "open":
        return open_dt.astimezone(WITA).strftime("%Y-%m-%d")
    midnight = et.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(WITA).strftime("%Y-%m-%d")


def _session_window_check(mani, started, finished):
    """Aturan (b) sesi-aware (§1.4, ACC 24 Nov 11:39). Kembalikan
    (name, ok, detail) — satu cek bernama session_window.

    Logika sesi HANYA dari `pipeline._market_session_detail` (satu-satunya
    sumber kebenaran sesi; TIDAK ada jalur paralel di sini — kalender
    libur/early-close/weekday tetap milik pipeline/config):
    - trigger dry_run: containment TIDAK diterapkan (gladi, bukan hari
      yang dihitung; manifest dry-run pagi WITA yang di luar jam sesi
      tetap lolos).
    - hari libur/akhir pekan (calendar holiday/weekend pada tanggal ET
      saat mulai): valid sebagai off_hours — syaratnya strata
      run_market_session di manifest == off_hours (konsisten dengan
      kalender) dan mulai/selesai pada tanggal ET yang sama.
    - hari bursa buka: seluruh jendela [mulai, selesai] harus berada
      dalam SATU sesi — status open di kedua ujung, tanggal ET yang
      sama, dan strata run_market_session == active.
    - di luar itu (run di luar jam sesi pada hari bursa buka, atau
      kalender unknown): GAGAL (fail-closed).
    """
    try:
        import pipeline as _pipeline
    except Exception as e:  # noqa: BLE001 - session logic tidak tersedia
        return ("session_window", False,
                "import pipeline gagal: %s: %s" % (type(e).__name__, e))
    det_s = _pipeline._market_session_detail(started)
    det_f = _pipeline._market_session_detail(finished)
    rms = mani.get("run_market_session") or {}
    strata = rms.get("strata")
    same_et_day = (started.astimezone(ET).strftime("%Y-%m-%d")
                   == finished.astimezone(ET).strftime("%Y-%m-%d"))
    if mani.get("trigger") == "dry_run":
        return ("session_window", True,
                "dry_run: containment tidak diterapkan (gladi); "
                "started=%s finished=%s"
                % (started, finished))
    if det_s.get("calendar") in ("holiday", "weekend"):
        ok = strata == "off_hours" and same_et_day
        return ("session_window", ok,
                "hari libur/akhir pekan: calendar=%s strata=%s "
                "same_et_day=%s (valid sebagai off_hours)"
                % (det_s.get("calendar"), strata, same_et_day))
    if det_s.get("status") == "open":
        ok = (det_f.get("status") == "open" and same_et_day
              and strata == "active")
        return ("session_window", ok,
                "hari bursa buka: start_status=%s finish_status=%s "
                "same_et_day=%s strata=%s (seluruh run harus dalam satu "
                "sesi)" % (det_s.get("status"), det_f.get("status"),
                           same_et_day, strata))
    return ("session_window", False,
            "run di luar sesi pada hari bursa buka / kalender unknown: "
            "start calendar=%s status=%s"
            % (det_s.get("calendar"), det_s.get("status")))


def verify_manifest(mani, path="<manifest>"):
    """Periksa satu manifest (dict). Kembalikan (ok, checks) dengan checks =
    list (name, ok, detail)."""
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    if not isinstance(mani, dict):
        return False, [("manifest_is_object", False,
                        "manifest di %s bukan JSON object" % path)]

    # --- identitas + versi
    check("manifest_schema_version",
          mani.get("manifest_schema_version") == MANIFEST_SCHEMA_VERSION,
          "manifest_schema_version=%s (expected %s)"
          % (mani.get("manifest_schema_version"), MANIFEST_SCHEMA_VERSION))
    check("run_id_present", bool(mani.get("run_id")),
          "run_id=%s" % mani.get("run_id"))
    run_date = mani.get("run_date_wita")
    check("run_date_present",
          isinstance(run_date, str) and bool(DATE_RE.match(run_date)),
          "run_date_wita=%s" % run_date)
    check("trigger_known", mani.get("trigger") in KNOWN_TRIGGERS,
          "trigger=%s" % mani.get("trigger"))
    # --- tidak ada input manual (§1.4: "tidak ada input manual")
    check("no_manual_input", mani.get("manual_input") is False,
          "manual_input=%s input_mode=%s"
          % (mani.get("manual_input"), mani.get("input_mode")))
    # --- scheduler config (§1.4: baris cron + zona waktu)
    sched = mani.get("scheduler") or {}
    check("scheduler_config_present",
          bool(sched.get("cron_line")) and bool(sched.get("timezone")),
          "cron_line=%s timezone=%s"
          % (sched.get("cron_line"), sched.get("timezone")))
    check("scheduler_timezone_wita", sched.get("timezone") == "Asia/Makassar",
          "timezone=%s" % sched.get("timezone"))
    # --- commit + versi + hash config
    check("git_commit_present",
          isinstance(mani.get("git_commit"), str)
          and bool(HEX40.match(mani.get("git_commit") or "")),
          "git_commit=%s" % mani.get("git_commit"))
    try:
        import config
        check("schema_version_matches_config",
              mani.get("schema_version") == config.SCHEMA_VERSION,
              "manifest=%s config=%s"
              % (mani.get("schema_version"), config.SCHEMA_VERSION))
        check("config_hash_matches_config",
              mani.get("config_hash") == config.CONFIG_HASH,
              "manifest=%s config=%s"
              % (mani.get("config_hash"), config.CONFIG_HASH))
        check("universe_version_matches_config",
              mani.get("universe_version") == config.UNIVERSE_VERSION,
              "manifest=%s config=%s"
              % (mani.get("universe_version"), config.UNIVERSE_VERSION))
    except Exception as e:  # noqa: BLE001 - config belum punya field versi
        check("config_version_fields_present", False,
              "config import/check gagal: %s: %s" % (type(e).__name__, e))
    # --- hash input (§1.4: hash manifest universe + hash file evidence)
    ih = mani.get("input_hashes") or {}
    check("input_hash_universe_manifest",
          isinstance(ih.get("universe_manifest"), str)
          and bool(HEX64.match(ih.get("universe_manifest") or "")),
          "universe_manifest=%s" % ih.get("universe_manifest"))
    ev = ih.get("evidence_files") or {}
    check("input_hash_evidence_files",
          isinstance(ev, dict) and len(ev) >= 1
          and all(isinstance(v, str) and bool(HEX64.match(v))
                  for v in ev.values()),
          "evidence_files=%s" % sorted(ev))
    # --- waktu mulai/selesai + atribusi (b) sesi-aware (ACC 24 Nov 11:39)
    # Manifest diatribusikan ke tanggal MULAI run (WITA), bukan tanggal
    # selesai — run 23:00 WITA yang selesai ~00:19 WITA hari berikutnya
    # tetap milik hari mulai, asal seluruh jendelanya dalam satu sesi.
    started = _parse_iso(mani.get("run_started_at"))
    finished = _parse_iso(mani.get("run_finished_at"))
    check("run_times_present", started is not None and finished is not None,
          "started=%s finished=%s"
          % (mani.get("run_started_at"), mani.get("run_finished_at")))
    if started is not None and finished is not None:
        check("run_started_before_finished", started < finished,
              "started=%s finished=%s"
              % (mani.get("run_started_at"), mani.get("run_finished_at")))
        start_wita = started.astimezone(WITA)
        session_start_wita = _session_start_wita_date(started)
        check("run_attributed_to_start_date_wita",
              start_wita.strftime("%Y-%m-%d") == run_date
              or session_start_wita == run_date,
              "started_wita=%s session_opened_wita=%s run_date=%s "
              "(retry sesi: run_date = tanggal WITA sesi dibuka)"
              % (start_wita.strftime("%Y-%m-%dT%H:%M"),
                 session_start_wita, run_date))
        check(*_session_window_check(mani, started, finished))
    else:
        check("run_started_before_finished", False, "waktu tidak ter-parse")
        check("run_attributed_to_start_date_wita", False,
              "waktu tidak ter-parse")
        check("session_window", False, "waktu tidak ter-parse")
    # --- market_session level run (§1.4b: sesi kalender di manifest)
    rms = mani.get("run_market_session") or {}
    check("run_market_session_present",
          isinstance(rms, dict)
          and rms.get("strata") in ("active", "off_hours", "unknown"),
          "run_market_session=%s" % rms)
    # --- token records
    tokens = mani.get("tokens")
    check("tokens_nonempty", isinstance(tokens, dict) and len(tokens) > 0,
          "tokens=%s" % (len(tokens) if isinstance(tokens, dict) else tokens))
    complete = []
    if isinstance(tokens, dict):
        bad_ok = []
        bad_err = []
        bad_ms = []
        for sym, rec in tokens.items():
            if not isinstance(rec, dict):
                bad_ok.append(sym)
                continue
            if rec.get("status") == "ok":
                if not rec.get("fetched_at") or not rec.get("source"):
                    bad_ok.append(sym)
                ms = rec.get("market_session")
                if (not isinstance(ms, dict)
                        or ms.get("strata")
                        not in ("active", "off_hours", "unknown")):
                    bad_ms.append(sym)
                if "manual" in str(rec.get("source") or "").lower():
                    bad_ok.append(sym)
            elif rec.get("status") == "error":
                if not rec.get("error"):
                    bad_err.append(sym)
            else:
                bad_ok.append(sym)
            if is_complete_token_record(rec):
                complete.append(sym)
        check("ok_records_have_fetched_at_and_source", not bad_ok,
              "bad=%s" % (bad_ok[:5] or "none"))
        check("error_records_carry_error", not bad_err,
              "bad=%s" % (bad_err[:5] or "none"))
        check("token_market_session_present", not bad_ms,
              "bad=%s" % (bad_ms[:5] or "none"))
    # --- minimum data usable per hari (§1.4)
    check("minimum_usable_at_least_one_complete_token", len(complete) >= 1,
          "complete=%d tokens=%s"
          % (len(complete), complete[:5]))
    summ = mani.get("summary") or {}
    check("summary_usable_consistent",
          summ.get("usable") is True
          and summ.get("complete_snapshots") == len(complete),
          "summary.usable=%s complete_snapshots=%s counted=%d"
          % (summ.get("usable"), summ.get("complete_snapshots"),
             len(complete)))

    failed = [c for c, ok, _ in checks if not ok]
    return (not failed), checks


def verify_manifest_file(path):
    """Baca + periksa satu file manifest. Kembalikan (ok, checks)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            mani = json.load(f)
    except (OSError, ValueError) as e:
        return False, [("manifest_readable", False, "%s: %s" % (path, e))]
    return verify_manifest(mani, path)


def _latest_manifest_for_date(directory, date_str):
    """Manifest terbaru untuk satu tanggal kalender WITA (attempt tertinggi,
    lalu run_finished_at terbaru). Kembalikan path atau None."""
    cands = []
    for path in glob.glob(os.path.join(
            directory, "daily_manifest_%s_attempt*.json" % date_str)):
        try:
            with open(path, "r", encoding="utf-8") as f:
                mani = json.load(f)
        except (OSError, ValueError):
            continue
        if mani.get("run_date_wita") != date_str:
            continue
        m = re.search(r"_attempt(\d+)\.json$", path)
        attempt = int(m.group(1)) if m else 0
        cands.append((attempt, mani.get("run_finished_at") or "", path))
    if not cands:
        return None
    cands.sort()
    return cands[-1][2]


def _date_range(start, end):
    d0 = _dt.date.fromisoformat(start)
    d1 = _dt.date.fromisoformat(end)
    out = []
    d = d0
    while d <= d1:
        out.append(d.isoformat())
        d += _dt.timedelta(days=1)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Verifikasi manifest run harian S1-D (fail-closed).")
    ap.add_argument("--manifest", nargs="+", metavar="PATH",
                    help="periksa file manifest tertentu (bukan jendela)")
    ap.add_argument("--dir", default=OUT,
                    help="direktori manifest (default: out/)")
    ap.add_argument("--start", default=DEFAULT_START,
                    help="awal jendela tanggal WITA (default: 2026-11-26)")
    ap.add_argument("--end", default=DEFAULT_END,
                    help="akhir jendela tanggal WITA (default: 2026-11-30)")
    args = ap.parse_args(argv)

    all_ok = True
    if args.manifest:
        for path in args.manifest:
            ok, checks = verify_manifest_file(path)
            failed = [c for c, good, _ in checks if not good]
            for name, good, detail in checks:
                print("%s %s %s" % ("PASS" if good else "FAIL", name,
                                    ("(%s)" % detail) if detail else ""))
            print("verify_daily_runs: %s %d/%d checks pass"
                  % (path, len(checks) - len(failed), len(checks)))
            all_ok = all_ok and ok
        print("verify_daily_runs: %s" % ("OK" if all_ok else "FAIL"))
        return 0 if all_ok else 1

    try:
        dates = _date_range(args.start, args.end)
    except ValueError as e:
        print("FAIL bad_date_range: %s" % e)
        return 1
    for date_str in dates:
        path = _latest_manifest_for_date(args.dir, date_str)
        if path is None:
            print("FAIL %s: no_daily_manifest (tidak ada manifest untuk "
                  "tanggal ini — hari TIDAK dihitung sukses)" % date_str)
            all_ok = False
            continue
        ok, checks = verify_manifest_file(path)
        failed = [c for c, good, _ in checks if not good]
        for name, good, detail in checks:
            print("%s %s:%s %s" % ("PASS" if good else "FAIL", date_str, name,
                                    ("(%s)" % detail) if detail else ""))
        print("verify_daily_runs: %s %s %d/%d checks pass"
              % (date_str, path, len(checks) - len(failed), len(checks)))
        all_ok = all_ok and ok
    print("verify_daily_runs: window %s..%s %s"
          % (args.start, args.end, "OK" if all_ok else "FAIL"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
