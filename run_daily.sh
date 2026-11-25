#!/usr/bin/env bash
# Wrapper run harian S1-D — Exit Radar / Base Stocks Maxxing
# (rencana Scope 1 v1.1 §1.4, revisi 25 Nov: cron 23:00 WITA, retry maks 2x
# jeda 30 menit berbasis sesi NYSE yang sama, overlap lock, atomic write
# di run.py, alert gagal).
#
# Dipasang oleh KOORDINATOR via cron (builder TIDAK memasang cron sendiri):
#   TZ=Asia/Makassar
#   0 23 * * * cd /home/hatch/workspace/base-exit-radar && bash run_daily.sh
#
# Perilaku:
#   * Overlap lock: flock non-blocking atas out/daily_run.lock — bila ada
#     run lain yang masih jalan, wrapper keluar (exit 2) TANPA menimpa.
#   * Retry: run awal + maks 2 retry (total 3 attempt), jeda 30 menit,
#     HANYA bila retry masih bisa SELESAI di dalam sesi NYSE yang sama
#     (sekarang + jeda + estimasi durasi run < akhir sesi — dihitung
#     session_retry.py dari kalender pipeline/config; regular 16:00 ET,
#     early close 13:00 ET, libur/akhir pekan = akhir hari ET). Tanggal
#     WITA yang berganti BUKAN alasan batal: retry membawa --run-date
#     agar manifest tetap milik tanggal sesi asal (§1.4b).
#   * Sukses = `python3 run.py --daily` exit 0 (manifest usable: >=1
#     snapshot lengkap, lihat verify_daily_runs.py).
#   * Gagal final = baris ALERT ke log + stderr (cron log) + exit 1.
#     Cron yang gagal = kabari, bukan diam.
#   * Semua output di-tee ke out/daily_run.log (cuplikan log ini masuk
#     manifest sebagai scheduler.log_excerpt).
#
# Gladi manual (BUKAN bagian 5 hari 26-30 Nov):
#   bash run_daily.sh --once --dry-run
#   --once    : satu attempt saja, tanpa retry
#   --dry-run : teruskan ke run.py (trigger dry_run di manifest)

set -u
cd "$(dirname "$0")"
mkdir -p out

LOG="out/daily_run.log"
LOCK="out/daily_run.lock"
MAX_ATTEMPTS=3
RETRY_DELAY_SEC=1800
# Estimasi durasi satu run penuh (detik): dry-run 24 Nov makan 79 menit
# (09:56→11:15 WITA); 100 menit = buffer konservatif untuk keputusan
# retry berbasis sesi (session_retry.py).
ESTIMATED_RUN_SEC=6000

ONCE=0
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --once) ONCE=1 ;;
        --dry-run) DRY_RUN=1 ;;
        *) echo "run_daily.sh: argumen tidak dikenal: $arg" >&2; exit 2 ;;
    esac
done

# Log ke file (tee) + stdout/stderr tetap mengalir (cron log ikut merekam).
exec > >(tee -a "$LOG") 2>&1

# Overlap lock (flock, non-blocking). FD 9 menahan lock selama wrapper hidup.
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "ALERT S1-D $(TZ=Asia/Makassar date '+%Y-%m-%dT%H:%M:%S%z'): run harian DITOLAK — lock $LOCK masih dipegang run lain (overlap dicegah). Tidak ada run baru yang dimulai."
    exit 2
fi

RUN_DATE="$(TZ=Asia/Makassar date '+%Y-%m-%d')"
echo "=== S1-D daily run mulai: $RUN_DATE WITA (trigger: $([ "$DRY_RUN" = 1 ] && echo dry_run || echo cron), once=$ONCE) ==="

RUN_ARGS="--daily"
if [ "$DRY_RUN" = 1 ]; then
    RUN_ARGS="$RUN_ARGS --dry-run --trigger dry_run"
else
    RUN_ARGS="$RUN_ARGS --trigger cron"
fi

attempt=1
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
    ATTEMPT_ARGS="$RUN_ARGS"
    if [ "$attempt" -gt 1 ]; then
        # Retry sesi (§1.4b): manifest tetap milik tanggal sesi asal,
        # walau retry jalan setelah tengah malam WITA.
        ATTEMPT_ARGS="$ATTEMPT_ARGS --run-date $RUN_DATE"
    fi
    echo "--- attempt $attempt/$MAX_ATTEMPTS: python3 run.py $ATTEMPT_ARGS ---"
    if python3 run.py $ATTEMPT_ARGS; then
        echo "=== S1-D daily run SELESAI (attempt $attempt): manifest usable untuk $RUN_DATE ==="
        exit 0
    fi
    echo "--- attempt $attempt GAGAL (exit non-zero / manifest tidak usable) ---"
    if [ "$ONCE" = 1 ] || [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
        break
    fi
    # Retry berbasis sesi (§1.4b, revisi 25 Nov): retry hanya bila masih
    # bisa SELESAI di dalam sesi NYSE yang sama — sekarang + jeda 30 mnt
    # + estimasi durasi run < akhir sesi (session_retry.py; satu-satunya
    # sumber kebenaran kalender = pipeline/config). Tanggal WITA yang
    # berganti BUKAN lagi alasan batal.
    REMAINING_SEC=$((RETRY_DELAY_SEC + ESTIMATED_RUN_SEC))
    if ! RETRY_REASON="$(python3 session_retry.py --run-date "$RUN_DATE" --remaining-sec "$REMAINING_SEC")"; then
        echo "ALERT S1-D: $RETRY_REASON"
        break
    fi
    echo "--- $RETRY_REASON ---"
    echo "--- retry dalam 30 menit (attempt $((attempt + 1))/$MAX_ATTEMPTS) ---"
    sleep "$RETRY_DELAY_SEC"
    attempt=$((attempt + 1))
done

echo "ALERT S1-D $(TZ=Asia/Makassar date '+%Y-%m-%dT%H:%M:%S%z'): run harian $RUN_DATE GAGAL setelah $attempt attempt — TIDAK ADA manifest usable hari ini; kabari chief (cron gagal = kabari, bukan diam)."
exit 1
