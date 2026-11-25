"""Keputusan retry berbasis sesi NYSE (aturan (b) sesi-aware, §1.4 v1.1
revisi 25 Nov 2026, sesi fix retry/IncompleteRead).

Masalah yang diperbaiki: `run_daily.sh` dulu hanya me-retry bila tanggal
WITA masih sama DAN jam < 23:30 — run 23:00 WITA yang gagal di tengah
jalan (mis. dry-run 24 Nov mati di token 168/415) TIDAK bisa di-retry
karena tanggal WITA sudah berganti, dan hari itu hilang.

Aturan baru: retry diizinkan HANYA bila retry masih bisa SELESAI di
dalam sesi NYSE yang sama dengan run awal, yaitu:
  sekarang + jeda retry + estimasi durasi run  <  akhir sesi
Akhir sesi = 16:00 ET (regular); early close dari
`config.US_MARKET_EARLY_CLOSE_2026` (27 Nov: 13:00 ET); hari
libur/akhir pekan = akhir hari ET yang sama (run off_hours valid asal
mulai/selesai pada tanggal ET yang sama — lihat verifier).
Syarat tambahan: tanggal ET "sekarang" harus sama dengan tanggal ET
saat run awal dimulai — retry yang sudah masuk sesi/hari ET berikutnya
DITOLAK (manifest-nya akan gagal cek `session_window` di verifier).

Prasyarat pemakaian: fungsi ini HANYA dipanggil `run_daily.sh` sesudah
attempt 1 gagal — attempt 1 selalu mulai 23:00 WITA = 10:00 ET, di
dalam sesi (hari bursa buka), jadi pada hari bursa buka "sekarang"
selalu >= jam buka sesi 09:30 ET. Pemeriksaan di sini hanya sisi
SELESAI (< akhir sesi), sesuai rumus §1.4; sisi MULAI dijamin oleh
jadwal cron + prasyarat ini, bukan diperiksa ulang di sini.

Satu-satunya sumber kebenaran kalender = `pipeline._market_session_detail`
+ tabel `config` yang sama dipakai `_market_session()` — TIDAK ada jalur
paralel di sini: klasifikasi libur/akhir pekan/early-close dibaca dari
pipeline, jam tutup dibaca dari config.

Dipakai `run_daily.sh` (CLI, exit 0 = retry diizinkan, 1 = dibatalkan)
dan diuji `gate.py::test_s1d_session_retry_incompleteread` (offline,
waktu sintetis — tanpa network).

Batas keras: modul ini TIDAK menyentuh decide()/threshold; ia hanya
membaca kalender dan jam.
"""

import argparse
import datetime as _dt
import os
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import pipeline

ET = ZoneInfo("America/New_York")
WITA = ZoneInfo("Asia/Makassar")
# Jam run harian dikunci 23:00 WITA (§1.4); retry selalu milik sesi yang
# dibuka run awal pada jam itu.
RUN_START_HOUR_WITA = 23
RUN_START_MINUTE_WITA = 0


def session_end_for_et_date(et_date, now_et=None):
    """Akhir sesi untuk satu tanggal ET (aware, zona ET) + jenisnya.

    Kembalikan (end_dt, kind) dengan kind = "regular" / "early_close" /
    "off_hours" (libur/akhir pekan: batasnya akhir hari ET). Bila kalender
    tidak dikenal untuk tanggal itu (di luar tahun kalender config),
    kembalikan (None, "unknown") — fail-closed, retry dibatalkan.
    `now_et` (bila diberi) dipakai untuk klasifikasi kalender via pipeline;
    bila tidak diberi, dipakai tengah hari ET tanggal itu.
    """
    probe = now_et
    if probe is None:
        probe = _dt.datetime(et_date.year, et_date.month, et_date.day,
                             12, 0, tzinfo=ET)
    det = pipeline._market_session_detail(probe)
    calendar = det.get("calendar")
    if calendar == "unknown":
        return None, "unknown"
    if calendar in ("holiday", "weekend"):
        end = probe.replace(hour=23, minute=59, second=59, microsecond=0)
        return end, "off_hours"
    day_str = et_date.strftime("%Y-%m-%d")
    close = config.US_MARKET_EARLY_CLOSE_2026.get(day_str)
    if close is not None:
        try:
            ch, cm = (int(x) for x in close.split(":"))
        except (ValueError, AttributeError):
            return None, "unknown"
        end = probe.replace(hour=ch, minute=cm, second=0, microsecond=0)
        return end, "early_close"
    end = probe.replace(hour=16, minute=0, second=0, microsecond=0)
    return end, "regular"


def retry_allowed(run_date_wita, now_utc, remaining_sec):
    """Bolehkah retry jalan sekarang? Kembalikan (allowed, reason, end_iso).

    - run_date_wita: tanggal sesi asal ("YYYY-MM-DD", WITA) — tanggal
      run awal, yang dipakai --run-date di run.py.
    - now_utc: datetime aware (UTC) saat keputusan dibuat.
    - remaining_sec: jeda retry + estimasi durasi run (detik) — retry
      harus SELESAI sebelum akhir sesi, bukan hanya mulai.
    - end_iso: akhir sesi (ISO, zona ET) atau None bila tak diketahui.
    """
    try:
        y, m, d = (int(x) for x in run_date_wita.split("-"))
        run_start_wita = _dt.datetime(y, m, d, RUN_START_HOUR_WITA,
                                      RUN_START_MINUTE_WITA, tzinfo=WITA)
    except (ValueError, AttributeError):
        return False, ("run_date tidak valid: %r (harus YYYY-MM-DD)"
                       % run_date_wita), None
    now_et = now_utc.astimezone(ET)
    run_start_et_date = run_start_wita.astimezone(ET).date()
    if now_et.date() != run_start_et_date:
        return False, (
            "tanggal ET sudah berganti (%s != %s, tanggal ET run awal) — "
            "retry akan masuk sesi/hari ET berikutnya"
            % (now_et.date(), run_start_et_date)), None
    end, kind = session_end_for_et_date(run_start_et_date, now_et)
    if end is None:
        return False, (
            "kalender sesi %s tidak dikenal (kind=%s) — retry dibatalkan "
            "(fail-closed)" % (run_start_et_date, kind)), None
    finish_et = (now_utc + _dt.timedelta(seconds=remaining_sec)).astimezone(ET)
    if finish_et < end:
        return True, (
            "retry diizinkan: selesai %s ET < akhir sesi %s ET (%s)"
            % (finish_et.strftime("%H:%M"), end.strftime("%H:%M"), kind)), \
            end.isoformat()
    return False, (
        "retry DIBATALKAN: selesai %s ET >= akhir sesi %s ET (%s) — "
        "run tidak bisa selesai dalam sesi yang sama"
        % (finish_et.strftime("%H:%M"), end.strftime("%H:%M"), kind)), \
        end.isoformat()


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Keputusan retry berbasis sesi NYSE (§1.4). "
                    "Exit 0 = retry diizinkan, 1 = dibatalkan.")
    ap.add_argument("--run-date", required=True, metavar="YYYY-MM-DD",
                    help="tanggal sesi asal (WITA) — tanggal run awal")
    ap.add_argument("--remaining-sec", required=True, type=int,
                    help="jeda retry + estimasi durasi run (detik)")
    args = ap.parse_args(argv)
    now_utc = _dt.datetime.now(_dt.timezone.utc)
    allowed, reason, _end = retry_allowed(
        args.run_date, now_utc, args.remaining_sec)
    print("session_retry: %s" % reason)
    return 0 if allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
