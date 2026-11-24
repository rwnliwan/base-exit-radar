#!/usr/bin/env python3
"""Guard standalone untuk decide() (S1-G, rencana Scope 1 v1.1 §5).

Membandingkan source live pipeline.decide() dengan hash yang direkam di
gate.py (_DECIDE_SOURCE_SHA256). Guard = source_sha256 + modul; hash AST
hanya info diagnostik (ast.dump berbeda antar versi Python).
Keluar 0 bila cocok, 1 bila decide() berubah (atau tidak terbaca).

Penggunaan:
  python3 scripts/guard_decide.py
  python3 gate.py   # tes s1g_decide_source_guard menjalankan cek yang sama
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gate


def main():
    ok, detail = gate._decide_guard()
    print(("PASS" if ok else "FAIL") + " decide() guard: " + detail)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
