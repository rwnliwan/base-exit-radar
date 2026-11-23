"""Capture evidence mentah (audit §3): raw response dari run yang sama,
disimpan beserta request, timestamp/status, dan manifest hash.

Mengambil (publik, read-only, tanpa key):
- Coinbase tokenized-stocks (semua halaman) -> coinbase_tokenized_stocks_page1.json
- DexScreener pools NVDAc + AAPLc
- GeckoTerminal pool teratas NVDAc + AAPLc (cross-check; AAPLc sebelumnya hilang)
- Hyperliquid metaAndAssetCtxs dex xyz + io

Output: evidence/<file>.json + evidence/manifest.json
(manifest: file, source URL, fetched_at, http_status, sha256, bytes)

Penggunaan:
  python3 capture_evidence.py
Jangan dipakai sebagai bagian gate (gate offline). Dijalankan manual saat
evidence perlu direfresh; manifest membuktikan rantai raw-ke-snapshot.
"""

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import adapter
import config

BASE = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.join(BASE, "evidence")


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def _get_raw(url):
    """GET mentah. Kembalikan (body_bytes, http_status, error)."""
    req = urllib.request.Request(
        url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_SEC) as resp:
            return resp.read(), resp.status, None
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = b""
        return body, e.code, "http_%s" % e.code
    except Exception as e:  # noqa: BLE001
        return b"", None, "fetch_error:%s" % type(e).__name__


def _post_raw(url, payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"User-Agent": config.USER_AGENT,
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT_SEC) as resp:
            return resp.read(), resp.status, None
    except urllib.error.HTTPError as e:
        try:
            b = e.read()
        except Exception:
            b = b""
        return b, e.code, "http_%s" % e.code
    except Exception as e:  # noqa: BLE001
        return b"", None, "fetch_error:%s" % type(e).__name__


def _save(name, body, url, status, error):
    path = os.path.join(EVID, name)
    with open(path, "wb") as f:
        f.write(body)
    entry = {"file": name, "source": url, "fetched_at": _now_iso(),
             "http_status": status, "error": error,
             "sha256": _sha256_bytes(body), "bytes": len(body)}
    print("[%s] %s bytes=%d sha256=%s status=%s err=%s"
          % (name, url, len(body), entry["sha256"][:16], status, error))
    return entry


def main():
    os.makedirs(EVID, exist_ok=True)
    manifest = {"captured_at": _now_iso(),
                "policy_version": config.POLICY_VERSION,
                "methodology_version": config.METHODOLOGY_VERSION,
                "schema_version": config.SCHEMA_VERSION,
                "entries": []}
    # Coinbase (halaman 1; token NVDAc/AAPLc ada di halaman ini).
    body, status, err = _get_raw(config.COINBASE_API_URL)
    manifest["entries"].append(_save(
        "coinbase_tokenized_stocks_page1.json", body,
        config.COINBASE_API_URL, status, err))
    # DexScreener + GeckoTerminal per token.
    for sym, tok in config.TOKENS.items():
        addr = tok["token_address"]
        url = config.DEXSCREENER_URL.format(address=addr)
        body, status, err = _get_raw(url)
        manifest["entries"].append(_save(
            "dexscreener_%s.json" % sym.lower(), body, url, status, err))
        # Pool teratas by liquidity (dari payload DexScreener barusan).
        top = None
        try:
            pairs = json.loads(body.decode("utf-8")).get("pairs", [])
            cands = [p for p in pairs if p.get("pairAddress", "").startswith("0x")]
            if cands:
                def _liq(p):
                    try:
                        return float((p.get("liquidity") or {}).get("usd") or -1)
                    except (TypeError, ValueError):
                        return -1.0
                top = max(cands, key=_liq).get("pairAddress")
        except Exception:
            top = None
        if top:
            url = config.GECKOTERMINAL_POOL_URL.format(pool=top)
            body, status, err = _get_raw(url)
            manifest["entries"].append(_save(
                "geckoterminal_%s_pool.json" % sym.lower(), body, url,
                status, err))
        else:
            print("[skip] geckoterminal %s: no top pool found" % sym)
    # Hyperliquid proxy dex xyz + io.
    for dex in ("xyz", "io"):
        body, status, err = _post_raw(
            config.HYPERLIQUID_INFO_URL, {"type": "metaAndAssetCtxs", "dex": dex})
        manifest["entries"].append(_save(
            "hyperliquid_metaAndAssetCtxs_%s.json" % dex, body,
            config.HYPERLIQUID_INFO_URL + " dex=" + dex, status, err))
    with open(os.path.join(EVID, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print("Manifest: evidence/manifest.json (%d entries)"
          % len(manifest["entries"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
