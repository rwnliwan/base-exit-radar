"""Pipeline prototipe Base (ingest -> validate -> assess -> decide -> explain
-> alert -> paper record). Lokal/offline. Tidak mengubah Radar produksi.

Mengikuti brief Instinct §4 (alur), §5 (kontrak data), §6 (redesign Exit
Score, bukan port). Tidak mewarisi bobot / min-3-dari-5 / threshold 70 /
cutoffs Solana. Tidak menampilkan score 0-100 seolah sudah dikalibrasi.

KOREKSI YANG MENGIKAT (§3) — diterapkan di seluruh pipeline:
1. nav_price SUDAH multiplier-adjusted. JANGAN dikali multiplier lagi.
   (Rumus token = equity x multiplier hanya untuk harga saham MENTAH.)
2. Gap DEX-vs-NAV beku = deskripsi berlabel saja. Bukan diskon/mispricing/
   arbitrase/tidak-bisa-dieksploitasi/pasti-false-positive.
3. TVL/reserve/likuiditas BUKAN executable depth. Hanya filter kelayakan.
4. Redemption: desain mengasumsikan TIDAK ADA jalur permissionless retail.
5. PoR: tidak ada sumber otomatis. Hanya catatan manual atau `unknown`.
6. Dua agregator baca pool sama = SATU pool (dedup by pool_address).
7. Proxy underlying (xyz:NVDA/xyz:AAPL) = UNDERLYING EQUITY PERP PROXY.
   Bukan ukuran exit-risk token. Tidak memicu alert token-exit.
"""

import fcntl
import hashlib
import json
import math
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import adapter
import config

# ------------------------------------------------------------------ helpers
_ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _is_address(s):
    return isinstance(s, str) and bool(_ADDR_RE.match(s))


def _to_float(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _parse_ts(s):
    """Parse ISO-8601 ke datetime (UTC). Kembalikan None bila tak valid."""
    if not isinstance(s, str):
        return None
    try:
        t = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(t)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def validate_snapshot_shape(snap):
    """Validasi bentuk snapshot (audit D). Kembalikan error TERSTRUKTUR yang
    field-nya bisa diuji — bukan sekadar exception mentah.

    Kembalikan {"ok": bool, "errors": [{"field", "reason"}]}. Dipakai entry
    point (run.py --replay) sebelum assess, dan oleh regression test D.
    assess_snapshot sendiri tetap melempar KeyError pada input tanpa kunci
    wajib (perilaku lama yang diuji gate §7 test 9).
    """
    errors = []
    if not isinstance(snap, dict):
        return {"ok": False, "errors": [
            {"field": "snapshot", "reason": "not_a_dict"}]}
    for field in ("snapshot_id", "asset", "reference", "pools", "coverage",
                  "fetched_at"):
        if field not in snap:
            errors.append({"field": field, "reason": "missing_field"})
    asset = snap.get("asset")
    if isinstance(asset, dict):
        for field in ("chain", "token_address", "symbol", "decimals"):
            if field not in asset:
                errors.append({"field": "asset." + field,
                               "reason": "missing_field"})
    elif "asset" in snap:
        errors.append({"field": "asset", "reason": "not_a_dict"})
    ref = snap.get("reference")
    if isinstance(ref, dict):
        for field in ("nav_price", "nav_price_updated_at", "age_seconds",
                      "session_status"):
            if field not in ref:
                errors.append({"field": "reference." + field,
                               "reason": "missing_field"})
    elif "reference" in snap:
        errors.append({"field": "reference", "reason": "not_a_dict"})
    if "pools" in snap and not isinstance(snap["pools"], list):
        errors.append({"field": "pools", "reason": "not_a_list"})
    if "coverage" in snap and not isinstance(snap["coverage"], dict):
        errors.append({"field": "coverage", "reason": "not_a_dict"})
    return {"ok": not errors, "errors": errors}


def _short_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _canonical_venue(dex):
    """Nama venue kanonis (audit C). Alias eksplisit dipetakan ke satu nama;
    label lain dipakai apa adanya (lowercase, strip). `aero` dan `aerodrome`
    adalah venue yang sama, bukan dua venue independen."""
    name = (dex or "").strip().lower()
    if not name:
        return ""
    return config.VENUE_ALIASES.get(name, name)


def _canonical_venue_for_pool(dex, factory):
    """Venue kanonis dari factory on-chain (bila diketahui), fallback ke label
    DexScreener. Factory Aero Slipstream CLFactory -> "aerodrome" (G1:
    Dromos Labs adalah pengembang, venue-nya Aero — BUKAN "dromos").
    Factory tak dikenal / tak terbaca -> label DexScreener apa adanya."""
    if factory:
        v = config.FACTORY_VENUE.get((factory or "").lower())
        if v:
            return v
    return _canonical_venue(dex)


def _venue_info_for_pool(dex, factory):
    """Info venue lengkap satu pool (G1): pisahkan identitas factory, label
    venue, dan independensi protokol.

    Kembalikan {"protocol_family", "venue_label_source", "factory_verified",
    "venue_verified"}:
    - protocol_family: keluarga protokol dari factory (bila terverifikasi)
      atau label DexScreener yang dikanonisasi (fallback).
    - venue_label_source: "factory" (factory terbaca + ada di mapping) atau
      "dexscreener_fallback" (factory tak terbaca / tak dikenal).
    - factory_verified: True bila factory terbaca DAN ada di FACTORY_VENUE.
    - venue_verified: sama dengan factory_verified (venue hanya terverifikasi
      bila factory-nya terverifikasi; label fallback BUKAN independensi
      terverifikasi).
    Dua factory dari protokol yang sama (mis. dua CLFactory Aero) = SATU
    family, bukan dua venue independen.
    """
    if factory:
        v = config.FACTORY_VENUE.get((factory or "").lower())
        if v:
            return {"protocol_family": v, "venue_label_source": "factory",
                    "factory_verified": True, "venue_verified": True}
    return {"protocol_family": _canonical_venue(dex),
            "venue_label_source": "dexscreener_fallback",
            "factory_verified": False, "venue_verified": False}


def _pool_venue(p):
    """Venue kanonis satu observasi pool. Pakai field `venue` bila ada
    (dihitung saat build dari factory on-chain); bila tidak (snapshot lama /
    fixture v0.2.x), fallback ke label DexScreener yang dikanonisasi."""
    v = (p.get("venue") or "").strip().lower()
    if v:
        return v
    return _canonical_venue(p.get("dex") or "")


def _market_session(eval_at):
    """Sesi pasar AS (NYSE) pada `eval_at` (audit B).

    Kembalikan "open" / "closed" / "unknown". "open" = Senin-Jumat, bukan
    libur NYSE 2026, 09:30-16:00 US/Eastern. Di luar itu "closed". Bila
    tanggal di luar kalender yang tercantum (libur belum terdaftar) maka
    "unknown" — jangan menyimpulkan tutup hanya karena feed tua.
    Kalender ini minimal dan wajib diperbarui tiap tahun; early close tidak
    dimodelkan.
    """
    if eval_at is None:
        return "unknown"
    try:
        et = eval_at.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        return "unknown"
    day = et.strftime("%Y-%m-%d")
    if et.weekday() >= 5:  # Sabtu/Minggu
        return "closed"
    if day in config.US_MARKET_HOLIDAYS_2026:
        return "closed"
    # Di luar tahun kalender: libur tidak diketahui -> unknown, bukan tutup.
    if not day.startswith("2026-"):
        return "unknown"
    minutes = et.hour * 60 + et.minute
    if 9 * 60 + 30 <= minutes < 16 * 60:
        return "open"
    return "closed"


def _build_time_payload(snap):
    """Rekonstruksi payload awal (build-time) dari snapshot untuk validasi
    identitas (audit C). Kunci build + assessment/proposal/alert=None.
    Kunci turunan (decision, explanation, ...) dikeluarkan.
    "oracle" (v0.3.0) hanya masuk hash bila ada di snapshot — snapshot lama
    (v0.2.x) tidak punya field ini; memaksa None akan mengubah hash dan
    menandai snapshot lama yang sah sebagai "transformed replay"."""
    build_keys = ("schema_version", "methodology_version", "fetched_at",
                  "asset", "reference", "multiplier", "pools", "coverage",
                  "exit_quote", "underlying_proxy", "oracle")
    payload = {k: snap.get(k) for k in build_keys}
    if "oracle" not in snap:
        payload.pop("oracle", None)
    payload["assessment"] = None
    payload["proposal"] = None
    payload["alert"] = None
    return payload


def verify_snapshot_identity(snap):
    """Validasi identitas snapshot saat replay (audit C).

    Hitung ulang snapshot_id dari payload awal dan bandingkan dengan yang
    tersimpan. Kembalikan dict {matches, stored_id, recomputed_id}.
    Snapshot yang dimodifikasi setelah build (fixture sintetis) TIDAK cocok
    — itu harus ditandai sebagai transformasi replay, bukan dibawa seolah
    payload asli tidak berubah.
    """
    stored = snap.get("snapshot_id")
    recomputed = "snap-" + _short_hash(_canonical(_build_time_payload(snap)))
    return {"matches": stored == recomputed,
            "stored_id": stored, "recomputed_id": recomputed}


def validate_exit_quote(quote, snap, eval_at=None, proposal_notional_usd=None,
                        median_price_usd=None):
    """Validator quote jual eksplisit (audit A + re-audit v2 E1 + re-audit v5 G5).

    Kembalikan {"status", "reason_codes", "details"} dengan status:
      "verified"           — quote FIRM valid, relevan nominal, belum kedaluwarsa.
      "simulated_verified" — SIMULASI on-chain (eth_call) valid: sanity sama
                             dengan firm, tetapi BUKAN komitmen eksekusi.
                             Layer B menjadi "simulated_exit_quote_verified"
                             dan TIDAK mengaktifkan proposal (G5).
      "missing"            — tidak ada quote (None).
      "invalid"            — quote ada tapi cacat (bentuk/identitas/isi salah).
      "stale"              — quote kedaluwarsa / terlalu tua.

    Kelas bukti (G5 — label jujur, bukan promosi diam-diam):
    - kind "firm"/"executable"/"guaranteed": komitmen eksekusi. Field
      output = amount_out_min; waktu = quoted_at + expires_at (expiry
      jaminan vendor). Status "verified" bila lolos.
    - kind "onchain_simulation": simulasi read-only hasil eth_call ke
      quoter (state pool saat call, tanpa signing/transaksi). Field output =
      amount_out_estimate (BUKAN amount_out_min — tidak ada minimum yang
      ditegakkan); waktu = observed_at + max_age_sec (max_age = aturan
      freshness INTERNAL, bukan expiry jaminan vendor); wajib block_number
      (replay). Status "simulated_verified" bila lolos.
    - kind "simulation"/"simulated"/"paper"/"indicative": DITOLAK — label
      kabur yang tidak membuktikan apa-apa. "onchain_simulation" diterima
      karena spesifik + terverifikasi on-chain (block + sanity), bukan
      karena labelnya mirip "simulation".

    Pemeriksaan: bentuk dict, field wajib, chain, token in/out (token_out
    HARUS alamat USDC Base allowlist), side SELL, jumlah & unit, output
    minimum/estimasi positif & finite, kind WAJIB (tanpa label TIDAK dianggap
    firm), waktu quote (stale/future), expiry/max-age, error sumber, jenis
    quote, notional (dinyatakan + dihitung dari amount_in x median +
    konsistensi keduanya), dan sanity harga (harga implisit
    amount_out/amount_in dalam toleransi median).
    `median_price_usd` = median DEX dari assess (None = tidak ada referensi
    harga -> quote tidak bisa diverifikasi sanity-nya).
    """
    if eval_at is None:
        eval_at = _parse_ts(snap.get("fetched_at")) or _now()
    if proposal_notional_usd is None:
        proposal_notional_usd = config.SIMULATION_NOTIONAL_USD
    tok = config.TOKENS.get(snap.get("asset", {}).get("symbol", ""), {})
    expected_addr = (tok.get("token_address") or "").lower()

    def _fail(status, code, detail=None):
        d = {"status": status, "reason_codes": [code], "details": detail or {}}
        return d

    if quote is None:
        return {"status": "missing", "reason_codes": ["exit_quote_missing"],
                "details": {"note": "no_exit_quote_present"}}
    if not isinstance(quote, dict):
        return _fail("invalid", "exit_quote_malformed",
                     {"type": type(quote).__name__})
    if len(quote) == 0:
        return _fail("invalid", "exit_quote_empty",
                     {"note": "empty_object_is_not_evidence"})
    if quote.get("error") is not None:
        return _fail("invalid", "exit_quote_source_error",
                     {"error": str(quote.get("error"))[:200]})

    # Jenis quote: WAJIB berlabel (re-audit v2, E1). Quote tanpa field kind
    # TIDAK dianggap firm — default lama `(quote.get("kind") or "firm")`
    # membiarkan quote tanpa label lolos sebagai firm.
    kind_raw = quote.get("kind")
    if kind_raw is None or (isinstance(kind_raw, str) and not kind_raw.strip()):
        return _fail("invalid", "exit_quote_kind_missing",
                     {"note": "kind_label_required_not_assumed_firm"})
    if not isinstance(kind_raw, str):
        return _fail("invalid", "exit_quote_unknown_kind",
                     {"kind": kind_raw})
    kind = kind_raw.strip().lower()
    if kind in ("indicative", "indication"):
        return _fail("invalid", "exit_quote_indicative_only",
                     {"kind": kind})
    if kind in ("simulation", "simulated", "paper"):
        return _fail("invalid", "exit_quote_simulation_only",
                     {"kind": kind})
    # Kelas bukti menentukan field output + field waktu yang dipakai.
    if kind in ("firm", "executable", "guaranteed"):
        evidence_class = "firm"
        out_field = "amount_out_min"
        time_field = "quoted_at"
    elif kind == "onchain_simulation":
        evidence_class = "onchain_simulation"
        out_field = "amount_out_estimate"
        time_field = "observed_at"
    else:
        return _fail("invalid", "exit_quote_unknown_kind",
                     {"kind": kind})

    # Field wajib: umum + spesifik kelas bukti.
    required = ["chain", "token_in", "token_out", "side", "amount_in",
                "source", "venue", out_field, time_field]
    if evidence_class == "firm":
        required.append("expires_at")
    else:
        required.extend(["block_number", "max_age_sec"])
    missing = [f for f in required if quote.get(f) in (None, "")]
    if missing:
        return _fail("invalid", "exit_quote_missing_fields",
                     {"missing_fields": missing, "evidence_class": evidence_class})
    if (quote.get("chain") or "") != config.CHAIN:
        return _fail("invalid", "exit_quote_wrong_chain",
                     {"quote_chain": quote.get("chain"),
                      "expected_chain": config.CHAIN})
    if (quote.get("token_in") or "").lower() != expected_addr:
        return _fail("invalid", "exit_quote_wrong_token",
                     {"token_in": quote.get("token_in"),
                      "expected": expected_addr})
    # token_out: HARUS alamat USDC Base allowlist (re-audit v2, E1).
    # String "USDC"/"SCAMCOIN"/alamat lain DITOLAK — quote yang keluar ke
    # aset bukan USDC bukan bukti exit USDC. Cek lama (hanya tolak string
    # 0x... yang bukan alamat) membiarkan "SCAMCOIN" lolos sebagai verified.
    token_out = quote.get("token_out") or ""
    if not isinstance(token_out, str) or not token_out.strip():
        return _fail("invalid", "exit_quote_wrong_token",
                     {"token_out": token_out})
    if token_out.lower() not in {a.lower() for a in config.USDC_BASE_ADDRESSES}:
        return _fail("invalid", "exit_quote_token_out_not_usdc",
                     {"token_out": token_out,
                      "allowed": "USDC_Base_allowlist"})
    if (quote.get("side") or "") != "SELL":
        return _fail("invalid", "exit_quote_wrong_side",
                     {"side": quote.get("side"), "expected": "SELL"})
    amount_in = _to_float(quote.get("amount_in"))
    if amount_in is None or amount_in <= 0:
        return _fail("invalid", "exit_quote_bad_amount",
                     {"amount_in": quote.get("amount_in")})
    amount_out = _to_float(quote.get(out_field))
    if amount_out is None or amount_out <= 0:
        return _fail("invalid", "exit_quote_bad_output",
                     {out_field: quote.get(out_field)})
    # Waktu quote: harus bisa diparse, tidak future, tidak stale.
    # Firm: expiry = jaminan vendor (expires_at harus > eval_at).
    # Simulasi: max_age = aturan freshness internal (observed_at + max_age_sec
    # harus > eval_at); TIDAK ada expiry jaminan vendor (G5).
    quoted_at = _parse_ts(quote.get(time_field))
    if quoted_at is None:
        return _fail("invalid", "exit_quote_bad_timestamp",
                     {time_field: quote.get(time_field)})
    if (quoted_at - eval_at).total_seconds() > config.MAX_FUTURE_SKEW_SEC:
        return _fail("invalid", "exit_quote_future_timestamp",
                     {time_field: quote.get(time_field)})
    if evidence_class == "firm":
        if (eval_at - quoted_at).total_seconds() > config.QUOTE_MAX_AGE_SEC:
            return _fail("stale", "exit_quote_stale",
                         {"quoted_at": quote.get("quoted_at"),
                          "age_seconds": (eval_at - quoted_at).total_seconds()})
        expires_at = _parse_ts(quote.get("expires_at"))
        if expires_at is None:
            return _fail("invalid", "exit_quote_bad_timestamp",
                         {"expires_at": quote.get("expires_at")})
        if expires_at <= eval_at:
            return _fail("stale", "exit_quote_expired",
                         {"expires_at": quote.get("expires_at")})
    else:
        # F2 (re-audit v6): validator TIDAK PERCAYA max_age milik quote.
        # Untuk firm, expires_at adalah komitmen vendor; untuk simulasi,
        # max_age adalah klaim diri sendiri — simulasi dengan max_age_sec
        # raksasa + observed_at 5 jam lalu LOLOS freshness di v0.3.1.
        # Cap ke aturan internal: max_age_efektif =
        # min(quote.max_age_sec, config.QUOTE_VALIDITY_SEC). Yang dipakai
        # untuk freshness HANYA max_age_efektif; nilai klaim dicatat di
        # detail agar transparan bila dicap.
        max_age_claimed = _to_float(quote.get("max_age_sec"))
        if max_age_claimed is None or max_age_claimed <= 0:
            return _fail("invalid", "exit_quote_bad_timestamp",
                         {"max_age_sec": quote.get("max_age_sec")})
        max_age = min(max_age_claimed, config.QUOTE_VALIDITY_SEC)
        if (eval_at - quoted_at).total_seconds() > max_age:
            return _fail("stale", "exit_quote_stale",
                         {time_field: quote.get(time_field),
                          "age_seconds": (eval_at - quoted_at).total_seconds(),
                          "max_age_sec": max_age,
                          "max_age_claimed_sec": max_age_claimed,
                          "max_age_capped_to_sec": config.QUOTE_VALIDITY_SEC,
                          "note": "simulation_older_than_internal_max_age"})
        block_number = quote.get("block_number")
        if not isinstance(block_number, int) or block_number <= 0:
            return _fail("invalid", "exit_quote_missing_fields",
                         {"missing_fields": ["block_number"],
                          "note": "simulation_requires_observation_block"})
    # Notional + sanity harga (re-audit v2, E1). notional_usd yang dinyatakan
    # quote TIDAK dipercaya begitu saja — quote lama lolos dengan
    # amount_out_min=1.0 + notional_usd=1e12 (klaim nominal raksasa untuk
    # output receh). Tiga lapis:
    #  (1) notional yang DINYATAKAN harus ada & >= nominal proposal;
    #  (2) notional yang DIHITUNG (amount_in x median DEX) harus >= nominal
    #      proposal — jumlah quote harus benar-benar mencakup proposal;
    #  (3) harga implisit (amount_out / amount_in) harus dalam toleransi
    #      median — quote yang menjamin harga jauh dari pasar bukan bukti exit;
    #  (4) notional yang dinyatakan harus konsisten dengan yang dihitung
    #      (dalam rasio toleransi) — klaim nominal ngawur ditolak.
    # Tanpa median (coverage tidak cukup) quote tidak bisa diverifikasi
    # sanity-nya -> invalid eksplisit, bukan lolos diam-diam.
    notional = _to_float(quote.get("notional_usd"))
    if notional is None:
        return _fail("invalid", "exit_quote_notional_unknown",
                     {"note": "quote_does_not_state_covered_notional"})
    if notional < proposal_notional_usd:
        return _fail("invalid", "exit_quote_notional_insufficient",
                     {"quote_notional_usd": notional,
                      "proposal_notional_usd": proposal_notional_usd})
    if median_price_usd is None or median_price_usd <= 0:
        return _fail("invalid", "exit_quote_median_unavailable",
                     {"note": "no_reference_median_to_sanity_check_quote"})
    computed_notional = amount_in * median_price_usd
    if computed_notional < proposal_notional_usd:
        return _fail("invalid", "exit_quote_notional_insufficient",
                     {"computed_notional_usd": computed_notional,
                      "proposal_notional_usd": proposal_notional_usd,
                      "note": "amounts_do_not_cover_proposal"})
    implied_price = amount_out / amount_in
    tol = config.QUOTE_PRICE_TOLERANCE_PCT / 100.0
    if abs(implied_price - median_price_usd) / median_price_usd > tol:
        return _fail("invalid", "exit_quote_price_sanity_fail",
                     {"implied_price_usd": implied_price,
                      "median_price_usd": median_price_usd,
                      "tolerance_pct": config.QUOTE_PRICE_TOLERANCE_PCT,
                      "note": "implied_price_far_from_market_median"})
    ratio = config.QUOTE_NOTIONAL_TOLERANCE_RATIO
    if notional < computed_notional / ratio or notional > computed_notional * ratio:
        return _fail("invalid", "exit_quote_notional_mismatch",
                     {"quote_notional_usd": notional,
                      "computed_notional_usd": computed_notional,
                      "tolerance_ratio": ratio,
                      "note": "declared_notional_inconsistent_with_amounts"})
    if evidence_class == "firm":
        return {"status": "verified", "reason_codes": [],
                "details": {"kind": kind, "evidence_class": "firm",
                            "venue": quote.get("venue"),
                            "notional_usd": notional,
                            "computed_notional_usd": computed_notional,
                            "implied_price_usd": implied_price,
                            "median_price_usd": median_price_usd,
                            "quoted_at": quote.get("quoted_at"),
                            "expires_at": quote.get("expires_at")}}
    return {"status": "simulated_verified", "reason_codes": [],
            "details": {"kind": kind, "evidence_class": "onchain_simulation",
                        "venue": quote.get("venue"),
                        "notional_usd": notional,
                        "computed_notional_usd": computed_notional,
                        "implied_price_usd": implied_price,
                        "median_price_usd": median_price_usd,
                        "observed_at": quote.get("observed_at"),
                        "block_number": quote.get("block_number"),
                        "block_hash": quote.get("block_hash"),
                        # max_age_sec di sini = max_age EFEKTIF (sudah dicap
                        # ke QUOTE_VALIDITY_SEC, F2); klaim asli dicatat
                        # terpisah agar transparan.
                        "max_age_sec": min(
                            _to_float(quote.get("max_age_sec"))
                            or config.QUOTE_VALIDITY_SEC,
                            config.QUOTE_VALIDITY_SEC),
                        "max_age_claimed_sec": quote.get("max_age_sec"),
                        "note": "onchain_simulation_not_an_execution_commitment"}}


def _quote_pool_eligible(pool_address, token_address, token_decimals,
                         factories, block=None):
    """Cek kelayakan pool untuk quote jual (G2) — SEBELUM quote diambil.

    Kembalikan (ok, reason, info). Pemeriksaan on-chain (read-only):
    - token0()/token1(): salah satu HARUS tokenIn (B20), yang lain adalah
      counterpart. Bila tokenIn bukan anggota pool -> tidak eligible.
    - counterpart HARUS USDC native (allowlist). USDT/USDbC/WETH/dll -> tolak
      pool ini (pilih pool eligible berikutnya, jangan relabel jadi USDC).
    - decimals: tokenIn harus == token_decimals (8), counterpart harus 6.
      Decimals salah -> tolak pool ini.
    - factory: harus ada di FACTORY_VENUE (protokol yang didukung). Factory
      tak dikenal -> tolak pool ini.
    `factories` = dict alamat pool (lower) -> factory (dari ingest).
    `info` = {"token0", "token1", "token_out", "venue", "factory"} bila ok.
    `block` = pin block untuk fetch_pool_tokens/decimals (replay exact).
    """
    info = {}
    tokens = adapter.fetch_pool_tokens(pool_address, block=block)
    if not tokens["ok"]:
        return False, "pool_tokens_unreadable:" + str(tokens["error"]), info
    token0 = (tokens["token0"] or "").lower()
    token1 = (tokens["token1"] or "").lower()
    token_in = (token_address or "").lower()
    if token_in == token0:
        counterpart = tokens["token1"]
    elif token_in == token1:
        counterpart = tokens["token0"]
    else:
        return False, "token_in_not_pool_member", info
    if (counterpart or "").lower() not in {
            a.lower() for a in config.USDC_BASE_ADDRESSES}:
        return False, "counterpart_not_usdc_allowlist", info
    # Hanya USDC native yang dipakai sebagai token_out quote (scope).
    if (counterpart or "").lower() != config.USDC_NATIVE_BASE.lower():
        return False, "counterpart_not_native_usdc", info
    dec_in = adapter.fetch_token_decimals(token_address, block=block)
    if not dec_in["ok"]:
        return False, "decimals_unreadable:" + str(dec_in["error"]), info
    if dec_in["decimals"] != token_decimals:
        return False, "token_in_decimals_mismatch", info
    dec_out = adapter.fetch_token_decimals(counterpart, block=block)
    if not dec_out["ok"]:
        return False, "decimals_unreadable:" + str(dec_out["error"]), info
    if dec_out["decimals"] != 6:
        return False, "counterpart_decimals_not_6", info
    factory = (factories or {}).get((pool_address or "").lower())
    venue = config.FACTORY_VENUE.get((factory or "").lower()) if factory else None
    if venue is None:
        return False, "factory_unsupported_or_unknown", info
    info = {"token0": tokens["token0"], "token1": tokens["token1"],
            "token_out": counterpart, "venue": venue, "factory": factory,
            "token_in_decimals": dec_in["decimals"],
            "token_out_decimals": dec_out["decimals"]}
    return True, "eligible", info


def _partial_fill_probe(pool_address, token_address, amount_in_wei,
                        base_amount_out_usd, block=None):
    """Double-quote probe (F1, re-audit v6): deteksi partial-fill yang benar.

    Quote kedua dengan amount_in x PARTIAL_FILL_PROBE_MULTIPLIER (2x) di
    pool yang sama (block sama). Kembalikan {"capped", "probe_ok", "ratio",
    "info"}:
    - capped=True bila ratio = probe_out / base_out < RATIO_MIN (1,5):
      menggandakan input hampir tidak menambah output -> quote pertama
      sudah di kapasitas pool (partial fill). Pool ditolak sebagai bukti exit.
    - probe_ok=True bila panggilan probe RPC berhasil dan mengembalikan
      output positif yang valid; False bila probe gagal RPC / output
      tidak valid (inconclusive). M2 (re-audit v7): bila REQUIRE_PROBE_SUCCESS
      True, probe_ok=False membuat quote TIDAK usable (lihat
      _probe_quote_usable) — pool ditolak, bukan dipakai inconclusive.
    `info` = {"probe_amount_in_wei", "probe_amount_out_usd", "ratio",
    "capped", "probe_ok", "error"} untuk transparansi di snapshot.
    """
    mult = config.PARTIAL_FILL_PROBE_MULTIPLIER
    probe_in_wei = int(amount_in_wei * mult)
    info = {"probe_amount_in_wei": probe_in_wei,
            "probe_amount_out_usd": None, "ratio": None,
            "capped": False, "probe_ok": False, "error": None}
    if not base_amount_out_usd or base_amount_out_usd <= 0:
        info["error"] = "base_amount_out_invalid"
        return {"capped": False, "probe_ok": False, "ratio": None,
                "info": info}
    q = adapter.fetch_sell_quote(pool_address, token_address, probe_in_wei,
                                 block=block)
    if not q["ok"]:
        info["error"] = str(q.get("error"))[:120]
        return {"capped": False, "probe_ok": False, "ratio": None,
                "info": info}
    probe_out = q["amount_out_usd"]
    info["probe_amount_out_usd"] = probe_out
    if not probe_out or probe_out <= 0:
        info["error"] = "probe_amount_out_invalid"
        return {"capped": False, "probe_ok": False, "ratio": None,
                "info": info}
    ratio = probe_out / base_amount_out_usd
    info["ratio"] = ratio
    capped = ratio < config.PARTIAL_FILL_PROBE_RATIO_MIN
    info["capped"] = capped
    info["probe_ok"] = True
    return {"capped": capped, "probe_ok": True, "ratio": ratio, "info": info}


def _probe_quote_usable(probe):
    """Apakah quote pertama boleh dipakai sebagai bukti exit (M2)?

    Usable bila probe TIDAK capped DAN probe berhasil (probe_ok). Bila
    REQUIRE_PROBE_SUCCESS True (default, M2 re-audit v7), probe yang gagal
    RPC membuat quote TIDAK usable — pool ditolak, bukan dipakai
    inconclusive (pool tipis + kegagalan probe transien tidak boleh lolos
    hanya dengan sanity ±10%). Bila REQUIRE_PROBE_SUCCESS False
    (kebijakan lama v0.3.2), probe gagal = inconclusive, quote tetap
    dipakai (sanity ±10% di validator tetap berlaku).
    """
    if probe.get("capped"):
        return False
    if config.REQUIRE_PROBE_SUCCESS and not probe.get("probe_ok"):
        return False
    return True


# ------------------------------------------------------------------ ingest
def ingest_token(symbol):
    """Ingest satu token: Coinbase record + pool DexScreener + cross-check
    GeckoTerminal + proxy Hyperliquid (dex baseline "xyz").

    Kembalikan (snapshot_partial, fetch_meta). `snapshot_partial` berisi
    data mentah + fetched_at per sumber. Validasi dilakukan di build_snapshot.
    Tidak ada yang di-hard-code dari snapshot harga sebelumnya.
    """
    tok = config.TOKENS[symbol]
    fetched_at = _now()
    meta = {"fetched_at": _iso(fetched_at), "sources": {}, "errors": {}}

    cb = adapter.fetch_coinbase_tokens()
    meta["sources"]["coinbase"] = cb["source"]
    if not cb["ok"]:
        meta["errors"]["coinbase"] = cb["error"]
    record = adapter.find_token(cb["tokens"], tok["token_address"]) if cb["ok"] else None

    ds = adapter.fetch_dexscreener_pools(tok["token_address"])
    meta["sources"]["dexscreener"] = ds["source"]
    if not ds["ok"]:
        meta["errors"]["dexscreener"] = ds["error"]

    # Cross-check GeckoTerminal HANYA untuk pool teratas (by liquidity).
    # Ini pool yang SAMA, bukan venue independen (dedup by pool_address).
    gt = {"ok": False, "pool": None, "fetched_at": _iso(fetched_at),
          "source": None, "error": None}
    top_pool = None
    if ds["ok"] and ds["pairs"]:
        def _liq(p):
            v = _to_float((p.get("liquidity") or {}).get("usd"))
            return v if v is not None else -1.0
        cands = [p for p in ds["pairs"]
                 if _is_address(p.get("pairAddress") or "")]
        if cands:
            top_pool = max(cands, key=_liq).get("pairAddress")
    if top_pool:
        gt = adapter.fetch_geckoterminal_pool(top_pool)
        meta["sources"]["geckoterminal"] = gt["source"]
        if not gt["ok"]:
            meta["errors"]["geckoterminal"] = gt["error"]

    hl = adapter.fetch_hyperliquid_proxy(config.PROXY_BASELINE_DEX)
    meta["sources"]["hyperliquid"] = hl["source"]
    if not hl["ok"]:
        meta["errors"]["hyperliquid"] = hl["error"]

    # --- Fase quoter (v0.3.0, read-only RPC): oracle pause + factory pool
    # + sell quote. Gagal -> unknown/None (graceful, bukan error fatal):
    # pipeline tetap jalan tanpa bukti exit (keputusan maks WATCH).
    # BLOCK DIPIN di awal (koreksi dok v0.3.1): semua eth_call berikut
    # (oracle, factory, token/decimals, quote) dihitung pada state block
    # yang SAMA, sehingga snapshot bisa direplay byte-exact dari transcript
    # RPC. Bila fetch_block gagal, block_pin=None -> "latest" (quote tetap
    # jalan; block_number tercatat dari hasil fetch_block berikutnya).
    block = adapter.fetch_block()
    meta["sources"]["block"] = block["source"]
    if not block["ok"]:
        meta["errors"]["block"] = block["error"]
    block_pin = ("0x%x" % block["block_number"]) if block.get("ok") else None

    oracle = adapter.fetch_oracle_params(tok["token_address"],
                                         block=block_pin)
    meta["sources"]["oracle_registry"] = oracle["source"]
    if not oracle["ok"]:
        meta["errors"]["oracle_registry"] = oracle["error"]

    # Factory tiap pool (venue kanonis dari factory on-chain, bukan label
    # DexScreener). Hanya pair beralamat valid; gagal -> fallback dexId.
    factories = {}
    if ds["ok"]:
        for p in ds["pairs"]:
            addr = p.get("pairAddress") or ""
            if _is_address(addr):
                f = adapter.fetch_pool_factory(addr, block=block_pin)
                if f["ok"]:
                    factories[addr.lower()] = f["factory"]
    if factories:
        meta["sources"]["pool_factory"] = "eth_call factory() per pool"

    # Sell quote (G2): pilih pool ELIGIBLE pertama menurut likuiditas.
    # Pool teratas yang gagal guard (bukan USDC / decimals salah / factory
    # tak didukung) DITOLAK dan pool eligible berikutnya dicoba — jangan
    # relabel pool non-USDC jadi USDC. amount_in dalam unit terkecil token,
    # dihitung dari integer (bukan float sebelum pembulatan).
    sell_quote = None
    if ds["ok"] and ds["pairs"]:
        def _liq2(p):
            v = _to_float((p.get("liquidity") or {}).get("usd"))
            return v if v is not None else -1.0
        cands = [p for p in ds["pairs"]
                 if _is_address(p.get("pairAddress") or "")]
        cands.sort(key=_liq2, reverse=True)
        for cand in cands:
            pool_addr = cand.get("pairAddress")
            pool_price = _to_float(cand.get("priceUsd"))
            if not pool_price or pool_price <= 0:
                continue
            ok, reason, info = _quote_pool_eligible(
                pool_addr, tok["token_address"], tok["decimals"], factories,
                block=block_pin)
            if not ok:
                meta["errors"]["quoter_pool_rejected:" + pool_addr.lower()] = reason
                continue
            amount_in = (config.SIMULATION_NOTIONAL_USD
                         * (1.0 + config.QUOTE_NOTIONAL_BUFFER_PCT / 100.0)
                         / pool_price)
            amount_in_wei = int(amount_in * (10 ** tok["decimals"]))
            # Pakai jumlah AKTUAL setelah pembulatan integer (G2).
            amount_in_actual = amount_in_wei / (10 ** tok["decimals"])
            q = adapter.fetch_sell_quote(
                pool_addr, tok["token_address"], amount_in_wei,
                block=block_pin)
            meta["sources"]["quoter"] = q["source"]
            if not q["ok"]:
                meta["errors"]["quoter"] = q["error"]
                continue
            # Double-quote probe (F1, re-audit v6): deteksi partial-fill
            # yang BENAR. Quote kedua dengan amount_in x MULTIPLIER di pool
            # yang sama (block sama). Bila output probe / output pertama <
            # RATIO_MIN, quote pertama sudah di kapasitas pool (partial
            # fill) -> tolak pool ini, coba pool berikutnya. M2 (re-audit
            # v7): probe WAJIB sukses (REQUIRE_PROBE_SUCCESS) — probe yang
            # gagal RPC juga menolak pool ini (quote tidak usable), bukan
            # dipakai inconclusive. Hasil probe disimpan di sell_quote
            # (transparan).
            probe = _partial_fill_probe(
                pool_addr, tok["token_address"], amount_in_wei,
                q["amount_out_usd"], block=block_pin)
            if not _probe_quote_usable(probe):
                if probe["capped"]:
                    meta["errors"]["quoter_partial_fill_probe:" + pool_addr.lower()] = (
                        "probe_ratio=%.3f<%.2f" % (
                            probe["ratio"], config.PARTIAL_FILL_PROBE_RATIO_MIN))
                else:
                    meta["errors"]["quoter_probe_failed:" + pool_addr.lower()] = (
                        "probe_error=%s" % (probe["info"].get("error") or "unknown"))
                continue
            sell_quote = {
                "ok": True, "amount_out_usd": q["amount_out_usd"],
                "amount_in": amount_in_actual, "amount_in_wei": amount_in_wei,
                "top_price_usd": pool_price, "top_pool": pool_addr,
                "token_out": info["token_out"], "venue": info["venue"],
                "factory": info["factory"],
                "token0": info["token0"], "token1": info["token1"],
                "block_number": block.get("block_number"),
                "block_hash": block.get("block_hash"),
                "sqrt_price_x96_after": q["sqrt_price_x96_after"],
                "ticks_crossed": q["ticks_crossed"],
                "partial_fill_probe": probe["info"],
                "fetched_at": q["fetched_at"], "source": q["source"],
            }
            break

    # fetched_at snapshot = SETELAH semua fetch selesai (G5/koreksi dok):
    # fetched_at di awal ingest membuat waktu quote (~38 dtk kemudian)
    # berada DI MASA DEPAN relatif terhadap fetched_at snapshot.
    meta["fetched_at"] = _iso(_now())
    return {
        "symbol": symbol,
        "token_cfg": tok,
        "coinbase_record": record,
        "dexscreener_pairs": ds["pairs"] if ds["ok"] else [],
        "geckoterminal_pool": gt["pool"] if gt["ok"] else None,
        "geckoterminal_pool_address": top_pool,
        "hyperliquid": hl["instruments"] if hl["ok"] else {},
        "oracle_params": oracle,
        "pool_factories": factories,
        "sell_quote": sell_quote,
        "meta": meta,
    }


# ---------------------------------------------------------------- validate
def build_snapshot(symbol, ingested=None):
    """Bangun snapshot (§5) dari hasil ingest + validasi.

    Error sumber -> `unknown`, BUKAN nol risiko. Nilai yang gagal validasi
    ditolak dan dicatat di coverage.rejected_observations / missing_fields.
    """
    tok = config.TOKENS[symbol]
    if ingested is None:
        ingested = ingest_token(symbol)
    fetched = _parse_ts(ingested["meta"]["fetched_at"]) or _now()
    missing = []
    rejected = []

    # ---- asset: kunci identitas chain + contract (bukan ticker saja)
    asset = {"chain": config.CHAIN, "token_address": tok["token_address"],
             "symbol": symbol, "decimals": tok["decimals"]}

    # ---- reference: nav_price APA ADANYA (sudah multiplier-adjusted).
    # JANGAN dikali multiplier lagi.
    rec = ingested["coinbase_record"]
    reference = {"nav_price": None, "nav_price_updated_at": None,
                 "age_seconds": None, "session_status": "unknown",
                 "session_status_basis": "not_determined",
                 "registry_pause_status": "unknown",
                 "source": config.COINBASE_API_URL}
    multiplier = {"value": None, "observed_at": None,
                  "source": config.COINBASE_API_URL}
    token_ok = False
    if rec is None:
        missing.append("coinbase_record")
    else:
        if (rec.get("contract_address") or "").lower() != tok["token_address"].lower():
            rejected.append({"field": "contract_address",
                             "reason": "mismatch_expected"})
        elif (rec.get("symbol") or "") != symbol:
            rejected.append({"field": "symbol", "reason": "mismatch_expected"})
        else:
            token_ok = True
        nav = _to_float(rec.get("nav_price"))
        if nav is None or nav <= 0:
            missing.append("nav_price")
            rejected.append({"field": "nav_price", "reason": "nonpositive_or_missing"})
        else:
            reference["nav_price"] = nav
        nav_ts = _parse_ts(rec.get("nav_price_updated_at"))
        if nav_ts is None:
            missing.append("nav_price_updated_at")
        else:
            if (nav_ts - fetched).total_seconds() > config.MAX_FUTURE_SKEW_SEC:
                rejected.append({"field": "nav_price_updated_at",
                                 "reason": "unreasonable_future_timestamp"})
                missing.append("nav_price_updated_at")
            else:
                reference["nav_price_updated_at"] = _iso(nav_ts)
                reference["age_seconds"] = int((fetched - nav_ts).total_seconds())
                # session_status: dari umur NAV (feed 24/5, heartbeat 24 jam).
                # Bukan tebakan dari weekday saja; alasan dicatat di basis.
                age_h = reference["age_seconds"] / 3600.0
                if age_h <= config.NAV_STALE_HOURS:
                    reference["session_status"] = "active"
                    reference["session_status_basis"] = (
                        "nav_age_%.1fh_within_24h_heartbeat" % age_h)
                else:
                    reference["session_status"] = "off_hours"
                    reference["session_status_basis"] = (
                        "nav_age_%.1fh_exceeds_24h_heartbeat_feed_holding_last_close"
                        % age_h)
        mult = _to_float(rec.get("multiplier"))
        if mult is None or mult <= 0:
            missing.append("multiplier")
        else:
            multiplier["value"] = mult
            multiplier["observed_at"] = reference["nav_price_updated_at"]
        # registry_pause_status: dibaca via RPC (v0.3.0, fase quoter).
        # "paused" = pause ORACLE (feed beku, NAV basi), BUKAN pause transfer.
        # Bila RPC gagal -> tetap `unknown` (ketiadaan field tidak membuktikan
        # semua fungsi aktif, brief §5).
        oracle = ingested.get("oracle_params") or {}
        if oracle.get("ok"):
            reference["registry_pause_status"] = (
                "paused" if oracle.get("paused") else "active")
        else:
            reference["registry_pause_status"] = "unknown"

    # ---- pools: observasi independen, dedup by pool_address.
    # Dua agregator baca pool sama = SATU pool (bukan dua venue).
    pools = []
    seen_pool = set()
    for p in ingested["dexscreener_pairs"]:
        addr = (p.get("pairAddress") or "").lower()
        if not _is_address(p.get("pairAddress") or ""):
            rejected.append({"field": "pairAddress", "reason": "invalid_address"})
            continue
        if addr in seen_pool:
            continue
        seen_pool.add(addr)
        if (p.get("chainId") or "") != "base":
            rejected.append({"pool": addr, "reason": "chain_not_base"})
            continue
        base_addr = (p.get("baseToken") or {}).get("address") or ""
        if base_addr.lower() != tok["token_address"].lower():
            rejected.append({"pool": addr, "reason": "base_token_mismatch"})
            continue
        dex = p.get("dexId") or ""
        quote = (p.get("quoteToken") or {}).get("symbol") or ""
        price = _to_float(p.get("priceUsd"))
        liq = _to_float((p.get("liquidity") or {}).get("usd"))
        if not dex or not quote:
            rejected.append({"pool": addr, "reason": "missing_dex_or_quote"})
            continue
        if price is None or price <= 0:
            rejected.append({"pool": addr, "reason": "price_nonpositive_or_missing"})
            continue
        if liq is None or liq <= 0:
            rejected.append({"pool": addr, "reason": "liquidity_nonpositive_or_missing"})
            continue
        obs = {"pool_address": p.get("pairAddress"), "dex": dex,
               "quote_asset": quote, "indicative_price_usd": price,
               "liquidity_usd": liq,
               # DexScreener tidak memberi timestamp harga -> `unknown`.
               # Jangan klaim harga fresh hanya karena fetch sukses (§5).
               "source_updated_at": "unknown",
               "fetched_at": ingested["meta"]["fetched_at"],
               "source": ingested["meta"]["sources"].get("dexscreener")}
        # Factory on-chain (v0.3.0): venue kanonis dari factory, bukan label
        # DexScreener. G1 (v0.3.1): simpan identitas factory, label venue,
        # dan status verifikasi TERPISAH — factory terbaca TIDAK sama dengan
        # venue terverifikasi; fallback DITANDAI, bukan dihitung sebagai
        # independensi terverifikasi.
        factory = (ingested.get("pool_factories") or {}).get(addr)
        vinfo = _venue_info_for_pool(dex, factory)
        obs["factory"] = factory
        obs["factory_verified"] = vinfo["factory_verified"]
        obs["protocol_family"] = vinfo["protocol_family"]
        obs["venue_label_source"] = vinfo["venue_label_source"]
        obs["venue_verified"] = vinfo["venue_verified"]
        obs["venue"] = vinfo["protocol_family"]
        # Cross-check GeckoTerminal untuk pool yang sama (bukan venue baru).
        if (ingested.get("geckoterminal_pool_address") or "").lower() == addr:
            g = ingested.get("geckoterminal_pool") or {}
            gattr = g.get("attributes", {}) if isinstance(g, dict) else {}
            gprice = _to_float(gattr.get("base_token_price_usd"))
            gres = _to_float(gattr.get("reserve_in_usd"))
            obs["cross_check"] = {
                "price_usd": gprice, "reserve_usd": gres,
                "fetched_at": ingested["meta"]["fetched_at"],
                "source": ingested["meta"]["sources"].get("geckoterminal"),
                "note": "same_pool_not_independent_venue"}
        pools.append(obs)
    pools.sort(key=lambda o: o["liquidity_usd"], reverse=True)

    # ---- underlying proxy (dex baseline "xyz"). Label eksplisit.
    proxy = None
    hl = ingested["hyperliquid"]
    instr = tok["proxy_instrument"]
    if instr in hl:
        raw = hl[instr]
        funding = _to_float(raw.get("funding"))
        oi = _to_float(raw.get("openInterest"))
        mark = _to_float(raw.get("markPx"))
        orac = _to_float(raw.get("oraclePx"))
        oi_notional = None
        if oi is not None and mark is not None:
            oi_notional = oi * mark  # DERIVED, beri label (bukan raw)
        proxy = {"instrument": instr, "dex": tok["proxy_dex"],
                 "funding_raw": funding, "funding_unit": "fraction/1h",
                 "funding_interval": "1h",
                 "open_interest_raw": oi, "oi_unit": "base_asset_units",
                 "oi_notional_usd_derived": oi_notional,
                 "markPx": mark, "oraclePx": orac,
                 "observed_at": ingested["meta"]["fetched_at"],
                 "source": ingested["meta"]["sources"].get("hyperliquid"),
                 "label": "UNDERLYING EQUITY PERP PROXY",
                 # OI change 24h: butuh baseline. Belum ada -> null.
                 "oi_change_24h": None,
                 "oi_change_24h_basis": "insufficient_history_no_baseline"}
    else:
        missing.append("underlying_proxy:" + instr)

    coverage = {
        "independent_pool_count": len({o["pool_address"].lower() for o in pools}),
        # Venue dihitung dari nama KANONIS (re-audit v2, E2; v0.3.0 dari
        # factory on-chain bila diketahui): "aero" dan "aerodrome" adalah
        # venue yang sama; dua CLFactory Aero = SATU family (G1).
        # Hash snapshot_id dihitung atas nilai final ini — v0.2 menghitung
        # dari dex mentah (7 venue) lalu assess menimpa jadi 6, sehingga
        # snapshot live asli ditandai "transformed replay" (hash != isi file).
        "independent_venue_count": len({_pool_venue(o) for o in pools}),
        # G1: independensi TERVERIFIKASI (factory) vs fallback (DexScreener).
        # verified_venue_count = distinct protocol family yang factory-nya
        # terverifikasi; fallback_pool_count = pool yang venue-nya dari
        # label DexScreener (bukan independensi terverifikasi).
        "verified_venue_count": len({_pool_venue(o) for o in pools
                                     if o.get("venue_verified")}),
        "verified_pool_count": len([o for o in pools
                                    if o.get("venue_verified")]),
        "fallback_pool_count": len([o for o in pools
                                    if o.get("venue_label_source")
                                    == "dexscreener_fallback"]),
        "missing_fields": missing,
        "rejected_observations": rejected,
    }

    # ---- oracle registry (v0.3.0): multiplier + paused dari OracleRegistry.
    oracle = ingested.get("oracle_params") or {}
    oracle_snap = None
    if oracle.get("ok"):
        oracle_snap = {
            "multiplier": oracle.get("multiplier"),
            "paused": bool(oracle.get("paused")),
            "source": oracle.get("source"),
            "fetched_at": oracle.get("fetched_at"),
        }

    # ---- exit_quote (v0.3.0, fase quoter; v0.3.1 G5 label jujur): dari sell
    # quote Aero Metaquoter V3 (read-only eth_call). kind =
    # "onchain_simulation" — simulasi on-chain saat call (deterministik dari
    # state pool), BUKAN komitmen eksekusi bertanda tangan. Output =
    # amount_out_estimate (BUKAN amount_out_min — tidak ada minimum yang
    # ditegakkan); waktu = observed_at + max_age_sec (max_age = aturan
    # freshness INTERNAL, bukan expiry jaminan vendor); block_number/block_hash
    # dicatat agar simulasi bisa direplay. Token_out + venue DITURUNKAN dari
    # pool yang sudah diperiksa (G2), bukan hardcode.
    exit_quote = None
    sq = ingested.get("sell_quote") or {}
    if sq.get("ok"):
        observed_at = _parse_ts(sq.get("fetched_at")) or fetched
        exit_quote = {
            "chain": config.CHAIN,
            "token_in": tok["token_address"],
            "token_out": sq.get("token_out") or config.USDC_NATIVE_BASE,
            "side": "SELL",
            "amount_in": sq["amount_in"],
            "amount_in_wei": sq["amount_in_wei"],
            "amount_out_estimate": sq["amount_out_usd"],
            "observed_at": _iso(observed_at),
            "max_age_sec": config.QUOTE_VALIDITY_SEC,
            "block_number": sq.get("block_number"),
            "block_hash": sq.get("block_hash"),
            "source": "aero-metaquoter-v3",
            "venue": sq.get("venue"),
            "kind": "onchain_simulation",
            # Notional yang dinyatakan = amount_in x harga pool teratas
            # (harga yang dipakai untuk mengukur jumlah quote).
            "notional_usd": sq["amount_in"] * sq["top_price_usd"],
            "pool": sq["top_pool"],
            "factory": sq.get("factory"),
            "sqrt_price_x96_after": sq.get("sqrt_price_x96_after"),
            "ticks_crossed": sq.get("ticks_crossed"),
            "token0": sq.get("token0"),
            "token1": sq.get("token1"),
            # Double-quote probe (F1, re-audit v6): hasil probe partial-fill
            # (ratio probe/base, capped atau tidak) — transparan di snapshot.
            "partial_fill_probe": sq.get("partial_fill_probe"),
        }

    snap = {
        "schema_version": config.SCHEMA_VERSION,
        "methodology_version": config.METHODOLOGY_VERSION,
        "fetched_at": ingested["meta"]["fetched_at"],
        "asset": asset,
        "reference": reference,
        "multiplier": multiplier,
        "pools": pools,
        "coverage": coverage,
        "exit_quote": exit_quote,
        "oracle": oracle_snap,
        "underlying_proxy": proxy,
        "assessment": None,
        "proposal": None,
        "alert": None,
        "_token_ok": token_ok,
        "_fetch_errors": ingested["meta"]["errors"],
    }
    snap["snapshot_id"] = "snap-" + _short_hash(_canonical(
        {k: v for k, v in snap.items() if not k.startswith("_")}))
    return snap


# ------------------------------------------------------------------ assess
# Kategori reason code (audit A-D). Hanya kode di dua set pertama yang
# mengubah keputusan; kode informasional dicatat untuk transparansi tanpa
# memblokir (mis. DexScreener tidak pernah memberi timestamp harga, jadi
# `dex_price_timestamp_unknown` adalah catatan kualitas data permanen, bukan
# sinyal keputusan — waktu observasi pool adalah `fetched_at`).
BLOCKING_CODES = {"token_not_confirmed", "reference_invalid",
                  "insufficient_cross_venue_coverage", "dex_deviation_extreme"}
PROPOSAL_BLOCKING_CODES = {
    "no_exit_quote_adapter", "exit_quote_missing", "exit_quote_empty",
    "exit_quote_malformed", "exit_quote_missing_fields",
    "exit_quote_wrong_chain", "exit_quote_wrong_token",
    "exit_quote_token_out_not_usdc", "exit_quote_kind_missing",
    "exit_quote_wrong_side", "exit_quote_bad_amount",
    "exit_quote_bad_output", "exit_quote_bad_timestamp",
    "exit_quote_future_timestamp", "exit_quote_stale",
    "exit_quote_expired", "exit_quote_source_error",
    "exit_quote_indicative_only", "exit_quote_simulation_only",
    "exit_quote_unknown_kind", "exit_quote_notional_unknown",
    "exit_quote_notional_insufficient", "exit_quote_notional_mismatch",
    "exit_quote_price_sanity_fail", "exit_quote_median_unavailable",
    "dex_pool_stale", "dex_pool_timestamp_unknown", "dex_data_stale",
    "nav_stale_off_hours", "nav_stale_active_session",
    "nav_timestamp_unknown", "nav_future_timestamp",
    "nav_paused_corporate_action",
    # G6: registry unknown/stale/mismatch menahan proposal (fail-closed).
    "oracle_registry_unknown", "oracle_registry_stale",
    "oracle_multiplier_mismatch",
    # G1: independensi terverifikasi (factory) di bawah minimum.
    "insufficient_verified_venue_coverage",
    "median_fragile_two_observations",
    "dex_deviation_watch", "proxy_missing", "snapshot_transformed_replay",
}
INFORMATIONAL_CODES = {"dex_price_timestamp_unknown"}


def assess_snapshot(snap, eval_at=None, eval_context="live"):
    """Penilaian tiga lapis (§6). Reason codes + coverage. BUKAN angka 0-100.

    Lapisan A: kondisi DEX token (median dari observasi independen).
    Lapisan B: bukti exit (validator quote eksplisit; tanpa sell quote yang
      valid -> indicative_only).
    Lapisan C: konteks underlying (proxy terpisah, tidak memicu alert token).

    `eval_at` = jam evaluasi (datetime UTC). Bila None, dipakai `fetched_at`
    snapshot — replay dievaluasi "sewaktu" snapshot diambil, bukan seolah
    data live sekarang. `eval_context` = "live" atau "replay" (dicatat di
    assessment; replay historis berlabel replay).
    """
    # token_ok: field internal `_token_ok` hanya ada di snapshot internal.
    # Snapshot publik (replay) tidak membawanya — turunkan ulang dari
    # identitas aset + tidak ada penolakan contract_address/symbol.
    # Audit C: validasi juga chain + decimals (bukan hanya contract/symbol).
    token_ok = snap.get("_token_ok")
    if token_ok is None:
        tok = config.TOKENS.get(snap.get("asset", {}).get("symbol", ""))
        asset = snap.get("asset", {}) or {}
        addr_ok = bool(tok) and (
            (asset.get("token_address", "") or "").lower()
            == tok["token_address"].lower())
        chain_ok = bool(tok) and (
            (asset.get("chain", "") or "") == config.CHAIN)
        dec_ok = bool(tok) and (
            asset.get("decimals") == tok["decimals"])
        rej = (snap.get("coverage") or {}).get("rejected_observations") or []
        id_rej = any(
            isinstance(r, dict) and r.get("field") in ("contract_address", "symbol")
            for r in rej)
        token_ok = bool(addr_ok and chain_ok and dec_ok and not id_rej)
    if eval_at is None:
        eval_at = _parse_ts(snap.get("fetched_at")) or _now()
    # ---- Identitas snapshot (audit C): cocokkan snapshot_id dengan hash
    # payload awal. HARUS dihitung SEBELUM coverage dihitung ulang di bawah
    # (recompute coverage mengubah field coverage snapshot; identitas dinilai
    # terhadap snapshot apa adanya saat dimuat, bukan setelah mutasi).
    # Bila tidak cocok, snapshot diubah setelah build — tandai sebagai
    # transformasi replay (bukan dibawa seolah payload asli).
    identity = verify_snapshot_identity(snap)
    codes = []
    layer_a = {"median_price_usd": None, "per_venue_deviation_pct": {},
               "nav_gap_pct_labeled": None, "note": ""}
    layer_b = {"exit_quote": None,
               "status": "indicative_only/exit_quality_unverified",
               "note": "no_sell_quote_adapter_in_prototype",
               "quote_validation": None}
    layer_c = {"proxy": None, "note": ""}
    freshness = {"eval_at": _iso(eval_at), "eval_context": eval_context,
                 "pool": {}, "nav": {}, "quote": {}}

    # ---- Coverage dihitung ULANG dari pool tervalidasi (audit C).
    # Jangan percaya count tersimpan: dedup address case-insensitive,
    # venue dikanonisasi (aero == aerodrome). Hasil hitung ulang disimpan
    # HANYA di assessment.coverage_recomputed — snap["coverage"] TIDAK
    # dimutasi (re-audit v2, E2): mutasi itu yang membuat hash snapshot_id
    # (dihitung atas coverage build) tidak cocok dengan isi file, sehingga
    # snapshot live asli ditandai "transformed replay". Selisih vs count
    # tersimpan dicatat untuk transparansi.
    pools = snap["pools"] or []
    stored_pool_count = (snap.get("coverage") or {}).get("independent_pool_count")
    stored_venue_count = (snap.get("coverage") or {}).get("independent_venue_count")
    seen_addr = set()
    venues = set()
    verified_venues = set()
    fallback_pools = 0
    has_factory_data = False
    for p in pools:
        addr = (p.get("pool_address") or "").lower()
        if _is_address(p.get("pool_address") or ""):
            seen_addr.add(addr)
        v = _pool_venue(p)
        if v:
            venues.add(v)
        # G1: hitung ulang independensi TERVERIFIKASI (factory) + fallback.
        # Pool dengan field venue_verified / venue_label_source (build v0.3.1)
        # dihitung; pool lama/fixture tanpa field itu tidak punya data
        # factory -> tidak dihitung sebagai verified, tidak juga sebagai
        # fallback (has_factory_data tetap False bila tak ada field).
        if "venue_verified" in p or "venue_label_source" in p:
            has_factory_data = True
            if p.get("venue_verified") and v:
                verified_venues.add(v)
            if p.get("venue_label_source") == "dexscreener_fallback":
                fallback_pools += 1
    n_pool = len(seen_addr)
    n_venue = len(venues)
    coverage_recomputed = {"stored_pool_count": stored_pool_count,
                           "recomputed_pool_count": n_pool,
                           "stored_venue_count": stored_venue_count,
                           "recomputed_venue_count": n_venue,
                           "canonical_venues": sorted(venues),
                           "verified_venue_count": len(verified_venues),
                           "verified_venues": sorted(verified_venues),
                           "fallback_pool_count": fallback_pools,
                           "has_factory_data": has_factory_data}
    # G1: bila data factory ADA (build v0.3.1) dan venue terverifikasi di
    # bawah minimum, independensi TIDAK terbukti -> proposal-blocking.
    # Fixture/snapshot lama tanpa data factory tidak kena kode ini (mereka
    # dinilai dengan count total seperti sebelumnya).
    if has_factory_data and len(verified_venues) < config.MIN_INDEPENDENT_VENUES:
        codes.append("insufficient_verified_venue_coverage")

    # ---- Freshness pool (audit B): umur dari fetched_at vs eval_at.
    # Pool basi (> MAX_POOL_AGE_MIN) dikeluarkan dari median — observasi basi
    # bukan observasi saat ini. Timestamp harga sumber "unknown" (DexScreener
    # tidak memberi) dicatat sebagai kode informasional, bukan fresh. Bila
    # sumber memberi timestamp harga, umur HARGA itu yang dipakai: fetch baru
    # tidak membuktikan harga baru.
    fresh_pools = []
    stale_pools = []
    unknown_ts_pools = []
    price_ts_unknown = False
    for p in pools:
        pf = _parse_ts(p.get("fetched_at"))
        if pf is None:
            unknown_ts_pools.append(p.get("pool_address"))
            continue
        age_fetch = (eval_at - pf).total_seconds()
        if age_fetch < -config.MAX_FUTURE_SKEW_SEC:
            unknown_ts_pools.append(p.get("pool_address"))
            continue
        if age_fetch > config.MAX_POOL_AGE_MIN * 60:
            stale_pools.append(p.get("pool_address"))
            continue
        ps = p.get("source_updated_at")
        if ps is None or ps == "unknown":
            price_ts_unknown = True
        else:
            ps_dt = _parse_ts(ps)
            if ps_dt is None:
                unknown_ts_pools.append(p.get("pool_address"))
                continue
            age_price = (eval_at - ps_dt).total_seconds()
            if age_price < -config.MAX_FUTURE_SKEW_SEC:
                unknown_ts_pools.append(p.get("pool_address"))
                continue
            if age_price > config.MAX_POOL_AGE_MIN * 60:
                stale_pools.append(p.get("pool_address"))
                continue
        fresh_pools.append(p)
        if (p.get("source_updated_at") or "unknown") == "unknown":
            price_ts_unknown = True
    if stale_pools:
        codes.append("dex_pool_stale")
    if unknown_ts_pools:
        codes.append("dex_pool_timestamp_unknown")
    if price_ts_unknown:
        codes.append("dex_price_timestamp_unknown")
    freshness["pool"] = {
        "fresh_count": len(fresh_pools),
        "stale_count": len(stale_pools),
        "unknown_timestamp_count": len(unknown_ts_pools),
        "max_age_min": config.MAX_POOL_AGE_MIN,
        "price_timestamp_unknown": price_ts_unknown,
    }

    # ---- Lapisan A: median + deviasi per-venue (hanya observasi independen
    # yang FRESH). Pool basi tidak ikut median.
    n_fresh = len({(p.get("pool_address") or "").lower()
                   for p in fresh_pools
                   if _is_address(p.get("pool_address") or "")})
    n_fresh_venue = len({_pool_venue(p)
                         for p in fresh_pools
                         if _pool_venue(p)})
    if n_fresh < config.MIN_INDEPENDENT_POOLS or n_fresh_venue < config.MIN_INDEPENDENT_VENUES:
        codes.append("insufficient_cross_venue_coverage")
        layer_a["note"] = (
            "only_%d_fresh_independent_pool(s)_%d_fresh_venue(s)_below_min_%d_pools_%d_venues_no_deviation_computed"
            % (n_fresh, n_fresh_venue, config.MIN_INDEPENDENT_POOLS,
               config.MIN_INDEPENDENT_VENUES))
    else:
        prices = sorted(o["indicative_price_usd"] for o in fresh_pools)
        m = len(prices)
        median = prices[m // 2] if m % 2 == 1 else (prices[m // 2 - 1] + prices[m // 2]) / 2.0
        layer_a["median_price_usd"] = median
        for o in fresh_pools:
            dev = (o["indicative_price_usd"] - median) / median * 100.0
            layer_a["per_venue_deviation_pct"][o["pool_address"]] = round(dev, 4)
        if m == 2:
            codes.append("median_fragile_two_observations")
            layer_a["note"] = "median_from_only_2_observations_fragile"
        # Gap DEX-vs-NAV beku: DESKRIPSI BERLABEL saja (§3). Bukan
        # diskon/mispricing/arbitrase/tidak-bisa-dieksploitasi/pasti-false-positive.
        nav = snap["reference"]["nav_price"]
        if nav is not None and nav > 0:
            gap = (median - nav) / nav * 100.0
            layer_a["nav_gap_pct_labeled"] = {
                "value_pct": round(gap, 4),
                "label": "dex_median_vs_last_published_nav",
                "nav_age_seconds": snap["reference"]["age_seconds"],
                "session_status": snap["reference"]["session_status"],
                "note": "labeled_description_only_cause_and_exploitability_unproven",
            }
        # Deviasi ekstrem / watch (threshold eksperimen, belum tervalidasi).
        max_dev = max((abs(v) for v in layer_a["per_venue_deviation_pct"].values()),
                      default=0.0)
        if max_dev > config.DEV_ABSTAIN_PCT:
            codes.append("dex_deviation_extreme")
        elif max_dev > config.DEV_WATCH_PCT:
            codes.append("dex_deviation_watch")

    # ---- Lapisan B: bukti exit — validator quote eksplisit (audit A + E1).
    # Objek non-null BUKAN bukti valid. Status layer B "verified" HANYA bila
    # validator menyatakan verified; selain itu tetap unverified.
    # Median DEX diteruskan agar validator bisa sanity-check harga + notional
    # (E1): quote tanpa referensi harga tidak bisa diverifikasi.
    quote_validation = validate_exit_quote(
        snap.get("exit_quote"), snap, eval_at=eval_at,
        proposal_notional_usd=config.SIMULATION_NOTIONAL_USD,
        median_price_usd=layer_a["median_price_usd"])
    layer_b["quote_validation"] = quote_validation
    freshness["quote"] = {"status": quote_validation["status"],
                          "reason_codes": quote_validation["reason_codes"]}
    if quote_validation["status"] == "verified":
        layer_b["status"] = "verified"
        layer_b["exit_quote"] = snap.get("exit_quote")
        layer_b["note"] = "sell_quote_validated"
    elif quote_validation["status"] == "simulated_verified":
        # G5: simulasi on-chain yang lolos sanity = bukti exit SIMULASI,
        # bukan komitmen eksekusi. Status layer B eksplisit agar tidak
        # pernah disalahartikan sebagai "verified" (firm).
        layer_b["status"] = "simulated_exit_quote_verified"
        layer_b["exit_quote"] = snap.get("exit_quote")
        layer_b["note"] = ("onchain_simulation_validated_not_an_execution_"
                           "commitment")
    else:
        layer_b["status"] = "indicative_only/exit_quality_unverified"
        layer_b["exit_quote"] = None
        layer_b["note"] = ("no_sell_quote_available"
                           if snap.get("exit_quote") is None
                           else "sell_quote_rejected_by_validator")
        codes.extend(quote_validation["reason_codes"])
        # Bila tidak ada quote SAMA SEKALI, itu juga berarti tidak ada adapter
        # quoter di prototipe ini — catat kode itu juga (kompatibilitas dengan
        # gate lama + membedakan "adapter belum ada" dari "quote ditolak").
        if snap.get("exit_quote") is None and "no_exit_quote_adapter" not in codes:
            codes.append("no_exit_quote_adapter")

    # ---- Lapisan C: konteks underlying (proxy terpisah)
    proxy = snap["underlying_proxy"]
    if proxy is None:
        codes.append("proxy_missing")
        layer_c["note"] = "underlying_proxy_not_found_in_hyperliquid_response"
    else:
        layer_c["proxy"] = {
            "instrument": proxy["instrument"], "dex": proxy["dex"],
            "funding_raw": proxy["funding_raw"],
            "funding_unit": proxy["funding_unit"],
            "open_interest_raw": proxy["open_interest_raw"],
            "oi_unit": proxy["oi_unit"],
            "oi_change_24h": None,
            "label": proxy["label"],
        }
        layer_c["note"] = (
            "proxy_displayed_separately_does_not_trigger_token_exit_alert")

    # ---- Freshness NAV + sesi pasar (audit B). Timestamp NAV unknown tetap
    # unknown (bukan fresh). Umur NAV dihitung ulang dari timestamp vs jam
    # evaluasi (bukan hanya field tersimpan) agar replay historis vs evaluasi
    # live dibedakan. NAV basi saat market AKTIF dibedakan dari NAV basi saat
    # market tutup (kalender NYSE minimal). Timestamp future di luar toleransi
    # skew ditolak eksplisit.
    # Registry pause (v0.3.0): bila OracleRegistry melaporkan paused=true,
    # NAV BEKU (feed Chainlink menahan nilai terakhir saat corporate action)
    # -> tandai sebagai NAV basi tersendiri. Ini BUKAN berarti token tidak
    # bisa dijual (transfer tidak diblokir) — quote DEX tetap valid sebagai
    # bukti exit; yang tidak valid adalah memakai NAV beku sebagai referensi
    # harga segar.
    if snap["reference"].get("registry_pause_status") == "paused":
        codes.append("nav_paused_corporate_action")
    # G6: registry unknown/stale/mismatch = proposal-blocking (fail-closed).
    # paused=false yang VALID diperlukan untuk jalur proposal; status unknown
    # (RPC gagal / data rusak) TIDAK BOLEH menghasilkan PAPER_PROPOSAL.
    if snap["reference"].get("registry_pause_status") == "unknown":
        codes.append("oracle_registry_unknown")
    oracle_snap = snap.get("oracle") or {}
    oracle_fetched = _parse_ts(oracle_snap.get("fetched_at")) if oracle_snap else None
    if oracle_snap and oracle_fetched is not None:
        if (eval_at - oracle_fetched).total_seconds() > config.REGISTRY_MAX_AGE_SEC:
            codes.append("oracle_registry_stale")
        elif (eval_at - oracle_fetched).total_seconds() < -config.MAX_FUTURE_SKEW_SEC:
            codes.append("oracle_registry_stale")
    elif oracle_snap and oracle_fetched is None:
        codes.append("oracle_registry_stale")
    # Cross-check multiplier: registry vs Coinbase harus cocok (toleransi
    # 0,5% untuk pembulatan float). Beda besar = token mismatch / data salah.
    cb_mult = (snap.get("multiplier") or {}).get("value")
    or_mult = oracle_snap.get("multiplier") if oracle_snap else None
    if cb_mult is not None and or_mult is not None and cb_mult > 0:
        if abs(or_mult - cb_mult) / cb_mult > 0.005:
            codes.append("oracle_multiplier_mismatch")
    if not token_ok:
        codes.append("token_not_confirmed")
    if snap["reference"]["nav_price"] is None:
        codes.append("reference_invalid")
    nav_age = snap["reference"]["age_seconds"]
    nav_ts_str = snap["reference"]["nav_price_updated_at"]
    nav_ts = _parse_ts(nav_ts_str) if nav_ts_str else None
    if nav_ts is None or nav_age is None:
        codes.append("nav_timestamp_unknown")
        freshness["nav"] = {"status": "timestamp_unknown"}
    else:
        nav_age_eval = int((eval_at - nav_ts).total_seconds())
        session = _market_session(eval_at)
        if nav_age_eval < -config.MAX_FUTURE_SKEW_SEC:
            codes.append("nav_future_timestamp")
            freshness["nav"] = {"status": "future_timestamp",
                                "age_seconds": nav_age_eval,
                                "market_session": session}
        elif nav_age_eval > config.NAV_STALE_HOURS * 3600:
            codes.append("nav_stale_off_hours")
            if session == "open":
                codes.append("nav_stale_active_session")
            freshness["nav"] = {"status": "stale",
                                "age_seconds": nav_age_eval,
                                "market_session": session}
        else:
            freshness["nav"] = {"status": "ok",
                                "age_seconds": nav_age_eval,
                                "market_session": session}

    # ---- Identitas snapshot (dihitung di awal, sebelum mutasi coverage):
    # bila tidak cocok, snapshot diubah setelah build — tandai sebagai
    # transformasi replay.
    if not identity["matches"]:
        codes.append("snapshot_transformed_replay")

    # ---- status: "unknown" bila identitas/referensi tak terkonfirmasi;
    # "degraded" bila ada reason code apa pun; "ok" hanya bila semua bersih.
    # (Prototipe tanpa quoter tidak pernah "ok" penuh — jujur by-design.)
    if not token_ok or snap["reference"]["nav_price"] is None:
        status = "unknown"
    elif codes:
        status = "degraded"
    else:
        status = "ok"

    basis = ("pools=%d venues=%d fresh_pools=%d nav_age=%s session=%s exit_quote=%s proxy=%s"
             % (n_pool, n_venue, n_fresh,
                ("%.1fh" % (nav_age / 3600.0)) if nav_age is not None else "unknown",
                snap["reference"]["session_status"],
                quote_validation["status"],
                "present" if proxy else "absent"))
    snap["assessment"] = {"status": status, "reason_codes": codes,
                          "confidence_basis": basis,
                          "layer_a": layer_a, "layer_b": layer_b,
                          "layer_c": layer_c,
                          "freshness": freshness,
                          "coverage_recomputed": coverage_recomputed,
                          "snapshot_identity": identity}
    return snap


# ------------------------------------------------------------------ decide
def decide(snap):
    """Policy deterministik (POLICY_VERSION). ABSTAIN / WATCH / PAPER_PROPOSAL.

    Aturan (berurutan):
    1. Blocking (token tak terkonfirmasi / referensi invalid / coverage tak
       cukup / deviasi ekstrem) -> ABSTAIN.
    2. Bukti bermasalah (quote invalid/missing/stale, pool/NAV basi,
       median rapuh, deviasi watch, proxy hilang, snapshot diubah) -> WATCH.
    3. Feature gate proposal MATI -> WATCH (paper_proposals_disabled).
       PAPER_PROPOSAL tidak terjangkau apa pun isi exit_quote selama gate
       ini False — by-design, bukan bug (audit A).
    4. Layer B belum verified -> WATCH (exit_evidence_not_verified).
       Layer B "simulated_exit_quote_verified" (G5) juga -> WATCH
       (exit_evidence_simulated_not_firm): simulasi yang lolos sanity
       adalah bukti exit simulasi, BUKAN komitmen eksekusi — ia tidak
       mengaktifkan proposal.
    5. Selain itu (quote FIRM verified + semua bersih + gate nyala) ->
       PAPER_PROPOSAL. Invariant: PAPER_PROPOSAL SELALU mensyaratkan layer B
       verified (firm), bukan unverified dan bukan simulasi.
    Di prototipe ini (quoter terpasang v0.3.1, gate mati), PAPER_PROPOSAL
    tetap tidak terjangkau — itu jujur dan by-design, bukan bug. Menahan
    semua alokasi di cash simulasi adalah hasil yang sah.
    """
    codes = set(snap["assessment"]["reason_codes"])
    reasons = []
    if codes & BLOCKING_CODES:
        decision = "ABSTAIN"
        reasons = sorted(codes & BLOCKING_CODES)
    elif codes & PROPOSAL_BLOCKING_CODES:
        decision = "WATCH"
        reasons = sorted(codes & PROPOSAL_BLOCKING_CODES)
    elif not config.PAPER_PROPOSALS_ENABLED:
        decision = "WATCH"
        reasons = ["paper_proposals_disabled"]
    elif snap["assessment"]["layer_b"]["status"] == "simulated_exit_quote_verified":
        decision = "WATCH"
        reasons = ["exit_evidence_simulated_not_firm"]
    elif snap["assessment"]["layer_b"]["status"] != "verified":
        decision = "WATCH"
        reasons = ["exit_evidence_not_verified"]
    else:
        # Hanya kode informasional tersisa (mis. dex_price_timestamp_unknown
        # — keterbatasan DexScreener yang permanen, bukan sinyal keputusan).
        # Quote tervalidasi + gate nyala -> PAPER_PROPOSAL.
        decision = "PAPER_PROPOSAL"
        reasons = []

    # Proposal: bobot/nominal adalah parameter policy EKSPERIMEN, bukan
    # preferensi investasi Alex. Jangan isi toleransi risiko Alex diam-diam.
    if decision == "PAPER_PROPOSAL":
        # Hanya terjangkau bila exit quote tervalidasi + gate proposal nyala.
        w = min(config.MAX_WEIGHT_PER_ASSET,
                1.0 / max(len(snap["pools"]), 1))
        proposal = {"weights": {snap["asset"]["symbol"]: round(w, 4)},
                    "cash_weight": round(1.0 - w, 4),
                    "simulation_notional": config.SIMULATION_NOTIONAL_USD,
                    "horizon_days": config.HORIZON_DAYS,
                    "expiry_days": config.EXPIRY_DAYS,
                    "reason": "exit_evidence_present_and_conditions_benign"}
    else:
        proposal = {"weights": {},
                    "cash_weight": 1.0,
                    "simulation_notional": config.SIMULATION_NOTIONAL_USD,
                    "horizon_days": config.HORIZON_DAYS,
                    "expiry_days": config.EXPIRY_DAYS,
                    "reason": "holding_all_simulated_cash_" + decision.lower()}
    snap["proposal"] = proposal
    snap["decision"] = decision
    snap["decision_reasons"] = reasons
    snap["policy_version"] = config.POLICY_VERSION
    return snap


# ------------------------------------------------------------------ explain
def explain(snap):
    """Rangkuman alasan + sumber dari objek tervalidasi. Jangan menciptakan
    harga/quote/alasan finansial baru."""
    a = snap["assessment"]
    ref = snap["reference"]
    lines = []
    lines.append("Decision %s under %s for %s (chain %s, contract %s)."
                 % (snap["decision"], snap["policy_version"],
                    snap["asset"]["symbol"], snap["asset"]["chain"],
                    snap["asset"]["token_address"]))
    lines.append("Reason codes: %s." % (", ".join(snap["decision_reasons"])
                                        or "none"))
    nav = ref["nav_price"]
    if nav is not None:
        lines.append("Reference NAV (already multiplier-adjusted, NOT "
                     "multiplied again): %s, updated %s, age %s, session %s."
                     % (nav, ref["nav_price_updated_at"],
                        ("%d seconds" % ref["age_seconds"])
                        if ref["age_seconds"] is not None else "unknown",
                        ref["session_status"]))
    else:
        lines.append("Reference NAV: unknown (not confirmed).")
    la = a["layer_a"]
    if la["median_price_usd"] is not None:
        # Jumlah pool/venue yang ditampilkan = hasil hitung ulang tervalidasi
        # (re-audit v2, E2), bukan count tersimpan mentah.
        rec = a.get("coverage_recomputed") or {}
        n_pool = rec.get("recomputed_pool_count",
                         (snap.get("coverage") or {}).get("independent_pool_count"))
        n_venue = rec.get("recomputed_venue_count",
                          (snap.get("coverage") or {}).get("independent_venue_count"))
        lines.append("DEX median (independent pools=%d, venues=%d): %s USD."
                     % (n_pool, n_venue, la["median_price_usd"]))
        if la["nav_gap_pct_labeled"] is not None:
            g = la["nav_gap_pct_labeled"]
            lines.append("Labeled description: DEX median is %s%% vs last "
                         "published NAV (age %s seconds, session %s). "
                         "Cause and exploitability unproven; not labeled a "
                         "discount, mispricing, or arbitrage."
                         % (g["value_pct"], g["nav_age_seconds"],
                            g["session_status"]))
    else:
        lines.append("DEX median: not computed (%s)."
                     % (la["note"] or "insufficient coverage"))
    lines.append("Exit evidence: %s (sell quote from Aero Metaquoter V3, "
                 "read-only eth_call; liquidity/TVL is not used as exit "
                 "evidence)."
                 % a["layer_b"]["status"])
    if snap.get("oracle") is not None:
        o = snap["oracle"]
        lines.append("Oracle registry: multiplier %s, paused %s "
                     "(read-only getOracleParams; paused = oracle feed frozen, "
                     "not a transfer pause)."
                     % (o.get("multiplier"), o.get("paused")))
    if snap["underlying_proxy"] is not None:
        p = snap["underlying_proxy"]
        lines.append("Underlying context (UNDERLYING EQUITY PERP PROXY, "
                     "separate): %s funding %s %s, OI raw %s %s. Proxy does "
                     "not trigger a token-exit alert."
                     % (p["instrument"], p["funding_raw"], p["funding_unit"],
                        p["open_interest_raw"], p["oi_unit"]))
    else:
        lines.append("Underlying proxy: unknown (not found).")
    if snap["decision"] in ("ABSTAIN", "WATCH"):
        lines.append("Paper record: all simulated cash (cash_weight 1.0), "
                     "no buy proposed. Holding cash is a valid outcome.")
    snap["explanation"] = " ".join(lines)
    return snap


# ------------------------------------------------------------------- alert
def alert_id_for(snap, mode):
    """ID alert deterministik: hash(snapshot_id + rule_version + decision +
    reason codes + asset + mode). Input sama -> ID sama (idempotensi)."""
    canon = _canonical({
        "snapshot_id": snap["snapshot_id"],
        "rule_version": snap["policy_version"],
        "decision": snap["decision"],
        "reasons": sorted(snap["decision_reasons"]),
        "asset": snap["asset"]["symbol"],
        "mode": mode,
    })
    return "alert-" + _short_hash(canon)


def emit_alert(snap, mode, seen_path):
    """Serialisasi payload alert ke dict (ditulis file oleh run.py).

    Dedup: bila alert_id sudah ada di seen_path, kembalikan duplicate=True
    dan JANGAN buat payload baru. Mode TEST/REPLAY dipakai saat replay agar
    alert sintetis tidak dikira kejadian pasar live.

    Audit D — kegagalan persist EKSPLISIT, bukan sukses palsu:
    - File belum ada (first run) -> store kosong, normal.
    - File ada tapi corrupt / bukan dict / tidak bisa dibaca -> error
      terstruktur (ok=False), JANGAN dianggap store kosong.
    - Tulis gagal (parent tidak ada, permission, disk penuh) -> error
      terstruktur (ok=False), JANGAN kembalikan duplicate=False seolah emit
      berhasil. Tulis atomik (temp file + os.replace) + file lock agar dua
      worker bersamaan tidak sama-sama mendapat izin emit baru untuk ID sama.
    Kembalikan {"ok", "duplicate", "alert_id", "mode", "payload", "error"}.
    Pemanggil WAJIB cek "ok" sebelum mengklaim emit berhasil.
    """
    aid = alert_id_for(snap, mode)
    lock_path = seen_path + ".lock"
    try:
        lock_f = open(lock_path, "w", encoding="utf-8")
    except OSError as e:
        return {"ok": False, "duplicate": False, "alert_id": aid, "mode": mode,
                "payload": None,
                "error": {"stage": "lock", "type": type(e).__name__,
                          "message": str(e)}}
    try:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            with open(seen_path, "r", encoding="utf-8") as f:
                seen = json.load(f)
            if not isinstance(seen, dict):
                return {"ok": False, "duplicate": False, "alert_id": aid,
                        "mode": mode, "payload": None,
                        "error": {"stage": "read", "type": "malformed_store",
                                  "message": "seen store is not a JSON object"}}
        except FileNotFoundError:
            seen = {}
        except (PermissionError, OSError) as e:
            return {"ok": False, "duplicate": False, "alert_id": aid,
                    "mode": mode, "payload": None,
                    "error": {"stage": "read", "type": type(e).__name__,
                              "message": str(e)}}
        except ValueError as e:
            return {"ok": False, "duplicate": False, "alert_id": aid,
                    "mode": mode, "payload": None,
                    "error": {"stage": "read", "type": "corrupt_store",
                              "message": "seen store is not valid JSON: %s" % e}}
        if aid in seen:
            return {"ok": True, "duplicate": True, "alert_id": aid,
                    "mode": mode, "seen_before": seen[aid], "payload": None,
                    "error": None}
        payload = {
            "alert_id": aid,
            "mode": mode,
            "rule_version": snap["policy_version"],
            "snapshot_id": snap["snapshot_id"],
            "asset": snap["asset"]["symbol"],
            "decision": snap["decision"],
            "reasons": sorted(snap["decision_reasons"]),
            "assessment_status": snap["assessment"]["status"],
            "median_price_usd": snap["assessment"]["layer_a"]["median_price_usd"],
            "nav_gap_pct_labeled":
                snap["assessment"]["layer_a"]["nav_gap_pct_labeled"],
            "exit_evidence": snap["assessment"]["layer_b"]["status"],
            "proxy_label": ("UNDERLYING EQUITY PERP PROXY"
                            if snap["underlying_proxy"] else None),
            "emitted_at": _iso(_now()),
            "note": ("TEST/REPLAY alert from a controlled replay, not a live "
                     "market event." if mode == "TEST/REPLAY" else
                     "Local alert only. Not sent to any production channel."),
        }
        seen[aid] = {"emitted_at": payload["emitted_at"], "mode": mode,
                     "snapshot_id": snap["snapshot_id"]}
        # Tulis atomik: temp file di direktori yang sama + os.replace.
        # Bila parent tidak ada / permission / disk penuh -> error, bukan sukses.
        try:
            parent = os.path.dirname(os.path.abspath(seen_path))
            fd, tmp_path = tempfile.mkstemp(prefix=".seen-", dir=parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(seen, f, indent=2, sort_keys=True)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, seen_path)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except OSError as e:
            return {"ok": False, "duplicate": False, "alert_id": aid,
                    "mode": mode, "payload": None,
                    "error": {"stage": "write", "type": type(e).__name__,
                              "message": str(e)}}
        return {"ok": True, "duplicate": False, "alert_id": aid, "mode": mode,
                "payload": payload, "error": None}
    finally:
        try:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
        except OSError:
            pass
        lock_f.close()


# -------------------------------------------------------------- paper record
def paper_record(snap):
    """Simpan usulan + snapshot yang mendasarinya. Tidak ada transaksi.
    Tidak ada klaim fill/return bila hanya ada indicative price."""
    return {
        "snapshot_id": snap["snapshot_id"],
        "asset": snap["asset"]["symbol"],
        "decision": snap["decision"],
        "decision_reasons": snap["decision_reasons"],
        "proposal": snap["proposal"],
        "assessment": snap["assessment"],
        "explanation": snap["explanation"],
        "fetched_at": snap["fetched_at"],
        "policy_version": snap["policy_version"],
        "methodology_version": snap["methodology_version"],
        "note": ("Paper (simulated) decision only. No transaction, no fill, "
                 "no return claim. Indicative prices only."),
    }


# ------------------------------------------------------------------- driver
def run_token(symbol, ingested=None):
    """Satu alur end-to-end untuk satu token (ingest->...->paper record)."""
    snap = build_snapshot(symbol, ingested=ingested)
    snap = assess_snapshot(snap)
    snap = decide(snap)
    snap = explain(snap)
    return snap


def public_snapshot(snap):
    """Snapshot tanpa field internal (prefix `_`) untuk disimpan/dibagikan."""
    return {k: v for k, v in snap.items() if not k.startswith("_")}
