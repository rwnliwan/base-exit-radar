#!/usr/bin/env python3
"""S2 probe BER-KEY jalur quote FIRM — 0x Swap API v2 + 1inch Swap API v6.

Tugas S2 (rencana Scope 1 v1.1, 24 Nov 2026, §2.1/§2.1b/§2.3/§2.4):
minta SELL quote NVDAc->USDC dan AAPLc->USDC pada notional $10.000
(= config.SIMULATION_NOTIONAL_USD) dari 0x + 1inch dengan API key
terdaftar, rekam respons MENTAH, nilai tiap respons field demi field
terhadap definisi FIRM yang dibekukan (§2.1, pipeline.validate_exit_quote).

ATURAN YANG DIPATUHI SKRIP INI:
- Kredensial HANYA via konektor terdaftar (custom.0x / custom.1inch)
  lewat dynamic_credentials (surrogate hsurr:). TIDAK ADA key di file,
  env, log, atau output ini. Respons vendor tidak mengandung key.
- TIDAK ADA signing / broadcast / dana bergerak. Endpoint /quote hanya
  mengembalikan data + transaksi siap-sign; skrip TIDAK PERNAH
  menandatangani atau mengirim transaksi apa pun.
- `expires_at` TIDAK PERNAH dibentuk dari jam lokal (now + TTL). Bila
  vendor tidak memberi semantik expiry, field itu dicatat ABSENT dan
  quote TIDAK dapat diklasifikasikan firm.
- `amount_out_min` HANYA diisi dari field vendor (0x `minBuyAmount`).
  Expected-out vendor TIDAK PERNAH dipakai seolah-olah min-out.
  Lantai yang dihitung klien dari toleransi slippage dicatat terpisah
  dengan label eksplisit "client-derived floor (NOT vendor-committed)".
- `kind` TIDAK PERNAH diasumsikan "firm". Bila vendor tidak memberi
  label kind, dicatat ABSENT.
- Alamat USDC Base yang dipakai: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
  (native Circle, config.USDC_NATIVE_BASE). Alamat lama berakhiran
  bd029029 SALAH dan TIDAK PERNAH dipakai di sini.
- amount_in dihitung dari median spot DexScreener saat probe (ceil ke
  base unit, 8 desimal) agar notional hitung >= $10.000; cara hitung
  dicatat per sampel.

Output: evidence/firm_quote_probes_keyed_2026-11-24.json
Hanya membaca config/adapter/pipeline (tidak mengubah kode produksi).
"""

import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import add_surrogate_to_request  # noqa: E402

import adapter  # noqa: E402  (read-only reuse: NAV, proxy, DexScreener, block)
import config  # noqa: E402
import pipeline  # noqa: E402  (hanya validate_exit_quote, read-only)

DATE_TAG = "2026-11-24"
OUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "evidence", "firm_quote_probes_keyed_%s.json" % DATE_TAG)

NOTIONAL_USD = config.SIMULATION_NOTIONAL_USD  # 10_000.0
USDC_NATIVE = config.USDC_NATIVE_BASE
WETH_BASE = "0x4200000000000000000000000000000000000006"
TOKENS = ("NVDAc", "AAPLc")
# Taker untuk quote 0x/1inch: alamat EVM taker, dibaca dari env PROBE_TAKER.
# Quote read-only — hanya mengembalikan data + tx siap-sign, tidak ada dana
# bergerak. Alamat pribadi tidak disimpan di repo (Rules 6.5); set env
# sebelum menjalankan probe ber-key.
TAKER = os.environ.get("PROBE_TAKER", "")
SLIPPAGE_BPS = 50          # 0x: slippageBps
SLIPPAGE_PCT = 0.5         # 1inch: slippage (persen)
UA = {"User-Agent": config.USER_AGENT}
UA_BROWSER = {"User-Agent":
              "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")


def _http_vendor(url, provider, timeout=60, retries=1):
    """GET ber-key via konektor terdaftar (surrogate; key tidak pernah
    terlihat di sini). Kembalikan {http_status, raw_text, json, error,
    attempts}."""
    attempts = []
    last = {"http_status": None, "raw_text": "", "json": None,
            "error": "no_attempt", "attempts": attempts}
    for _ in range(retries + 1):
        import time as _time
        t0 = _time.time()
        req = urllib.request.Request(url, headers=dict(UA_BROWSER))
        if provider == "custom.0x":
            req.add_header("0x-version", "v2")
        add_surrogate_to_request(req, provider,
                                 allowed_hosts=["api.0x.org", "api.1inch.dev"])
        try:
            with urllib.request.build_opener(_NoRedirect()).open(
                    req, timeout=timeout) as r:
                text = r.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(text)
                except Exception:
                    parsed = None
                attempts.append({"http_status": r.status, "error": None,
                                 "elapsed_sec": round(_time.time() - t0, 2)})
                last = {"http_status": r.status, "raw_text": text,
                        "json": parsed, "error": None, "attempts": attempts}
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
                    "json": parsed, "error": "http_%s" % e.code,
                    "attempts": attempts}
            if e.code < 500 and e.code != 429:
                break
        except Exception as e:  # noqa: BLE001
            attempts.append({"http_status": None,
                             "error": "fetch_error:%s" % type(e).__name__,
                             "elapsed_sec": round(_time.time() - t0, 2)})
            last = {"http_status": None, "raw_text": "", "json": None,
                    "error": "fetch_error:%s" % type(e).__name__,
                    "attempts": attempts}
    return last


def _http_public(method, url, body=None, timeout=60, retries=1):
    h = dict(UA)
    attempts = []
    last = {"http_status": None, "raw_text": "", "json": None,
            "error": "no_attempt", "attempts": attempts}
    for _ in range(retries + 1):
        import time as _time
        t0 = _time.time()
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
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
                        "json": parsed, "error": None, "attempts": attempts}
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
                    "json": parsed, "error": "http_%s" % e.code,
                    "attempts": attempts}
            if e.code < 500 and e.code != 429:
                break
        except Exception as e:  # noqa: BLE001
            attempts.append({"http_status": None,
                             "error": "fetch_error:%s" % type(e).__name__,
                             "elapsed_sec": round(_time.time() - t0, 2)})
            last = {"http_status": None, "raw_text": "", "json": None,
                    "error": "fetch_error:%s" % type(e).__name__,
                    "attempts": attempts}
    return last


# ------------------------------------------------------- referensi (reuse)
def _safe_fetch_coinbase_tokens():
    try:
        return adapter.fetch_coinbase_tokens(), "adapter"
    except Exception:  # noqa: BLE001
        tokens, err = [], None
        url = config.COINBASE_API_URL
        for _ in range(10):
            r = _http_public("GET", url)
            if r["json"] is None or not isinstance(r["json"], dict):
                err = r["error"] or "http_%s" % r["http_status"]
                break
            tokens.extend(r["json"].get("tokens", []))
            nxt = r["json"].get("next_page_token")
            if not nxt:
                err = None
                break
            url = config.COINBASE_API_URL + "?page_token=" + str(nxt)
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
        r = _http_public("POST", config.HYPERLIQUID_INFO_URL,
                         {"type": "metaAndAssetCtxs", "dex": dex})
        out = {"ok": False, "instruments": {}, "fetched_at": _now_iso(),
               "source": config.HYPERLIQUID_INFO_URL + " dex=" + dex,
               "error": None}
        if r["json"] is None:
            out["error"] = r["error"] or "http_%s" % r["http_status"]
            return out, "probe-local"
        try:
            meta, ctxs = r["json"][0], r["json"][1]
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
        r = _http_public("GET", url)
        if r["json"] is None:
            return {"ok": False, "pairs": [], "fetched_at": _now_iso(),
                    "source": url, "error": r["error"]}, "probe-local"
        pairs = r["json"].get("pairs", []) if isinstance(r["json"], dict) else []
        return {"ok": True, "pairs": pairs, "fetched_at": _now_iso(),
                "source": url, "error": None}, "probe-local"


def _safe_fetch_block():
    try:
        return adapter.fetch_block(), "adapter"
    except Exception:  # noqa: BLE001
        out = {"ok": False, "block_number": None, "block_hash": None,
               "fetched_at": _now_iso(), "source": "eth_blockNumber",
               "error": None}
        num = _http_public("POST", config.BASE_RPC_URLS[0],
                           {"jsonrpc": "2.0", "method": "eth_blockNumber",
                            "params": [], "id": 1})
        if num["json"] is None or "result" not in num["json"]:
            out["error"] = num["error"] or "block_bad_number"
            return out, "probe-local"
        try:
            block_number = int(num["json"]["result"], 16)
        except (TypeError, ValueError):
            out["error"] = "block_bad_number"
            return out, "probe-local"
        blk = _http_public("POST", config.BASE_RPC_URLS[0],
                           {"jsonrpc": "2.0", "method": "eth_getBlockByNumber",
                            "params": [num["json"]["result"], False], "id": 2})
        if blk["json"] is None or not isinstance(
                (blk["json"].get("result") or {}).get("hash"), str):
            out["error"] = blk["error"] or "block_bad_hash"
            return out, "probe-local"
        out["block_number"] = block_number
        out["block_hash"] = blk["result"]["hash"]
        out["ok"] = True
        return out, "probe-local"


def _median_dexscreener_usdc(token_addr):
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
            if qt.lower() == USDC_NATIVE.lower() and px \
                    and math.isfinite(px) and px > 0:
                prices.append(px)
    prices.sort()
    if not prices:
        return None, res, []
    n = len(prices)
    med = prices[n // 2] if n % 2 == 1 \
        else (prices[n // 2 - 1] + prices[n // 2]) / 2.0
    return med, res, prices


def _amount_in_for_notional(spot_usd, decimals):
    tokens = NOTIONAL_USD / spot_usd
    base = math.ceil(tokens * (10 ** decimals))
    return base, base / (10 ** decimals)


# ------------------------------------------------------------------ vendor
def probe_0x_price(token_addr, amount_in_base):
    url = ("https://api.0x.org/swap/allowance-holder/price"
           "?chainId=8453"
           "&sellToken=%s&buyToken=%s&sellAmount=%s"
           % (token_addr, USDC_NATIVE, amount_in_base))
    return _http_vendor(url, "custom.0x")


def probe_0x_quote(token_addr, amount_in_base, endpoint="allowance-holder"):
    url = ("https://api.0x.org/swap/%s/quote"
           "?chainId=8453"
           "&sellToken=%s&buyToken=%s&sellAmount=%s"
           "&taker=%s&slippageBps=%s"
           % (endpoint, token_addr, USDC_NATIVE, amount_in_base,
              TAKER, SLIPPAGE_BPS))
    return _http_vendor(url, "custom.0x")


def probe_1inch_quote(token_addr, amount_in_base):
    url = ("https://api.1inch.dev/swap/v6.0/8453/quote"
           "?src=%s&dst=%s&amount=%s"
           % (token_addr, USDC_NATIVE, amount_in_base))
    return _http_vendor(url, "custom.1inch")


def probe_1inch_swap(token_addr, amount_in_base):
    url = ("https://api.1inch.dev/swap/v6.0/8453/swap"
           "?src=%s&dst=%s&amount=%s&from=%s&slippage=%s"
           % (token_addr, USDC_NATIVE, amount_in_base, TAKER, SLIPPAGE_PCT))
    return _http_vendor(url, "custom.1inch")


def _find_expiry_keys(obj, prefix=""):
    """Cari kunci bertema expiry/deadline di respons mentah (rekursif)."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(w in kl for w in ("expir", "deadline", "valid", "ttl",
                                     "timeout", "until")):
                hits.append({"field": prefix + str(k), "value": v})
            hits.extend(_find_expiry_keys(v, prefix + str(k) + "."))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(_find_expiry_keys(v, "%s[%d]." % (prefix, i)))
    return hits


def _route_summary_0x(body):
    if not isinstance(body, dict):
        return None
    route = body.get("route") or {}
    fills = route.get("fills") or []
    return {"sources": [f.get("source") for f in fills if isinstance(f, dict)],
            "fills": fills,
            "tokens": route.get("tokens")}


def _pct_diff(a, b):
    if a is None or b is None or b == 0:
        return None
    return abs(a - b) / abs(b) * 100.0


def assess(vendor, kind_call, symbol, resp, amount_in_base, amount_in_tokens,
           median_usd, nav_px, proxy_px, other_vendor_expected_price):
    """Nilai satu respons mentah terhadap definisi §2.1.

    expected_out / min_out / price_impact / slippage dipisah (§2.1b).
    `expires_at` hanya dari semantik vendor; bila absent -> ABSENT.
    """
    body = resp.get("json")
    http_status = resp.get("http_status")
    a = {"vendor": vendor, "call": kind_call, "symbol": symbol,
         "http_status": http_status, "error": resp.get("error"),
         "attempts": resp.get("attempts"),
         "amount_in_base_units": amount_in_base,
         "amount_in_tokens": amount_in_tokens,
         "median_dexscreener_usd": median_usd,
         "notional_calc_usd": (amount_in_tokens * median_usd
                               if median_usd else None),
         "raw_response": body,
         "raw_text_truncated": (resp.get("raw_text") or "")[:2000],
         "expiry_keys_found": _find_expiry_keys(body) if body else [],
         "kind_vendor_label": None,
         "expected_out_usdc": None, "expected_out_field": None,
         "min_out_usdc": None, "min_out_field": None,
         "price_impact_pct": None, "price_impact_field": None,
         "slippage_requested_pct": SLIPPAGE_PCT,
         "slippage_field": None,
         "implied_price_expected": None, "implied_price_min_out": None,
         "fee_note": None, "route": None,
         "expires_at": None, "expires_at_provenance": None,
         "verdict": None, "verdict_reason": None,
         "validator_faithful": None, "cross_check": None}
    if body is None or not isinstance(body, dict):
        a["verdict"] = "TIDAK_FIRM"
        a["verdict_reason"] = "no_parseable_response"
        return a
    if http_status != 200:
        a["verdict"] = "TIDAK_FIRM"
        a["verdict_reason"] = "http_%s" % http_status
        a["error_body"] = body
        return a

    if vendor == "0x":
        # buyAmount = expected-out (USDC base units, 6 desimal);
        # minBuyAmount = lantai revert (USDC base units).
        try:
            buy = int(body.get("buyAmount")) / 1e6
        except (TypeError, ValueError):
            buy = None
        try:
            mn = int(body.get("minBuyAmount")) / 1e6
        except (TypeError, ValueError):
            mn = None
        a["expected_out_usdc"] = buy
        a["expected_out_field"] = "buyAmount"
        a["min_out_usdc"] = mn
        a["min_out_field"] = "minBuyAmount" if mn is not None else None
        a["liquidity_available"] = body.get("liquidityAvailable")
        a["route"] = _route_summary_0x(body)
        a["fee_note"] = ("fees object present (see raw); gasFee/totalNetworkFee "
                         "reported separately; buyAmount is expected output "
                         "before the minBuyAmount revert bound applies")
        if kind_call == "quote":
            tx = body.get("transaction") or {}
            a["tx_ready_to_sign"] = {
                "to": tx.get("to"), "data_present": bool(tx.get("data")),
                "data_len": len(tx.get("data") or ""),
                "gas": tx.get("gas"), "value": tx.get("value")}
            a["slippage_field"] = "slippageBps request param = %s" % SLIPPAGE_BPS
        # 0x tidak memberi label kind di respons price/quote.
        a["kind_vendor_label"] = None
        a["expires_at_provenance"] = (
            "ABSENT: tidak ada field expiry/deadline/valid-until di respons "
            "mentah (pencarian rekursif: %s). 0x menamai endpoint Permit2 "
            "'firm quote' di dokumentasi, tetapi responsnya sendiri tidak "
            "membawa semantik expiry." % (a["expiry_keys_found"],))
    elif vendor == "1inch":
        if kind_call == "quote":
            try:
                dst = int(body.get("dstAmount")) / 1e6
            except (TypeError, ValueError):
                dst = None
            a["expected_out_usdc"] = dst
            a["expected_out_field"] = "dstAmount"
            a["min_out_usdc"] = None
            a["min_out_field"] = None
            a["fee_note"] = ("dstAmount = expected output indikatif; /quote "
                             "tidak memberi min-out, expiry, atau tx")
        else:  # swap
            try:
                dst = int(body.get("dstAmount")) / 1e6
            except (TypeError, ValueError):
                dst = None
            a["expected_out_usdc"] = dst
            a["expected_out_field"] = "dstAmount"
            a["min_out_usdc"] = None
            a["min_out_field"] = None
            tx = body.get("tx") or {}
            a["tx_ready_to_sign"] = {
                "to": tx.get("to"), "data_present": bool(tx.get("data")),
                "data_len": len(tx.get("data") or ""),
                "gas": tx.get("gas"), "value": tx.get("value")}
            a["protocols"] = body.get("protocols")
            a["slippage_field"] = "slippage request param = %s%%" % SLIPPAGE_PCT
            a["fee_note"] = ("dstAmount = expected output; /swap tidak "
                             "memberi min-out (tidak ada field minAmountOut "
                             "atau sejenis) dan tidak memberi expiry")
        a["kind_vendor_label"] = None
        a["expires_at_provenance"] = (
            "ABSENT: tidak ada field expiry/deadline/valid-until di respons "
            "mentah (pencarian rekursif: %s). Endpoint /quote 1inch "
            "bersifat indikatif menurut dokumentasi vendor."
            % (a["expiry_keys_found"],))

    # Harga implisit (USDC per token).
    if a["expected_out_usdc"] is not None and amount_in_tokens:
        a["implied_price_expected"] = a["expected_out_usdc"] / amount_in_tokens
    if a["min_out_usdc"] is not None and amount_in_tokens:
        a["implied_price_min_out"] = a["min_out_usdc"] / amount_in_tokens
    # Price impact = expected-out vs spot median (per §2.1b, dipisah).
    if a["expected_out_usdc"] is not None and median_usd:
        spot_out = amount_in_tokens * median_usd
        a["price_impact_pct"] = ((a["expected_out_usdc"] - spot_out)
                                 / spot_out * 100.0) if spot_out else None
        a["price_impact_basis"] = "expected-out vs median DexScreener (spot)"
    # Slippage realisasi tidak dapat dihitung dari satu quote (butuh
    # realisasi); yang ada hanya toleransi yang diminta.
    a["slippage_realised_pct"] = None
    a["slippage_note"] = ("toleransi yang diminta klien (%s%%) adalah "
                          "parameter permintaan, BUKAN realisasi dan BUKAN "
                          "komitmen vendor" % SLIPPAGE_PCT)

    # Cross-check §2.1b (per sampel).
    cc = {"formula": "|P_implied_execution - P_ref| / P_ref * 100 <= 1%",
          "p_implied_execution": a["implied_price_min_out"],
          "p_implied_execution_basis": "min-out / amount_in (harga terburuk "
                                       "yang dikomitmenkan vendor)",
          "primary_other_vendor": None, "nav_implied": None,
          "proxy_hyperliquid_xyz": None,
          "commitment_cross_check_pct": None,
          "commitment_cross_check_pass": None,
          "indicative_cross_check": {}}
    if a["implied_price_min_out"] is not None:
        if other_vendor_expected_price is not None:
            cc["primary_other_vendor"] = {
                "ref_price": other_vendor_expected_price,
                "diff_pct": _pct_diff(a["implied_price_min_out"],
                                      other_vendor_expected_price),
                "note": "harga INDIKATIF vendor lain (expected-out), bukan "
                        "min-out — perbandingan komitmen-vs-indikatif, "
                        "dilabeli demikian"}
            cc["commitment_cross_check_pct"] = cc["primary_other_vendor"]["diff_pct"]
            cc["commitment_cross_check_pass"] = (
                cc["commitment_cross_check_pct"] is not None
                and cc["commitment_cross_check_pct"] <= 1.0)
        if nav_px is not None:
            cc["nav_implied"] = {"ref_price": nav_px,
                                 "diff_pct": _pct_diff(
                                     a["implied_price_min_out"], nav_px)}
        if proxy_px is not None:
            cc["proxy_hyperliquid_xyz"] = {
                "ref_price": proxy_px,
                "diff_pct": _pct_diff(a["implied_price_min_out"], proxy_px)}
    # Perbandingan indikatif (expected-price vs referensi) — INDIKATIF SAJA.
    if a["implied_price_expected"] is not None:
        for name, ref in (("other_vendor_expected", other_vendor_expected_price),
                          ("nav_implied", nav_px),
                          ("proxy_hyperliquid_xyz", proxy_px)):
            if ref is not None:
                cc["indicative_cross_check"][name] = {
                    "ref_price": ref,
                    "diff_pct": _pct_diff(a["implied_price_expected"], ref)}
    a["cross_check"] = cc

    # Verdict §2.1: kind label + amount_out_min + expires_at wajib.
    missing = []
    if a["kind_vendor_label"] is None:
        missing.append("kind (tidak ada label firm/executable/guaranteed "
                       "di respons vendor)")
    if a["min_out_usdc"] is None:
        missing.append("amount_out_min")
    if a["expires_at"] is None:
        missing.append("expires_at (tidak ada semantik expiry vendor)")
    if missing:
        a["verdict"] = "TIDAK_FIRM"
        a["verdict_reason"] = "missing_fields: " + "; ".join(missing)
    else:
        a["verdict"] = "FIRM_CANDIDATE"
        a["verdict_reason"] = "semua field §2.1 hadir (perlu validator + cross-check)"

    # Validator faithful: petakan jujur (kind='firm' HANYA bila vendor
    # memberi min-out; expires_at TETAP absent -> validator harus menolak
    # missing_fields [expires_at]). Bila min-out absent, pemetaan jujur
    # tidak dapat dibangun sama sekali (kind missing -> kind_missing).
    a["validator_faithful"] = _validator_faithful(
        a, symbol, median_usd)
    return a


def _validator_faithful(a, symbol, median_usd):
    """Jalankan pipeline.validate_exit_quote atas pemetaan jujur.

    quoted_at dipakai = waktu evaluasi (now) karena vendor tidak memberi
    timestamp quote; expires_at TIDAK diisi (absent) — validator harus
    menolaknya. Ini pemetaan yang jujur, bukan pemetaan yang lolos.
    """
    if a["min_out_usdc"] is None:
        return {"status": "invalid",
                "reason_codes": ["exit_quote_kind_missing"],
                "details": {"note": "no vendor min-out and no vendor kind "
                            "label; no faithful firm mapping exists"}}
    quote = {"chain": config.CHAIN,
             "token_in": config.TOKENS[symbol]["token_address"],
             "token_out": USDC_NATIVE,
             "side": "SELL",
             "amount_in": a["amount_in_tokens"],
             "source": a["vendor"],
             "venue": a["vendor"],
             "kind": "firm",
             "amount_out_min": a["min_out_usdc"],
             "quoted_at": _now_iso(),
             "expires_at": None,
             "notional_usd": NOTIONAL_USD}
    snap = {"fetched_at": _now_iso(),
            "asset": {"symbol": symbol}}
    try:
        return pipeline.validate_exit_quote(
            quote, snap, proposal_notional_usd=NOTIONAL_USD,
            median_price_usd=median_usd)
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "reason_codes": ["validator_exception"],
                "details": {"error": "%s: %s" % (type(e).__name__, e)}}


def main():
    if not TAKER:
        raise SystemExit("Set PROBE_TAKER env ke alamat EVM taker untuk probe ber-key.")
    out = {"probe": "S2 keyed firm-quote probes 0x + 1inch",
           "date": DATE_TAG,
           "generated_at_utc": _now_iso(),
           "plan": "docs/scope1-rencana-eksekusi-2026-11-24.md §2.1, §2.1b, "
                   "§2.3, §2.4, §2.5",
           "definition_doc": "docs/firm-quote-definition-2026-11-24.md",
           "direction": "SELL", "notional_usd": NOTIONAL_USD,
           "chain": "base (8453)",
           "usdc_address": USDC_NATIVE,
           "usdc_address_note": "native Circle; alamat lama bd029029 SALAH, "
                                "tidak dipakai",
           "weth_address": WETH_BASE,
           "taker": TAKER,
           "taker_note": "taker dari env PROBE_TAKER; quote read-only, "
                         "tidak ada signing/broadcast/dana bergerak",
           "slippage_requested_pct": SLIPPAGE_PCT,
           "slippage_requested_bps_0x": SLIPPAGE_BPS,
           "cross_check_predeclared": {
               "primary": "quote vendor LAIN untuk pair/arah/ukuran sama "
                          "(0x <-> 1inch)",
               "fallback": "NAV-implied (Coinbase nav_price, sudah "
                           "multiplier-adjusted) + proxy Hyperliquid xyz",
               "formula": "|P_implied_execution - P_ref| / P_ref * 100 <= 1%",
               "p_implied_execution": "min-out / amount_in"},
           "samples": [], "references": {}, "block_pin": None,
           "summary": {}}

    # Block pin + referensi fallback (sebelum probe vendor).
    block, block_method = _safe_fetch_block()
    out["block_pin"] = dict(block)
    out["block_pin"]["fetch_method"] = block_method

    cb, cb_method = _safe_fetch_coinbase_tokens()
    nav = {}
    if cb.get("ok"):
        for s in TOKENS:
            t = adapter.find_token(cb.get("tokens", []),
                                   config.TOKENS[s]["token_address"]) or {}
            nav[s] = {"nav_price": t.get("nav_price"),
                      "nav_price_updated_at": t.get("nav_price_updated_at"),
                      "note": "nav_price SUDAH multiplier-adjusted (§3 koreksi 1)"}
    out["references"]["nav_implied"] = {
        "ok": bool(cb.get("ok")), "fetch_method": cb_method,
        "per_token": nav, "error": cb.get("error")}
    hl, hl_method = _safe_fetch_hyperliquid_proxy("xyz")
    proxy = {}
    if hl.get("ok"):
        inst = hl.get("instruments", {})
        for s in TOKENS:
            name = config.TOKENS[s].get("proxy_instrument")
            px = (inst.get(name) or {}).get("markPx") if name else None
            proxy[s] = {"instrument": name, "markPx": px,
                        "oraclePx": (inst.get(name) or {}).get("oraclePx")
                        if name else None}
    out["references"]["hyperliquid_proxy_xyz"] = {
        "ok": bool(hl.get("ok")), "fetch_method": hl_method,
        "per_token": proxy, "error": hl.get("error"),
        "note": "proxy underlying equity perp, BUKAN harga token Base"}

    # Spot median + amount_in per token (cara hitung dicatat).
    spot = {}
    for s in TOKENS:
        med, _res, prices = _median_dexscreener_usdc(
            config.TOKENS[s]["token_address"])
        dec = config.TOKENS[s]["decimals"]
        amt_base, amt_tok = _amount_in_for_notional(med, dec) \
            if med else (None, None)
        spot[s] = {"token_address": config.TOKENS[s]["token_address"],
                   "decimals": dec,
                   "median_dexscreener_usdc": med,
                   "median_pool_prices_usd": prices,
                   "amount_in_base_units": amt_base,
                   "amount_in_tokens": amt_tok,
                   "amount_in_method": "ceil(10000 / median_spot * 10^decimals) "
                                       "agar notional hitung >= $10.000",
                   "notional_calc_usd": amt_tok * med if med and amt_tok else None}
    out["spot_and_amount_in"] = spot

    # Probe vendor per token: 0x price, 0x quote, 1inch quote, 1inch swap.
    raw_expected = {}  # (vendor, symbol) -> implied expected price
    pending = []
    for s in TOKENS:
        amt_base = spot[s]["amount_in_base_units"]
        amt_tok = spot[s]["amount_in_tokens"]
        if amt_base is None:
            out["samples"].append({"vendor": "ALL", "symbol": s,
                                   "verdict": "TIDAK_FIRM",
                                   "verdict_reason": "no_spot_median"})
            continue
        addr = config.TOKENS[s]["token_address"]
        med = spot[s]["median_dexscreener_usdc"]
        nav_px = None
        try:
            nav_px = float(nav[s]["nav_price"]) if nav[s].get("nav_price") else None
        except (TypeError, ValueError):
            nav_px = None
        px_px = None
        try:
            px_px = float(proxy[s]["markPx"]) if proxy[s].get("markPx") else None
        except (TypeError, ValueError):
            px_px = None
        # 0x price (indikatif) + 0x quote (firm candidate).
        r_price = probe_0x_price(addr, amt_base)
        r_quote = probe_0x_quote(addr, amt_base)
        # Fallback permit2 bila allowance-holder quote gagal auth/route.
        permit2_resp = None
        if r_quote.get("http_status") != 200:
            permit2_resp = probe_0x_quote(addr, amt_base, endpoint="permit2")
        # 1inch quote (indikatif) + swap (tx siap-sign).
        r_iq = probe_1inch_quote(addr, amt_base)
        r_is = probe_1inch_swap(addr, amt_base)
        for (vendor, call, resp) in (
                ("0x", "price", r_price),
                ("0x", "quote", r_quote),
                ("1inch", "quote", r_iq),
                ("1inch", "swap", r_is)):
            pending.append((vendor, call, s, resp, amt_base, amt_tok, med,
                            nav_px, px_px))
        # Simpan respons permit2 terpisah (bila dipakai).
        out.setdefault("permit2_fallback", {})[s] = {
            "used": permit2_resp is not None,
            "http_status": permit2_resp.get("http_status") if permit2_resp else None,
            "raw_response": permit2_resp.get("json") if permit2_resp else None,
            "error": permit2_resp.get("error") if permit2_resp else None}

    # Dua pass: pass 1 kumpulkan expected price tiap vendor (untuk
    # cross-check primer), pass 2 nilai dengan pembanding lengkap.
    for (vendor, call, s, resp, amt_base, amt_tok, med, nav_px, px_px) in pending:
        body = resp.get("json")
        exp = None
        if isinstance(body, dict) and resp.get("http_status") == 200:
            if vendor == "0x":
                try:
                    exp = int(body.get("buyAmount")) / 1e6 / amt_tok
                except (TypeError, ValueError):
                    exp = None
            else:
                try:
                    exp = int(body.get("dstAmount")) / 1e6 / amt_tok
                except (TypeError, ValueError):
                    exp = None
        raw_expected[(vendor, s)] = exp
    for (vendor, call, s, resp, amt_base, amt_tok, med, nav_px, px_px) in pending:
        other = "1inch" if vendor == "0x" else "0x"
        other_exp = raw_expected.get((other, s))
        a = assess(vendor, call, s, resp, amt_base, amt_tok, med,
                   nav_px, px_px, other_exp)
        # Lantai turunan klien (bukan min-out vendor) — dicatat terpisah.
        if a["expected_out_usdc"] is not None:
            a["client_derived_floor_usdc"] = a["expected_out_usdc"] * (
                1 - SLIPPAGE_PCT / 100.0)
            a["client_derived_floor_note"] = (
                "expected-out x (1 - 0,5%) — lantai hitung klien, BUKAN "
                "min-out yang dikomitmenkan vendor")
        out["samples"].append(a)

    # Ringkasan.
    firm = [x for x in out["samples"] if x.get("verdict") == "FIRM_CANDIDATE"]
    out["summary"] = {
        "total_samples": len(out["samples"]),
        "firm_candidates": len(firm),
        "not_firm": len(out["samples"]) - len(firm),
        "per_vendor": {
            v: {"total": len([x for x in out["samples"] if x["vendor"] == v]),
                "firm": len([x for x in out["samples"]
                             if x["vendor"] == v
                             and x.get("verdict") == "FIRM_CANDIDATE"])}
            for v in ("0x", "1inch")},
        "fallback_references": {
            "nav_implied_ok": out["references"]["nav_implied"]["ok"],
            "nav_tokens_ok": [s for s in TOKENS
                              if nav.get(s, {}).get("nav_price")],
            "proxy_ok": out["references"]["hyperliquid_proxy_xyz"]["ok"],
            "proxy_tokens_ok": [s for s in TOKENS
                                if proxy.get(s, {}).get("markPx")]},
        "verdict_overall": ("ADA kandidat firm" if firm
                            else "TIDAK ADA kandidat yang lolos — hasil sah (§2.5)")}

    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, sort_keys=False)
    print("wrote %s (%d samples, %d firm candidates)"
          % (OUT_PATH, len(out["samples"]), len(firm)))
    for x in out["samples"]:
        print("- %s %s %s: %s | %s | expected-out=%s min-out=%s "
              "expiry=%s" % (x["vendor"], x["call"], x["symbol"],
                             x["verdict"], x["verdict_reason"],
                             x.get("expected_out_usdc"),
                             x.get("min_out_usdc"),
                             x.get("expires_at")))
    return out


if __name__ == "__main__":
    main()
