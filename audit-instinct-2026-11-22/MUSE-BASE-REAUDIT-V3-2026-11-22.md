# [muse] Re-audit v3 Base prototype — 1 must-fix baru (F1) sebelum gate dinyalakan

Tanggal: 22 Nov 2026 (WITA). Auditor: Instinct (independen, zip v3 diunduh
dan dijalankan sendiri dari folder Drive Base). Skor kejujuran laporan v3:
**8/10** (v2: 8,5/10).

## Ringkasan verdict

| Klaim v3 | Verdict |
|---|---|
| Gate 16/16 PASS | TERBUKTI (dijalankan sendiri, 16/16) |
| Repro A-D tetap lolos | TERBUKTI (script reviewer di-run ulang: A quote `{}`/null = WATCH cash 1.0; B stale pool = ABSTAIN + `nav_timestamp_unknown`; C chain salah = ABSTAIN `token_not_confirmed`, coverage 1-pool-2-klaim dan 2-pool-1-venue = ABSTAIN; D dedup gagal tulis = emit kedua tidak keluar, file tidak ada) |
| E1 validator diperketat (logika) | TERBUKTI sebagian — lihat F1 di bawah |
| E2 snapshot self-consistent | TERBUKTI penuh |
| E3 dokumen segar | TERBUKTI |
| Batas keras (quoter belum dipasang, gate mati, live WATCH cash 1.0) | TERBUKTI |

## F1 (MUST-FIX, blokir pengaktifan gate — bukan kondisi sekarang): kedua alamat di `USDC_BASE_ADDRESSES` salah

`config.py` v0.2.1:

```python
USDC_BASE_ADDRESSES = {
    "0x833589fcd6edb6e08f4c7c32d4f71b54bd029029",  # diklaim USDC native (Circle)
    "0x50c5725949a6f0c72e6c4a641f24049a917db0cb",  # diklaim USDC.e bridged
}
```

Komentar config bilang "Keduanya USDC asli di Base". **Keduanya bukan.**

1. Native USDC (Circle) di Base yang asli:
   `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
   (sumber: BaseScan token page USDC; blog resmi Circle). Alamat di config
   berbeda di 8 hex terakhir (`bd029029` vs `bda02913`) — alamat mangled,
   bukan token apa pun yang relevan.
2. `0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb` adalah **DAI bridged di
   Base** (sumber: BaseScan "Dai Stablecoin (DAI)", Uniswap app), bukan
   USDC.e. USDC.e/USDbC yang asli:
   `0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA`
   (sumber: Blockscout, docs Circle).

Akibatnya begitu quoter dipasang dan gate dinyalakan:

- Quote jual yang membayar **native USDC asli** (USDC paling likuid di
  Base) **DITOLAK** sebagai `exit_quote_token_out_not_usdc`. Terbukti:
  probe auditor dengan token_out `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
  (sisanya quote firm valid) -> `invalid`.
- Quote jual yang membayar **DAI** **DITERIMA** sebagai bukti exit USDC
  (`verified`). Terbukti: probe auditor dengan token_out alamat DAI ->
  `verified`. Ini persis lubang yang E1 seharusnya tutup, hanya ganti
  arah: aset non-USDC lolos sebagai exit USDC.

### Kenapa gate 27/27 tidak menangkap ini

`gate.py::_valid_quote` memakai token_out
`0x833589fCD6eDb6E08f4c7C32D4f71b54bd029029` — alamat salah yang SAMA
dengan config (komentarnya bahkan bilang "alamat USDC Base asli"). Tes
jadi self-referential: config salah + fixture salah yang cocok = PASS.
Tidak ada satu pun tes yang memakai alamat USDC Base yang benar, jadi
kesalahan konstanta tidak mungkin ketahuan dari gate.

### Fix yang diminta

1. Ganti isi `USDC_BASE_ADDRESSES` dengan:
   - `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (native USDC, Circle)
   - `0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA` (USDC.e / USDbC bridged)
2. `gate.py::_valid_quote`: pakai alamat **native USDC asli** yang
   ditulis eksplisit di test (bukan konstanta config), supaya tes memutus
   kesalahan konstanta, bukan mengonfirmasinya.
3. Tambah regression test:
   - token_out = native USDC asli -> `verified` (quote lain valid);
   - token_out = USDC.e asli -> `verified`;
   - token_out = DAI `0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb` ->
     `invalid exit_quote_token_out_not_usdc`;
   - token_out = alamat mangled lama `0x833589fcd6edb6e08f4c7c32d4f71b54bd029029`
     -> `invalid`.
4. Verifikasi alamat ke sumber independen (BaseScan/Circle) sebelum
   commit — konstanta keamanan jangan diketik dari ingatan.

### Acceptance criteria (dicek auditor di re-audit berikutnya)

- Keempat tes di atas PASS di mesin auditor, dijalankan dari zip baru.
- Probe independen auditor (bukan tes gate) dengan native USDC asli ->
  `verified`; dengan DAI -> `invalid`.
- Gate tetap 16/16 atau lebih setelah perubahan.

## Yang TERBUKTI penuh (detail)

- **E2.** `build_snapshot` menghitung coverage dari venue kanonis
  (`_canonical_venue`, aero == aerodrome) dan `assess_snapshot` tidak lagi
  mutasi `snap["coverage"]` (diff v2->v3 diverifikasi baris per baris;
  3 baris mutasi dihapus). Snapshot v0.2.1 NVDAc + AAPLc di zip evidence:
  `verify_snapshot_identity` -> `matches: True`, stored == recomputed.
  File v0.2.0 lama (snap-a7da34c2855e4e92) memang mismatch secara
  konstruksi di bawah algoritma v0.2.1 (recomputed snap-3145488b...) —
  terkonfirmasi artefak historis, bukan bug baru. Auditor juga menjalankan
  **live run sendiri** (`python3 run.py --token NVDAc`, fetch publik
  sungguhan): snapshot baru snap-806a044098621497 self-consistent
  (matches: True, stored 11 pool/6 venue == recomputed 11/6), decision
  WATCH cash 1.0.
- **E3.** Angka README (NVDAc median $132,94 gap +2,40%; AAPLc $350,07
  gap +1,38%; keduanya WATCH cash 1.0, NAV basi off_hours) cocok persis
  dengan file decision di `out/v0.2.1/`. Evidence dipisah per versi,
  tanpa file `.lock`. Manifest evidence: 7/7 hash file mentah cocok.
- **Batas keras.** `adapter.py` identik byte-per-byte dengan v2 (quoter
  belum dipasang). `PAPER_PROPOSALS_ENABLED = False`. Probe end-to-end
  auditor: quote firm VALID penuh (status `verified`) + NAV fresh + gate
  mati -> decision tetap **WATCH, cash_weight 1.0**. Live run v0.2.1
  kedua token WATCH cash 1.0. sha256 keenam file source di
  `gate_results.json` cocok dengan isi zip.
- **Validator (logika E1).** 3 probe lama (tanpa kind, SCAMCOIN, notional
  1e12) sekarang `invalid`, plus 21 probe adversarial auditor berperilaku
  benar: kind numerik/kosong/indicative ditolak, kind uppercase diterima,
  side BUY ditolak, chain salah ditolak, future/stale/expired ditolak,
  harga ±16% dari median ditolak (±9% lolos), notional di bawah proposal
  dan klaim 10x ditolak, NaN/Infinity/negatif ditolak, median None ->
  `exit_quote_median_unavailable`.

## Catatan minor (bukan must-fix)

- Zip `code-v3` sendirian tidak bisa menjalankan gate: 3 tes butuh folder
  `evidence/` yang ada di zip evidence terpisah (FileNotFoundError).
  Sesuai struktur README memang satu proyek, tapi reviewer yang hanya
  unzip code-v3 akan melihat 3 FAIL. Pertimbangkan bundle ulang atau
  cantumkan langkah merge di README.
- Manifest evidence masih berlabel versi v0.2.0 (captured 13:27 UTC) —
  benar sebagai capture mentah, hanya catat supaya tidak dibaca sebagai
  evidence v0.2.1.

## Yang TIDAK diuji auditor

- Live run AAPLc (hanya NVDAc yang dijalankan live sendiri; klaim AAPLc
  diverifikasi dari file evidence, bukan fetch ulang).
- `capture_evidence.py` tidak dijalankan ulang (langkah manual).
- Kebenaran isi data DexScreener/Coinbase per pool (hanya kewajaran
  median: live auditor $132,66 vs evidence $132,94, selisih wajar untuk
  beda waktu fetch).
- Jalur PAPER_PROPOSAL dengan gate NYALA (di luar batas keras; invariant
  hanya dicek di level kode).

## Kesimpulan

E2, E3, gate, repro A-D, batas keras: bersih. Satu must-fix F1 pada
konstanta allowlist USDC — tidak berdampak sekarang (gate mati, quoter
belum ada) tapi WAJIB beres sebelum quoter dipasang / gate dinyalakan.
Setelah F1 beres + tes regresi alamat asli masuk, prototipe siap dibawa
ke review 28 Nov untuk bahasan fase quoter.
