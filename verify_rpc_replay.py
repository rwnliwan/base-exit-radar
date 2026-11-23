#!/usr/bin/env python3
"""Replay RPC transcript byte-exact (v0.3.3).

Membaca 18 file evidence/rpc/*.json, mengulang request yang tersimpan
(eth_call / eth_getBlockByNumber, block pin yang sama) ke mainnet.base.org,
dan membandingkan hasil dengan response yang tersimpan. Juga mencocokkan
amount_out quote/probe dengan snapshot out/v0.3.3/.

Keluar 0 bila semua cocok, 1 bila ada mismatch. Dipakai chief untuk
verifikasi replay sebelum paket dikirim ke auditor.
"""
import json
import os
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
RPC_DIR = os.path.join(BASE, "evidence", "rpc")
SNAP_DIR = os.path.join(BASE, "out", "v0.3.3")
RPC_URL = "https://mainnet.base.org"


def _post(payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RPC_URL, data=data,
        headers={"Content-Type": "application/json",
                 "User-Agent": "base-prototype-replay/0.3.3"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main():
    files = sorted(f for f in os.listdir(RPC_DIR)
                   if f.endswith(".json") and f != "manifest.json")
    ok = 0
    bad = []
    for name in files:
        path = os.path.join(RPC_DIR, name)
        with open(path, "r", encoding="utf-8") as f:
            rec = json.load(f)
        req = rec["request"]
        saved = rec["response"]
        try:
            live = _post(req)
        except Exception as e:  # noqa: BLE001 - laporkan sebagai mismatch
            bad.append((name, "rpc_error:%s" % e))
            continue
        # Bandingkan result saja (id/jsonrpc bisa berbeda urutan/tambahan).
        if live.get("result") == saved.get("result"):
            ok += 1
        else:
            bad.append((name, "result_mismatch"))
    # Cocokkan amount_out quote/probe dengan snapshot v0.3.3.
    for sym in ("NVDAc", "AAPLc"):
        snaps = [f for f in os.listdir(SNAP_DIR)
                 if f.startswith("snapshot_%s_" % sym)]
        if not snaps:
            bad.append((sym, "snapshot_missing"))
            continue
        with open(os.path.join(SNAP_DIR, snaps[0]), "r",
                  encoding="utf-8") as f:
            snap = json.load(f)
        q = snap.get("exit_quote") or {}
        for kind in ("quote", "quote_probe"):
            with open(os.path.join(RPC_DIR, "%s_%s.json" % (sym, kind)),
                      "r", encoding="utf-8") as f:
                rec = json.load(f)
            result = rec["response"]["result"]
            # amountOut = kata pertama (32 byte) dari hasil decode.
            amount_out = int(result[2:66], 16)
            if kind == "quote":
                expect = q.get("amount_out_estimate")
                # amount_out_estimate dalam USDC (6 desimal, float).
                match = expect is not None and abs(
                    amount_out / 1e6 - expect) < 0.01
            else:
                probe = q.get("partial_fill_probe") or {}
                expect = probe.get("probe_amount_out_usd")
                match = expect is not None and abs(
                    amount_out / 1e6 - expect) < 0.01
            if match:
                ok += 1
            else:
                bad.append((sym + "_" + kind,
                            "snapshot_amount_out_mismatch"))
    print("replay: %d ok, %d bad" % (ok, len(bad)))
    for name, why in bad:
        print("  MISMATCH %s: %s" % (name, why))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
