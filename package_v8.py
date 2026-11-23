"""Paket v8 (v0.3.3): MD5 manifest + zip code + zip evidence.

- MD5SUMS-v8.txt: md5 semua file paket (code + evidence + out/v0.3.3),
  agar MD5 upload Drive bisa diverifikasi ke manifest sumber
  (koreksi dok re-audit v5 #6).
- base-prototype-code-v8.zip: kode + evidence/ + fixtures/ + docs
  (gate 19/19 jalan SENDIRIAN dari code zip saja, tanpa merge evidence).
- base-prototype-gate-evidence-v8.zip: evidence/ + out/v0.3.3/ +
  gate_results.json + gate_log.md (bukti run + replay RPC).

Penggunaan:
  python3 package_v8.py
Output di ../ (folder radar-tokenized-stocks/).
"""

import hashlib
import os
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
PARENT = os.path.dirname(BASE)

CODE_ZIP = os.path.join(PARENT, "base-prototype-code-v8.zip")
EVID_ZIP = os.path.join(PARENT, "base-prototype-gate-evidence-v8.zip")
MANIFEST = os.path.join(PARENT, "MD5SUMS-v8.txt")

# File kode (root base-prototype) yang masuk code zip.
CODE_FILES = [
    "README.md", "DECISION_MEMO.md", "DESIGN.md", "QUOTER-RESEARCH.md",
    "config.py", "adapter.py", "pipeline.py", "run.py", "gate.py",
    "capture_evidence.py", "capture_rpc_evidence.py",
    "verify_rpc_replay.py",
    "package_v6.py", "package_v7.py", "package_v8.py",
]

# Folder yang masuk code zip (seluruh isi, rekursif).
# out/v0.3.0 ikut karena gate (test_quoter_g1_g6) membaca snapshot live
# v0.3.0 sebagai fixture G1 (fallback counter 5 vs 0) — tanpa itu gate
# tidak jalan 19/19 dari code zip saja. out/v0.3.1 + out/v0.3.2 +
# out/v0.3.3 ikut sebagai jejak audit lengkap (snapshot + decision tiap
# versi).
CODE_DIRS = ["fixtures", "evidence", "out/v0.3.0", "out/v0.3.1",
             "out/v0.3.2", "out/v0.3.3"]

# Folder/file yang masuk evidence zip.
EVID_DIRS = ["evidence", "out/v0.3.3"]
EVID_FILES = ["out/gate_results.json", "out/gate_log.md"]


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk_files(root, rel_base):
    """Semua file di bawah root, sebagai (path_abs, path_rel)."""
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            ap = os.path.join(dirpath, fn)
            rp = os.path.relpath(ap, rel_base)
            out.append((ap, rp))
    return out


def main():
    # --- kumpulkan file ---
    code_entries = []
    for fn in CODE_FILES:
        ap = os.path.join(BASE, fn)
        if os.path.exists(ap):
            code_entries.append((ap, fn))
    for d in CODE_DIRS:
        code_entries.extend(_walk_files(os.path.join(BASE, d), BASE))
    evid_entries = []
    for fn in EVID_FILES:
        ap = os.path.join(BASE, fn)
        if os.path.exists(ap):
            evid_entries.append((ap, fn))
    for d in EVID_DIRS:
        evid_entries.extend(_walk_files(os.path.join(BASE, d), BASE))
    # Buang __pycache__ dari code zip.
    code_entries = [(a, r) for a, r in code_entries
                    if "__pycache__" not in r]

    # --- MD5 manifest (semua file paket, unik, terurut) ---
    all_rel = sorted({r for _a, r in code_entries + evid_entries})
    lines = []
    for rel in all_rel:
        ap = os.path.join(BASE, rel)
        lines.append("%s  %s" % (_md5(ap), rel))
    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write("# MD5SUMS v8 — Base Stocks Maxxing prototipe v0.3.3\n")
        f.write("# Dibuat: paket v8 (minor M1-M3 re-audit v7, "
                "gate 19/19, live run v0.3.3 23 Nov 2026 00:12 WITA)\n")
        f.write("# Verifikasi: md5sum -c MD5SUMS-v8.txt (dari folder "
                "base-prototype/)\n")
        f.write("\n".join(lines) + "\n")
    print("manifest: %s (%d file)" % (MANIFEST, len(lines)))

    # --- zip code ---
    with zipfile.ZipFile(CODE_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for ap, rel in sorted(code_entries, key=lambda x: x[1]):
            z.write(ap, os.path.join("base-prototype", rel))
    print("code zip: %s (%d file, %d byte)"
          % (CODE_ZIP, len(code_entries), os.path.getsize(CODE_ZIP)))

    # --- zip evidence ---
    with zipfile.ZipFile(EVID_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for ap, rel in sorted(evid_entries, key=lambda x: x[1]):
            z.write(ap, os.path.join("base-prototype", rel))
    print("evidence zip: %s (%d file, %d byte)"
          % (EVID_ZIP, len(evid_entries), os.path.getsize(EVID_ZIP)))
    print("code md5: %s" % _md5(CODE_ZIP))
    print("evid md5: %s" % _md5(EVID_ZIP))


if __name__ == "__main__":
    main()
