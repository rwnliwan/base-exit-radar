"""Gerbang alert end-to-end (§7 brief Instinct) — 9 tes.

Setiap tes memakai snapshot nyata (fixtures/snapshot_live_20261122_*.json)
atau fixture yang dimodifikasi dari snapshot itu (disimpan di fixtures/).
Replay memakai mode TEST/REPLAY agar alert sintetis tidak dikira kejadian
pasar live. Alert dedup memakai seen file SEMENTARA (bukan alerts_seen.json
produksi lokal) agar tes tidak mencemari dedup run live.

Penggunaan:
  python3 gate.py
Output:
  out/gate_results.json   (hasil per tes: expected vs actual, pass/fail)
  out/gate_log.md         (log test yang bisa dibaca manusia)

Kriteria lulus per tes ada di docstring masing-masing tes (dari §7 brief).
"""

import copy
import hashlib
import json
import os
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import pipeline

BASE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(BASE, "fixtures")
OUT = os.path.join(BASE, "out")
SEEN_TEST = os.path.join(OUT, "alerts_seen_gate_test.json")

# Alamat token Base untuk tes validator (re-audit v3, F1). Ditulis EKSPLISIT
# sebagai literal di file tes ini — BUKAN diambil dari config
# (config.USDC_BASE_ADDRESSES). Tujuannya: tes memutus kesalahan konstanta,
# bukan mengonfirmasinya. Di v0.2.1, _valid_quote memakai alamat salah yang
# SAMA dengan config (self-referential) sehingga gate 27/27 tidak menangkap
# bahwa allowlist-nya salah. Alamat di bawah diverifikasi ke BaseScan +
# CoinGecko API (22 Nov 2026):
#  - _REAL_USDC_NATIVE: USDC native (Circle) — BaseScan "USDC (USDC)".
#  - _REAL_USDC_E: Bridged USDC / USDbC — CoinGecko "Bridged USDC (Base)".
#  - _DAI_BASE: L2 Standard Bridged DAI — BUKAN USDC (harus ditolak).
#  - _MANGLED_OLD: alamat mangled v0.2.1 (...bd029029) — bukan token apa pun.
_REAL_USDC_NATIVE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
_REAL_USDC_E = "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA"
_DAI_BASE = "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb"
_MANGLED_OLD = "0x833589fcd6edb6e08f4c7c32d4f71b54bd029029"


def _load_fixture(name):
    with open(os.path.join(FIX, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _save_fixture(name, obj):
    p = os.path.join(FIX, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
    return p


def _reassess(snap, eval_at=None, eval_context="replay"):
    """Jalankan ulang assess+decide+explain dari snapshot (tanpa fetch).
    Default eval_context="replay" (gate menilai ulang snapshot historis);
    eval_at default = fetched_at snapshot (evaluasi "sewaktu" diambil)."""
    snap = pipeline.assess_snapshot(snap, eval_at=eval_at,
                                    eval_context=eval_context)
    snap = pipeline.decide(snap)
    snap = pipeline.explain(snap)
    return snap


def _recompute_snapshot_id(snap):
    """Hitung ulang snapshot_id dari payload awal (setelah memodifikasi
    snapshot untuk tes). Dipakai agar snapshot sintetis yang dibangun tes
    punya identitas konsisten (bukan ditandai transformed)."""
    payload = pipeline._build_time_payload(snap)
    snap["snapshot_id"] = "snap-" + pipeline._short_hash(
        pipeline._canonical(payload))
    return snap


def _fresh_nav_fixture(symbol="NVDAc"):
    """Fixture live dengan NAV fresh (age 1 detik, session active) — kontrol
    untuk tes quote/freshness, seperti repro audit. Registry juga diset
    aktif (G6): multiplier registry = multiplier Coinbase, paused=False,
    fetched_at = fetched_at snapshot — agar kontrol quote yang valid bisa
    mencapai PAPER_PROPOSAL saat gate nyala (bukan diblokir registry unknown
    dari snapshot v0.2.2 yang memang tidak punya data oracle)."""
    base = _load_fixture("snapshot_live_20261122_%s.json" % symbol)
    snap = copy.deepcopy(base)
    fetched = pipeline._parse_ts(snap["fetched_at"])
    snap["reference"].update(
        age_seconds=1,
        nav_price_updated_at=pipeline._iso(
            fetched - timedelta(seconds=1)),
        session_status="active",
        session_status_basis="controlled_fresh_nav_fixture",
        registry_pause_status="active",
    )
    mult = (snap.get("multiplier") or {}).get("value")
    snap["oracle"] = {"multiplier": mult, "paused": False,
                      "source": config.ORACLE_REGISTRY,
                      "fetched_at": snap["fetched_at"]}
    return snap


def _valid_quote(symbol, eval_at, notional_usd=10000.0):
    """Quote jual firm yang valid untuk tes (kind=firm, SELL, token_out alamat
    USDC Base asli, notional cukup, quoted 60 dtk sebelum eval, expiry 600
    dtk sesudah eval). token_out memakai literal _REAL_USDC_NATIVE (bukan
    konstanta config) supaya tes memutus kesalahan konstanta (F1). Implied
    price 10400/80 = 130.0 vs median fixture 131.97 (rasio 0.985, dalam
    toleransi sanity ±10%); notional hitung 80 x 131.97 = 10557.6 >= proposal
    10000; notional dinyatakan 10000 konsisten dengan hitung (rasio 0.947,
    dalam 2x)."""
    tok = config.TOKENS[symbol]
    quoted = eval_at - timedelta(seconds=60)
    expires = eval_at + timedelta(seconds=600)
    return {
        "chain": config.CHAIN,
        "token_in": tok["token_address"],
        "token_out": _REAL_USDC_NATIVE,
        "side": "SELL",
        "amount_in": 80.0,
        "amount_out_min": 10400.0,
        "quoted_at": pipeline._iso(quoted),
        "expires_at": pipeline._iso(expires),
        "source": "test-quoter",
        "venue": "aerodrome",
        "kind": "firm",
        "notional_usd": notional_usd,
    }


# ------------------------------------------------------------------ tes A
def test_quote_validation():
    """Audit A: validator quote eksplisit. Null/kosong/malformed/invalid/
    stale TIDAK BOLEH menghasilkan proposal (cash-only). PAPER_PROPOSAL
    selalu mensyaratkan layer B verified + feature gate nyala."""
    base = _fresh_nav_fixture("NVDAc")
    eval_at = pipeline._parse_ts(base["fetched_at"])
    cases = []  # (nama, quote, kode_yang_diharapkan)
    cases.append(("null", None, "exit_quote_missing"))
    cases.append(("empty_dict", {}, "exit_quote_empty"))
    cases.append(("string", "not-a-quote", "exit_quote_malformed"))
    cases.append(("list", [], "exit_quote_malformed"))
    q = _valid_quote("NVDAc", eval_at)
    q2 = copy.deepcopy(q)
    del q2["amount_out_min"]
    cases.append(("missing_field", q2, "exit_quote_missing_fields"))
    q = _valid_quote("NVDAc", eval_at)
    q["chain"] = "ethereum"
    cases.append(("wrong_chain", q, "exit_quote_wrong_chain"))
    q = _valid_quote("NVDAc", eval_at)
    q["token_in"] = "0x0000000000000000000000000000000000000000"
    cases.append(("wrong_token", q, "exit_quote_wrong_token"))
    q = _valid_quote("NVDAc", eval_at)
    q["side"] = "BUY"
    cases.append(("wrong_side", q, "exit_quote_wrong_side"))
    q = _valid_quote("NVDAc", eval_at)
    q["amount_in"] = 0
    cases.append(("amount_zero", q, "exit_quote_bad_amount"))
    q = _valid_quote("NVDAc", eval_at)
    q["amount_in"] = float("nan")
    cases.append(("amount_nan", q, "exit_quote_bad_amount"))
    q = _valid_quote("NVDAc", eval_at)
    q["amount_out_min"] = -5
    cases.append(("output_negative", q, "exit_quote_bad_output"))
    q = _valid_quote("NVDAc", eval_at)
    q["kind"] = "indicative"
    cases.append(("indicative", q, "exit_quote_indicative_only"))
    q = _valid_quote("NVDAc", eval_at)
    q["kind"] = "simulation"
    cases.append(("simulation", q, "exit_quote_simulation_only"))
    q = _valid_quote("NVDAc", eval_at)
    q["quoted_at"] = pipeline._iso(
        eval_at - timedelta(seconds=3600))
    cases.append(("stale_quote", q, "exit_quote_stale"))
    q = _valid_quote("NVDAc", eval_at)
    q["quoted_at"] = pipeline._iso(
        eval_at + timedelta(seconds=3600))
    cases.append(("future_quote", q, "exit_quote_future_timestamp"))
    q = _valid_quote("NVDAc", eval_at)
    q["expires_at"] = pipeline._iso(
        eval_at - timedelta(seconds=10))
    cases.append(("expired_quote", q, "exit_quote_expired"))
    q = _valid_quote("NVDAc", eval_at)
    q["error"] = "quoter_unavailable"
    cases.append(("source_error", q, "exit_quote_source_error"))
    q = _valid_quote("NVDAc", eval_at, notional_usd=100.0)
    cases.append(("small_notional", q, "exit_quote_notional_insufficient"))
    q = _valid_quote("NVDAc", eval_at)
    del q["notional_usd"]
    cases.append(("notional_unknown", q, "exit_quote_notional_unknown"))
    # --- Re-audit v2, E1: validator terlalu longgar (ketiga probe ini lolos
    # sebagai verified di v0.2.0). Wajib ditolak sebelum gate dinyalakan.
    q = _valid_quote("NVDAc", eval_at)
    del q["kind"]
    cases.append(("kind_missing", q, "exit_quote_kind_missing"))
    q = _valid_quote("NVDAc", eval_at)
    q["token_out"] = "SCAMCOIN"
    cases.append(("token_out_scamcoin", q, "exit_quote_token_out_not_usdc"))
    q = _valid_quote("NVDAc", eval_at)
    q["amount_out_min"] = 1.0
    q["notional_usd"] = 1e12
    cases.append(("absurd_output_and_notional", q, "exit_quote_price_sanity_fail"))
    # Isolasi: harga ngawur dengan notional konsisten -> sanity harga.
    q = _valid_quote("NVDAc", eval_at)
    q["amount_out_min"] = 1.0
    q["notional_usd"] = 10557.6
    cases.append(("absurd_output_only", q, "exit_quote_price_sanity_fail"))
    # Isolasi: notional ngawur dengan harga wajar -> mismatch.
    q = _valid_quote("NVDAc", eval_at)
    q["notional_usd"] = 1e12
    cases.append(("absurd_notional_only", q, "exit_quote_notional_mismatch"))
    # --- Re-audit v3, F1: allowlist USDC v0.2.1 salah (native mangled,
    # "USDC.e" ternyata DAI). DAI dan alamat mangled lama HARUS ditolak.
    q = _valid_quote("NVDAc", eval_at)
    q["token_out"] = _DAI_BASE
    cases.append(("token_out_dai", q, "exit_quote_token_out_not_usdc"))
    q = _valid_quote("NVDAc", eval_at)
    q["token_out"] = _MANGLED_OLD
    cases.append(("token_out_mangled_old", q, "exit_quote_token_out_not_usdc"))

    failed = []
    for name, quote, want_code in cases:
        snap = copy.deepcopy(base)
        snap["exit_quote"] = quote
        snap = _reassess(snap, eval_at=eval_at)
        ok = (snap["decision"] != "PAPER_PROPOSAL"
              and snap["proposal"]["cash_weight"] == 1.0
              and want_code in snap["assessment"]["reason_codes"]
              and snap["assessment"]["layer_b"]["status"]
              != "verified")
        if not ok:
            failed.append("%s: decision=%s codes=%s" % (
                name, snap["decision"], snap["assessment"]["reason_codes"]))
    # --- Re-audit v3, F1: alamat USDC ASLI (literal, bukan konstanta config)
    # harus DITERIMA sebagai bukti exit. Dijalankan dengan gate NYALA
    # sementara: quote valid -> layer B verified + PAPER_PROPOSAL. Ini
    # membuktikan allowlist berisi alamat yang benar (bukan sekadar menolak
    # yang salah). token_out USDC.e asli juga harus verified.
    verified_cases = []
    q = _valid_quote("NVDAc", eval_at)  # token_out = native USDC asli
    verified_cases.append(("usdc_native_real_verified", q))
    q = _valid_quote("NVDAc", eval_at)
    q["token_out"] = _REAL_USDC_E
    verified_cases.append(("usdc_e_real_verified", q))
    old_gate = config.PAPER_PROPOSALS_ENABLED
    try:
        config.PAPER_PROPOSALS_ENABLED = True
        for name, quote in verified_cases:
            snap = copy.deepcopy(base)
            snap["exit_quote"] = quote
            _recompute_snapshot_id(snap)
            snap = _reassess(snap, eval_at=eval_at)
            ok = (snap["decision"] == "PAPER_PROPOSAL"
                  and snap["assessment"]["layer_b"]["status"] == "verified"
                  and snap["assessment"]["layer_b"]["quote_validation"]["status"] == "verified")
            if not ok:
                failed.append("%s: decision=%s layer_b=%s codes=%s" % (
                    name, snap["decision"],
                    snap["assessment"]["layer_b"]["status"],
                    snap["assessment"]["reason_codes"]))
    finally:
        config.PAPER_PROPOSALS_ENABLED = old_gate
    # Kontrol null-vs-empty dari lampiran audit: sama-sama cash-only.
    # Invariant: PAPER_PROPOSAL butuh layer B verified + gate nyala.
    # (a) Quote valid + gate NYALA (sementara) -> PAPER_PROPOSAL, layer B verified.
    snap = copy.deepcopy(base)
    snap["exit_quote"] = _valid_quote("NVDAc", eval_at)
    _recompute_snapshot_id(snap)
    old_gate = config.PAPER_PROPOSALS_ENABLED
    try:
        config.PAPER_PROPOSALS_ENABLED = True
        snap = _reassess(snap, eval_at=eval_at)
        inv_a = (snap["decision"] == "PAPER_PROPOSAL"
                 and snap["assessment"]["layer_b"]["status"] == "verified"
                 and snap["proposal"]["weights"].get("NVDAc", 0) > 0)
    finally:
        config.PAPER_PROPOSALS_ENABLED = old_gate
    if not inv_a:
        failed.append("invariant_valid_quote_gate_on: decision=%s layer_b=%s"
                      % (snap["decision"],
                         snap["assessment"]["layer_b"]["status"]))
    # (b) Quote valid + gate MATI (default) -> WATCH paper_proposals_disabled.
    snap = copy.deepcopy(base)
    snap["exit_quote"] = _valid_quote("NVDAc", eval_at)
    _recompute_snapshot_id(snap)
    snap = _reassess(snap, eval_at=eval_at)
    if not (snap["decision"] == "WATCH"
            and "paper_proposals_disabled" in snap["decision_reasons"]):
        failed.append("invariant_valid_quote_gate_off: decision=%s reasons=%s"
                      % (snap["decision"], snap["decision_reasons"]))
    # (c) Quote invalid (kosong) + gate NYALA -> tetap WATCH (bukan proposal).
    snap = copy.deepcopy(base)
    snap["exit_quote"] = {}
    _recompute_snapshot_id(snap)
    try:
        config.PAPER_PROPOSALS_ENABLED = True
        snap = _reassess(snap, eval_at=eval_at)
        inv_c = snap["decision"] != "PAPER_PROPOSAL"
    finally:
        config.PAPER_PROPOSALS_ENABLED = old_gate
    if not inv_c:
        failed.append("invariant_empty_quote_gate_on: decision=%s"
                      % snap["decision"])
    return _result(
        "quote_validation",
        "null/empty/malformed/invalid/stale quotes -> cash-only WATCH; "
        "real USDC (native + USDC.e) verified; PAPER_PROPOSAL requires "
        "verified layer B + gate on",
        "%d/%d cases cash-only; failed: %s"
        % (len(cases) + 3 + len(verified_cases) - len(failed),
           len(cases) + 3 + len(verified_cases), failed or "none"),
        not failed,
        "validator statuses: missing/invalid/stale/verified; gate default OFF")


# ------------------------------------------------------------------ tes B
def test_freshness():
    """Audit B: freshness per-jenis-data (pool/quote/NAV) benar-benar diuji,
    bukan hanya string status. Reason codes terpisah; batas threshold tepat;
    replay historis vs evaluasi live dibedakan."""
    base = _load_fixture("snapshot_live_20261122_NVDAc.json")
    eval_at = pipeline._parse_ts(base["fetched_at"])
    checks = []

    # (a) DEX stale: semua pool fetched_at + source_updated_at -> 2026-01-01.
    s = copy.deepcopy(base)
    for p in s["pools"]:
        p["fetched_at"] = "2026-01-01T00:00:00Z"
        p["source_updated_at"] = "2026-01-01T00:00:00Z"
    s = _reassess(s, eval_at=eval_at)
    checks.append(("dex_stale_code",
                   "dex_pool_stale" in s["assessment"]["reason_codes"]))
    checks.append(("dex_stale_no_proposal",
                   s["decision"] != "PAPER_PROPOSAL"))
    # (b) Source timestamp unknown -> kode informasional terpisah.
    s = copy.deepcopy(base)
    s = _reassess(s, eval_at=eval_at)
    checks.append(("price_ts_unknown_code",
                   "dex_price_timestamp_unknown"
                   in s["assessment"]["reason_codes"]))
    # (c) Fetch baru + harga sumber tua -> pool basi (fetch != harga fresh).
    s = copy.deepcopy(base)
    for p in s["pools"]:
        p["source_updated_at"] = "2026-01-01T00:00:00Z"
    s = _reassess(s, eval_at=eval_at)
    checks.append(("fresh_fetch_old_price_stale",
                   "dex_pool_stale" in s["assessment"]["reason_codes"]))
    # (d) Quote stale terpisah dari NAV stale (NAV fresh, quote basi).
    s = _fresh_nav_fixture("NVDAc")
    q = _valid_quote("NVDAc", eval_at)
    q["quoted_at"] = pipeline._iso(
        eval_at - timedelta(seconds=3600))
    s["exit_quote"] = q
    s = _reassess(s, eval_at=eval_at)
    checks.append(("quote_stale_separate",
                   "exit_quote_stale" in s["assessment"]["reason_codes"]
                   and "nav_stale_off_hours"
                   not in s["assessment"]["reason_codes"]))
    # (e) NAV stale saat market AKTIF (Senin 23 Nov 2026 15:00 UTC = 10:00 ET).
    s = copy.deepcopy(base)
    monday_open = pipeline._parse_ts("2026-11-23T15:00:00Z")
    s = _reassess(s, eval_at=monday_open)
    checks.append(("nav_stale_active_session",
                   "nav_stale_active_session"
                   in s["assessment"]["reason_codes"]))
    # (f) NAV stale saat market TUTUP (Minggu) -> tanpa active_session.
    s = copy.deepcopy(base)
    sunday = pipeline._parse_ts("2026-11-22T15:00:00Z")
    s = _reassess(s, eval_at=sunday)
    checks.append(("nav_stale_weekend_no_active",
                   "nav_stale_off_hours" in s["assessment"]["reason_codes"]
                   and "nav_stale_active_session"
                   not in s["assessment"]["reason_codes"]))
    # (g) NAV stale saat libur (Thanksgiving 26 Nov 2026) -> tanpa active.
    s = copy.deepcopy(base)
    thanksgiving = pipeline._parse_ts("2026-11-26T15:00:00Z")
    s = _reassess(s, eval_at=thanksgiving)
    checks.append(("nav_stale_holiday_no_active",
                   "nav_stale_off_hours" in s["assessment"]["reason_codes"]
                   and "nav_stale_active_session"
                   not in s["assessment"]["reason_codes"]))
    # (h) Timestamp NAV hilang -> reason eksplisit, bukan diam-diam WATCH.
    s = copy.deepcopy(base)
    s["reference"].update(nav_price_updated_at=None, age_seconds=None,
                          session_status="unknown")
    s = _reassess(s, eval_at=eval_at)
    checks.append(("nav_timestamp_unknown_code",
                   "nav_timestamp_unknown"
                   in s["assessment"]["reason_codes"]))
    # (i) Batas tepat threshold pool: umur tepat 60 menit -> fresh; 60m+1d -> basi.
    s = copy.deepcopy(base)
    for p in s["pools"]:
        p["fetched_at"] = pipeline._iso(
            eval_at - timedelta(minutes=60))
    s = _reassess(s, eval_at=eval_at)
    checks.append(("pool_age_exact_60m_fresh",
                   "dex_pool_stale" not in s["assessment"]["reason_codes"]))
    s = copy.deepcopy(base)
    for p in s["pools"]:
        p["fetched_at"] = pipeline._iso(
            eval_at - timedelta(minutes=60, seconds=1))
    s = _reassess(s, eval_at=eval_at)
    checks.append(("pool_age_60m1s_stale",
                   "dex_pool_stale" in s["assessment"]["reason_codes"]))
    # (j) Replay historis vs evaluasi live: snapshot yang sama, eval_at =
    # fetched_at (replay) -> pool fresh; eval_at = sekarang (live, jauh
    # setelah fetch) -> pool basi. Konteks evaluasi tercatat.
    s = copy.deepcopy(base)
    s_replay = _reassess(copy.deepcopy(s), eval_at=eval_at,
                         eval_context="replay")
    s_live = _reassess(copy.deepcopy(s), eval_at=pipeline._now(),
                       eval_context="live")
    checks.append(("replay_vs_live_freshness",
                   "dex_pool_stale" not in s_replay["assessment"]["reason_codes"]
                   and "dex_pool_stale" in s_live["assessment"]["reason_codes"]))
    checks.append(("eval_context_recorded",
                   s_replay["assessment"]["freshness"]["eval_context"] == "replay"
                   and s_live["assessment"]["freshness"]["eval_context"] == "live"))
    failed = [c for c, ok in checks if not ok]
    return _result(
        "freshness",
        "DEX/quote/NAV freshness tested by time input; separate codes; "
        "replay vs live distinguished",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "pool/quote/nav stale codes + market session (open/closed/holiday)")


# ------------------------------------------------------------------ tes C
def test_coverage_recomputed():
    """Audit C: replay memvalidasi ulang chain + coverage dihitung ulang dari
    pool tervalidasi (bukan percaya count tersimpan). Alias venue dipetakan."""
    base = _load_fixture("snapshot_live_20261122_NVDAc.json")
    eval_at = pipeline._parse_ts(base["fetched_at"])
    checks = []

    # (a) Wrong chain/contract/symbol/decimals -> token_not_confirmed + ABSTAIN.
    for field, value in (("chain", "ethereum"),
                         ("token_address",
                          "0x0000000000000000000000000000000000000000"),
                         ("symbol", "FAKEc"),
                         ("decimals", 6)):
        s = copy.deepcopy(base)
        s["asset"][field] = value
        s = _reassess(s, eval_at=eval_at)
        checks.append(("reject_%s" % field,
                       "token_not_confirmed" in s["assessment"]["reason_codes"]
                       and s["decision"] == "ABSTAIN"))
    # (b) Count palsu (terlalu tinggi/rendah) tidak mengubah hasil hitung ulang.
    # Hasil hitung ulang dibaca dari assessment.coverage_recomputed; count
    # tersimpan TIDAK dimutasi (re-audit v2, E2) — assess tidak menulis
    # ulang snap["coverage"].
    s = copy.deepcopy(base)
    s["coverage"]["independent_pool_count"] = 99
    s["coverage"]["independent_venue_count"] = 99
    s = _reassess(s, eval_at=eval_at)
    checks.append(("fake_count_high_ignored",
                   s["assessment"]["coverage_recomputed"]["recomputed_pool_count"] == 11
                   and s["assessment"]["coverage_recomputed"]["recomputed_venue_count"] == 6
                   and s["coverage"]["independent_pool_count"] == 99
                   and s["coverage"]["independent_venue_count"] == 99))
    s = copy.deepcopy(base)
    s["coverage"]["independent_pool_count"] = 0
    s["coverage"]["independent_venue_count"] = 0
    s = _reassess(s, eval_at=eval_at)
    checks.append(("fake_count_low_ignored",
                   s["assessment"]["coverage_recomputed"]["recomputed_pool_count"] == 11
                   and s["assessment"]["coverage_recomputed"]["recomputed_venue_count"] == 6
                   and s["coverage"]["independent_pool_count"] == 0
                   and s["coverage"]["independent_venue_count"] == 0))
    # (c) Duplikat address beda casing tidak menambah pool.
    s = copy.deepcopy(base)
    dup = copy.deepcopy(s["pools"][0])
    dup["pool_address"] = dup["pool_address"].upper()
    s["pools"].append(dup)
    s = _reassess(s, eval_at=eval_at)
    checks.append(("dup_address_case_insensitive",
                   s["assessment"]["coverage_recomputed"]["recomputed_pool_count"] == 11))
    # (d) Dua pool venue sama (aero + aerodrome = 1 venue) -> ABSTAIN.
    s = copy.deepcopy(base)
    s["pools"] = s["pools"][:2]
    for p in s["pools"]:
        p["dex"] = "aero"
    s["pools"][1]["dex"] = "aerodrome"
    s = _reassess(s, eval_at=eval_at)
    checks.append(("two_pools_one_venue_abstain",
                   s["decision"] == "ABSTAIN"
                   and "insufficient_cross_venue_coverage"
                   in s["assessment"]["reason_codes"]))
    # (e) Alias venue: aero + aerodrome dihitung 1 venue kanonis.
    s = copy.deepcopy(base)
    s = _reassess(s, eval_at=eval_at)
    checks.append(("venue_alias_canonical",
                   s["assessment"]["coverage_recomputed"]["recomputed_venue_count"] == 6
                   and "aerodrome" in s["assessment"]["coverage_recomputed"]["canonical_venues"]
                   and "aero" not in s["assessment"]["coverage_recomputed"]["canonical_venues"]))
    # (f) Payload diubah dengan ID/hash lama -> ditandai transformed replay.
    s = copy.deepcopy(base)
    s["pools"][0]["indicative_price_usd"] = 999.0
    s = _reassess(s, eval_at=eval_at)
    checks.append(("transformed_payload_marked",
                   "snapshot_transformed_replay"
                   in s["assessment"]["reason_codes"]))
    # (g) Payload asli (ID/hash cocok) -> tidak ditandai.
    s = copy.deepcopy(base)
    s = _reassess(s, eval_at=eval_at)
    checks.append(("original_payload_not_marked",
                   "snapshot_transformed_replay"
                   not in s["assessment"]["reason_codes"]))
    failed = [c for c, ok in checks if not ok]
    return _result(
        "coverage_recomputed",
        "chain/identity validated; counts recomputed from validated pools; "
        "venue aliases canonical; transformed payloads marked",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "recomputed pools=11 venues=6 (aero==aerodrome)")


# ------------------------------------------- tes identitas snapshot (E2)
def test_snapshot_identity_live_build():
    """Re-audit v2, E2: snapshot yang dibangun build_snapshot HARUS
    self-consistent saat di-replay — identitas cocok, TIDAK ditandai
    transformed. Regresi atas bug v0.2.0: hash dihitung dari coverage mentah
    (7 venue, aero/aerodrome terpisah) tapi file menyimpan 6 (kanonis),
    sehingga snapshot live v0.2.0 ASLI ditandai transformed replay.
    Catatan: file live v0.2.0 lama (snap-a7da34c2855e4e92) tetap tidak konsisten
    secara konstruksi (hash atas 7, isi 6) — artefak historis, bukan target
    tes ini. Tes ini membuktikan snapshot yang dibangun kode BARU konsisten.
    """
    import adapter as _adapter
    evid = os.path.join(BASE, "evidence")

    def _load(name):
        with open(os.path.join(evid, name), "r", encoding="utf-8") as f:
            return json.load(f)

    cb = _load("coinbase_tokenized_stocks_page1.json")
    hl_xyz = _load("hyperliquid_metaAndAssetCtxs_xyz.json")

    def _hl_instruments(raw):
        meta, ctxs = raw[0], raw[1]
        out = {}
        for i, u in enumerate(meta.get("universe", [])):
            ctx = ctxs[i] if i < len(ctxs) else {}
            out[u.get("name")] = {
                "funding": ctx.get("funding"),
                "openInterest": ctx.get("openInterest"),
                "markPx": ctx.get("markPx"),
                "oraclePx": ctx.get("oraclePx"),
            }
        return out

    orig = (_adapter.fetch_coinbase_tokens,
            _adapter.fetch_dexscreener_pools,
            _adapter.fetch_geckoterminal_pool,
            _adapter.fetch_hyperliquid_proxy,
            _adapter.fetch_oracle_params,
            _adapter.fetch_pool_factory,
            _adapter.fetch_sell_quote,
            _adapter.fetch_pool_tokens,
            _adapter.fetch_token_decimals,
            _adapter.fetch_block)
    checks = []
    try:
        # RPC quoter dimatikan di tes ini (offline): oracle/factory/quote
        # gagal -> snapshot seperti v0.2.2 (exit_quote None, registry unknown,
        # venue fallback ke label DexScreener). Tes quoter live ada di
        # test_quoter_adapter (mock RPC di level adapter, bukan ingest).
        _adapter.fetch_oracle_params = lambda addr, block=None: {
            "ok": False, "multiplier": None, "paused": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.ORACLE_REGISTRY, "error": "mock_rpc_off"}
        _adapter.fetch_pool_factory = lambda addr, block=None: {
            "ok": False, "factory": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": "mock_rpc_off"}
        _adapter.fetch_sell_quote = lambda pool, tok, amt, block=None: {
            "ok": False, "amount_out_usd": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.AERO_METAQUOTER, "error": "mock_rpc_off"}
        _adapter.fetch_pool_tokens = lambda addr, block=None: {
            "ok": False, "token0": None, "token1": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": "mock_rpc_off"}
        _adapter.fetch_token_decimals = lambda addr, block=None: {
            "ok": False, "decimals": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": "mock_rpc_off"}
        _adapter.fetch_block = lambda: {
            "ok": False, "block_number": None, "block_hash": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": "eth_blockNumber", "error": "mock_rpc_off"}
        for sym in ("NVDAc", "AAPLc"):
            ds = _load("dexscreener_%s.json" % sym.lower())
            gt = _load("geckoterminal_%s_pool.json" % sym.lower())
            _adapter.fetch_coinbase_tokens = lambda: {
                "ok": True, "tokens": cb.get("tokens", []),
                "fetched_at": pipeline._iso(pipeline._now()),
                "source": config.COINBASE_API_URL, "error": None, "pages": 1}
            _adapter.fetch_dexscreener_pools = lambda addr: {
                "ok": True, "pairs": ds.get("pairs", []),
                "fetched_at": pipeline._iso(pipeline._now()),
                "source": config.DEXSCREENER_URL.format(address=addr),
                "error": None}
            _adapter.fetch_geckoterminal_pool = lambda pool: {
                "ok": True, "pool": gt.get("data"),
                "fetched_at": pipeline._iso(pipeline._now()),
                "source": config.GECKOTERMINAL_POOL_URL.format(pool=pool),
                "error": None}
            _adapter.fetch_hyperliquid_proxy = lambda dex="xyz": {
                "ok": True, "instruments": _hl_instruments(hl_xyz),
                "fetched_at": pipeline._iso(pipeline._now()),
                "source": config.HYPERLIQUID_INFO_URL + " dex=" + dex,
                "error": None}
            # Bangun snapshot dengan kode BARU, nilai (assess), ambil bentuk
            # tersimpan (public_snapshot = isi file), lalu replay.
            snap = pipeline.build_snapshot(sym)
            snap = pipeline.assess_snapshot(snap)
            stored = pipeline.public_snapshot(snap)
            identity = pipeline.verify_snapshot_identity(stored)
            checks.append(("%s_build_identity_matches" % sym,
                           identity["matches"]))
            checks.append(("%s_build_coverage_canonical" % sym,
                           stored["coverage"]["independent_venue_count"]
                           == snap["assessment"]["coverage_recomputed"]["recomputed_venue_count"]
                           and stored["coverage"]["independent_pool_count"]
                           == snap["assessment"]["coverage_recomputed"]["recomputed_pool_count"]))
            replay = _reassess(copy.deepcopy(stored))
            checks.append(("%s_replay_not_transformed" % sym,
                           "snapshot_transformed_replay"
                           not in replay["assessment"]["reason_codes"]))
            checks.append(("%s_replay_coverage_agrees" % sym,
                           replay["assessment"]["coverage_recomputed"]["stored_venue_count"]
                           == replay["assessment"]["coverage_recomputed"]["recomputed_venue_count"]
                           and replay["assessment"]["coverage_recomputed"]["stored_pool_count"]
                           == replay["assessment"]["coverage_recomputed"]["recomputed_pool_count"]))
    finally:
        (_adapter.fetch_coinbase_tokens,
         _adapter.fetch_dexscreener_pools,
         _adapter.fetch_geckoterminal_pool,
         _adapter.fetch_hyperliquid_proxy,
         _adapter.fetch_oracle_params,
         _adapter.fetch_pool_factory,
         _adapter.fetch_sell_quote,
         _adapter.fetch_pool_tokens,
         _adapter.fetch_token_decimals,
         _adapter.fetch_block) = orig
    failed = [c for c, ok in checks if not ok]
    return _result(
        "snapshot_identity_live_build",
        "snapshot built by fixed build_snapshot is self-consistent on replay: "
        "identity matches, no transformed flag, stored == recomputed coverage",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "E2 regression: build -> public_snapshot -> replay")


# ------------------------------------------------------------------ tes D
def test_dedup_persistence():
    """Audit D: kegagalan persist dedup eksplisit (bukan sukses palsu).
    Error terstruktur per field; replay setelah restart tetap duplicate;
    dua worker bersamaan tidak sama-sama dapat izin emit baru."""
    import subprocess
    snap = _load_fixture("snapshot_live_20261122_NVDAc.json")
    snap = _reassess(copy.deepcopy(snap))
    checks = []

    # (a) Parent dir tidak ada -> ok=False + error terstruktur, file tak ada.
    with tempfile.TemporaryDirectory() as d:
        bad = os.path.join(d, "missing-parent", "seen.json")
        r1 = pipeline.emit_alert(snap, "TEST/REPLAY", bad)
        r2 = pipeline.emit_alert(snap, "TEST/REPLAY", bad)
        checks.append(("missing_parent_error",
                       not r1["ok"] and not r2["ok"]
                       and r1["error"] is not None
                       and set(r1["error"]) >= {"stage", "type", "message"}
                       and not os.path.exists(bad)))
    # (b) Store corrupt -> ok=False, corrupt_store.
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "seen.json")
        with open(p, "w", encoding="utf-8") as f:
            f.write("{corrupt json")
        r = pipeline.emit_alert(snap, "TEST/REPLAY", p)
        checks.append(("corrupt_store_error",
                       not r["ok"]
                       and r["error"]["type"] == "corrupt_store"))
    # (c) Store JSON valid tapi bukan dict -> ok=False, malformed_store.
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "seen.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)
        r = pipeline.emit_alert(snap, "TEST/REPLAY", p)
        checks.append(("malformed_store_error",
                       not r["ok"]
                       and r["error"]["type"] == "malformed_store"))
    # (d) Write gagal (parent adalah FILE, bukan dir) -> ok=False.
    with tempfile.TemporaryDirectory() as d:
        blocker = os.path.join(d, "blocker")
        with open(blocker, "w", encoding="utf-8") as f:
            f.write("x")
        p = os.path.join(blocker, "seen.json")
        r = pipeline.emit_alert(snap, "TEST/REPLAY", p)
        checks.append(("write_failure_error",
                       not r["ok"] and r["error"] is not None
                       and r["error"]["stage"] in ("lock", "write")))
    # (e) Disk penuh (simulasi via mock os.replace) -> ok=False.
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "seen.json")
        orig_replace = os.replace
        def _boom(*a, **k):
            raise OSError("No space left on device")
        os.replace = _boom
        try:
            r = pipeline.emit_alert(snap, "TEST/REPLAY", p)
        finally:
            os.replace = orig_replace
        checks.append(("disk_full_error",
                       not r["ok"] and r["error"]["stage"] == "write"))
    # (f) Replay setelah restart (proses baru) tetap duplicate.
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "seen.json")
        r1 = pipeline.emit_alert(snap, "TEST/REPLAY", p)
        code = (
            "import sys, json; sys.path.insert(0, %r); "
            "import pipeline; snap = pipeline.explain(pipeline.decide("
            "pipeline.assess_snapshot(json.load(open(%r))))); "
            "r = pipeline.emit_alert(snap, 'TEST/REPLAY', %r); "
            "print(json.dumps({'ok': r['ok'], 'duplicate': r['duplicate']}))"
            % (BASE, os.path.join(FIX, "snapshot_live_20261122_NVDAc.json"), p))
        out = subprocess.run([sys.executable, "-c", code],
                             capture_output=True, text=True, timeout=60)
        r2 = json.loads(out.stdout.strip().splitlines()[-1])
        checks.append(("restart_still_duplicate",
                       r1["ok"] and not r1["duplicate"]
                       and r2["ok"] and r2["duplicate"]))
    # (g) Dua worker bersamaan -> tepat satu dapat izin emit baru.
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "seen.json")
        code = (
            "import sys, json; sys.path.insert(0, %r); "
            "import pipeline; snap = pipeline.explain(pipeline.decide("
            "pipeline.assess_snapshot(json.load(open(%r))))); "
            "r = pipeline.emit_alert(snap, 'TEST/REPLAY', %r); "
            "print(json.dumps({'ok': r['ok'], 'duplicate': r['duplicate']}))"
            % (BASE, os.path.join(FIX, "snapshot_live_20261122_NVDAc.json"), p))
        procs = [subprocess.Popen([sys.executable, "-c", code],
                                  stdout=subprocess.PIPE, text=True)
                 for _ in range(2)]
        results = []
        for pr in procs:
            out, _ = pr.communicate(timeout=60)
            results.append(json.loads(out.strip().splitlines()[-1]))
        n_new = sum(1 for r in results if r["ok"] and not r["duplicate"])
        n_dup = sum(1 for r in results if r["ok"] and r["duplicate"])
        checks.append(("concurrent_one_new_one_dup",
                       n_new == 1 and n_dup == 1))
    # (h) Input malformed -> error terstruktur, diuji per field.
    v = pipeline.validate_snapshot_shape({})
    checks.append(("malformed_shape_fields",
                   not v["ok"]
                   and {e["field"] for e in v["errors"]}
                   >= {"snapshot_id", "asset", "reference", "pools",
                       "coverage", "fetched_at"}
                   and all(set(e) == {"field", "reason"} for e in v["errors"])))
    v = pipeline.validate_snapshot_shape("not-a-dict")
    checks.append(("malformed_shape_not_dict",
                   not v["ok"]
                   and v["errors"] == [{"field": "snapshot",
                                        "reason": "not_a_dict"}]))
    v = pipeline.validate_snapshot_shape(snap)
    checks.append(("valid_shape_ok", v["ok"] and v["errors"] == []))
    failed = [c for c, ok in checks if not ok]
    return _result(
        "dedup_persistence",
        "persist failures are structured errors (not empty success); "
        "restart still duplicate; concurrent workers get exactly one new emit",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "error stages: lock/read/write; ok flag enforced")


# ------------------------------------------------------- tes happy-path x2
def test_happy_path_both_tokens():
    """Audit §3: happy-path parametrik NVDAc + AAPLc melewati adapter mock
    (raw capture) -> build -> assess -> decide -> explain -> emit ->
    paper record. Bukan hanya reassess fixture."""
    import adapter as _adapter
    evid = os.path.join(BASE, "evidence")

    def _load(name):
        with open(os.path.join(evid, name), "r", encoding="utf-8") as f:
            return json.load(f)

    cb = _load("coinbase_tokenized_stocks_page1.json")
    hl_xyz = _load("hyperliquid_metaAndAssetCtxs_xyz.json")

    def _hl_instruments(raw):
        meta, ctxs = raw[0], raw[1]
        out = {}
        for i, u in enumerate(meta.get("universe", [])):
            ctx = ctxs[i] if i < len(ctxs) else {}
            out[u.get("name")] = {
                "funding": ctx.get("funding"),
                "openInterest": ctx.get("openInterest"),
                "markPx": ctx.get("markPx"),
                "oraclePx": ctx.get("oraclePx"),
            }
        return out

    orig = (_adapter.fetch_coinbase_tokens,
            _adapter.fetch_dexscreener_pools,
            _adapter.fetch_geckoterminal_pool,
            _adapter.fetch_hyperliquid_proxy,
            _adapter.fetch_oracle_params,
            _adapter.fetch_pool_factory,
            _adapter.fetch_sell_quote,
            _adapter.fetch_pool_tokens,
            _adapter.fetch_token_decimals,
            _adapter.fetch_block)
    checks = []
    try:
        # RPC quoter dimatikan di tes ini (offline) — lihat
        # test_snapshot_identity_live_build untuk alasannya.
        _adapter.fetch_oracle_params = lambda addr, block=None: {
            "ok": False, "multiplier": None, "paused": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.ORACLE_REGISTRY, "error": "mock_rpc_off"}
        _adapter.fetch_pool_factory = lambda addr, block=None: {
            "ok": False, "factory": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": "mock_rpc_off"}
        _adapter.fetch_sell_quote = lambda pool, tok, amt, block=None: {
            "ok": False, "amount_out_usd": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.AERO_METAQUOTER, "error": "mock_rpc_off"}
        _adapter.fetch_pool_tokens = lambda addr, block=None: {
            "ok": False, "token0": None, "token1": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": "mock_rpc_off"}
        _adapter.fetch_token_decimals = lambda addr, block=None: {
            "ok": False, "decimals": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": "mock_rpc_off"}
        _adapter.fetch_block = lambda: {
            "ok": False, "block_number": None, "block_hash": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": "eth_blockNumber", "error": "mock_rpc_off"}
        for sym in ("NVDAc", "AAPLc"):
            tok = config.TOKENS[sym]
            ds = _load("dexscreener_%s.json" % sym.lower())
            gt = _load("geckoterminal_%s_pool.json" % sym.lower())
            top = None
            cands = [p for p in ds.get("pairs", [])
                     if p.get("pairAddress", "").startswith("0x")]
            if cands:
                def _liq(p):
                    try:
                        return float((p.get("liquidity") or {}).get("usd") or -1)
                    except (TypeError, ValueError):
                        return -1.0
                top = max(cands, key=_liq).get("pairAddress")
            _adapter.fetch_coinbase_tokens = lambda: {
                "ok": True, "tokens": cb.get("tokens", []),
                "fetched_at": pipeline._iso(pipeline._now()),
                "source": config.COINBASE_API_URL, "error": None, "pages": 1}
            _adapter.fetch_dexscreener_pools = lambda addr: {
                "ok": True, "pairs": ds.get("pairs", []),
                "fetched_at": pipeline._iso(pipeline._now()),
                "source": config.DEXSCREENER_URL.format(address=addr),
                "error": None}
            _adapter.fetch_geckoterminal_pool = lambda pool: {
                "ok": True, "pool": gt.get("data"),
                "fetched_at": pipeline._iso(pipeline._now()),
                "source": config.GECKOTERMINAL_POOL_URL.format(pool=pool),
                "error": None}
            _adapter.fetch_hyperliquid_proxy = lambda dex="xyz": {
                "ok": True, "instruments": _hl_instruments(hl_xyz),
                "fetched_at": pipeline._iso(pipeline._now()),
                "source": config.HYPERLIQUID_INFO_URL + " dex=" + dex,
                "error": None}
            snap = pipeline.run_token(sym)
            snap = pipeline.explain(snap)
            if os.path.exists(SEEN_TEST):
                os.remove(SEEN_TEST)
            res = pipeline.emit_alert(snap, "TEST/REPLAY", SEEN_TEST)
            rec = pipeline.paper_record(snap)
            checks.append(("%s_decision_watch_or_abstain" % sym,
                           snap["decision"] in ("WATCH", "ABSTAIN")))
            checks.append(("%s_identity" % sym,
                           snap["asset"]["chain"] == "base"
                           and snap["asset"]["token_address"].lower()
                           == tok["token_address"].lower()))
            checks.append(("%s_nav_present" % sym,
                           snap["reference"]["nav_price"] is not None
                           and snap["reference"]["nav_price"] > 0))
            checks.append(("%s_pools" % sym,
                           snap["coverage"]["independent_pool_count"] >= 1))
            checks.append(("%s_explain" % sym,
                           isinstance(snap.get("explanation"), str)
                           and len(snap["explanation"]) > 50))
            checks.append(("%s_emit_ok" % sym,
                           res["ok"] and not res["duplicate"]))
            checks.append(("%s_paper_record" % sym,
                           rec["decision"] == snap["decision"]
                           and rec["proposal"]["cash_weight"] == 1.0))
            checks.append(("%s_top_pool_crosscheck" % sym,
                           top is not None
                           and snap["pools"][0]["pool_address"] == top))
    finally:
        (_adapter.fetch_coinbase_tokens,
         _adapter.fetch_dexscreener_pools,
         _adapter.fetch_geckoterminal_pool,
         _adapter.fetch_hyperliquid_proxy,
         _adapter.fetch_oracle_params,
         _adapter.fetch_pool_factory,
         _adapter.fetch_sell_quote,
         _adapter.fetch_pool_tokens,
         _adapter.fetch_token_decimals,
         _adapter.fetch_block) = orig
    failed = [c for c, ok in checks if not ok]
    return _result(
        "happy_path_both_tokens",
        "NVDAc + AAPLc full chain (mock adapter from raw capture): build, "
        "assess, decide, explain, emit, paper record",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "raw capture evidence/ used as adapter mock source")


# ------------------------------------------------------- tes NAV x multiplier
def test_nav_multiplier_build():
    """Audit §3: test NAV memakai variasi NAV/multiplier PADA BUILD (bukan
    hanya konstanta fixture). NAV disimpan apa adanya, tidak dikali lagi."""
    import adapter as _adapter
    evid = os.path.join(BASE, "evidence")

    def _load(name):
        with open(os.path.join(evid, name), "r", encoding="utf-8") as f:
            return json.load(f)

    cb = _load("coinbase_tokenized_stocks_page1.json")
    ds = _load("dexscreener_nvdac.json")
    gt = _load("geckoterminal_nvdac_pool.json")
    hl_xyz = _load("hyperliquid_metaAndAssetCtxs_xyz.json")

    def _hl_instruments(raw):
        meta, ctxs = raw[0], raw[1]
        out = {}
        for i, u in enumerate(meta.get("universe", [])):
            ctx = ctxs[i] if i < len(ctxs) else {}
            out[u.get("name")] = {
                "funding": ctx.get("funding"),
                "openInterest": ctx.get("openInterest"),
                "markPx": ctx.get("markPx"),
                "oraclePx": ctx.get("oraclePx"),
            }
        return out

    orig = (_adapter.fetch_coinbase_tokens,
            _adapter.fetch_dexscreener_pools,
            _adapter.fetch_geckoterminal_pool,
            _adapter.fetch_hyperliquid_proxy,
            _adapter.fetch_oracle_params,
            _adapter.fetch_pool_factory,
            _adapter.fetch_sell_quote,
            _adapter.fetch_pool_tokens,
            _adapter.fetch_token_decimals,
            _adapter.fetch_block)
    checks = []
    try:
        # RPC quoter dimatikan di tes ini (offline) — lihat
        # test_snapshot_identity_live_build untuk alasannya.
        _adapter.fetch_oracle_params = lambda addr, block=None: {
            "ok": False, "multiplier": None, "paused": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.ORACLE_REGISTRY, "error": "mock_rpc_off"}
        _adapter.fetch_pool_factory = lambda addr, block=None: {
            "ok": False, "factory": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": "mock_rpc_off"}
        _adapter.fetch_sell_quote = lambda pool, tok, amt, block=None: {
            "ok": False, "amount_out_usd": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.AERO_METAQUOTER, "error": "mock_rpc_off"}
        _adapter.fetch_pool_tokens = lambda addr, block=None: {
            "ok": False, "token0": None, "token1": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": "mock_rpc_off"}
        _adapter.fetch_token_decimals = lambda addr, block=None: {
            "ok": False, "decimals": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": "mock_rpc_off"}
        _adapter.fetch_block = lambda: {
            "ok": False, "block_number": None, "block_hash": None,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": "eth_blockNumber", "error": "mock_rpc_off"}
        _adapter.fetch_dexscreener_pools = lambda addr: {
            "ok": True, "pairs": ds.get("pairs", []),
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.DEXSCREENER_URL.format(address=addr),
            "error": None}
        _adapter.fetch_geckoterminal_pool = lambda pool: {
            "ok": True, "pool": gt.get("data"),
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.GECKOTERMINAL_POOL_URL.format(pool=pool),
            "error": None}
        _adapter.fetch_hyperliquid_proxy = lambda dex="xyz": {
            "ok": True, "instruments": _hl_instruments(hl_xyz),
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.HYPERLIQUID_INFO_URL + " dex=" + dex,
            "error": None}
        # Variasi NAV/multiplier pada BUILD (kasus audit: NAV 200, mult 3).
        for nav, mult in ((200.0, 3.0), (129.82480034, 1.0005379395763694),
                          (50.5, 1.5), (1000.0, 0.5)):
            tokens = copy.deepcopy(cb.get("tokens", []))
            rec = None
            for t in tokens:
                if (t.get("contract_address") or "").lower() == \
                        config.TOKENS["NVDAc"]["token_address"].lower():
                    rec = t
                    break
            rec["nav_price"] = nav
            rec["multiplier"] = mult
            rec["nav_price_updated_at"] = pipeline._iso(pipeline._now())
            _adapter.fetch_coinbase_tokens = lambda: {
                "ok": True, "tokens": tokens,
                "fetched_at": pipeline._iso(pipeline._now()),
                "source": config.COINBASE_API_URL, "error": None, "pages": 1}
            snap = pipeline.build_snapshot("NVDAc")
            checks.append(("nav_%.1f_mult_%.2f_stored_as_is" % (nav, mult),
                           snap["reference"]["nav_price"] == nav
                           and snap["multiplier"]["value"] == mult))
            checks.append(("nav_%.1f_not_multiplied" % nav,
                           abs(snap["reference"]["nav_price"] - nav * mult) > 0.01
                           if abs(nav * mult - nav) > 0.01 else True))
    finally:
        (_adapter.fetch_coinbase_tokens,
         _adapter.fetch_dexscreener_pools,
         _adapter.fetch_geckoterminal_pool,
         _adapter.fetch_hyperliquid_proxy,
         _adapter.fetch_oracle_params,
         _adapter.fetch_pool_factory,
         _adapter.fetch_sell_quote,
         _adapter.fetch_pool_tokens,
         _adapter.fetch_token_decimals,
         _adapter.fetch_block) = orig
    failed = [c for c, ok in checks if not ok]
    return _result(
        "nav_multiplier_build",
        "NAV stored as-is (not multiplied) across NAV/multiplier variations "
        "on the build path",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "variations: (200,3), (129.82,1.0005), (50.5,1.5), (1000,0.5)")


def test_quoter_adapter():
    """Fase quoter (v0.3.1): adapter Aero Metaquoter V3 + registry pause +
    label venue dari factory — semua dengan mock RPC (offline, tanpa network).

    G1: "Dromos" BUKAN venue — factory 0x9cb2... adalah Aero Slipstream
    CLFactory (sumber resmi Aero). G4: decoder fail-closed (error RPC =
    error). G5: simulasi dilabeli onchain_simulation, layer B
    simulated_exit_quote_verified (bukan "verified"/firm).
    """
    import adapter as _adapter
    import urllib.request
    evid = os.path.join(BASE, "evidence")
    checks = []

    def _load(name):
        with open(os.path.join(evid, name), "r", encoding="utf-8") as f:
            return json.load(f)

    # --- (a) Parsing adapter dengan mock rpc_call (canned hex) ---
    # Metaquoter: amountOut 1.330.390.000 micro-USDC = $1.330,39 (10 token).
    # sqrtPriceX96After realistis untuk pool ~$133 (sqrt(133)*2**96 ~ 9,1e29)
    # — HARUS di dalam (MIN_SQRT_RATIO, MAX_SQRT_RATIO), kalau tidak G3
    # menolaknya sebagai kemungkinan partial fill.
    _SQRT_AFTER = 913300000000000000000000000000

    def _rpc_quote(to, data):
        words = (format(1330390000, "064x") + format(_SQRT_AFTER, "064x")
                 + format(1, "064x"))
        return words, None

    q = _adapter.fetch_sell_quote(
        "0xF668e21993f0ACd7ab00BB1cFbAeD0df28A3C8EC",
        config.TOKENS["NVDAc"]["token_address"], 10 * 10 ** 8,
        rpc_call=_rpc_quote)
    checks.append(("quoter_parses_amount_out",
                   q["ok"] and abs(q["amount_out_usd"] - 1330.39) < 0.01
                   and q["ticks_crossed"] == 1))
    checks.append(("quoter_rpc_error_is_not_ok",
                   not _adapter.fetch_sell_quote(
                       "0xF668e21993f0ACd7ab00BB1cFbAeD0df28A3C8EC",
                       config.TOKENS["NVDAc"]["token_address"], 10 * 10 ** 8,
                       rpc_call=lambda to, data: (None, "rpc_error:boom"))["ok"]))
    # Oracle: multiplier 1.000538 (WAD) + paused false, lalu paused true.
    mult_word = format(1000537939576369481, "064x")
    q = _adapter.fetch_oracle_params(
        config.TOKENS["NVDAc"]["token_address"],
        rpc_call=lambda to, data: (mult_word + format(0, "064x"), None))
    checks.append(("oracle_parses_multiplier_paused_false",
                   q["ok"] and abs(q["multiplier"] - 1.000538) < 1e-6
                   and q["paused"] is False))
    q = _adapter.fetch_oracle_params(
        config.TOKENS["NVDAc"]["token_address"],
        rpc_call=lambda to, data: (mult_word + format(1, "064x"), None))
    checks.append(("oracle_parses_paused_true",
                   q["ok"] and q["paused"] is True))
    # Factory: Aero Slipstream CLFactory (0x9cb2...).
    fac = _adapter.fetch_pool_factory(
        "0xF668e21993f0ACd7ab00BB1cFbAeD0df28A3C8EC",
        rpc_call=lambda to, data: (
            format(0, "064x")[:-40]
            + config.AERO_SLIPSTREAM_CL_FACTORY[2:].lower(), None))
    checks.append(("factory_parses_aero_slipstream",
                   fac["ok"] and fac["factory"].lower()
                   == config.AERO_SLIPSTREAM_CL_FACTORY.lower()))

    # --- (b) G4 fail-closed: _eth_call HANYA terima outer "result".
    # Error RPC apa pun — termasuk "error.data" (revert payload, mis.
    # Error(string)) — adalah KEGAGALAN, bukan hasil. Metaquoter V3
    # mengembalikan tuple NORMAL (outer "result"); query live independen
    # (2 RPC, block 60.841.377) mengonfirmasi ini.
    class _FakeResp:
        def __init__(self, body):
            self._body = body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._body

    orig_urlopen = urllib.request.urlopen
    try:
        # Outer "result" normal -> hasil.
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "result":
                           "0x" + format(1330390000, "064x")})
        urllib.request.urlopen = lambda req, timeout=None: _FakeResp(body)
        result, err = _adapter._eth_call(
            config.AERO_METAQUOTER, "0x0a674142", "https://mainnet.base.org")
        checks.append(("eth_call_result_is_result",
                       err is None and result is not None
                       and int(result[:64], 16) == 1330390000))
        # Error dengan "data" (revert-with-result / Error(string)) -> ERROR.
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "error": {
            "code": 3, "message": "execution reverted",
            "data": "0x" + format(1330390000, "064x")}})
        urllib.request.urlopen = lambda req, timeout=None: _FakeResp(body)
        result, err = _adapter._eth_call(
            config.AERO_METAQUOTER, "0x0a674142", "https://mainnet.base.org")
        checks.append(("eth_call_error_data_is_error",
                       result is None and err is not None))
        body2 = json.dumps({"jsonrpc": "2.0", "id": 1, "error": {
            "code": 3, "message": "execution reverted"}})
        urllib.request.urlopen = lambda req, timeout=None: _FakeResp(body2)
        result2, err2 = _adapter._eth_call(
            config.AERO_METAQUOTER, "0x0a674142", "https://mainnet.base.org")
        checks.append(("eth_call_revert_without_data_is_error",
                       result2 is None and err2 is not None))
    finally:
        urllib.request.urlopen = orig_urlopen

    # --- (c) Factory -> venue kanonis (G1: Aero Slipstream = aerodrome) ---
    checks.append(("venue_aero_slipstream_factory",
                   pipeline._canonical_venue_for_pool(
                       "aero", config.AERO_SLIPSTREAM_CL_FACTORY) == "aerodrome"))
    checks.append(("venue_aerodrome_factory",
                   pipeline._canonical_venue_for_pool(
                       "aero", config.AERODROME_CL_FACTORY) == "aerodrome"))
    checks.append(("venue_unknown_factory_falls_back_to_dex",
                   pipeline._canonical_venue_for_pool(
                       "aero", "0x0000000000000000000000000000000000000001")
                   == "aerodrome"))
    checks.append(("venue_no_factory_falls_back_to_dex",
                   pipeline._canonical_venue_for_pool("aero", None)
                   == "aerodrome"))
    checks.append(("pool_venue_prefers_venue_field",
                   pipeline._pool_venue(
                       {"dex": "aero", "venue": "aerodrome"}) == "aerodrome"))
    checks.append(("pool_venue_falls_back_without_field",
                   pipeline._pool_venue({"dex": "aero"}) == "aerodrome"))
    # G1: info venue terpisah — factory terverifikasi vs fallback.
    _vi = pipeline._venue_info_for_pool("aero", config.AERO_SLIPSTREAM_CL_FACTORY)
    checks.append(("venue_info_aero_slipstream_verified",
                   _vi["protocol_family"] == "aerodrome"
                   and _vi["venue_label_source"] == "factory"
                   and _vi["factory_verified"] is True
                   and _vi["venue_verified"] is True))
    _vi2 = pipeline._venue_info_for_pool(
        "nami", "0x0000000000000000000000000000000000000001")
    checks.append(("venue_info_unknown_factory_is_fallback",
                   _vi2["protocol_family"] == "nami"
                   and _vi2["venue_label_source"] == "dexscreener_fallback"
                   and _vi2["factory_verified"] is False
                   and _vi2["venue_verified"] is False))
    # G1: dua CLFactory Aero = SATU family, bukan dua venue.
    _fams = {pipeline._canonical_venue_for_pool(
                 "aero", f) for f in (config.AERO_SLIPSTREAM_CL_FACTORY,
                                      config.AERODROME_CL_FACTORY_CURRENT)}
    checks.append(("two_aero_factories_one_family", _fams == {"aerodrome"}))

    # --- (d) Full build dengan quoter mock: layer B simulated_verified,
    # venue aerodrome (G1/G5). Mock juga fetch_pool_tokens,
    # fetch_token_decimals (G2 guard) dan fetch_block (G5).
    cb = _load("coinbase_tokenized_stocks_page1.json")
    ds = _load("dexscreener_nvdac.json")
    gt = _load("geckoterminal_nvdac_pool.json")
    hl_xyz = _load("hyperliquid_metaAndAssetCtxs_xyz.json")

    def _hl_instruments(raw):
        meta, ctxs = raw[0], raw[1]
        out = {}
        for i, u in enumerate(meta.get("universe", [])):
            ctx = ctxs[i] if i < len(ctxs) else {}
            out[u.get("name")] = {
                "funding": ctx.get("funding"),
                "openInterest": ctx.get("openInterest"),
                "markPx": ctx.get("markPx"),
                "oraclePx": ctx.get("oraclePx"),
            }
        return out

    top_price = None
    cands = [p for p in ds.get("pairs", [])
             if p.get("pairAddress", "").startswith("0x")]
    if cands:
        def _liq(p):
            try:
                return float((p.get("liquidity") or {}).get("usd") or -1)
            except (TypeError, ValueError):
                return -1.0
        top = max(cands, key=_liq)
        top_price = float(top.get("priceUsd"))
        top_addr = top.get("pairAddress")
    orig = (_adapter.fetch_coinbase_tokens,
            _adapter.fetch_dexscreener_pools,
            _adapter.fetch_geckoterminal_pool,
            _adapter.fetch_hyperliquid_proxy,
            _adapter.fetch_oracle_params,
            _adapter.fetch_pool_factory,
            _adapter.fetch_sell_quote,
            _adapter.fetch_pool_tokens,
            _adapter.fetch_token_decimals,
            _adapter.fetch_block)
    try:
        _adapter.fetch_coinbase_tokens = lambda: {
            "ok": True, "tokens": cb.get("tokens", []),
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.COINBASE_API_URL, "error": None, "pages": 1}
        _adapter.fetch_dexscreener_pools = lambda addr: {
            "ok": True, "pairs": ds.get("pairs", []),
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.DEXSCREENER_URL.format(address=addr),
            "error": None}
        _adapter.fetch_geckoterminal_pool = lambda pool: {
            "ok": True, "pool": gt.get("data"),
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.GECKOTERMINAL_POOL_URL.format(pool=pool),
            "error": None}
        _adapter.fetch_hyperliquid_proxy = lambda dex="xyz": {
            "ok": True, "instruments": _hl_instruments(hl_xyz),
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.HYPERLIQUID_INFO_URL + " dex=" + dex,
            "error": None}
        _adapter.fetch_oracle_params = lambda addr, block=None: {
            "ok": True, "multiplier": 1.000538, "paused": False,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.ORACLE_REGISTRY, "error": None}
        # Factory: pool teratas = Aero Slipstream; sisanya gagal -> fallback.
        _adapter.fetch_pool_factory = lambda addr, block=None: (
            {"ok": True, "factory": config.AERO_SLIPSTREAM_CL_FACTORY,
             "fetched_at": pipeline._iso(pipeline._now()),
             "source": addr, "error": None}
            if (addr or "").lower() == (top_addr or "").lower()
            else {"ok": False, "factory": None,
                  "fetched_at": pipeline._iso(pipeline._now()),
                  "source": addr, "error": "mock_factory_off"})
        # G2 guard: pool teratas = token0 USDC native, token1 NVDAc.
        _adapter.fetch_pool_tokens = lambda addr, block=None: {
            "ok": True, "token0": config.USDC_NATIVE_BASE,
            "token1": config.TOKENS["NVDAc"]["token_address"],
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": None}
        _adapter.fetch_token_decimals = lambda addr, block=None: {
            "ok": True,
            "decimals": (8 if (addr or "").lower()
                         == config.TOKENS["NVDAc"]["token_address"].lower()
                         else 6),
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": addr, "error": None}
        # G5: block observasi.
        _adapter.fetch_block = lambda: {
            "ok": True, "block_number": 60841377,
            "block_hash": "0x" + "ab" * 32,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": "eth_blockNumber", "error": None}
        # Quote mock: amount_out = amount_in x harga top x (1 - 0,2% slippage).
        def _mock_quote(pool, tok, amount_in_wei, block=None):
            amount_in = amount_in_wei / 10 ** 8
            return {"ok": True,
                    "amount_out_usd": amount_in * top_price * 0.998,
                    "sqrt_price_x96_after": _SQRT_AFTER, "ticks_crossed": 1,
                    "pool": pool, "token_in": tok,
                    "amount_in_wei": amount_in_wei,
                    "fetched_at": pipeline._iso(pipeline._now()),
                    "source": config.AERO_METAQUOTER, "error": None}
        _adapter.fetch_sell_quote = _mock_quote
        snap = pipeline.run_token("NVDAc")
        lb = snap["assessment"]["layer_b"]
        checks.append(("build_exit_quote_present",
                       snap["exit_quote"] is not None
                       and snap["exit_quote"]["source"] == "aero-metaquoter-v3"
                       and snap["exit_quote"]["venue"] == "aerodrome"
                       and snap["exit_quote"]["kind"] == "onchain_simulation"
                       and snap["exit_quote"]["token_out"]
                       == config.USDC_NATIVE_BASE
                       and snap["exit_quote"].get("amount_out_estimate") is not None
                       and "amount_out_min" not in snap["exit_quote"]
                       and "expires_at" not in snap["exit_quote"]
                       and snap["exit_quote"].get("block_number") == 60841377))
        checks.append(("build_layer_b_simulated_verified",
                       lb["status"] == "simulated_exit_quote_verified"))
        checks.append(("build_registry_active",
                       snap["reference"]["registry_pause_status"] == "active"
                       and snap["oracle"] is not None
                       and snap["oracle"]["paused"] is False))
        checks.append(("build_top_pool_venue_aerodrome",
                       snap["pools"][0]["venue"] == "aerodrome"))
        checks.append(("build_top_pool_factory_verified",
                       snap["pools"][0].get("factory_verified") is True
                       and snap["pools"][0].get("venue_label_source") == "factory"))
        checks.append(("build_coverage_verified_venue_count",
                       snap["coverage"]["verified_venue_count"] >= 1
                       and snap["coverage"]["fallback_pool_count"] >= 0))
        checks.append(("build_decision_still_watch_gate_off",
                       snap["decision"] == "WATCH"
                       and snap["proposal"]["cash_weight"] == 1.0))
        # --- (e) Oracle paused -> kode nav_paused_corporate_action ---
        _adapter.fetch_oracle_params = lambda addr, block=None: {
            "ok": True, "multiplier": 1.000538, "paused": True,
            "fetched_at": pipeline._iso(pipeline._now()),
            "source": config.ORACLE_REGISTRY, "error": None}
        snap2 = pipeline.run_token("NVDAc")
        checks.append(("paused_oracle_marks_nav_stale",
                       "nav_paused_corporate_action"
                       in snap2["assessment"]["reason_codes"]))
        checks.append(("paused_oracle_quote_still_simulated_verified",
                       snap2["assessment"]["layer_b"]["status"]
                       == "simulated_exit_quote_verified"))
    finally:
        (_adapter.fetch_coinbase_tokens,
         _adapter.fetch_dexscreener_pools,
         _adapter.fetch_geckoterminal_pool,
         _adapter.fetch_hyperliquid_proxy,
         _adapter.fetch_oracle_params,
         _adapter.fetch_pool_factory,
         _adapter.fetch_sell_quote,
         _adapter.fetch_pool_tokens,
         _adapter.fetch_token_decimals,
         _adapter.fetch_block) = orig
    failed = [c for c, ok in checks if not ok]
    return _result(
        "quoter_adapter",
        "Aero Metaquoter V3 + OracleRegistry + factory venue (mock RPC, "
        "offline): parsing, fail-closed decoder, venue mapping (Aero "
        "Slipstream = aerodrome), full build layer B "
        "simulated_exit_quote_verified, paused oracle marks NAV stale",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "v0.3.1 quoter phase; gate stays off, decision stays WATCH")


def _result(name, expected, actual, passed, details=""):
    return {"test": name, "expected": expected, "actual": actual,
            "pass": bool(passed), "details": details}


# ------------------------------------------------------------------- tes 1
def test_happy_path():
    """Dua token resmi terbaca, identitas tepat, nilai/timestamp/source
    tersimpan. Keputusan policy bisa dijelaskan sampai ke input."""
    snap = _load_fixture("snapshot_live_20261122_NVDAc.json")
    snap = _reassess(copy.deepcopy(snap))
    checks = []
    checks.append(("chain==base", snap["asset"]["chain"] == "base"))
    checks.append(("contract==expected",
                   snap["asset"]["token_address"].lower()
                   == config.TOKENS["NVDAc"]["token_address"].lower()))
    checks.append(("symbol==NVDAc", snap["asset"]["symbol"] == "NVDAc"))
    checks.append(("nav_price>0",
                   snap["reference"]["nav_price"] is not None
                   and snap["reference"]["nav_price"] > 0))
    checks.append(("nav_updated_at present",
                   snap["reference"]["nav_price_updated_at"] is not None))
    checks.append(("fetched_at present", bool(snap["fetched_at"])))
    checks.append(("pools>=min",
                   snap["coverage"]["independent_pool_count"]
                   >= config.MIN_INDEPENDENT_POOLS))
    checks.append(("decision in {ABSTAIN,WATCH,PAPER_PROPOSAL}",
                   snap["decision"] in ("ABSTAIN", "WATCH", "PAPER_PROPOSAL")))
    checks.append(("explanation non-empty",
                   isinstance(snap.get("explanation"), str)
                   and len(snap["explanation"]) > 50))
    checks.append(("explanation mentions contract",
                   snap["asset"]["token_address"] in snap["explanation"]))
    failed = [c for c, ok in checks if not ok]
    return _result(
        "happy_path",
        "identity correct, values/timestamps/sources saved, decision explainable",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "snapshot=%s decision=%s" % (snap["snapshot_id"], snap["decision"]))


# ------------------------------------------------------------------- tes 2
def test_controlled_trigger():
    """Ubah satu fixture kondisi DEX secara eksplisit. Seluruh pipeline
    menghasilkan satu alert lokal TEST/REPLAY. Jangan klaim trigger sintetis
    sebagai alert pasar nyata."""
    base = _load_fixture("snapshot_live_20261122_NVDAc.json")
    snap = copy.deepcopy(base)
    # Ubah SATU pool (teratas by liquidity) agar harganya +8% di atas median.
    # Itu melewati DEV_ABSTAIN_PCT (5%) -> ABSTAIN (dex_deviation_extreme).
    median = snap["assessment"]["layer_a"]["median_price_usd"]
    top = snap["pools"][0]
    old_price = top["indicative_price_usd"]
    top["indicative_price_usd"] = round(median * 1.08, 4)
    _save_fixture("fixture_trigger_deviation.json", snap)
    snap = _reassess(snap)
    # Emit alert TEST/REPLAY (seen file sementara).
    if os.path.exists(SEEN_TEST):
        os.remove(SEEN_TEST)
    res = pipeline.emit_alert(snap, "TEST/REPLAY", SEEN_TEST)
    expected = ("decision=ABSTAIN reason=dex_deviation_extreme, "
                "one TEST/REPLAY alert emitted")
    actual = ("decision=%s reasons=%s alert_duplicate=%s mode=%s"
              % (snap["decision"], snap["decision_reasons"],
                 res["duplicate"], res["mode"]))
    passed = (snap["decision"] == "ABSTAIN"
              and "dex_deviation_extreme" in snap["decision_reasons"]
              and not res["duplicate"] and res["mode"] == "TEST/REPLAY")
    return _result("controlled_trigger", expected, actual, passed,
                   "input change: pool %s price %.4f -> %.4f (+8%% vs median %.2f); "
                   "rule_version=%s; alert_id=%s"
                   % (top["pool_address"], old_price,
                      top["indicative_price_usd"], median,
                      snap["policy_version"], res["alert_id"]))


# ------------------------------------------------------------------- tes 3
def test_nav_weekend():
    """Replay nilai NAV Jumat dan snapshot Minggu. NAV tampil sebagai last
    published reference + age/off-hours, tidak dipakai sebagai live-price
    alarm atau dasar mispricing."""
    snap = _load_fixture("snapshot_live_20261122_NVDAc.json")
    snap = _reassess(copy.deepcopy(snap))
    ref = snap["reference"]
    gap = snap["assessment"]["layer_a"]["nav_gap_pct_labeled"]
    checks = []
    checks.append(("nav_updated_at is Friday",
                   ref["nav_price_updated_at"].startswith("2026-11-20")))
    checks.append(("fetched_at is Sunday",
                   snap["fetched_at"].startswith("2026-11-22")))
    checks.append(("session_status==off_hours",
                   ref["session_status"] == "off_hours"))
    checks.append(("nav age > 24h", (ref["age_seconds"] or 0) > 24 * 3600))
    checks.append(("nav_gap is labeled description",
                   gap is not None
                   and gap["label"] == "dex_median_vs_last_published_nav"
                   and "cause_and_exploitability_unproven" in gap["note"]))
    checks.append(("nav_gap not labeled mispricing/arbitrage",
                   "mispricing" not in json.dumps(gap).lower()
                   or "unproven" in json.dumps(gap).lower()))
    # NAV gap TIDAK memicu reason code alert sendiri.
    checks.append(("no nav_gap reason code",
                   not any("nav_gap" in c or "mispric" in c
                           for c in snap["decision_reasons"])))
    # NAV tidak dikali multiplier (lihat juga tes 4).
    checks.append(("nav_price is raw (not multiplied)",
                   abs(ref["nav_price"] - 129.82480034) < 1e-9))
    failed = [c for c, ok in checks if not ok]
    return _result(
        "nav_weekend",
        "NAV shown as last published reference + age/off-hours; not a live alarm",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "nav_age_seconds=%s nav_gap_pct=%s"
        % (ref["age_seconds"],
           (gap or {}).get("value_pct")))


# ------------------------------------------------------------------- tes 4
def test_multiplier():
    """Buktikan NAV tidak dikalikan lagi. Raw share conversion memakai
    multiplier yang sesuai waktu/unit."""
    snap = _load_fixture("snapshot_live_20261122_NVDAc.json")
    ref = snap["reference"]
    mult = snap["multiplier"]["value"]
    raw_nav = 129.82480034  # nilai mentah dari API Coinbase (evidence)
    checks = []
    # (a) nav_price yang disimpan == nilai mentah API (tidak dikali).
    checks.append(("stored nav == raw API nav",
                   abs(ref["nav_price"] - raw_nav) < 1e-9))
    # (b) Bila dikali multiplier, hasilnya BERBEDA -> bukti tidak dikali.
    multiplied = raw_nav * mult
    checks.append(("nav x multiplier != stored nav (proves not multiplied)",
                   abs(multiplied - ref["nav_price"]) > 0.01))
    # (c) Round-trip raw share: raw_share = nav / multiplier; lalu
    #     raw_share x multiplier == nav (konsisten, memakai multiplier
    #     yang efektif saat itu, bukan multiplier hari ini untuk seluruh seri).
    raw_share = raw_nav / mult
    checks.append(("raw_share x multiplier == nav (round-trip)",
                   abs(raw_share * mult - raw_nav) < 1e-9))
    # (d) Multiplier tercatat terpisah (untuk referensi), bukan diterapkan
    #     ke nav_price.
    checks.append(("multiplier recorded separately",
                   mult is not None and mult > 1.0))
    failed = [c for c, ok in checks if not ok]
    return _result(
        "multiplier",
        "NAV not multiplied again; raw share conversion uses effective multiplier",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "nav=%.8f multiplier=%.16f nav_x_mult=%.8f raw_share=%.8f"
        % (raw_nav, mult, multiplied, raw_share))


# ------------------------------------------------------------------- tes 5
def test_missing_stale():
    """Putuskan sumber atau buat data basi. Usulan baru diblokir/ABSTAIN
    sesuai policy; tidak ada risiko nol palsu. Freshness gate quote,
    observasi DEX, dan NAV terpisah."""
    # (a) Sumber DEX putus: pools kosong.
    base = _load_fixture("snapshot_live_20261122_NVDAc.json")
    s1 = copy.deepcopy(base)
    s1["pools"] = []
    s1["coverage"]["independent_pool_count"] = 0
    s1["coverage"]["independent_venue_count"] = 0
    _save_fixture("fixture_missing_pools.json", s1)
    s1 = _reassess(s1)
    a_ok = (s1["decision"] == "ABSTAIN"
            and "insufficient_cross_venue_coverage" in s1["decision_reasons"]
            and s1["assessment"]["layer_a"]["median_price_usd"] is None)
    # (b) NAV sangat basi (7 hari).
    s2 = copy.deepcopy(base)
    s2["reference"]["nav_price_updated_at"] = "2026-11-15T23:42:40Z"
    s2["reference"]["age_seconds"] = 7 * 24 * 3600
    s2["reference"]["session_status"] = "off_hours"
    _save_fixture("fixture_stale_nav.json", s2)
    s2 = _reassess(s2)
    b_ok = ("nav_stale_off_hours" in s2["decision_reasons"]
            and s2["decision"] in ("ABSTAIN", "WATCH")
            and s2["decision"] != "PAPER_PROPOSAL")
    # (c) Freshness gate terpisah: quote / DEX / NAV masing-masing tercatat.
    c_ok = (s1["assessment"]["layer_b"]["status"]
            == "indicative_only/exit_quality_unverified")
    passed = a_ok and b_ok and c_ok
    return _result(
        "missing_stale",
        "missing source -> ABSTAIN (no zero-risk); stale NAV flagged; gates separate",
        "missing_pools: decision=%s (expect ABSTAIN) ok=%s; "
        "stale_nav: decision=%s codes=%s ok=%s; gates_separate ok=%s"
        % (s1["decision"], a_ok, s2["decision"], s2["decision_reasons"],
           b_ok, c_ok),
        passed,
        "missing pools median=None (not 0); stale NAV age=604800s flagged")


# ------------------------------------------------------------------- tes 6
def test_coverage():
    """Dua agregator untuk satu pool dihitung satu pool. Satu venue tidak
    menghasilkan cross-venue confidence palsu."""
    snap = _load_fixture("snapshot_live_20261122_NVDAc.json")
    snap = _reassess(copy.deepcopy(snap))
    # (a) Pool teratas punya cross_check GeckoTerminal (pool yang sama).
    top = snap["pools"][0]
    a_ok = ("cross_check" in top
            and top["cross_check"].get("note")
            == "same_pool_not_independent_venue")
    # Jumlah pool di pools[] == independent_pool_count (tidak double-count).
    a_ok = a_ok and (len(snap["pools"])
                     == snap["coverage"]["independent_pool_count"])
    # (b) Hanya satu pool valid -> ABSTAIN, median None (bukan nol).
    s2 = copy.deepcopy(snap)
    s2["pools"] = [copy.deepcopy(s2["pools"][0])]
    s2["coverage"]["independent_pool_count"] = 1
    s2["coverage"]["independent_venue_count"] = 1
    _save_fixture("fixture_single_pool.json", s2)
    s2 = _reassess(s2)
    b_ok = (s2["decision"] == "ABSTAIN"
            and "insufficient_cross_venue_coverage" in s2["decision_reasons"]
            and s2["assessment"]["layer_a"]["median_price_usd"] is None)
    return _result(
        "coverage",
        "two aggregators one pool = one pool; one venue -> no false confidence",
        "cross_check_same_pool ok=%s; single_pool decision=%s (expect ABSTAIN) "
        "median=None ok=%s" % (a_ok, s2["decision"], b_ok),
        bool(a_ok and b_ok),
        "live pools=%d venues=%d; single-pool fixture median=None"
        % (snap["coverage"]["independent_pool_count"],
           snap["coverage"]["independent_venue_count"]))


# ------------------------------------------------------------------- tes 7
def test_proxy():
    """Funding ekstrem atau perubahan OI saja tidak memicu klaim token-exit.
    Label proxy bertahan sampai payload alert/paper proposal. Histori belum
    cukup menghasilkan null, bukan perubahan 24h rekaan."""
    base = _load_fixture("snapshot_live_20261122_NVDAc.json")
    snap = copy.deepcopy(base)
    # Funding ekstrem (5%/jam) + OI raksasa pada proxy.
    snap["underlying_proxy"]["funding_raw"] = 0.05
    snap["underlying_proxy"]["open_interest_raw"] = 999999999.0
    _save_fixture("fixture_proxy_extreme.json", snap)
    snap = _reassess(snap)
    if os.path.exists(SEEN_TEST):
        os.remove(SEEN_TEST)
    res = pipeline.emit_alert(snap, "TEST/REPLAY", SEEN_TEST)
    # Keputusan TIDAK berubah karena proxy saja (tetap WATCH; bukan ABSTAIN
    # karena proxy, bukan PAPER_PROPOSAL).
    a_ok = (snap["decision"] == "WATCH"
            and "no_exit_quote_adapter" in snap["decision_reasons"])
    # Label proxy bertahan sampai payload alert.
    b_ok = (not res["duplicate"]
            and res["payload"]["proxy_label"]
            == "UNDERLYING EQUITY PERP PROXY")
    # OI change 24h = null (insufficient_history), bukan 0% / rekaan.
    c_ok = (snap["underlying_proxy"]["oi_change_24h"] is None
            and snap["underlying_proxy"]["oi_change_24h_basis"]
            == "insufficient_history_no_baseline")
    return _result(
        "proxy",
        "extreme funding/OI alone does not trigger token-exit claim; label persists; OI change null",
        "decision=%s (expect WATCH) ok=%s; alert proxy_label ok=%s; "
        "oi_change_24h=None ok=%s" % (snap["decision"], a_ok, b_ok, c_ok),
        bool(a_ok and b_ok and c_ok),
        "funding set to 0.05 (5%%/h); decision unchanged by proxy alone")


# ------------------------------------------------------------------- tes 8
def test_liquidity_vs_exit():
    """TVL besar tanpa sell quote tetap exit_quality_unverified; tidak ada
    klaim bisa menjual nominal tertentu."""
    snap = _load_fixture("snapshot_live_20261122_NVDAc.json")
    snap = _reassess(copy.deepcopy(snap))
    top_liq = snap["pools"][0]["liquidity_usd"] if snap["pools"] else 0
    checks = []
    checks.append(("top pool liquidity is large (>$1M)",
                   top_liq > 1_000_000))
    checks.append(("exit_quote is None", snap["exit_quote"] is None))
    checks.append(("layer_b status indicative_only",
                   snap["assessment"]["layer_b"]["status"]
                   == "indicative_only/exit_quality_unverified"))
    checks.append(("decision is not PAPER_PROPOSAL",
                   snap["decision"] != "PAPER_PROPOSAL"))
    # Tidak ada klaim "bisa menjual nominal X" di explanation/paper record.
    rec = pipeline.paper_record(snap)
    blob = json.dumps(rec) + snap["explanation"]
    checks.append(("no sell-nominal claim in paper record/explanation",
                   "can sell" not in blob.lower()
                   and "bisa menjual" not in blob.lower()))
    failed = [c for c, ok in checks if not ok]
    return _result(
        "liquidity_vs_exit",
        "large TVL without sell quote stays exit_quality_unverified; no sell claim",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "top_pool_liquidity_usd=%.2f decision=%s" % (top_liq, snap["decision"]))


# ------------------------------------------------------------------- tes 9
def test_idempotency():
    """Replay snapshot/rule sama tidak menduplikasi alert. Input buruk
    menghasilkan error terstruktur, bukan output sukses kosong."""
    snap = _load_fixture("snapshot_live_20261122_NVDAc.json")
    snap = _reassess(copy.deepcopy(snap))
    if os.path.exists(SEEN_TEST):
        os.remove(SEEN_TEST)
    r1 = pipeline.emit_alert(snap, "TEST/REPLAY", SEEN_TEST)
    r2 = pipeline.emit_alert(snap, "TEST/REPLAY", SEEN_TEST)
    a_ok = (not r1["duplicate"] and r2["duplicate"]
            and r1["alert_id"] == r2["alert_id"])
    # Input buruk -> error terstruktur (exception), bukan sukses kosong.
    try:
        pipeline.assess_snapshot({})
        b_ok = False
        b_detail = "assess_snapshot({}) returned success (BAD: empty success)"
    except (KeyError, TypeError, AttributeError) as e:
        b_ok = True
        b_detail = "assess_snapshot({}) raised %s (structured error, not empty success)" % type(e).__name__
    return _result(
        "idempotency",
        "same snapshot/rule replay does not duplicate alert; bad input errors",
        "first emit duplicate=%s, second emit duplicate=%s, same id=%s; "
        "bad input: %s" % (r1["duplicate"], r2["duplicate"],
                           r1["alert_id"] == r2["alert_id"], b_detail),
        bool(a_ok and b_ok),
        "alert_id=%s" % r1["alert_id"])


# ------------------------------------------------- tes quoter G1-G6 (v0.3.1)
def test_quoter_g1_g6():
    """Regresi must-fix G1-G6 re-audit v5 Instinct (22 Nov 2026).

    G1: factory/venue/independensi terpisah (fallback tidak dihitung
    verified; dua factory Aero = satu family).
    G2: guard quote (token0/token1, decimals, factory) — pool non-USDC,
    decimals salah, factory tak didukung DITOLAK, bukan direlabel.
    G3: partial-fill — terminal sqrt-price di batas MIN/MAX ditolak.
    G4: decoder fail-closed — error RPC, trailing bytes, bool=2, alamat
    non-kanonis, tick overflow DITOLAK.
    G5: label jujur — simulasi = onchain_simulation / simulated_verified,
    tidak pernah dipromosikan jadi firm; tanpa block_number ditolak.
    G6: registry unknown/stale/mismatch = proposal-blocking (gate on pun
    tidak pernah PAPER_PROPOSAL).
    """
    import adapter as _adapter
    checks = []
    _SQRT_OK = 913300000000000000000000000000  # ~$133, dalam (MIN, MAX)
    _TOK = config.TOKENS["NVDAc"]["token_address"]
    _USDC = config.USDC_NATIVE_BASE
    _POOL = "0xF668e21993f0ACd7ab00BB1cFbAeD0df28A3C8EC"

    def _w3(a, s, t):
        return (format(a, "064x") + format(s, "064x") + format(t, "064x"))

    # ---- G1: venue terpisah ----
    _vi = pipeline._venue_info_for_pool("aero", config.AERO_SLIPSTREAM_CL_FACTORY)
    checks.append(("g1_aero_slipstream_is_aerodrome_verified",
                   _vi["protocol_family"] == "aerodrome"
                   and _vi["venue_verified"] is True))
    _vi = pipeline._venue_info_for_pool("nami", config.NAMI_ALGEBRA_FACTORY)
    checks.append(("g1_nami_factory_verified",
                   _vi["protocol_family"] == "nami"
                   and _vi["venue_verified"] is True))
    _vi = pipeline._venue_info_for_pool("hydrex", config.HYDREX_ALGEBRA_FACTORY)
    checks.append(("g1_hydrex_factory_verified",
                   _vi["protocol_family"] == "hydrex"
                   and _vi["venue_verified"] is True))
    _vi = pipeline._venue_info_for_pool("topaz", config.TOPAZ_CL_FACTORY)
    checks.append(("g1_topaz_factory_verified",
                   _vi["protocol_family"] == "topaz"
                   and _vi["venue_verified"] is True))
    _vi = pipeline._venue_info_for_pool("equalizer", config.EQUALIZER_FACTORY)
    checks.append(("g1_equalizer_factory_verified",
                   _vi["protocol_family"] == "equalizer"
                   and _vi["venue_verified"] is True))
    _vi = pipeline._venue_info_for_pool(
        "arbitrary-label", "0x0000000000000000000000000000000000000001")
    checks.append(("g1_unknown_factory_not_verified",
                   _vi["venue_verified"] is False
                   and _vi["venue_label_source"] == "dexscreener_fallback"))
    # Fallback counter cocok dengan observasi per pool (G1 repro).
    # Snapshot live v0.3.0 (11 pool NVDAc, semua factory terbaca): di bawah
    # mapping v0.3.0 (hanya 4 factory: Dromos, Aero legacy, Aero current,
    # Uniswap) ada 5 pool fallback — persis klaim re-audit v5 ("0 fallback"
    # SALAH). Di bawah mapping v0.3.1 (8 factory, + Nami/Hydrex/Topaz/
    # Equalizer terverifikasi BaseScan) fallback = 0. Dan distinct family
    # v0.3.1 = 6 (aerodrome, uniswap, nami, hydrex, topaz, equalizer),
    # BUKAN 7 — "dromos" bukan venue terpisah.
    _v030 = os.path.join(BASE, "out", "v0.3.0",
                         "snapshot_NVDAc_snap-2fed783e9f2dbf82.json")
    with open(_v030, "r", encoding="utf-8") as f:
        _s030 = json.load(f)
    _pools030 = _s030.get("pools") or []
    _old_map = {config.AERO_SLIPSTREAM_CL_FACTORY.lower(),
                config.AERODROME_CL_FACTORY.lower(),
                config.AERODROME_CL_FACTORY_CURRENT.lower(),
                config.UNISWAP_V3_FACTORY.lower()}
    _fb_old = len([p for p in _pools030
                   if (p.get("factory") or "").lower() not in _old_map])
    _fb_new = len([p for p in _pools030
                   if (p.get("factory") or "").lower()
                   not in config.FACTORY_VENUE])
    _fams_new = {pipeline._canonical_venue_for_pool(
        p.get("dex"), p.get("factory")) for p in _pools030}
    checks.append(("g1_fallback_counter_matches_pools",
                   len(_pools030) == 11 and _fb_old == 5 and _fb_new == 0
                   and _fams_new == {"aerodrome", "uniswap", "nami",
                                     "hydrex", "topaz", "equalizer"}))
    # Dua factory Aero = satu family (bukan dua venue independen).
    _fams = {pipeline._canonical_venue_for_pool("aero", f) for f in (
        config.AERO_SLIPSTREAM_CL_FACTORY, config.AERODROME_CL_FACTORY,
        config.AERODROME_CL_FACTORY_CURRENT)}
    checks.append(("g1_three_aero_factories_one_family", _fams == {"aerodrome"}))

    # ---- G2: guard quote (mock RPC token/decimals) ----
    _USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
    _USDBC = "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA"
    _WETH = "0x4200000000000000000000000000000000000006"

    def _mk_tokens(t0, t1):
        def _f(addr, block=None):
            return {"ok": True, "token0": t0, "token1": t1,
                    "fetched_at": pipeline._iso(pipeline._now()),
                    "source": addr, "error": None}
        return _f

    def _mk_dec(dec_map):
        def _f(addr, block=None):
            d = dec_map.get((addr or "").lower())
            if d is None:
                return {"ok": False, "decimals": None,
                        "fetched_at": pipeline._iso(pipeline._now()),
                        "source": addr, "error": "mock_dec_off"}
            return {"ok": True, "decimals": d,
                    "fetched_at": pipeline._iso(pipeline._now()),
                    "source": addr, "error": None}
        return _f

    _fac = {_POOL.lower(): config.AERO_SLIPSTREAM_CL_FACTORY}
    _dec_ok = {_TOK.lower(): 8, _USDC.lower(): 6}
    orig2 = (_adapter.fetch_pool_tokens, _adapter.fetch_token_decimals)
    try:
        # (i) Pool token/USDC native, decimals benar, factory didukung -> ok.
        _adapter.fetch_pool_tokens = _mk_tokens(_USDC, _TOK)
        _adapter.fetch_token_decimals = _mk_dec(_dec_ok)
        ok, reason, info = pipeline._quote_pool_eligible(_POOL, _TOK, 8, _fac)
        checks.append(("g2_usdc_native_eligible",
                       ok and info.get("token_out", "").lower() == _USDC.lower()
                       and info.get("venue") == "aerodrome"))
        # (ii) Counterpart USDT -> tolak.
        _adapter.fetch_pool_tokens = _mk_tokens(_USDT, _TOK)
        _adapter.fetch_token_decimals = _mk_dec(
            {_TOK.lower(): 8, _USDT.lower(): 6})
        ok, reason, _i = pipeline._quote_pool_eligible(_POOL, _TOK, 8, _fac)
        checks.append(("g2_usdt_counterpart_rejected",
                       not ok and reason == "counterpart_not_usdc_allowlist"))
        # (iii) Counterpart USDbC (bukan native, scope native-only) -> tolak.
        _adapter.fetch_pool_tokens = _mk_tokens(_USDBC, _TOK)
        _adapter.fetch_token_decimals = _mk_dec(
            {_TOK.lower(): 8, _USDBC.lower(): 6})
        ok, reason, _i = pipeline._quote_pool_eligible(_POOL, _TOK, 8, _fac)
        checks.append(("g2_usdbc_counterpart_rejected",
                       not ok and reason == "counterpart_not_native_usdc"))
        # (iv) Counterpart WETH -> tolak.
        _adapter.fetch_pool_tokens = _mk_tokens(_WETH, _TOK)
        _adapter.fetch_token_decimals = _mk_dec(
            {_TOK.lower(): 8, _WETH.lower(): 18})
        ok, reason, _i = pipeline._quote_pool_eligible(_POOL, _TOK, 8, _fac)
        checks.append(("g2_weth_counterpart_rejected",
                       not ok and reason == "counterpart_not_usdc_allowlist"))
        # (v) TokenIn bukan anggota pool -> tolak.
        _adapter.fetch_pool_tokens = _mk_tokens(_USDC, _USDT)
        _adapter.fetch_token_decimals = _mk_dec(
            {_USDC.lower(): 6, _USDT.lower(): 6})
        ok, reason, _i = pipeline._quote_pool_eligible(_POOL, _TOK, 8, _fac)
        checks.append(("g2_token_not_member_rejected",
                       not ok and reason == "token_in_not_pool_member"))
        # (vi) Factory tak didukung -> tolak.
        _adapter.fetch_pool_tokens = _mk_tokens(_USDC, _TOK)
        _adapter.fetch_token_decimals = _mk_dec(_dec_ok)
        ok, reason, _i = pipeline._quote_pool_eligible(_POOL, _TOK, 8, {})
        checks.append(("g2_unsupported_factory_rejected",
                       not ok and reason == "factory_unsupported_or_unknown"))
        # (vii) Decimals tokenIn salah (6, bukan 8) -> tolak.
        _adapter.fetch_pool_tokens = _mk_tokens(_USDC, _TOK)
        _adapter.fetch_token_decimals = _mk_dec({_TOK.lower(): 6, _USDC.lower(): 6})
        ok, reason, _i = pipeline._quote_pool_eligible(_POOL, _TOK, 8, _fac)
        checks.append(("g2_wrong_token_decimals_rejected",
                       not ok and reason == "token_in_decimals_mismatch"))
        # (viii) Decimals counterpart salah (18, bukan 6) -> tolak.
        _adapter.fetch_pool_tokens = _mk_tokens(_USDC, _TOK)
        _adapter.fetch_token_decimals = _mk_dec({_TOK.lower(): 8, _USDC.lower(): 18})
        ok, reason, _i = pipeline._quote_pool_eligible(_POOL, _TOK, 8, _fac)
        checks.append(("g2_wrong_counterpart_decimals_rejected",
                       not ok and reason == "counterpart_decimals_not_6"))
    finally:
        (_adapter.fetch_pool_tokens, _adapter.fetch_token_decimals) = orig2

    # ---- G3: partial-fill (terminal sqrt-price) ----
    # KOREKSI F1 (re-audit v6): guard batas MIN/MAX HANYA menangkap terminal
    # sqrt-price TEPAT di batas. Signature partial-fill standar (terminal
    # MIN+1/MAX−1 — quoter memakai itu sebagai limit saat sqrtPriceLimitX96
    # =0) TIDAK tertangkap guard ini. Tes v0.3.1 yang meng-assert min+1/
    # max-1 sebagai "OK" SALAH secara konseptual (itu signature partial
    # fill, bukan bukti sehat). Yang benar: bound guard membiarkan min+1/
    # max-1 lolos (keterbatasan TERDOKUMENTASI), dan deteksi partial-fill
    # yang benar = double-quote probe (test_quoter_f1_f2) + sanity ±10%.
    def _q_with_sqrt(sqrt_val, ticks=1, amount_out=10500000000):
        return _adapter.fetch_sell_quote(
            _POOL, _TOK, 79 * 10 ** 8,
            rpc_call=lambda to, data: (_w3(amount_out, sqrt_val, ticks), None))

    q = _q_with_sqrt(_SQRT_OK)
    checks.append(("g3_normal_sqrt_ok", q["ok"]))
    # MIN+1/MAX−1 LOLOS bound guard (keterbatasan terdokumentasi — BUKAN
    # bukti sehat; probe yang menangkap partial fill nyata).
    q = _q_with_sqrt(config.MIN_SQRT_RATIO + 1)
    checks.append(("g3_bound_guard_limitation_min_plus_1_passes",
                   q["ok"]))
    q = _q_with_sqrt(config.MAX_SQRT_RATIO - 1)
    checks.append(("g3_bound_guard_limitation_max_minus_1_passes",
                   q["ok"]))
    q = _q_with_sqrt(config.MIN_SQRT_RATIO)
    checks.append(("g3_terminal_min_rejected",
                   not q["ok"] and q["error"] == "quote_possible_partial_fill"))
    q = _q_with_sqrt(config.MAX_SQRT_RATIO)
    checks.append(("g3_terminal_max_rejected",
                   not q["ok"] and q["error"] == "quote_possible_partial_fill"))
    q = _q_with_sqrt(_SQRT_OK, amount_out=0)
    checks.append(("g3_zero_output_rejected",
                   not q["ok"] and q["error"] == "quote_zero_output"))

    # ---- G4: decoder fail-closed ----
    # Error(string) repro G4: payload Error(string) 96+ byte yang dulu
    # diparse jadi quote "sukses" (amount_out ~3,96e69). Kini: _eth_call
    # menolak error.data, dan kalaupun payload itu sampai sebagai "result",
    # word ke-2 (offset 0x20 = 32) <= MIN_SQRT_RATIO -> G3 menolak.
    _err_str = ("08c379a0" + format(32, "064x") + format(11, "064x")
                + "4572726f7220737472696e670000000000000000000000000000"
                + "0000000000000000000000000000")
    q = _adapter.fetch_sell_quote(
        _POOL, _TOK, 79 * 10 ** 8,
        rpc_call=lambda to, data: (_err_str, None))
    checks.append(("g4_error_string_payload_rejected", not q["ok"]))
    # Trailing bytes -> malformed.
    q = _adapter.fetch_sell_quote(
        _POOL, _TOK, 79 * 10 ** 8,
        rpc_call=lambda to, data: (_w3(10500000000, _SQRT_OK, 1) + "00", None))
    checks.append(("g4_trailing_bytes_rejected",
                   not q["ok"] and q["error"] == "quote_malformed_result"))
    # Short payload -> malformed.
    q = _adapter.fetch_sell_quote(
        _POOL, _TOK, 79 * 10 ** 8,
        rpc_call=lambda to, data: (_w3(10500000000, _SQRT_OK, 1)[:100], None))
    checks.append(("g4_short_payload_rejected",
                   not q["ok"] and q["error"] == "quote_malformed_result"))
    # Hex malformed -> malformed.
    q = _adapter.fetch_sell_quote(
        _POOL, _TOK, 79 * 10 ** 8,
        rpc_call=lambda to, data: ("zz" * 96, None))
    checks.append(("g4_malformed_hex_rejected",
                   not q["ok"] and q["error"] == "quote_malformed_result"))
    # Tick overflow (> uint32) -> ditolak.
    q = _adapter.fetch_sell_quote(
        _POOL, _TOK, 79 * 10 ** 8,
        rpc_call=lambda to, data: (_w3(10500000000, _SQRT_OK, 2 ** 32), None))
    checks.append(("g4_tick_overflow_rejected",
                   not q["ok"] and q["error"] == "quote_bad_ticks"))
    # Sqrt > uint160 -> ditolak.
    q = _adapter.fetch_sell_quote(
        _POOL, _TOK, 79 * 10 ** 8,
        rpc_call=lambda to, data: (_w3(10500000000, 2 ** 160, 1), None))
    checks.append(("g4_sqrt_overflow_rejected",
                   not q["ok"] and q["error"] == "quote_bad_sqrt_price"))
    # Bool registry = 2 -> ditolak (G4 repro).
    _mw = format(1000537939576369481, "064x")
    o = _adapter.fetch_oracle_params(
        _TOK, rpc_call=lambda to, data: (_mw + format(2, "064x"), None))
    checks.append(("g4_oracle_bool_2_rejected",
                   not o["ok"] and o["error"] == "oracle_bad_paused_bool"))
    # Alamat factory non-kanonis (padding bukan nol) -> ditolak.
    f = _adapter.fetch_pool_factory(
        _POOL, rpc_call=lambda to, data: (
            "000000000000000000000001" + _USDC[2:].lower(), None))
    checks.append(("g4_factory_noncanonical_address_rejected",
                   not f["ok"] and f["error"] == "factory_bad_address"))
    # Alamat factory nol -> ditolak.
    f = _adapter.fetch_pool_factory(
        _POOL, rpc_call=lambda to, data: (format(0, "064x"), None))
    checks.append(("g4_factory_zero_address_rejected",
                   not f["ok"] and f["error"] == "factory_bad_address"))

    # ---- G5: label jujur ----
    _snap = _load_fixture("snapshot_live_20261122_NVDAc.json")
    _eval = pipeline._parse_ts(_snap.get("fetched_at"))
    _med = _snap["assessment"]["layer_a"]["median_price_usd"]

    def _sim_quote(**over):
        q = {"chain": "base", "token_in": _TOK, "token_out": _USDC,
             "side": "SELL", "amount_in": 79.006772009,
             "amount_out_estimate": 10500.54,
             "observed_at": _snap["fetched_at"],
             "max_age_sec": 300, "block_number": 60841377,
             "block_hash": "0x" + "ab" * 32,
             "source": "aero-metaquoter-v3", "venue": "aerodrome",
             "kind": "onchain_simulation",
             "notional_usd": 10500.54, "pool": _POOL}
        q.update(over)
        return q

    v = pipeline.validate_exit_quote(_sim_quote(), _snap, eval_at=_eval,
                                     median_price_usd=_med)
    checks.append(("g5_simulation_valid_gets_simulated_verified",
                   v["status"] == "simulated_verified"))
    checks.append(("g5_simulation_never_promoted_to_firm",
                   v["status"] != "verified"))
    # Simulasi tanpa block_number -> invalid.
    _q = _sim_quote()
    del _q["block_number"]
    v = pipeline.validate_exit_quote(_q, _snap, eval_at=_eval,
                                     median_price_usd=_med)
    checks.append(("g5_simulation_without_block_rejected",
                   v["status"] == "invalid"))
    # Simulasi yang memakai amount_out_min (bukan estimate) -> invalid
    # (field wajib kelas simulasi tidak ada).
    _q = _sim_quote()
    del _q["amount_out_estimate"]
    _q["amount_out_min"] = 10500.54
    v = pipeline.validate_exit_quote(_q, _snap, eval_at=_eval,
                                     median_price_usd=_med)
    checks.append(("g5_simulation_with_amount_out_min_rejected",
                   v["status"] == "invalid"))
    # Label "simulation" kabur tetap ditolak (bukan onchain_simulation).
    _q = _sim_quote(kind="simulation")
    v = pipeline.validate_exit_quote(_q, _snap, eval_at=_eval,
                                     median_price_usd=_med)
    checks.append(("g5_bare_simulation_label_rejected",
                   v["status"] == "invalid"
                   and v["reason_codes"] == ["exit_quote_simulation_only"]))
    # Firm path tetap jalan (kompatibilitas): kind firm + amount_out_min +
    # quoted_at + expires_at -> verified.
    _fq = {"chain": "base", "token_in": _TOK, "token_out": _USDC,
           "side": "SELL", "amount_in": 79.006772009,
           "amount_out_min": 10500.54, "quoted_at": _snap["fetched_at"],
           "expires_at": pipeline._iso(_eval + __import__("datetime").timedelta(seconds=300)),
           "source": "aero-metaquoter-v3", "venue": "aerodrome",
           "kind": "firm", "notional_usd": 10500.54, "pool": _POOL}
    v = pipeline.validate_exit_quote(_fq, _snap, eval_at=_eval,
                                     median_price_usd=_med)
    checks.append(("g5_firm_path_still_verified", v["status"] == "verified"))
    # decide(): simulasi yang tervalidasi TIDAK mengaktifkan proposal
    # meski gate ON.
    _s2 = copy.deepcopy(_snap)
    _s2["exit_quote"] = _sim_quote()
    _s2 = pipeline.assess_snapshot(_s2, eval_at=_eval)
    checks.append(("g5_layer_b_status_is_simulated",
                   _s2["assessment"]["layer_b"]["status"]
                   == "simulated_exit_quote_verified"))
    _old_gate = config.PAPER_PROPOSALS_ENABLED
    try:
        config.PAPER_PROPOSALS_ENABLED = True
        _s3 = copy.deepcopy(_s2)
        _s3["assessment"]["reason_codes"] = [
            c for c in _s3["assessment"]["reason_codes"]
            if c not in pipeline.PROPOSAL_BLOCKING_CODES]
        _s3 = pipeline.decide(_s3)
        checks.append(("g5_simulated_never_proposes_even_gate_on",
                       _s3["decision"] == "WATCH"
                       and "exit_evidence_simulated_not_firm"
                       in _s3["decision_reasons"]))
    finally:
        config.PAPER_PROPOSALS_ENABLED = _old_gate

    # ---- G6: registry unknown/stale/mismatch ----
    checks.append(("g6_codes_are_proposal_blocking",
                   {"oracle_registry_unknown", "oracle_registry_stale",
                    "oracle_multiplier_mismatch"}
                   <= pipeline.PROPOSAL_BLOCKING_CODES))
    # Registry unknown -> kode muncul.
    _s4 = copy.deepcopy(_snap)
    _s4["reference"]["registry_pause_status"] = "unknown"
    _s4["oracle"] = None
    _s4 = pipeline.assess_snapshot(_s4, eval_at=_eval)
    checks.append(("g6_registry_unknown_blocks",
                   "oracle_registry_unknown"
                   in _s4["assessment"]["reason_codes"]))
    # Registry stale (fetched_at 1 jam lalu) -> kode muncul.
    _s5 = copy.deepcopy(_snap)
    _s5["reference"]["registry_pause_status"] = "active"
    _s5["oracle"] = {"multiplier": 1.000538, "paused": False,
                     "source": config.ORACLE_REGISTRY,
                     "fetched_at": pipeline._iso(
                         _eval - __import__("datetime").timedelta(hours=1))}
    _s5 = pipeline.assess_snapshot(_s5, eval_at=_eval)
    checks.append(("g6_registry_stale_blocks",
                   "oracle_registry_stale"
                   in _s5["assessment"]["reason_codes"]))
    # Multiplier mismatch (registry 1.05 vs Coinbase 1.0005) -> kode muncul.
    _s6 = copy.deepcopy(_snap)
    _s6["reference"]["registry_pause_status"] = "active"
    _s6["oracle"] = {"multiplier": 1.05, "paused": False,
                     "source": config.ORACLE_REGISTRY,
                     "fetched_at": _snap["fetched_at"]}
    _s6 = pipeline.assess_snapshot(_s6, eval_at=_eval)
    checks.append(("g6_multiplier_mismatch_blocks",
                   "oracle_multiplier_mismatch"
                   in _s6["assessment"]["reason_codes"]))
    # Repro G6 (audit): snapshot bersih + quote firm valid + registry
    # unknown -> dengan gate ON pun TIDAK PERNAH PAPER_PROPOSAL.
    _s7 = copy.deepcopy(_snap)
    _s7["exit_quote"] = _fq
    _s7["reference"]["registry_pause_status"] = "unknown"
    _s7["oracle"] = None
    _s7 = pipeline.assess_snapshot(_s7, eval_at=_eval)
    _old_gate = config.PAPER_PROPOSALS_ENABLED
    try:
        config.PAPER_PROPOSALS_ENABLED = True
        _s7 = pipeline.decide(_s7)
        checks.append(("g6_unknown_registry_never_proposes_gate_on",
                       _s7["decision"] != "PAPER_PROPOSAL"
                       and "oracle_registry_unknown"
                       in _s7["decision_reasons"]))
    finally:
        config.PAPER_PROPOSALS_ENABLED = _old_gate

    failed = [c for c, ok in checks if not ok]
    return _result(
        "quoter_g1_g6",
        "regression G1-G6 re-audit v5: venue terpisah, guard quote, "
        "partial-fill, decoder fail-closed, label jujur, registry blocking",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "v0.3.1; gate stays off, decision stays WATCH")


def test_quoter_f1_f2_m1_m3():
    """Regresi follow-up F1+F2+F3 re-audit v6 + minor M1-M3 re-audit v7
    Instinct (22-23 Nov 2026).

    F1 (dari G3): deteksi partial-fill yang benar.
      - MAX_SQRT_RATIO = nilai EXACT TickMath (v0.3.1 salah 1e9x).
      - Double-quote probe: probe 2x amount_in; rasio < 1,5 = capped
        (partial fill) -> quote ditolak; rasio ~1,9 = sehat -> diterima.
      - Guard batas hanya exact-bound (min+1/max-1 lolos — keterbatasan
        terdokumentasi, bukan bukti sehat).
    F2 (dari G5): validator cap max_age milik quote ke QUOTE_VALIDITY_SEC.
      - Simulasi max_age raksasa + observed_at 5 jam lalu -> stale.
      - Simulasi max_age raksasa + observed_at baru -> simulated_verified
        TAPI max_age_sec di detail = 300 (dicap), klaim asli tercatat.
    F3: factory Aerodrome V2 (0x420D...) -> aerodrome.
    M1 (re-audit v7): MAX_SQRT_RATIO = KONSTANTA KONTRAK TickMath.sol
      (bukan floor rumus); nilai v0.3.2 tidak lagi dipakai.
    M2 (re-audit v7): probe WAJIB sukses — probe gagal RPC membuat quote
      TIDAK usable (pool ditolak), bukan dipakai inconclusive.
    M3 (re-audit v7): `factory` disimpan di exit_quote snapshot.
    """
    import adapter as _adapter
    checks = []
    _TOK = config.TOKENS["NVDAc"]["token_address"]
    _USDC = config.USDC_NATIVE_BASE
    _POOL = "0xF668e21993f0ACd7ab00BB1cFbAeD0df28A3C8EC"

    # ---- F1a: MAX_SQRT_RATIO (v0.3.2: floor eksak rumus; v0.3.3: M1 =
    # konstanta KONTRAK TickMath.sol) ----
    # floor(sqrt(1.0001^887272) * 2^96)
    # = floor(10001^443636 * 2^96 / 10000^443636).
    _exact_max = (pow(10001, 443636) * pow(2, 96)) // pow(10000, 443636)
    # M1: konfigurasi memakai konstanta kontrak (bukan floor rumus).
    _contract_max = 1461446703485210103287273052203988822378723970342
    checks.append(("m1_max_sqrt_ratio_is_contract_constant",
                   config.MAX_SQRT_RATIO == _contract_max))
    checks.append(("m1_formula_floor_not_used",
                   config.MAX_SQRT_RATIO != _exact_max))
    checks.append(("m1_contract_constant_larger_than_formula_floor",
                   config.MAX_SQRT_RATIO > _exact_max))
    checks.append(("f1_max_sqrt_ratio_49_digits",
                   len(str(config.MAX_SQRT_RATIO)) == 49))
    checks.append(("f1_min_sqrt_ratio_correct",
                   config.MIN_SQRT_RATIO == 4295128739))
    # Nilai v0.3.1 yang salah (1e9x terlalu kecil) tidak lagi dipakai.
    checks.append(("f1_old_wrong_max_not_used",
                   config.MAX_SQRT_RATIO
                   != 1461446703485210103287273058057407946277))

    # ---- F1b: double-quote probe ----
    _BASE_IN = 79 * 10 ** 8
    _BASE_OUT = 10500000000  # $10.500,00 (USDC 6 desimal, micro unit)

    def _mock_quote_factory(probe_out=None, probe_error=None):
        def _f(pool, tok, amt, block=None):
            if amt == _BASE_IN:
                return {"ok": True,
                        "amount_out_usd": _BASE_OUT / 1e6,
                        "sqrt_price_x96_after": 913300000000000000000000000000,
                        "ticks_crossed": 1, "pool": pool, "token_in": tok,
                        "amount_in_wei": amt,
                        "fetched_at": pipeline._iso(pipeline._now()),
                        "source": config.AERO_METAQUOTER, "error": None}
            if amt == _BASE_IN * config.PARTIAL_FILL_PROBE_MULTIPLIER:
                if probe_error is not None:
                    return {"ok": False, "amount_out_usd": None,
                            "sqrt_price_x96_after": None,
                            "ticks_crossed": None,
                            "pool": pool, "token_in": tok,
                            "amount_in_wei": amt,
                            "fetched_at": pipeline._iso(pipeline._now()),
                            "source": config.AERO_METAQUOTER,
                            "error": probe_error}
                return {"ok": True,
                        "amount_out_usd": (probe_out if probe_out is not None
                                           else int(_BASE_OUT * 1.9)) / 1e6,
                        "sqrt_price_x96_after": 913300000000000000000000000000,
                        "ticks_crossed": 2, "pool": pool, "token_in": tok,
                        "amount_in_wei": amt,
                        "fetched_at": pipeline._iso(pipeline._now()),
                        "source": config.AERO_METAQUOTER, "error": None}
            return {"ok": False, "amount_out_usd": None,
                    "sqrt_price_x96_after": None, "ticks_crossed": None,
                    "pool": pool, "token_in": tok, "amount_in_wei": amt,
                    "fetched_at": pipeline._iso(pipeline._now()),
                    "source": config.AERO_METAQUOTER,
                    "error": "mock_unexpected_amount"}
        return _f

    _orig_quote = _adapter.fetch_sell_quote
    try:
        # (i) Probe capped: probe_out = 1.02x base (rasio 1,02 < 1,5).
        _adapter.fetch_sell_quote = _mock_quote_factory(
            probe_out=int(_BASE_OUT * 1.02))
        r = pipeline._partial_fill_probe(_POOL, _TOK, _BASE_IN,
                                         _BASE_OUT / 1e6)
        checks.append(("f1_probe_capped_ratio_1_02_detected",
                       r["capped"] is True and abs(r["ratio"] - 1.02) < 0.01))
        # (ii) Probe sehat: probe_out = 1.9x base.
        _adapter.fetch_sell_quote = _mock_quote_factory(
            probe_out=int(_BASE_OUT * 1.9))
        r = pipeline._partial_fill_probe(_POOL, _TOK, _BASE_IN,
                                         _BASE_OUT / 1e6)
        checks.append(("f1_probe_healthy_ratio_1_9_accepted",
                       r["capped"] is False and abs(r["ratio"] - 1.9) < 0.01))
        # (iii) Probe gagal RPC -> probe_ok False, TIDAK capped (bukan
        # partial fill), TAPI M2 (v0.3.3): quote TIDAK usable — pool
        # ditolak, bukan dipakai inconclusive.
        _adapter.fetch_sell_quote = _mock_quote_factory(
            probe_error="rpc_error:boom")
        r = pipeline._partial_fill_probe(_POOL, _TOK, _BASE_IN,
                                         _BASE_OUT / 1e6)
        checks.append(("f1_probe_rpc_fail_not_capped_but_probe_not_ok",
                       r["capped"] is False
                       and r["probe_ok"] is False
                       and r["info"]["error"] is not None))
        checks.append(("m2_probe_rpc_fail_quote_not_usable",
                       pipeline._probe_quote_usable(r) is False))
        # M2: capped -> tidak usable; sehat -> usable; kebijakan lama
        # (REQUIRE_PROBE_SUCCESS=False) -> probe gagal tetap usable
        # (inconclusive, perilaku v0.3.2).
        checks.append(("m2_capped_quote_not_usable",
                       pipeline._probe_quote_usable(
                           {"capped": True, "probe_ok": True}) is False))
        checks.append(("m2_healthy_probe_quote_usable",
                       pipeline._probe_quote_usable(
                           {"capped": False, "probe_ok": True}) is True))
        _old_req = config.REQUIRE_PROBE_SUCCESS
        try:
            config.REQUIRE_PROBE_SUCCESS = False
            checks.append(("m2_old_policy_probe_fail_still_usable",
                           pipeline._probe_quote_usable(
                               {"capped": False, "probe_ok": False}) is True))
        finally:
            config.REQUIRE_PROBE_SUCCESS = _old_req
        checks.append(("m2_require_probe_success_enabled",
                       config.REQUIRE_PROBE_SUCCESS is True))
        # (iv) Repro auditor: partial fill nyata (output ter-cap di
        # likuiditas) — probe ratio ~1.0 -> capped.
        _adapter.fetch_sell_quote = _mock_quote_factory(
            probe_out=int(_BASE_OUT * 1.0))
        r = pipeline._partial_fill_probe(_POOL, _TOK, _BASE_IN,
                                         _BASE_OUT / 1e6)
        checks.append(("f1_probe_auditor_repro_ratio_1_0_capped",
                       r["capped"] is True))
    finally:
        _adapter.fetch_sell_quote = _orig_quote

    # ---- F2: validator cap max_age ----
    _snap = _load_fixture("snapshot_live_20261122_NVDAc.json")
    _eval = pipeline._parse_ts(_snap.get("fetched_at"))
    _med = _snap["assessment"]["layer_a"]["median_price_usd"]

    def _sim_quote(**over):
        q = {"chain": "base", "token_in": _TOK, "token_out": _USDC,
             "side": "SELL", "amount_in": 79.006772009,
             "amount_out_estimate": 10500.54,
             "observed_at": _snap["fetched_at"],
             "max_age_sec": 300, "block_number": 60841377,
             "block_hash": "0x" + "ab" * 32,
             "source": "aero-metaquoter-v3", "venue": "aerodrome",
             "kind": "onchain_simulation",
             "notional_usd": 10500.54, "pool": _POOL}
        q.update(over)
        return q

    # Repro auditor F2: max_age raksasa + observed_at 5 jam lalu -> stale
    # (di v0.3.1 lolos karena validator percaya max_age milik quote).
    _old = pipeline._iso(_eval - __import__("datetime").timedelta(hours=5))
    v = pipeline.validate_exit_quote(
        _sim_quote(observed_at=_old, max_age_sec=999999), _snap,
        eval_at=_eval, median_price_usd=_med)
    checks.append(("f2_giant_max_age_old_observation_stale",
                   v["status"] == "stale"))
    # max_age raksasa + observed_at baru -> simulated_verified TAPI
    # max_age_sec di detail DICAP ke 300, klaim asli tercatat.
    v = pipeline.validate_exit_quote(
        _sim_quote(max_age_sec=999999), _snap, eval_at=_eval,
        median_price_usd=_med)
    checks.append(("f2_giant_max_age_capped_to_300",
                   v["status"] == "simulated_verified"
                   and v["details"].get("max_age_sec") == 300
                   and v["details"].get("max_age_claimed_sec") == 999999))
    # max_age normal (300) + observed_at baru -> tetap simulated_verified.
    v = pipeline.validate_exit_quote(_sim_quote(), _snap, eval_at=_eval,
                                     median_price_usd=_med)
    checks.append(("f2_normal_max_age_still_verified",
                   v["status"] == "simulated_verified"
                   and v["details"].get("max_age_sec") == 300))

    # ---- F3: Aerodrome V2 factory -> aerodrome ----
    _vi = pipeline._venue_info_for_pool(
        "aerodrome", config.AERODROME_V2_FACTORY)
    checks.append(("f3_aerodrome_v2_factory_is_aerodrome_verified",
                   _vi["protocol_family"] == "aerodrome"
                   and _vi["venue_verified"] is True))
    checks.append(("f3_aerodrome_v2_in_factory_venue",
                   config.FACTORY_VENUE.get(
                       config.AERODROME_V2_FACTORY.lower()) == "aerodrome"))

    # ---- M3: factory disimpan di exit_quote snapshot ----
    _now = pipeline._iso(pipeline._now())
    _ing = {
        "meta": {"fetched_at": _now, "errors": {}, "sources": {}},
        "coinbase_record": {"contract_address": _TOK, "symbol": "NVDAc",
                            "nav_price": 132.97,
                            "nav_price_updated_at": _now,
                            "multiplier": 1.000538},
        "dexscreener_pairs": [],
        "geckoterminal_pool": None,
        "geckoterminal_pool_address": None,
        "hyperliquid": {},
        "oracle_params": {"ok": False},
        "pool_factories": {},
        "sell_quote": {"ok": True, "amount_out_usd": 10500.54,
                       "amount_in": 79.0, "amount_in_wei": 79 * 10 ** 8,
                       "top_price_usd": 132.97, "top_pool": _POOL,
                       "token_out": _USDC, "venue": "aerodrome",
                       "factory": config.AERO_SLIPSTREAM_CL_FACTORY,
                       "token0": _USDC, "token1": _TOK,
                       "block_number": 60857668,
                       "block_hash": "0x" + "ab" * 32,
                       "sqrt_price_x96_after": 913300000000000000000000000000,
                       "ticks_crossed": 1,
                       "partial_fill_probe": {"ratio": 1.99,
                                              "capped": False,
                                              "probe_ok": True},
                       "fetched_at": _now,
                       "source": "aero-metaquoter-v3"},
    }
    _snap_m3 = pipeline.build_snapshot("NVDAc", ingested=_ing)
    checks.append(("m3_exit_quote_factory_saved",
                   _snap_m3["exit_quote"] is not None
                   and _snap_m3["exit_quote"].get("factory")
                   == config.AERO_SLIPSTREAM_CL_FACTORY))
    checks.append(("m3_exit_quote_venue_still_saved",
                   _snap_m3["exit_quote"] is not None
                   and _snap_m3["exit_quote"].get("venue") == "aerodrome"))

    failed = [c for c, ok in checks if not ok]
    return _result(
        "quoter_f1_f2_m1_m3",
        "follow-up F1+F2+F3 re-audit v6 + minor M1-M3 re-audit v7: "
        "MAX kontrak TickMath, double-quote probe, validator cap max_age, "
        "factory Aero V2, probe wajib sukses, factory di exit_quote",
        "%d/%d checks pass; failed: %s" % (len(checks) - len(failed),
                                           len(checks), failed or "none"),
        not failed,
        "v0.3.3; gate stays off, decision stays WATCH")


# ------------------------------------------------------- tes S1-G (Scope 1)
# S1-G (rencana eksekusi Scope 1 v1.1 §5, kill-switch kriteria 5):
# tes integritas gate — dikerjakan SEBELUM merge pertama, gerbang untuk
# semua merge berikutnya. Dua penahan diuji TERPISAH (aturan 3 decide():
# gate OFF; aturan 4: bukti simulasi bukan firm), guard hash/AST untuk
# decide(), nilai PAPER_PROPOSALS_ENABLED dibaca dari config, dan quote
# simulasi (apa pun isinya) TIDAK PERNAH -> PAPER_PROPOSAL.
#
# Rekaman decide() saat ini (pipeline.py, HEAD 4a47a4c, 24 Nov 2026):
# dihitung dari inspect.getsource(pipeline.decide) — sha256 teks sumber
# + sha256 ast.dump(ast.parse(sumber)). Bila source decide() berubah
# (edit, rename, monkeypatch saat import), tes guard GAGAL.
_DECIDE_SOURCE_SHA256 = (
    "9fbaae011f040bbc317acf7b51f4a8c08bd3340a12c597a8fa25b57eff2d12c4")
_DECIDE_AST_SHA256 = (
    "2d8b5447749c438870d4b47fcd76f4ef38c77701686de8a13e32d1d75a3afc5f")


def _decide_guard():
    """Bandingkan source + AST live pipeline.decide() dengan rekaman S1-G.
    Return (ok, detail). Dipakai tes gate dan scripts/guard_decide.py."""
    import ast as _ast
    import inspect as _inspect
    try:
        src = _inspect.getsource(pipeline.decide)
    except (OSError, TypeError) as e:
        return False, "decide() source unreadable: %s: %s" % (
            type(e).__name__, e)
    src_hash = hashlib.sha256(src.encode("utf-8")).hexdigest()
    try:
        ast_hash = hashlib.sha256(
            _ast.dump(_ast.parse(src)).encode("utf-8")).hexdigest()
    except SyntaxError as e:
        return False, "decide() source unparseable: %s" % e
    ok = (src_hash == _DECIDE_SOURCE_SHA256
          and ast_hash == _DECIDE_AST_SHA256
          and pipeline.decide.__module__ == "pipeline")
    return ok, ("source_sha256=%s (recorded %s); ast_sha256=%s (recorded %s); "
                "module=%s; lines=%d"
                % (src_hash, _DECIDE_SOURCE_SHA256, ast_hash,
                   _DECIDE_AST_SHA256, pipeline.decide.__module__,
                   len(src.splitlines())))


def _sim_quote_for_gate(eval_at, **over):
    """Quote simulasi on-chain yang VALID sebagai simulated_verified
    (kind=onchain_simulation, amount_out_estimate, block_number ada).
    Varian apa pun dari quote ini tetap simulasi — bukan komitmen eksekusi.
    token_out memakai literal _REAL_USDC_NATIVE (bukan konstanta config)."""
    q = {"chain": config.CHAIN,
         "token_in": config.TOKENS["NVDAc"]["token_address"],
         "token_out": _REAL_USDC_NATIVE,
         "side": "SELL",
         "amount_in": 79.006772009,
         "amount_out_estimate": 10500.54,
         "observed_at": pipeline._iso(eval_at),
         "max_age_sec": 300,
         "block_number": 60841377,
         "block_hash": "0x" + "ab" * 32,
         "source": "aero-metaquoter-v3",
         "venue": "aerodrome",
         "kind": "onchain_simulation",
         "notional_usd": 10500.54,
         "pool": "0xF668e21993f0ACd7ab00BB1cFbAeD0df28A3C8EC"}
    q.update(over)
    return q


def test_s1g_gate_off_blocks_all_quotes():
    """S1-G (a): penahan 1 — gate OFF menahan SEMUA quote. Quote firm yang
    valid sekalipun + quote simulasi yang lolos validator TIDAK menghasilkan
    PAPER_PROPOSAL; penahannya adalah aturan 3 decide()
    (paper_proposals_disabled), bukan aturan lain. Snapshot_id dihitung
    ulang sesudah memasang quote agar snapshot tidak ditandai transformed
    (aturan 2) — isolasi aturan 3 yang diuji."""
    base = _fresh_nav_fixture("NVDAc")
    eval_at = pipeline._parse_ts(base["fetched_at"])
    if config.PAPER_PROPOSALS_ENABLED is not False:
        return _result("s1g_gate_off_blocks_all_quotes",
                       "gate OFF by default",
                       "config.PAPER_PROPOSALS_ENABLED=%r (not False)"
                       % config.PAPER_PROPOSALS_ENABLED,
                       False, "precondition failed: gate already on")
    cases = [
        ("firm_valid", _valid_quote("NVDAc", eval_at)),
        ("sim_valid", _sim_quote_for_gate(eval_at)),
        ("sim_usdc_e", _sim_quote_for_gate(eval_at,
                                           token_out=_REAL_USDC_E)),
        ("sim_huge_notional", _sim_quote_for_gate(
            eval_at, amount_in=7900.6772009, notional_usd=1000000.0,
            amount_out_estimate=1050054.0)),
        ("indicative", dict(_valid_quote("NVDAc", eval_at),
                            kind="indicative")),
        ("quote_null", None),
        ("quote_empty", {}),
    ]
    failed = []
    for name, quote in cases:
        snap = copy.deepcopy(base)
        snap["exit_quote"] = quote
        _recompute_snapshot_id(snap)
        snap = _reassess(snap, eval_at=eval_at)
        clean = name in ("firm_valid", "sim_valid", "sim_usdc_e",
                         "sim_huge_notional")
        ok = (snap["decision"] != "PAPER_PROPOSAL"
              and snap["proposal"]["cash_weight"] == 1.0
              and snap["proposal"]["weights"] == {})
        if clean:
            # Kasus bersih: aturan 3 HARUS menjadi penahannya (bukan
            # aturan 2/4) — bukti gate OFF yang menahan, bukan validator.
            ok = ok and snap["decision_reasons"] == ["paper_proposals_disabled"]
        if not ok:
            failed.append("%s: decision=%s reasons=%s layer_b=%s" % (
                name, snap["decision"], snap["decision_reasons"],
                snap["assessment"]["layer_b"]["status"]))
    return _result(
        "s1g_gate_off_blocks_all_quotes",
        "gate OFF: firm valid + simulasi valid + indikatif + null/empty "
        "-> bukan PAPER_PROPOSAL; kasus bersih ditahan aturan 3 "
        "(paper_proposals_disabled)",
        "%d/%d quotes blocked; failed: %s"
        % (len(cases) - len(failed), len(cases), failed or "none"),
        not failed,
        "rule 3 decide(): gate OFF holds every quote")


def test_s1g_gate_on_isolated_blocks_simulation():
    """S1-G (b): penahan 2 — gate ON DALAM TES TERISOLASI tetap menahan
    simulasi. Gate dinyalakan sementara (try/finally, dipulihkan ke False)
    HANYA di dalam tes ini. Simulasi yang lolos validator
    (simulated_verified) -> WATCH exit_evidence_simulated_not_firm
    (aturan 4). Kontrol: quote firm valid + gate ON -> PAPER_PROPOSAL —
    membuktikan gate ON benar-benar membuka jalur aturan 5, jadi yang
    menahan simulasi adalah aturan 4, bukan gate atau validator."""
    base = _fresh_nav_fixture("NVDAc")
    eval_at = pipeline._parse_ts(base["fetched_at"])
    sim_cases = [
        ("sim_valid", _sim_quote_for_gate(eval_at)),
        ("sim_usdc_e", _sim_quote_for_gate(eval_at,
                                           token_out=_REAL_USDC_E)),
        ("sim_other_venue", _sim_quote_for_gate(eval_at, venue="uniswap")),
        ("sim_other_source", _sim_quote_for_gate(
            eval_at, source="other-quoter")),
        ("sim_huge_notional", _sim_quote_for_gate(
            eval_at, amount_in=7900.6772009, notional_usd=1000000.0,
            amount_out_estimate=1050054.0)),
    ]
    failed = []
    old_gate = config.PAPER_PROPOSALS_ENABLED
    try:
        config.PAPER_PROPOSALS_ENABLED = True
        for name, quote in sim_cases:
            snap = copy.deepcopy(base)
            snap["exit_quote"] = quote
            _recompute_snapshot_id(snap)
            snap = _reassess(snap, eval_at=eval_at)
            ok = (snap["decision"] == "WATCH"
                  and snap["decision_reasons"]
                  == ["exit_evidence_simulated_not_firm"]
                  and snap["assessment"]["layer_b"]["status"]
                  == "simulated_exit_quote_verified"
                  and snap["proposal"]["cash_weight"] == 1.0)
            if not ok:
                failed.append("%s: decision=%s reasons=%s layer_b=%s" % (
                    name, snap["decision"], snap["decision_reasons"],
                    snap["assessment"]["layer_b"]["status"]))
        # Kontrol: firm valid + gate ON HARUS PAPER_PROPOSAL (jalur
        # aturan 5 terbuka — isolasi membuktikan aturan 4 yang menahan
        # simulasi, bukan gate yang masih mati).
        snap = copy.deepcopy(base)
        snap["exit_quote"] = _valid_quote("NVDAc", eval_at)
        _recompute_snapshot_id(snap)
        snap = _reassess(snap, eval_at=eval_at)
        if snap["decision"] != "PAPER_PROPOSAL":
            failed.append("control_firm_gate_on: decision=%s reasons=%s "
                          "layer_b=%s (expected PAPER_PROPOSAL)"
                          % (snap["decision"], snap["decision_reasons"],
                             snap["assessment"]["layer_b"]["status"]))
    finally:
        config.PAPER_PROPOSALS_ENABLED = old_gate
    if config.PAPER_PROPOSALS_ENABLED is not False:
        failed.append("gate_not_restored: PAPER_PROPOSALS_ENABLED=%r"
                      % config.PAPER_PROPOSALS_ENABLED)
    return _result(
        "s1g_gate_on_isolated_blocks_simulation",
        "gate ON (isolated): simulasi valid -> WATCH "
        "exit_evidence_simulated_not_firm; kontrol firm valid -> "
        "PAPER_PROPOSAL; gate dipulihkan ke False",
        "%d/%d sim cases blocked by rule 4 + control firm PAPER_PROPOSAL; "
        "failed: %s" % (len(sim_cases) + 1 - len(failed),
                        len(sim_cases) + 1, failed or "none"),
        not failed,
        "rule 4 decide(): simulated evidence never activates a proposal")


def test_s1g_paper_proposals_enabled_false():
    """S1-G: PAPER_PROPOSALS_ENABLED tetap False — dibaca dari nilai config
    yang hidup DAN dari teks sumber config.py (AST), bukan asumsi. Tes
    gagal bila nilainya True, bila bukan literal False di sumber, atau
    bila ada lebih dari satu assignment di config.py."""
    import ast as _ast
    checks = []
    # (a) Nilai live di modul config yang diimpor gate.
    checks.append(("live_value_is_False",
                   config.PAPER_PROPOSALS_ENABLED is False))
    # (b) Teks sumber config.py: tepat satu assignment, literal False.
    with open(os.path.join(BASE, "config.py"), "r", encoding="utf-8") as f:
        tree = _ast.parse(f.read())
    assigns = []
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Assign):
            for t in node.targets:
                if isinstance(t, _ast.Name) \
                        and t.id == "PAPER_PROPOSALS_ENABLED":
                    assigns.append(node.value)
    checks.append(("source_single_assignment", len(assigns) == 1))
    checks.append(("source_literal_False",
                   len(assigns) == 1
                   and isinstance(assigns[0], _ast.Constant)
                   and assigns[0].value is False))
    # (c) Nilai yang dipakai decide() adalah nilai config yang sama
    # (bukan salinan lokal): baca ulang atribut modul.
    checks.append(("decide_reads_same_config_value",
                   getattr(config, "PAPER_PROPOSALS_ENABLED") is False))
    failed = [c for c, ok in checks if not ok]
    return _result(
        "s1g_paper_proposals_enabled_false",
        "PAPER_PROPOSALS_ENABLED is False (live value + single literal "
        "False assignment in config.py source)",
        "%d/%d checks pass; live=%r assignments=%d; failed: %s"
        % (len(checks) - len(failed), len(checks),
           config.PAPER_PROPOSALS_ENABLED, len(assigns),
           failed or "none"),
        not failed,
        "config.py:269 PAPER_PROPOSALS_ENABLED = False")


def test_s1g_simulation_never_paper_proposal():
    """S1-G: quote simulasi (APA PUN isinya) -> keputusan TIDAK PERNAH
    PAPER_PROPOSAL — diuji pada KEDUA keadaan gate (OFF default dan ON
    terisolasi). Matriks mencakup simulasi valid, simulasi yang memakai
    field kelas firm (amount_out_min), label kind kabur, tanpa block,
    max_age raksasa, observasi basi, dan estimate ngawur. Setiap varian:
    decision != PAPER_PROPOSAL dan cash_weight == 1.0."""
    base = _fresh_nav_fixture("NVDAc")
    eval_at = pipeline._parse_ts(base["fetched_at"])
    old_obs = pipeline._iso(eval_at - timedelta(hours=5))
    variants = [
        ("sim_valid", _sim_quote_for_gate(eval_at)),
        ("sim_usdc_e", _sim_quote_for_gate(eval_at,
                                           token_out=_REAL_USDC_E)),
        ("sim_with_amount_out_min", dict(
            _sim_quote_for_gate(eval_at), amount_out_min=10500.54)),
        ("sim_kind_simulation_label", _sim_quote_for_gate(
            eval_at, kind="simulation")),
        ("sim_no_block", dict(_sim_quote_for_gate(eval_at),
                              block_number=None)),
        ("sim_giant_max_age", _sim_quote_for_gate(
            eval_at, max_age_sec=999999)),
        ("sim_stale_observation", _sim_quote_for_gate(
            eval_at, observed_at=old_obs)),
        ("sim_tiny_estimate", _sim_quote_for_gate(
            eval_at, amount_out_estimate=1.0, notional_usd=1.0)),
        ("sim_zero_estimate", _sim_quote_for_gate(
            eval_at, amount_out_estimate=0.0, notional_usd=0.0)),
    ]
    # Hapus kunci block_number (bukan None) untuk varian tanpa block.
    del variants[4][1]["block_number"]
    failed = []
    for gate_state in (False, True):
        old_gate = config.PAPER_PROPOSALS_ENABLED
        try:
            config.PAPER_PROPOSALS_ENABLED = gate_state
            for name, quote in variants:
                snap = copy.deepcopy(base)
                snap["exit_quote"] = quote
                _recompute_snapshot_id(snap)
                snap = _reassess(snap, eval_at=eval_at)
                ok = (snap["decision"] != "PAPER_PROPOSAL"
                      and snap["proposal"]["cash_weight"] == 1.0
                      and snap["proposal"]["weights"] == {})
                if not ok:
                    failed.append("gate_%s/%s: decision=%s reasons=%s" % (
                        "on" if gate_state else "off", name,
                        snap["decision"], snap["decision_reasons"]))
        finally:
            config.PAPER_PROPOSALS_ENABLED = old_gate
    if config.PAPER_PROPOSALS_ENABLED is not False:
        failed.append("gate_not_restored_after_matrix")
    return _result(
        "s1g_simulation_never_paper_proposal",
        "every simulation variant (any content) -> never PAPER_PROPOSAL, "
        "cash_weight 1.0, under gate OFF and gate ON (isolated)",
        "%d/%d variant x gate-state runs never PAPER_PROPOSAL; failed: %s"
        % (len(variants) * 2 - len(failed), len(variants) * 2,
           failed or "none"),
        not failed,
        "9 simulation variants x 2 gate states = 18 runs")


def test_s1g_decide_source_guard():
    """S1-G: guard hash/AST decide() — GAGAL bila source decide() berubah
    dari rekaman (edit, rename, monkeypatch). Hash direkam 24 Nov 2026
    dari pipeline.py HEAD 4a47a4c; perbandingan dihitung tiap run gate."""
    ok, detail = _decide_guard()
    return _result(
        "s1g_decide_source_guard",
        "decide() source + AST hashes match the S1-G recording "
        "(no change since 24 Nov 2026)",
        detail,
        ok,
        "guard: source_sha256 + ast_sha256 of inspect.getsource(decide)")


# -------------------------------------------------------------------- main
TESTS = [
    ("happy_path", test_happy_path),
    ("controlled_trigger", test_controlled_trigger),
    ("nav_weekend", test_nav_weekend),
    ("multiplier", test_multiplier),
    ("missing_stale", test_missing_stale),
    ("coverage", test_coverage),
    ("proxy", test_proxy),
    ("liquidity_vs_exit", test_liquidity_vs_exit),
    ("idempotency", test_idempotency),
    # Regression pasca-audit Instinct 22 Nov 2026 (must-fix A-D + §3).
    ("quote_validation", test_quote_validation),
    ("freshness", test_freshness),
    ("coverage_recomputed", test_coverage_recomputed),
    ("snapshot_identity_live_build", test_snapshot_identity_live_build),
    ("dedup_persistence", test_dedup_persistence),
    ("happy_path_both_tokens", test_happy_path_both_tokens),
    ("nav_multiplier_build", test_nav_multiplier_build),
    # Fase quoter v0.3.0 (ACC Septian 22 Nov 2026).
    ("quoter_adapter", test_quoter_adapter),
    # Must-fix G1-G6 re-audit v5 (v0.3.1).
    ("quoter_g1_g6", test_quoter_g1_g6),
    # Follow-up F1+F2+F3 re-audit v6 + minor M1-M3 re-audit v7 (v0.3.3).
    ("quoter_f1_f2_m1_m3", test_quoter_f1_f2_m1_m3),
    # S1-G tes integritas gate (rencana Scope 1 v1.1 §5, 25 Nov 2026).
    ("s1g_gate_off_blocks_all_quotes", test_s1g_gate_off_blocks_all_quotes),
    ("s1g_gate_on_isolated_blocks_simulation",
     test_s1g_gate_on_isolated_blocks_simulation),
    ("s1g_paper_proposals_enabled_false",
     test_s1g_paper_proposals_enabled_false),
    ("s1g_simulation_never_paper_proposal",
     test_s1g_simulation_never_paper_proposal),
    ("s1g_decide_source_guard", test_s1g_decide_source_guard),
]


def _source_identity():
    """Identitas source yang diaudit: sha256 tiap file Python + versi."""
    files = ["pipeline.py", "config.py", "adapter.py", "run.py", "gate.py",
             "capture_evidence.py"]
    out = {}
    for name in files:
        p = os.path.join(BASE, name)
        if os.path.exists(p):
            with open(p, "rb") as f:
                out[name] = hashlib.sha256(f.read()).hexdigest()
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    run_at = pipeline._iso(pipeline._now())
    results = []
    for name, fn in TESTS:
        try:
            r = fn()
        except Exception as e:  # noqa: BLE001 - satu tes gagal != crash harness
            r = _result(name, "see test docstring",
                        "EXCEPTION %s: %s" % (type(e).__name__, e), False,
                        "test raised; harness continued")
        results.append(r)
        mark = "PASS" if r["pass"] else "FAIL"
        print("[%s] %s: %s" % (mark, r["test"], r["actual"]))
    n_pass = sum(1 for r in results if r["pass"])
    summary = {"gate": "base-prototype §7 + audit regression A-D",
               "run_at": run_at,
               "policy_version": config.POLICY_VERSION,
               "methodology_version": config.METHODOLOGY_VERSION,
               "schema_version": config.SCHEMA_VERSION,
               "source_identity": _source_identity(),
               "test_config": {
                   "min_independent_pools": config.MIN_INDEPENDENT_POOLS,
                   "min_independent_venues": config.MIN_INDEPENDENT_VENUES,
                   "nav_stale_hours": config.NAV_STALE_HOURS,
                   "max_pool_age_min": config.MAX_POOL_AGE_MIN,
                   "quote_max_age_sec": config.QUOTE_MAX_AGE_SEC,
                   "max_future_skew_sec": config.MAX_FUTURE_SKEW_SEC,
                   "dev_watch_pct": config.DEV_WATCH_PCT,
                   "dev_abstain_pct": config.DEV_ABSTAIN_PCT,
                   "paper_proposals_enabled": config.PAPER_PROPOSALS_ENABLED,
                   "simulation_notional_usd": config.SIMULATION_NOTIONAL_USD,
                   "max_weight_per_asset": config.MAX_WEIGHT_PER_ASSET,
               },
               "total": len(results), "passed": n_pass,
               "failed": len(results) - n_pass,
               "results": results}
    with open(os.path.join(OUT, "gate_results.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    lines = ["# Gate §7 — hasil test (Base prototype)",
             "",
             "Policy: %s | Method: %s | Schema: %s" % (
                 config.POLICY_VERSION, config.METHODOLOGY_VERSION,
                 config.SCHEMA_VERSION),
             "",
             "Hasil: **%d/%d PASS**." % (n_pass, len(results)),
             "",
             "| Tes | Hasil | Expected | Actual |",
             "|-----|-------|----------|--------|"]
    for r in results:
        lines.append("| %s | %s | %s | %s |" % (
            r["test"], "PASS" if r["pass"] else "FAIL",
            r["expected"], r["actual"]))
    lines.append("")
    lines.append("Detail per tes (termasuk fixture yang dimodifikasi) ada di "
                "`gate_results.json` dan `fixtures/`. Replay memakai mode "
                "TEST/REPLAY; alert sintetis bukan kejadian pasar live.")
    with open(os.path.join(OUT, "gate_log.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("Gate: %d/%d PASS. Hasil di out/gate_results.json + out/gate_log.md."
          % (n_pass, len(results)))
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
