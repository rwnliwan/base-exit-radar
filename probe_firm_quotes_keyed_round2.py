#!/usr/bin/env python3
"""Round 2 karakterisasi — probe ber-key S2 (0x + 1inch), 24 Nov 2026.

Round 1 menemukan DUA penolakan yang perlu dikarakterisasi sebelum
disimpulkan (bukan diulang buta):
- 0x: HTTP 422 SELL_TOKEN_NOT_AUTHORIZED_FOR_TRADE di price DAN quote
  (allowance-holder + permit2), kedua token. Apakah ini soal ukuran?
  Apakah soal arah SELL saja (BUY USDC->NVDAc mungkin diizinkan)?
- 1inch /swap: HTTP 400 NOT_ENOUGH_BALANCE — taker Septian memegang
  0 NVDAc/AAPLc, jadi 1inch menolak MEMBANGUN tx swap untuk taker itu.
  Apakah skema /swap sendiri punya min-out/expiry bila `from` adalah
  alamat yang MEMEGANG token (pool Aerodrome, pemegang besar)? Probe
  ini memakai alamat pool HANYA sebagai parameter `from` read-only
  untuk mengungkap skema respons — TIDAK ADA signing/broadcast/dana
  bergerak, dan hasilnya DILABELI "schema probe, bukan quote untuk
  wallet Septian" (tidak dapat dihitung sebagai sampel firm untuk
  taker Septian).

Hasil di-append ke evidence/firm_quote_probes_keyed_2026-11-24.json
(kunci "round2_characterization"); round 1 tidak diubah.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_firm_quotes_keyed as p1  # noqa: E402

OUT_PATH = p1.OUT_PATH
USDC = p1.USDC_NATIVE
TAKER = p1.TAKER

# Alamat pool Aerodrome (pemegang NVDAc/AAPLc) — dipakai HANYA sebagai
# parameter `from` read-only pada /swap untuk mengungkap skema respons.
HOLDER = {
    "NVDAc": "0xF668e21993f0ACd7ab00BB1cFbAeD0df28A3C8EC",
    "AAPLc": "0xF5FCB9CDAFcE67d50AfEf298F88E709d2B946BA6",
}


def _swap_with_from(token_addr, amount_in_base, from_addr):
    url = ("https://api.1inch.dev/swap/v6.0/8453/swap"
           "?src=%s&dst=%s&amount=%s&from=%s&slippage=%s"
           % (token_addr, USDC, amount_in_base, from_addr, p1.SLIPPAGE_PCT))
    return p1._http_vendor(url, "custom.1inch")


def main():
    with open(OUT_PATH) as f:
        out = json.load(f)
    spot = out["spot_and_amount_in"]
    nav = out["references"]["nav_implied"]["per_token"]
    proxy = out["references"]["hyperliquid_proxy_xyz"]["per_token"]
    r2 = {"generated_at_utc": p1._now_iso(),
          "purpose": "karakterisasi penolakan round 1 (ukuran? arah? "
                     "saldo taker? skema /swap?)",
          "probes": []}

    for s in ("NVDAc", "AAPLc"):
        addr = p1.config.TOKENS[s]["token_address"]
        amt_base = spot[s]["amount_in_base_units"]
        amt_tok = spot[s]["amount_in_tokens"]
        med = spot[s]["median_dexscreener_usdc"]
        nav_px = float(nav[s]["nav_price"])
        px_px = float(proxy[s]["markPx"])

        # 1) 0x price, jumlah KECIL (0,01 token) — singkirkan hipotesis ukuran.
        tiny = 1_000_000  # 0,01 token (8 desimal)
        r = p1.probe_0x_price(addr, tiny)
        r2["probes"].append({
            "id": "0x_price_tiny_%s" % s,
            "question": "Apakah 422 0x disebabkan ukuran $10rb?",
            "sell_amount_base_units": tiny, "sell_amount_tokens": 0.01,
            "http_status": r["http_status"], "raw_response": r["json"],
            "error": r["error"]})

        # 2) 0x price arah BELI (USDC -> token, $10rb) — token diblokir
        # total, atau hanya sebagai SELL?
        url = ("https://api.0x.org/swap/allowance-holder/price"
               "?chainId=8453&sellToken=%s&buyToken=%s&sellAmount=%s"
               % (USDC, addr, 10_000_000))
        rb = p1._http_vendor(url, "custom.0x")
        body = rb["json"] if isinstance(rb.get("json"), dict) else None
        buy_summary = None
        if body and rb["http_status"] == 200:
            try:
                buy_summary = {"buyAmount_tokens": int(body.get("buyAmount")) / 1e8,
                               "liquidityAvailable": body.get("liquidityAvailable"),
                               "minBuyAmount_tokens": (int(body.get("minBuyAmount")) / 1e8
                                                       if body.get("minBuyAmount") else None)}
            except (TypeError, ValueError):
                buy_summary = None
        r2["probes"].append({
            "id": "0x_price_buy_USDC_to_%s" % s,
            "question": "Apakah 0x mengizinkan arah BELI (USDC->token $10rb)?",
            "sell_amount_usdc_base_units": 10_000_000,
            "http_status": rb["http_status"], "raw_response": rb["json"],
            "error": rb["error"], "buy_summary": buy_summary})

        # 3) 1inch /swap dengan from = pool pemegang token (schema probe).
        rs = _swap_with_from(addr, amt_base, HOLDER[s])
        body = rs["json"] if isinstance(rs.get("json"), dict) else None
        swap_summary = None
        if body and rs["http_status"] == 200:
            try:
                swap_summary = {
                    "dstAmount_usdc": int(body.get("dstAmount")) / 1e6,
                    "tx_to": (body.get("tx") or {}).get("to"),
                    "tx_data_present": bool((body.get("tx") or {}).get("data")),
                    "tx_gas": (body.get("tx") or {}).get("gas"),
                    "top_level_keys": sorted(body.keys())}
            except (TypeError, ValueError):
                swap_summary = None
        # Nilai skema /swap holder-from dengan assess yang sama (pembanding
        # primer = expected 0x tidak ada -> None; fallback NAV/proxy ada).
        a = p1.assess("1inch", "swap_holder_from_schema_probe", s, rs,
                      amt_base, amt_tok, med, nav_px, px_px, None)
        a["schema_probe_only"] = True
        a["schema_probe_note"] = (
            "from = alamat pool Aerodrome pemegang token, dipakai HANYA "
            "sebagai parameter read-only untuk mengungkap skema respons "
            "/swap. BUKAN quote untuk wallet Septian; TIDAK dihitung "
            "sebagai sampel firm (taker != Septian, saldo taker Septian "
            "tetap 0 sehingga /swap untuk taker itu tetap 400).")
        a["holder_from"] = HOLDER[s]
        r2["probes"].append({
            "id": "1inch_swap_holder_from_%s" % s,
            "question": "Apakah skema /swap 1inch punya min-out/expiry bila "
                        "from memegang token?",
            "from": HOLDER[s],
            "http_status": rs["http_status"], "raw_response": rs["json"],
            "error": rs["error"], "swap_summary": swap_summary,
            "assessment": a})

    out["round2_characterization"] = r2
    # Ringkasan round 2 (tanpa mengubah ringkasan round 1).
    ox_tiny = [q for q in r2["probes"] if q["id"].startswith("0x_price_tiny")]
    ox_buy = [q for q in r2["probes"] if q["id"].startswith("0x_price_buy")]
    inch = [q for q in r2["probes"] if q["id"].startswith("1inch_swap_holder")]
    out["round2_summary"] = {
        "0x_tiny_amount_still_422": all(
            q["http_status"] == 422 for q in ox_tiny),
        "0x_tiny_error_names": sorted({(q["raw_response"] or {}).get("name")
                                       for q in ox_tiny}),
        "0x_buy_direction": {q["id"]: {"http": q["http_status"],
                                       "error_name": (q["raw_response"] or {}).get("name"),
                                       "buy_summary": q.get("buy_summary")}
                             for q in ox_buy},
        "1inch_swap_holder_from": {
            q["id"]: {"http": q["http_status"],
                      "verdict": q["assessment"]["verdict"],
                      "reason": q["assessment"]["verdict_reason"],
                      "expected_out_usdc": q["assessment"].get("expected_out_usdc"),
                      "min_out_usdc": q["assessment"].get("min_out_usdc"),
                      "expiry_keys": q["assessment"].get("expiry_keys_found")}
            for q in inch},
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print("appended round2 to %s" % OUT_PATH)
    print(json.dumps(out["round2_summary"], indent=2))


if __name__ == "__main__":
    main()
