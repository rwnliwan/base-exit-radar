"""Capture RPC transcript (re-audit v5, koreksi dok #3): raw request/response
eth_call untuk run live v0.3.2, agar klaim historical exact bisa direplay.

Membaca snapshot v0.3.3 (out/v0.3.3/) lalu mengulang panggilan RPC yang SAMA
(calldata sama) PADA BLOCK yang sama (block_number snapshot) — sehingga
hasilnya harus cocok dengan nilai snapshot (bukan "latest" yang sudah
bergerak). Output: evidence/rpc/<token>_<call>.json + evidence/rpc/manifest.json.

Yang ditangkap per token:
- quote: eth_call quoteExactInputSingleV3(pool, tokenIn, amountIn, 0)
- quote_probe: eth_call yang sama dengan amountIn x 2 (double-quote probe
  F1, v0.3.2) — amountOut harus cocok dengan snapshot partial_fill_probe.
- oracle: eth_call getOracleParams(token)
- factory: eth_call factory() pool teratas
- tokens: eth_call token0()/token1() pool teratas
- decimals: eth_call decimals() tokenIn + counterpart
- block: eth_getBlockByNumber(block_number) -> hash

Setiap file: {request: {method, params, rpc_url}, response: <raw JSON>,
fetched_at, block_number, note}. Manifest: file, sha256, bytes, block_number.

Penggunaan:
  python3 capture_rpc_evidence.py
Jangan dipakai sebagai bagian gate (gate offline). Dijalankan manual saat
evidence perlu direfresh; manifest membuktikan rantai RPC-ke-snapshot.
"""

import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone

import adapter
import config

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "out", "v0.3.3")
RPC_DIR = os.path.join(BASE, "evidence", "rpc")


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def _rpc_raw(method, params, rpc_url):
    """Satu JSON-RPC mentah. Kembalikan (request_dict, response_dict).
    Retry 3x (jeda 2 dtk) bila koneksi putus/timeout — RPC publik kadang
    menutup koneksi; capture tidak boleh mati di tengah jalan."""
    req = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    body = json.dumps(req).encode("utf-8")
    request = urllib.request.Request(
        rpc_url, data=body,
        headers={"User-Agent": config.USER_AGENT,
                 "Content-Type": "application/json"})
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=config.HTTP_TIMEOUT_SEC) as resp:
                raw = resp.read()
            return req, json.loads(raw.decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < 2:
                import time
                time.sleep(2)
    raise last_err


def _eth_call_at_block(to, data, block_number, rpc_url):
    """eth_call pada block tertentu (bukan latest)."""
    blk = "0x%x" % block_number
    return _rpc_raw("eth_call",
                    [{"to": to, "data": data}, blk], rpc_url)


def _capture_token(symbol, snap):
    """Tangkap semua panggilan RPC untuk satu token. Kembalikan list file."""
    q = snap.get("exit_quote") or {}
    pool = q.get("pool")
    token = (snap.get("asset") or {}).get("token_address")
    amount_in_wei = q.get("amount_in_wei")
    block_number = q.get("block_number")
    rpc_url = config.BASE_RPC_URLS[0]
    files = []

    def _save(name, request, response, note):
        obj = {"token": symbol, "request": request, "response": response,
               "rpc_url": rpc_url, "block_number": block_number,
               "fetched_at": _now_iso(), "note": note}
        path = os.path.join(RPC_DIR, "%s_%s.json" % (symbol, name))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, sort_keys=True)
            f.write("\n")
        files.append(path)
        return path

    # --- quote (calldata persis seperti live run) ---
    data = ("0x0a674142" + adapter._addr_word(pool)
            + adapter._addr_word(token)
            + adapter._uint_word(amount_in_wei) + adapter._uint_word(0))
    req, resp = _eth_call_at_block(config.AERO_METAQUOTER, data,
                                   block_number, rpc_url)
    _save("quote", req, resp,
          "quoteExactInputSingleV3(pool, tokenIn, amountIn, 0) pada block "
          "snapshot; amountOut harus cocok dengan snapshot "
          "amount_out_estimate (USDC 6 desimal).")
    # --- probe quote (F1, v0.3.2): calldata sama, amountIn x 2 ---
    probe = (q.get("partial_fill_probe") or {})
    probe_in_wei = probe.get("probe_amount_in_wei")
    if probe_in_wei:
        data = ("0x0a674142" + adapter._addr_word(pool)
                + adapter._addr_word(token)
                + adapter._uint_word(probe_in_wei) + adapter._uint_word(0))
        req, resp = _eth_call_at_block(config.AERO_METAQUOTER, data,
                                       block_number, rpc_url)
        _save("quote_probe", req, resp,
              "quoteExactInputSingleV3(pool, tokenIn, amountIn x 2, 0) "
              "pada block snapshot (double-quote probe F1); amountOut "
              "harus cocok dengan snapshot partial_fill_probe.")
    # --- oracle ---
    data = "0xd4197e82" + adapter._addr_word(token)
    req, resp = _eth_call_at_block(config.ORACLE_REGISTRY, data,
                                   block_number, rpc_url)
    _save("oracle", req, resp,
          "getOracleParams(token) pada block snapshot; multiplier/paused "
          "harus cocok dengan snapshot oracle.")
    # --- factory pool teratas ---
    req, resp = _eth_call_at_block(pool, "0xc45a0155", block_number, rpc_url)
    _save("factory", req, resp,
          "factory() pool teratas pada block snapshot; harus cocok dengan "
          "snapshot pools[0].factory.")
    # --- token0/token1 pool teratas ---
    for sel, name in (("0x0dfe1681", "token0"), ("0xd21220a7", "token1")):
        req, resp = _eth_call_at_block(pool, sel, block_number, rpc_url)
        _save(name, req, resp,
              "%s() pool teratas pada block snapshot (G2 guard)." % name)
    # --- decimals tokenIn + counterpart ---
    for addr, name in ((token, "decimals_token_in"),
                       (q.get("token_out"), "decimals_token_out")):
        if not addr:
            continue
        req, resp = _eth_call_at_block(addr, "0x313ce567",
                                       block_number, rpc_url)
        _save(name, req, resp,
              "decimals() %s pada block snapshot (G2 guard)." % name)
    # --- block ---
    req, resp = _rpc_raw("eth_getBlockByNumber",
                         ["0x%x" % block_number, False], rpc_url)
    _save("block", req, resp,
          "eth_getBlockByNumber(block snapshot); hash harus cocok dengan "
          "snapshot exit_quote.block_hash.")
    return files


def main():
    os.makedirs(RPC_DIR, exist_ok=True)
    manifest = []
    for symbol in ("NVDAc", "AAPLc"):
        # Cari snapshot v0.3.2 (nama file berisi snapshot_id).
        cands = [f for f in os.listdir(OUT)
                 if f.startswith("snapshot_%s_snap-" % symbol)]
        if not cands:
            print("snapshot v0.3.2 %s tidak ditemukan, lewati" % symbol)
            continue
        with open(os.path.join(OUT, cands[0]), "r", encoding="utf-8") as f:
            snap = json.load(f)
        files = _capture_token(symbol, snap)
        for path in files:
            with open(path, "rb") as f:
                raw = f.read()
            manifest.append({
                "file": os.path.basename(path),
                "sha256": _sha256_bytes(raw),
                "bytes": len(raw),
                "block_number": snap.get("exit_quote", {}).get("block_number"),
                "fetched_at": _now_iso(),
            })
        print("%s: %d file RPC ditangkap (block %s)"
              % (symbol, len(files),
                 snap.get("exit_quote", {}).get("block_number")))
    mpath = os.path.join(RPC_DIR, "manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump({"files": manifest, "fetched_at": _now_iso()}, f,
                  indent=2, sort_keys=True)
        f.write("\n")
    print("manifest: %s (%d file)" % (mpath, len(manifest)))


if __name__ == "__main__":
    main()
