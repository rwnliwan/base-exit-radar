#!/usr/bin/env python3
"""S2 probe jalur quote FIRM — kandidat TANPA key (Odos / KyberSwap / Uniswap).

Tugas S2 (rencana Scope 1 v1.1, 24 Nov 2026, §2.1/§2.1b/§2.3/§2.4):
minta SELL quote NVDAc->USDC dan AAPLc->USDC pada notional $10.000
(= config.SIMULATION_NOTIONAL_USD) dari tiga kandidat publik, rekam
respons MENTAH, dan nilai tiap respons field demi field terhadap definisi
FIRM yang dibekukan (§2.1, pipeline.validate_exit_quote).

ATURAN YANG DIPATUHI SKRIP INI (bukan sekadar komentar):
- TIDAK ADA API key. Ketiga kandidat di-probe tanpa key. 0x/1inch TIDAK
  di-probe di sini (key belum diterima; menyusul bila chief meneruskan).
- `expires_at` TIDAK PERNAH dibentuk dari jam lokal (now + TTL). Bila
  vendor tidak memberi semantik expiry, field itu dicatat ABSENT dan
  quote TIDAK dapat diklasifikasikan firm.
- `amount_out_min` HANYA diisi dari field vendor. Expected-out vendor
  TIDAK PERNAH dipakai seolah-olah min-out. Lantai yang dihitung klien
  dari toleransi slippage dicatat terpisah dengan label eksplisit
  "client-derived floor (NOT vendor-committed)" — bukan bukti min-out.
- `kind` TIDAK PERNAH diasumsikan "firm". Bila vendor tidak memberi
  label kind, dicatat ABSENT.
- Simulasi TIDAK PERNAH disebut firm. Tidak ada eksekusi, tidak ada
  signing, tidak ada transaksi, tidak ada mainnet (hanya HTTP read-only
  ke API publik + RPC read-only untuk pin block).
- Sumber pembanding DITETAPKAN SEBELUM probe (§2.1b): primer = quote
  vendor LAIN untuk pair/arah/ukuran sama; fallback = harga NAV-implied
  (Coinbase, sudah multiplier-adjusted) + proxy Hyperliquid xyz,
  keduanya dilabeli REFERENSI (bukan harga eksekusi).

Output: evidence/firm_quote_probes_2026-11-24.json
Hanya membaca config/adapter (tidak mengubah kode produksi).
"""

import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import adapter  # noqa: E402  (read-only reuse: NAV, proxy, DexScreener, block)
import config  # noqa: E402
import pipeline  # noqa: E402  (hanya validate_exit_quote, read-only)

DATE_TAG = "2026-11-24"
OUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "evidence", "firm_quote_probes_%s.json" % DATE_TAG)

NOTIONAL_USD = config.SIMULATION_NOTIONAL_USD  # 10_000.0
USDC_NATIVE = config.USDC_NATIVE_BASE
TOKENS = ("NVDAc", "AAPLc")
# Toleransi slippage YANG DIPILIH KLIEN saat meminta quote (bukan komitmen
# vendor). Dipakai seragam 0,5% di semua kandidat yang menerimanya.
SLIPPAGE_PCT = 0.5
SLIPPAGE_BPS = 50

UA = {"User-Agent": config.USER_AGENT}


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http(method, url, body=None, headers=None, timeout=60, retries=1):
    """Satu HTTP call (dengan 1 retry atas timeout / 5xx).

    Kembalikan dict {http_status, raw_text, json, error, attempts}.
    `attempts` = daftar tiap percobaan {http_status, error, elapsed_sec}.
    Round 1 memakai timeout 30 dtk tanpa retry dan menghasilkan timeout
    untuk Odos/Uniswap + 429 untuk Kyber-NVDAc; round 2 memakai timeout
    60 dtk + 1 retry agar kegagalan transport dibedakan dari kegagalan
    skema vendor.
    """
    import time as _time
    h = dict(UA)
    if headers:
        h.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json"
    attempts = []
    last = {"http_status": None, "raw_text": "", "json": None,
            "error": "no_attempt"}
    for attempt in range(retries + 1):
        t0 = _time.time()
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(text)
                except Exception:
                    parsed = None
                attempts.append({"http_status": r.status, "error": None,
                                 "elapsed_sec": round(_time.time() - t0, 2)})
                last = {"http_status": r.status, "raw_text": text,
                        "json": parsed, "error": None}
                break
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            attempts.append({"http_status": e.code,
                             "error": "http_%s" % e.code,
                             "elapsed_sec": round(_time.time() - t0, 2)})
            last = {"http_status": e.code, "raw_text": text,
                    "json": parsed, "error": "http_%s" % e.code}
            if e.code < 500 and e.code != 429:
                break
        except Exception as e:  # noqa: BLE001
            attempts.append({"http_status": None,
                             "error": "fetch_error:%s" % type(e).__name__,
                             "elapsed_sec": round(_time.time() - t0, 2)})
            last = {"http_status": None, "raw_text": "",
                    "json": None,
                    "error": "fetch_error:%s" % type(e).__name__}
        if attempt < retries:
            _time.sleep(5)
    last["attempts"] = attempts
    return last


# ------------------------------------------------------------------ referensi
# Fetch referensi (NAV / proxy / DexScreener / block) LEWAT adapter bila
# adapter sehat; bila adapter rusak (mis. edit konkuren S1 yang merujuk
# config yang belum ada — AttributeError HTTP_MAX_RETRIES, 24 Nov),
# jatuh ke implementasi lokal di bawah (urllib langsung, endpoint sama
# dari config). Metode yang dipakai dicatat di evidence per round.
def _local_get_json(url):
    r = _http("GET", url)
    if r["json"] is not None:
        return r["json"], None
    return None, (r["error"] or "http_%s" % r["http_status"])


def _local_post_json(url, payload):
    r = _http("POST", url, body=payload)
    if r["json"] is not None:
        return r["json"], None
    return None, (r["error"] or "http_%s" % r["http_status"])


def _safe_fetch_coinbase_tokens():
    try:
        return adapter.fetch_coinbase_tokens(), "adapter"
    except Exception as e:  # noqa: BLE001 - adapter rusak (edit konkuren)
        tokens, err = [], None
        url = config.COINBASE_API_URL
        for _ in range(10):
            payload, err = _local_get_json(url)
            if err is not None or not isinstance(payload, dict):
                break
            tokens.extend(payload.get("tokens", []))
            nxt = payload.get("next_page_token")
            if not nxt:
                err = None
                break
            url = config.COINBASE_API_URL + "?page_token=" + str(nxt)
            if any((t.get("contract_address") or "").lower() in (
                    config.TOKENS["NVDAc"]["token_address"].lower(),
                    config.TOKENS["AAPLc"]["token_address"].lower())
                   for t in tokens) and len(tokens) >= 100:
                # Kedua token sudah ketemu; lanjut hanya bila perlu.
                # (Tetap lanjut sampai cursor habis? Tidak — probe hanya
                # butuh NAV kedua token; hentikan bila keduanya ketemu.)
                addrs = {(t.get("contract_address") or "").lower() for t in tokens}
                if all(config.TOKENS[s]["token_address"].lower() in addrs
                       for s in TOKENS):
                    break
        return {"ok": err is None, "tokens": tokens, "fetched_at": _now_iso(),
                "source": config.COINBASE_API_URL, "error": err}, "probe-local"


def _safe_fetch_hyperliquid_proxy(dex="xyz"):
    try:
        return adapter.fetch_hyperliquid_proxy(dex), "adapter"
    except Exception:  # noqa: BLE001
        payload, err = _local_post_json(
            config.HYPERLIQUID_INFO_URL, {"type": "metaAndAssetCtxs", "dex": dex})
        out = {"ok": False, "instruments": {}, "fetched_at": _now_iso(),
               "source": config.HYPERLIQUID_INFO_URL + " dex=" + dex, "error": None}
        if err is not None:
            out["error"] = err
            return out, "probe-local"
        try:
            meta, ctxs = payload[0], payload[1]
            for i, u in enumerate(meta.get("universe", [])):
                ctx = ctxs[i] if i < len(ctxs) else {}
                out["instruments"][u.get("name")] = {
                    "funding": ctx.get("funding"),
                    "openInterest": ctx.get("openInterest"),
                    "markPx": ctx.get("markPx"),
                    "oraclePx": ctx.get("oraclePx")}
        except Exception as e:  # noqa: BLE001
            out["error"] = "parse_error:%s" % type(e).__name__
            return out, "probe-local"
        out["ok"] = True
        return out, "probe-local"


def _safe_fetch_dexscreener_pools(token_address):
    try:
        return adapter.fetch_dexscreener_pools(token_address), "adapter"
    except Exception:  # noqa: BLE001
        url = config.DEXSCREENER_URL.format(address=token_address)
        payload, err = _local_get_json(url)
        if err is not None:
            return {"ok": False, "pairs": [], "fetched_at": _now_iso(),
                    "source": url, "error": err}, "probe-local"
        pairs = payload.get("pairs", []) if isinstance(payload, dict) else []
        return {"ok": True, "pairs": pairs, "fetched_at": _now_iso(),
                "source": url, "error": None}, "probe-local"


def _safe_fetch_block():
    try:
        return adapter.fetch_block(), "adapter"
    except Exception:  # noqa: BLE001
        out = {"ok": False, "block_number": None, "block_hash": None,
               "fetched_at": _now_iso(), "source": "eth_blockNumber",
               "error": None}
        num, err = _local_post_json(
            config.BASE_RPC_URLS[0],
            {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1})
        if err is not None or not isinstance(num, dict) or "result" not in num:
            out["error"] = err or "block_bad_number"
            return out, "probe-local"
        try:
            block_number = int(num["result"], 16)
        except (TypeError, ValueError):
            out["error"] = "block_bad_number"
            return out, "probe-local"
        blk, err = _local_post_json(
            config.BASE_RPC_URLS[0],
            {"jsonrpc": "2.0", "method": "eth_getBlockByNumber",
             "params": [num["result"], False], "id": 2})
        if err is not None or not isinstance(blk, dict) \
                or not isinstance((blk.get("result") or {}).get("hash"), str):
            out["error"] = err or "block_bad_hash"
            return out, "probe-local"
        out["block_number"] = block_number
        out["block_hash"] = blk["result"]["hash"]
        out["ok"] = True
        return out, "probe-local"


def _median_dexscreener_usdc(token_addr):
    """Median priceUsd atas pair DexScreener yang quote-nya USDC native.

    Dipakai HANYA sebagai median sanity untuk pemanggilan validator
    (bukan sebagai pembanding independen §2.1b — DexScreener/GeckoTerminal
    membaca pool yang sama dengan pipeline, jadi bukan pembanding sah).
    """
    res, _method = _safe_fetch_dexscreener_pools(token_addr)
    prices = []
    if res.get("ok"):
        for p in res.get("pairs", []):
            qt = (p.get("quoteToken") or {}).get("address", "")
            px = p.get("priceUsd")
            try:
                px = float(px)
            except (TypeError, ValueError):
                px = None
            if qt.lower() == USDC_NATIVE.lower() and px and math.isfinite(px) and px > 0:
                prices.append(px)
    prices.sort()
    if not prices:
        return None, res, []
    n = len(prices)
    med = prices[n // 2] if n % 2 == 1 else (prices[n // 2 - 1] + prices[n // 2]) / 2.0
    return med, res, prices


def _amount_in_for_notional(spot_usd, decimals):
    """amount_in (base units, ceil) agar notional hitung >= $10.000."""
    tokens = NOTIONAL_USD / spot_usd
    base = math.ceil(tokens * (10 ** decimals))
    return base, base / (10 ** decimals)


# ------------------------------------------------------------------ vendor
def probe_odos(token_addr, amount_in_base):
    url = "https://api.odos.xyz/soroban/quote/v2"
    body = {
        "chainId": 8453,
        "inputTokens": [{"tokenAddress": token_addr,
                         "amount": str(amount_in_base)}],
        "outputTokens": [{"tokenAddress": USDC_NATIVE, "proportion": 1}],
        "slippageLimitPercent": SLIPPAGE_PCT,
        # Placeholder alamat untuk quote-only (tanpa wallet): alamat nol.
        # Tidak ada signing/transaksi; field ini wajib diisi API.
        "userAddr": "0x0000000000000000000000000000000000000000",
        "compact": True,
    }
    return _http("POST", url, body=body)


def probe_kyber(token_addr, amount_in_base):
    url = ("https://aggregator-api.kyberswap.com/base/api/v1/routes"
           "?tokenIn=%s&tokenOut=%s&amountIn=%s&slippageTolerance=%s"
           % (token_addr, USDC_NATIVE, amount_in_base, SLIPPAGE_BPS))
    return _http("GET", url, headers={"x-client-id": "exit-radar-probe"})


def probe_uniswap(token_addr, amount_in_base):
    """Endpoint TERDOKUMENTASI saat ini (Trading API, developers.uniswap.org):
    POST https://trade-api.gateway.uniswap.org/v1/quote — WAJIB x-api-key.
    Di-probe TANPA key: hasil yang diharapkan = penolakan auth (dicatat
    mentah). Percobaan kedua: endpoint Routing API lama
    GET https://api.uniswap.org/v1/quote (juga tanpa key)."""
    primary = _http("POST", "https://trade-api.gateway.uniswap.org/v1/quote",
                    body={
                        "type": "EXACT_INPUT",
                        "amount": str(amount_in_base),
                        "tokenInChainId": 8453,
                        "tokenOutChainId": 8453,
                        "tokenIn": token_addr,
                        "tokenOut": USDC_NATIVE,
                        "swapper": "0x0000000000000000000000000000000000000000",
                    },
                    headers={"x-universal-router-version": "2.0"})
    legacy_url = ("https://api.uniswap.org/v1/quote"
                  "?tokenInAddress=%s&tokenInChainId=8453"
                  "&tokenOutAddress=%s&tokenOutChainId=8453"
                  "&amount=%s&type=exactIn"
                  % (token_addr, USDC_NATIVE, amount_in_base))
    legacy = _http("GET", legacy_url)
    return {"primary_trade_api": primary, "legacy_routing_api": legacy}


# ------------------------------------------------------------------ penilaian
def _find_expiry_keys(obj, prefix=""):
    """Cari kunci bertema expiry di respons (rekursif, 2 level)."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            lk = k.lower()
            if any(w in lk for w in ("expir", "deadline", "validuntil",
                                     "valid_until", "ttl", "expires")):
                found.append(prefix + k)
            if isinstance(v, (dict, list)):
                found.extend(_find_expiry_keys(v, prefix + k + "."))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:5]):
            found.extend(_find_expiry_keys(v, prefix + "[%d]." % i))
    return found


def assess(vendor, symbol, resp_json, http_status, amount_in_base,
           amount_in_tokens, spot_usd):
    """Penilaian field demi field vs definisi beku §2.1.

    Empat kuantitas dipisah (§2.1b): expected-out, min-out, price impact,
    slippage. Yang tidak diberikan vendor dicatat None/ABSENT — tidak
    pernah diisi dari perhitungan klien.
    """
    a = {"vendor": vendor, "symbol": symbol, "http_status": http_status,
         "direction": "SELL", "notional_usd_target": NOTIONAL_USD,
         "amount_in_base_units": amount_in_base,
         "amount_in_tokens": amount_in_tokens,
         "spot_reference_usd": spot_usd,
         "expected_out_usdc": None, "expected_out_field": None,
         "amount_out_min_usdc": None, "amount_out_min_field": None,
         "price_impact_pct": None, "price_impact_field": None,
         "slippage_pct": None, "slippage_field": None,
         "slippage_tolerance_requested_pct": SLIPPAGE_PCT,
         "client_derived_floor_usdc": None,
         "client_derived_floor_note": None,
         "expires_at": None, "expires_at_field": None,
         "expires_at_provenance": None, "expiry_like_keys_found": [],
         "kind_label": None, "quoted_at": None,
         "fee_included_in_min_out": None, "fee_note": None,
         "route_or_pool": None, "checks": {}, "verdict": None,
         "verdict_reasons": []}
    if resp_json is None:
        a["checks"]["response_parseable"] = False
        a["verdict"] = "TIDAK_FIRM"
        a["verdict_reasons"].append("no_parseable_response")
        return a
    a["checks"]["response_parseable"] = True
    a["expiry_like_keys_found"] = _find_expiry_keys(resp_json)

    if vendor == "odos":
        # Skema respons: odos-sdk SingleQuoteResponse (docs.odos.xyz):
        # outAmounts, inAmounts, pathId, blockNumber, priceImpact,
        # percentDiff, netOutValue, gasEstimate... TANPA expiry/min-out.
        a["expected_out_usdc"] = _usdc(resp_json.get("outAmounts"), 0)
        a["expected_out_field"] = "outAmounts[0]" if resp_json.get("outAmounts") else None
        a["price_impact_pct"] = resp_json.get("priceImpact")
        a["price_impact_field"] = "priceImpact" if "priceImpact" in resp_json else None
        # blockNumber Odos = block komputasi route (bukan quoted_at firm).
        a["vendor_block_number"] = resp_json.get("blockNumber")
        a["route_or_pool"] = "pathId=%s" % (resp_json.get("pathId") or "?")
        a["fee_note"] = ("Odos: outAmounts = expected output; gas dilaporkan "
                         "terpisah (gasEstimate/gasEstimateValue). Dokumen "
                         "Odos tidak menyatakan outAmounts sebagai minimum "
                         "yang dijamin; outputMin adalah parameter yang "
                         "dipasok CALLER saat eksekusi (swapTokenInfo di "
                         "OdosRouterV2), bukan field quote vendor.")
        a["fee_included_in_min_out"] = "N/A — no min-out field from vendor"
    elif vendor == "kyber":
        data = resp_json.get("data") or {}
        rs = data.get("routeSummary") or {}
        # Skema routeSummary (docs.kyberswap.com, OpenAPI v2.13.0):
        # tokenIn, amountIn, amountInUsd, tokenOut, amountOut, amountOutUsd,
        # gas, gasPrice, gasUsd, l1FeeUsd, route, routeID, checksum,
        # timestamp. TANPA min-out, TANPA expiry.
        a["expected_out_usdc"] = _usdc(rs.get("amountOut"))
        a["expected_out_field"] = "data.routeSummary.amountOut" if rs.get("amountOut") else None
        # `timestamp` routeSummary dicatat mentah — BUKAN quoted_at firm:
        # ia penanda waktu route indikatif, bukan waktu quote yang
        # dikomitmenkan vendor (tidak ada kind firm / min-out / expiry).
        a["vendor_timestamp_raw"] = rs.get("timestamp")
        a["route_or_pool"] = _kyber_route(rs.get("route"))
        a["fee_note"] = ("Kyber: amountOut = expected output sesudah fee pool "
                         "(bukan minimum); gas dilaporkan terpisah (gasUsd). "
                         "Tidak ada field min-out. `deadline` hanya ada di "
                         "POST /route/build sebagai parameter YANG DIPILIH "
                         "KLIEN (default +20 menit) — bukan jaminan expiry "
                         "vendor atas quote GET /routes. Docs: jangan cache "
                         "route >5-10 detik — itu anjuran refetch, bukan "
                         "semantik expiry field.")
        a["fee_included_in_min_out"] = "N/A — no min-out field from vendor"
    elif vendor == "uniswap":
        a["fee_note"] = ("Tidak ada respons quote (penolakan auth / tanpa "
                         "rute). Tidak ada field apa pun untuk dinilai.")

    # Lantai turunan klien — DICATAT TERPISAH, BUKAN min-out vendor.
    if a["expected_out_usdc"] is not None:
        a["client_derived_floor_usdc"] = a["expected_out_usdc"] * (1 - SLIPPAGE_PCT / 100.0)
        a["client_derived_floor_note"] = (
            "expected-out x (1 - 0,5%) — dihitung klien dari toleransi "
            "slippage yang diminta. BUKAN amount_out_min vendor dan TIDAK "
            "memenuhi §2.1.")
        # Slippage di sini = deviasi harga eksekusi indikatif vs spot.
        a["slippage_pct"] = ((a["expected_out_usdc"] / amount_in_tokens) / spot_usd - 1.0) * 100.0
        a["slippage_field"] = ("computed: (expected-out/amount_in)/spot - 1 "
                               "(deviasi harga indikatif vs spot DexScreener, "
                               "bukan realisasi vs ekspektasi)")

    # Checklist §2.1 (field demi field).
    c = a["checks"]
    c["kind_in_firm_executable_guaranteed"] = False  # tidak ada vendor memberi label kind
    c["kind_label_present"] = a["kind_label"] is not None
    c["amount_out_min_present_from_vendor"] = a["amount_out_min_usdc"] is not None
    c["expires_at_present_with_vendor_semantics"] = a["expires_at"] is not None
    c["quoted_at_present"] = a["quoted_at"] is not None
    c["expected_out_present"] = a["expected_out_usdc"] is not None
    if a["expected_out_usdc"] is not None and a["expected_out_usdc"] > 0:
        c["implied_price_within_10pct_of_spot"] = (
            abs((a["expected_out_usdc"] / amount_in_tokens) - spot_usd) / spot_usd <= 0.10)
    else:
        c["implied_price_within_10pct_of_spot"] = None

    reasons = []
    if not c["kind_label_present"]:
        reasons.append("kind_absent: vendor tidak memberi label kind "
                       "(firm/executable/guaranteed) — validator menolak "
                       "quote tanpa kind (exit_quote_kind_missing)")
    if not c["amount_out_min_present_from_vendor"]:
        reasons.append("amount_out_min_absent: tidak ada field min-out "
                       "dari vendor; expected-out bukan min-out")
    if not c["expires_at_present_with_vendor_semantics"]:
        reasons.append("expires_at_absent: tidak ada field expiry dengan "
                       "semantik vendor (kunci bertema expiry yang "
                       "ditemukan: %s) — tanpa semantik expiry, quote "
                       "TIDAK dapat diklasifikasikan firm (§2.1b)" % (
                           a["expiry_like_keys_found"] or "tidak ada"))
    a["verdict_reasons"] = reasons
    a["verdict"] = "FIRM" if not reasons else "TIDAK_FIRM"
    return a


def _usdc(out_amounts, idx=0, raw_is_base_units=False):
    """outAmounts Odos: list string (USDC 6 desimal). Kyber: string base units."""
    try:
        if isinstance(out_amounts, list):
            v = float(out_amounts[idx])
        else:
            v = float(out_amounts)
    except (TypeError, ValueError, IndexError):
        return None
    return v / 1e6


def _kyber_route(route):
    if not route:
        return None
    legs = []
    try:
        for hop in route:
            for step in hop:
                legs.append("%s:%s->%s" % (
                    step.get("exchange"), step.get("tokenIn"), step.get("tokenOut")))
    except Exception:
        return "route_present_unparsed"
    return "; ".join(legs) if legs else "route_present_unparsed"


def validator_faithful(assessment, symbol, median_usd, snap_fetched_at):
    """Panggil validate_exit_quote dengan pemetaan JUJUR dari field vendor.

    kind=None (vendor tidak memberi label), amount_out_min/expires_at
    tidak diisi karena vendor tidak memberikannya. Hasil yang diharapkan:
    invalid (kind missing / missing fields). Ini BUKAN kegagalan skrip —
    ini bukti validator menolak quote tanpa label/field firm.
    """
    tok = config.TOKENS[symbol]
    quote = {
        "chain": config.CHAIN,
        "token_in": tok["token_address"],
        "token_out": USDC_NATIVE,
        "side": "SELL",
        "amount_in": assessment["amount_in_tokens"],
        "source": assessment["vendor"],
        "venue": assessment["vendor"],
        "notional_usd": NOTIONAL_USD,
        # kind, amount_out_min, expires_at, quoted_at: ABSENT (vendor
        # tidak memberikannya) — sengaja tidak diisi/diisi None.
        "kind": None,
    }
    snap = {"asset": {"symbol": symbol}, "fetched_at": snap_fetched_at}
    try:
        return pipeline.validate_exit_quote(
            quote, snap, eval_at=None,
            proposal_notional_usd=NOTIONAL_USD, median_price_usd=median_usd)
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "reason_codes": ["validator_exception"],
                "details": {"error": "%s: %s" % (type(e).__name__, e)}}


def validator_generous(assessment, symbol, median_usd, snap_fetched_at):
    """HIPOTETIS, BUKAN pemetaan sah: seandainya expected-out dipakai
    seolah-olah min-out DAN kind diasumsikan 'firm' — apakah validator
    lolos? (Jawaban yang diharapkan: tetap invalid, karena expires_at
    tetap absent.) Dicatat terpisah agar tidak ada yang mengira
    pemetaan ini dipakai sebagai bukti.
    """
    if assessment["expected_out_usdc"] is None:
        return {"status": "not_applicable",
                "reason_codes": ["no_expected_out_to_map"],
                "details": {}}
    tok = config.TOKENS[symbol]
    quote = {
        "chain": config.CHAIN,
        "token_in": tok["token_address"],
        "token_out": USDC_NATIVE,
        "side": "SELL",
        "amount_in": assessment["amount_in_tokens"],
        "source": assessment["vendor"],
        "venue": assessment["vendor"],
        "notional_usd": NOTIONAL_USD,
        "kind": "firm",
        "amount_out_min": assessment["expected_out_usdc"],
        "quoted_at": snap_fetched_at,
        # expires_at: tetap ABSENT — tidak ada semantik vendor.
    }
    snap = {"asset": {"symbol": symbol}, "fetched_at": snap_fetched_at}
    try:
        return pipeline.validate_exit_quote(
            quote, snap, eval_at=None,
            proposal_notional_usd=NOTIONAL_USD, median_price_usd=median_usd)
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "reason_codes": ["validator_exception"],
                "details": {"error": "%s: %s" % (type(e).__name__, e)}}


# ------------------------------------------------------------------ main
def main():
    append_round = "--append-round" in sys.argv
    t_start = _now_iso()
    if append_round and os.path.exists(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8") as f:
            out = json.load(f)
        for s in out.get("samples", []):
            s.setdefault("round", 1)
        round_no = 1 + max([s.get("round", 1) for s in out.get("samples", [])] or [1])
        out["meta"]["rounds_note"] = (
            "Round 1: timeout HTTP 30 dtk tanpa retry + lookup proxy "
            "Hyperliquid salah kunci (\"NVDA\" bukan \"xyz:NVDA\"). "
            "Round 2+: timeout 60 dtk + 1 retry, lookup proxy diperbaiki.")
        out.setdefault("manual_transport_checks", []).append({
            "checked_at_utc": "2026-11-24 ~00:40-00:46 UTC (via curl, VM + egress yang sama)",
            "note": ("Pemeriksaan transport manual setelah round 1, untuk "
                     "membedakan kegagalan transport dari kegagalan skema vendor."),
            "checks": [
                {"target": "POST https://api.odos.xyz/soroban/quote/v2",
                 "tries": 3, "result": "HTTP 530, body 'error code: 1033' (Cloudflare) — 3/3 kali, ~4 dtk",
                 "interpretation": "endpoint tidak terjangkau dari egress VM ini (Cloudflare 1033)"},
                {"target": "POST https://trade-api.gateway.uniswap.org/v1/quote (tanpa x-api-key)",
                 "tries": 1, "result": "HTTP 401 {\"errorCode\":\"Unauthorized\",\"detail\":\"Unauthenticated api key or session\"}",
                 "interpretation": "definitif: Trading API wajib API key — jalur tanpa key mati di auth"},
                {"target": "GET https://aggregator-api.kyberswap.com/base/api/v1/routes (NVDAc $10k)",
                 "tries": 2, "result": "HTTP 429 {\"message\":\"Forbidden\",\"status\":429} — 2/2 kali",
                 "interpretation": "rate-limit dari sisi Kyber/egress untuk pair NVDAc; AAPLc sempat 200 di round 1"},
            ]})
    else:
        round_no = 1
        out = {
        "meta": {
            "probe_date": DATE_TAG,
            "probe_started_at_utc": t_start,
            "plan": "docs/scope1-rencana-eksekusi-2026-11-24.md §2.1, §2.1b, §2.3, §2.4",
            "validator": "pipeline.validate_exit_quote (pipeline.py:242-502)",
            "notional_usd": NOTIONAL_USD,
            "direction": "SELL",
            "token_out": USDC_NATIVE,
            "chain": "base (8453)",
            "eval_window_sec": config.QUOTE_MAX_AGE_SEC,
            "cross_check_spec": {
                "primary_predeclared": "quote vendor LAIN untuk pair/arah/ukuran sama",
                "fallback_predeclared": ("NAV-implied (Coinbase nav_price, "
                                         "sudah multiplier-adjusted) + proxy "
                                         "Hyperliquid xyz — keduanya REFERENSI, "
                                         "bukan harga eksekusi"),
                "formula": "|P_implied_execution - P_ref| / P_ref x 100 <= 1%",
                "P_implied_execution": "min-out / amount_in (harga terburuk yang dikomitmenkan vendor)",
                "note": ("Cross-check §2.1b membandingkan harga eksekusi "
                         "YANG DIKOMITMENKAN (min-out). Bila vendor tidak "
                         "memberi min-out, cross-check komitmen TIDAK DAPAT "
                         "dihitung — perbandingan harga indikatif antar "
                         "vendor/referensi dicatat terpisah dengan label "
                         "INDIKATIF SAJA, bukan sebagai cross-check §2.1b."),
            },
            "expiry_rule": ("expires_at WAJIB provenance semantik vendor; "
                            "DILARANG dibentuk dari jam lokal (now + TTL)."),
            "no_key": True,
            "excluded_this_run": "0x permit2/v2 + 1inch v6 (butuh key; key belum diterima)",
        },
        "pinned_block": None,
        "references": {},
        "samples": [],
    }

    # Block pin (fetch_block, RPC publik) — jendela evaluasi yang sama.
    block, block_method = _safe_fetch_block()
    out["pinned_block"] = block
    out.setdefault("pinned_block_rounds", {})[str(round_no)] = block

    # Referensi fallback (R6): NAV-implied + proxy — diuji ketersediaannya.
    cb, cb_method = _safe_fetch_coinbase_tokens()
    nav = {}
    if cb.get("ok"):
        for t in cb.get("tokens", []):
            addr = (t.get("contract_address") or "").lower()
            for sym in TOKENS:
                if addr == config.TOKENS[sym]["token_address"].lower():
                    nav[sym] = {
                        "nav_price": t.get("nav_price"),
                        "nav_price_updated_at": t.get("nav_price_updated_at"),
                        "multiplier": t.get("multiplier"),
                        "note": "nav_price SUDAH multiplier-adjusted (§3 koreksi 1)",
                    }
    hl, hl_method = _safe_fetch_hyperliquid_proxy("xyz")
    proxy = {}
    if hl.get("ok"):
        for sym in TOKENS:
            # KOREKSI round 2: adapter mengunci instrumen dengan NAMA LENGKAP
            # ("xyz:NVDA"), bukan "NVDA" saja. Round 1 salah lookup ("NVDA")
            # sehingga proxy tercatat tidak tersedia padahal fetch sukses.
            inst = config.TOKENS[sym]["proxy_instrument"]  # xyz:NVDA / xyz:AAPL
            row = hl.get("instruments", {}).get(inst)
            if row:
                proxy[sym] = {"markPx": row.get("markPx"),
                              "oraclePx": row.get("oraclePx"),
                              "instrument": inst,
                              "note": "UNDERLYING EQUITY PERP PROXY, bukan harga token"}
    out["references"] = {
        "fetch_method": {"coinbase": cb_method, "hyperliquid": hl_method,
                         "block": block_method,
                         "note": ("probe-local = adapter rusak saat round itu "
                                  "(edit konkuren S1 merujuk config yang belum "
                                  "ada); endpoint + bentuk respons sama dengan adapter")},
        "nav_implied": {"ok": bool(cb.get("ok")), "tokens_found": sorted(nav.keys()),
                        "fetched_at": cb.get("fetched_at"),
                        "source": cb.get("source"), "error": cb.get("error"),
                        "per_token": nav,
                        "label": "REFERENSI (bukan harga eksekusi)"},
        "hyperliquid_proxy_xyz": {"ok": bool(hl.get("ok")), "tokens_found": sorted(proxy.keys()),
                                  "fetched_at": hl.get("fetched_at"),
                                  "source": hl.get("source"), "error": hl.get("error"),
                                  "per_token": proxy,
                                  "label": "REFERENSI (bukan harga eksekusi)"},
    }
    out.setdefault("reference_rounds", {})[str(round_no)] = out["references"]

    for symbol in TOKENS:
        tok = config.TOKENS[symbol]
        median_usd, dex_res, _prices = _median_dexscreener_usdc(tok["token_address"])
        spot = median_usd
        if spot is None:
            out["samples"].append({
                "vendor": "ALL", "symbol": symbol, "round": round_no,
                "error": "no_dexscreener_median_for_sizing",
                "dexscreener": dex_res})
            continue
        amount_in_base, amount_in_tokens = _amount_in_for_notional(
            spot, tok["decimals"])
        snap_fetched_at = _now_iso()

        # --- Odos ---
        r = probe_odos(tok["token_address"], amount_in_base)
        a = assess("odos", symbol, r["json"], r["http_status"],
                   amount_in_base, amount_in_tokens, spot)
        a["validator_faithful_mapping"] = validator_faithful(
            a, symbol, median_usd, snap_fetched_at)
        a["validator_generous_hypothetical"] = validator_generous(
            a, symbol, median_usd, snap_fetched_at)
        out["samples"].append({
            "vendor": "odos", "vendor_endpoint": "POST https://api.odos.xyz/soroban/quote/v2",
            "round": round_no,
            "symbol": symbol, "requested_at_utc": snap_fetched_at,
            "amount_in_base_units": amount_in_base,
            "amount_in_tokens": amount_in_tokens,
            "spot_median_dexscreener_usd": spot,
            "computed_notional_usd": amount_in_tokens * spot,
            "http_status": r["http_status"], "http_error": r["error"],
            "http_attempts": r.get("attempts"),
            "raw_response": r["json"] if r["json"] is not None else r["raw_text"],
            "assessment": a,
            "cross_check": None,  # diisi setelah semua vendor selesai
        })

        # --- KyberSwap ---
        r = probe_kyber(tok["token_address"], amount_in_base)
        a = assess("kyber", symbol, r["json"], r["http_status"],
                   amount_in_base, amount_in_tokens, spot)
        a["validator_faithful_mapping"] = validator_faithful(
            a, symbol, median_usd, snap_fetched_at)
        a["validator_generous_hypothetical"] = validator_generous(
            a, symbol, median_usd, snap_fetched_at)
        out["samples"].append({
            "vendor": "kyber", "vendor_endpoint": "GET https://aggregator-api.kyberswap.com/base/api/v1/routes",
            "round": round_no,
            "symbol": symbol, "requested_at_utc": snap_fetched_at,
            "amount_in_base_units": amount_in_base,
            "amount_in_tokens": amount_in_tokens,
            "spot_median_dexscreener_usd": spot,
            "computed_notional_usd": amount_in_tokens * spot,
            "http_status": r["http_status"], "http_error": r["error"],
            "http_attempts": r.get("attempts"),
            "raw_response": r["json"] if r["json"] is not None else r["raw_text"],
            "assessment": a,
            "cross_check": None,
        })

        # --- Uniswap Routing API (tanpa key) ---
        r = probe_uniswap(tok["token_address"], amount_in_base)
        prim = r["primary_trade_api"]
        a = assess("uniswap", symbol, prim["json"], prim["http_status"],
                   amount_in_base, amount_in_tokens, spot)
        a["validator_faithful_mapping"] = validator_faithful(
            a, symbol, median_usd, snap_fetched_at)
        a["validator_generous_hypothetical"] = validator_generous(
            a, symbol, median_usd, snap_fetched_at)
        out["samples"].append({
            "vendor": "uniswap", "vendor_endpoint": "POST https://trade-api.gateway.uniswap.org/v1/quote (+ legacy GET https://api.uniswap.org/v1/quote)",
            "round": round_no,
            "symbol": symbol, "requested_at_utc": snap_fetched_at,
            "amount_in_base_units": amount_in_base,
            "amount_in_tokens": amount_in_tokens,
            "spot_median_dexscreener_usd": spot,
            "computed_notional_usd": amount_in_tokens * spot,
            "http_status": prim["http_status"], "http_error": prim["error"],
            "http_attempts": prim.get("attempts"),
            "raw_response": prim["json"] if prim["json"] is not None else prim["raw_text"],
            "raw_response_legacy_routing_api": (
                r["legacy_routing_api"]["json"]
                if r["legacy_routing_api"]["json"] is not None
                else r["legacy_routing_api"]["raw_text"]),
            "http_status_legacy_routing_api": r["legacy_routing_api"]["http_status"],
            "http_attempts_legacy_routing_api": r["legacy_routing_api"].get("attempts"),
            "assessment": a,
            "cross_check": None,
        })

    # --- Cross-check per sampel (setelah semua vendor selesai) ---
    # Hanya sampel round ini yang dihitung (ulang) — sampel round lama
    # menyimpan cross-check dari referensi round-nya sendiri.
    round_samples = [s for s in out["samples"] if s.get("round", 1) == round_no]
    by_token = {}
    for s in round_samples:
        by_token.setdefault(s["symbol"], {})[s["vendor"]] = s
    for symbol, vendors in by_token.items():
        nav_px = None
        try:
            nav_px = float(out["references"]["nav_implied"]["per_token"][symbol]["nav_price"])
        except (KeyError, TypeError, ValueError):
            nav_px = None
        px_px = None
        try:
            px_px = float(out["references"]["hyperliquid_proxy_xyz"]["per_token"][symbol]["markPx"])
        except (KeyError, TypeError, ValueError):
            px_px = None
        for vendor, s in vendors.items():
            if "assessment" not in s:
                continue
            a = s["assessment"]
            exp = a["expected_out_usdc"]
            cc = {
                "comparator_primary": "quote vendor LAIN (pair/arah/ukuran sama)",
                "comparator_fallback_nav_implied_usd": nav_px,
                "comparator_fallback_proxy_markPx_usd": px_px,
                "direction": "SELL", "size_usd": NOTIONAL_USD,
                "window_sec": config.QUOTE_MAX_AGE_SEC,
                "pinned_block": (out["pinned_block"] or {}).get("block_number"),
                "fee_note": a["fee_note"],
                "committed_cross_check_applicable": False,
                "committed_cross_check_reason": (
                    "TIDAK DAPAT dihitung: vendor tidak memberi min-out, "
                    "sehingga P_implied_execution = min-out/amount_in "
                    "tidak ada. Rumus §2.1b butuh harga yang DIKOMITMENKAN."),
                "committed_diff_pct": None,
                "indicative_comparisons": [],
                "indicative_note": ("Perbandingan di bawah ini memakai harga "
                                    "INDIKATIF (expected-out/amount_in), BUKAN "
                                    "harga eksekusi yang dikomitmenkan. Bukan "
                                    "cross-check §2.1b; tidak dapat meloloskan "
                                    "sampel ke bar 10."),
            }
            if exp is not None:
                p_ind = exp / s["amount_in_tokens"]
                for name, ref in (("other_vendor_expected_price", None),
                                  ("nav_implied", nav_px),
                                  ("hyperliquid_proxy_xyz", px_px)):
                    if ref:
                        cc["indicative_comparisons"].append({
                            "reference": name, "ref_price_usd": ref,
                            "indicative_price_usd": p_ind,
                            "diff_pct": abs(p_ind - ref) / ref * 100.0,
                            "within_1pct": abs(p_ind - ref) / ref * 100.0 <= 1.0,
                        })
                # Primer: vendor lain (harga indikatifnya).
                others = [v for v in vendors.values()
                          if v["vendor"] != vendor
                          and v["assessment"]["expected_out_usdc"] is not None]
                for o in others:
                    p_o = o["assessment"]["expected_out_usdc"] / o["amount_in_tokens"]
                    cc["indicative_comparisons"].append({
                        "reference": "other_vendor:%s_expected_price" % o["vendor"],
                        "ref_price_usd": p_o,
                        "indicative_price_usd": p_ind,
                        "diff_pct": abs(p_ind - p_o) / p_o * 100.0,
                        "within_1pct": abs(p_ind - p_o) / p_o * 100.0 <= 1.0,
                    })
            s["cross_check"] = cc

    # --- Ringkasan ---
    firm = [s for s in out["samples"]
            if s.get("assessment", {}).get("verdict") == "FIRM"]
    out["summary"] = {
        "probe_finished_at_utc": _now_iso(),
        "rounds": sorted({s.get("round", 1) for s in out["samples"]}),
        "samples_total": len(out["samples"]),
        "samples_firm": len(firm),
        "per_round": {
            str(rn): {"samples": sum(1 for s in out["samples"] if s.get("round", 1) == rn),
                      "firm": sum(1 for s in out["samples"]
                                  if s.get("round", 1) == rn
                                  and s.get("assessment", {}).get("verdict") == "FIRM"),
                      "fallback_nav_ok": out.get("reference_rounds", {}).get(str(rn), {}).get("nav_implied", {}).get("ok"),
                      "fallback_proxy_ok": out.get("reference_rounds", {}).get(str(rn), {}).get("hyperliquid_proxy_xyz", {}).get("ok"),
                      "fallback_proxy_tokens": out.get("reference_rounds", {}).get(str(rn), {}).get("hyperliquid_proxy_xyz", {}).get("tokens_found")}
            for rn in sorted({s.get("round", 1) for s in out["samples"]})},
        "per_vendor": {
            v: {"samples": sum(1 for s in out["samples"] if s["vendor"] == v),
                "firm": sum(1 for s in out["samples"]
                            if s["vendor"] == v and s.get("assessment", {}).get("verdict") == "FIRM"),
                "verdict": ("FIRM" if any(
                    s["vendor"] == v and s.get("assessment", {}).get("verdict") == "FIRM"
                    for s in out["samples"]) else "TIDAK_FIRM")}
            for v in ("odos", "kyber", "uniswap")},
        "fallback_references_available": {
            "nav_implied": out["references"]["nav_implied"]["ok"],
            "hyperliquid_proxy_xyz": out["references"]["hyperliquid_proxy_xyz"]["ok"],
        },
        "overall": ("ADA kandidat FIRM" if firm else
                    "TIDAK ADA kandidat yang lolos — hasil sah (§2.5)"),
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=False)
    print("wrote %s" % OUT_PATH)
    print(json.dumps(out["summary"], indent=2))


if __name__ == "__main__":
    main()
