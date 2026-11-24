"""Verifikasi sensus universe Coinbase — fail-closed (S1-A, §1.2).

Memeriksa keempat syarat acceptance dari manifest + evidence + config:
  1. cursor terminal habis (last_next_page_token None + cursor_terminal True)
  2. error None
  3. ok True
  4. tidak ada loop/halaman malformed (page token unik; tiap halaman punya
     field `tokens`; tiap token punya `contract_address` berpola 0xb200...;
     tidak ada alamat duplikat)
Plus konsistensi: total manifest == jumlah token evidence == jumlah
halaman; subset_suspected False; universe_version + total + config_hash
manifest cocok dengan config.py.

Exit 0 bila SEMUA lolos; non-zero bila ada satu pun gagal (fail-closed).
Dipakai gate S1-A; JANGAN klaim sensus lengkap sebelum skrip ini lolos.

Penggunaan: python3 verify_census.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(BASE, "evidence",
                        "coinbase_tokenized_stocks_manifest.json")
ALL = os.path.join(BASE, "evidence", "coinbase_tokenized_stocks_all.json")
ADDR_RE = re.compile(r"^0x[bB]200[0-9a-fA-F]{36}$")


def main():
    checks = []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    try:
        with open(MANIFEST, "r", encoding="utf-8") as f:
            mani = json.load(f)
    except (OSError, ValueError) as e:
        print("FAIL manifest_unreadable: %s" % e)
        return 1
    try:
        with open(ALL, "r", encoding="utf-8") as f:
            all_doc = json.load(f)
    except (OSError, ValueError) as e:
        print("FAIL evidence_unreadable: %s" % e)
        return 1

    tokens = all_doc.get("tokens")
    if not isinstance(tokens, list):
        print("FAIL evidence_tokens_not_a_list")
        return 1

    # Syarat 1 — cursor terminal habis.
    check("cursor_terminal",
          mani.get("cursor_terminal") is True
          and mani.get("last_next_page_token") is None,
          "cursor_terminal=%s last_next_page_token=%s"
          % (mani.get("cursor_terminal"), mani.get("last_next_page_token")))
    # Syarat 2 — error None.
    check("error_none", mani.get("error") is None,
          "error=%s" % mani.get("error"))
    # Syarat 3 — ok True.
    check("ok_true", mani.get("ok") is True, "ok=%s" % mani.get("ok"))
    # Syarat 4a — tidak ada loop halaman (page token unik).
    pages = mani.get("page_summaries") or []
    seen = [p.get("next_page_token") for p in pages
            if p.get("next_page_token") is not None]
    check("no_pagination_loop", len(seen) == len(set(seen))
          and mani.get("page_tokens_unique") is True,
          "page_tokens=%d unique=%d" % (len(seen), len(set(seen))))
    # Syarat 4b — tidak ada halaman malformed (tiap halaman punya tokens).
    check("no_malformed_pages",
          bool(pages) and all(
              isinstance(p.get("token_count"), int)
              and p["token_count"] > 0 for p in pages),
          "pages=%d" % len(pages))
    # Syarat 4c — tiap token punya contract_address berpola 0xb200...
    bad_addr = [t.get("contract_address") for t in tokens
                if not ADDR_RE.match((t or {}).get("contract_address") or "")]
    check("all_tokens_have_b200_address", not bad_addr,
          "mismatches=%d %s" % (len(bad_addr), bad_addr[:3]))
    # Syarat 4d — tidak ada alamat duplikat.
    addrs = [(t.get("contract_address") or "").lower() for t in tokens]
    check("no_duplicate_addresses", len(addrs) == len(set(addrs)),
          "total=%d unique=%d" % (len(addrs), len(set(addrs))))
    # Konsistensi jumlah.
    page_total = sum(p.get("token_count", 0) for p in pages)
    check("total_matches_evidence",
          mani.get("total_tokens") == len(tokens) == page_total,
          "manifest=%s evidence=%d pages_sum=%d"
          % (mani.get("total_tokens"), len(tokens), page_total))
    check("pages_count_matches",
          mani.get("pages") == len(pages),
          "manifest_pages=%s summaries=%d" % (mani.get("pages"), len(pages)))
    # Bukan subset yang dicurigai.
    check("subset_not_suspected", mani.get("subset_suspected") is False,
          "subset_suspected=%s reason=%s"
          % (mani.get("subset_suspected"),
             mani.get("subset_suspected_reason")))
    # Metadata wajib tiap token (kontrak §1.2c): symbol + decimals.
    bad_meta = [t.get("symbol") for t in tokens
                if not (t or {}).get("symbol")
                or (t or {}).get("decimals") is None]
    check("all_tokens_have_symbol_and_decimals", not bad_meta,
          "missing=%d" % len(bad_meta))
    # Universe/config berversi cocok dengan config.py.
    try:
        import config
        check("universe_version_matches_config",
              mani.get("universe_version") == config.UNIVERSE_VERSION,
              "manifest=%s config=%s"
              % (mani.get("universe_version"), config.UNIVERSE_VERSION))
        check("total_matches_config",
              mani.get("total_tokens") == config.UNIVERSE_TOTAL_TOKENS,
              "manifest=%s config=%s"
              % (mani.get("total_tokens"), config.UNIVERSE_TOTAL_TOKENS))
        check("config_hash_matches_config",
              mani.get("config_hash") == config.CONFIG_HASH,
              "manifest=%s config=%s"
              % (mani.get("config_hash"), config.CONFIG_HASH))
    except Exception as e:  # noqa: BLE001 - config belum punya field versi
        check("config_version_fields_present", False,
              "config import/check gagal: %s: %s" % (type(e).__name__, e))

    failed = [c for c, ok, _ in checks if not ok]
    for name, ok, detail in checks:
        print("%s %s %s" % ("PASS" if ok else "FAIL", name,
                            ("(%s)" % detail) if detail else ""))
    print("verify_census: %d/%d checks pass; total_tokens=%s pages=%s"
          % (len(checks) - len(failed), len(checks),
             mani.get("total_tokens"), mani.get("pages")))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
