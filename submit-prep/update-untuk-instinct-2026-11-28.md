# UPDATE BASE EXIT RADAR — untuk Instinct (28 Nov 2026, ~14:00 WITA)

Diverifikasi chief dari disk hari ini (manifest + `verify_daily_runs.py` +
re-run `gate.py`). Angka di bawah bukan dari ingatan. Lanjutan dari brief
review 27 Nov 21:20 (`submit-prep/review-brief-2026-11-28.md`).

## 1. Run harian (Scope 1, otomatis cron 23:00 WITA)

- **25 Nov:** otomatis (cron), verifikasi 24/24 PASS, usable — tapi hanya
  **326/415** snapshot lengkap. Hari parsial, tidak dihitung penuh.
  Keputusan: ABSTAIN 415/415.
- **26 Nov:** **415/415**, usable, 24/24 PASS. ABSTAIN 405 / WATCH 10,
  0 PAPER_PROPOSAL. (Thanksgiving, bursa tutup, strata off_hours.)
- **27 Nov:** **415/415**, usable, 24/24 PASS. ABSTAIN 405 / WATCH 10,
  0 PAPER_PROPOSAL. (Early close, strata active.)
- Hasil 26 dan 27 Nov **IDENTIK** (10 simbol WATCH yang sama, jumlah alasan
  yang sama) — gap data yang sama selama minggu libur Thanksgiving.
- Run Hari 3 malam ini 28 Nov 23:00.

## 2. Isi keputusan (dari manifest 27 Nov, `tokens`)

- **10 WATCH:** AAPLc, AMZNc, ANTc, GOOGLc, METAc, MSFTc, MSTRc, NVDAc,
  SNDKc, SPCXc — semuanya punya venue terverifikasi (2–4 venue).
  - 2 di antaranya (**AAPLc, NVDAc**) beralasan `paper_proposals_disabled`:
    datanya lengkap dan layak jadi PAPER_PROPOSAL, tapi gate menahan di
    WATCH karena belum ada quote FIRM. Ini gate yang bekerja sesuai desain.
  - 8 lainnya beralasan `proxy_missing`: venue terverifikasi tapi
    proxy/underlying belum ada.
- **405 ABSTAIN:** 401 kurang cakupan lintas-venue +
  402 reference tidak valid (NAV/proxy hilang).

## 3. Kill-switch (checkpoint 30 Nov) — status per kriteria

1. **Data asli otomatis 5 hari: 2/5 hari penuh** (26–27 Nov). Butuh 28, 29,
   30 Nov tanpa putus. On track.
2. **Quote FIRM: 0/8 — BELUM. Blocker utama.** Tidak ada probe firm baru
   sejak 24 Nov (0x tolak 422; 1inch quote tapi swap gagal 400). Alamat
   pool terverifikasi on-chain (NVDAc/USDC `0xF668`, AAPLc/USDC `0xF5FC`,
   factory Dromos) — itu identitas venue, bukan quote firm.
3. **Brief otomatis ≥3 hari: 3 hari otomatis berturut-turut (25–27 Nov)**,
   reproducible (hash input di manifest). Tapi hari penuh 415/415 baru 2 —
   hari ke-3 malam ini.
4. **Hash Sepolia: BELUM — tidak ada tx.** Desain ada (DESIGN.md §8);
   deploy menunggu gate + ACC.
5. **Integritas gate: TERBUKTI, diverifikasi ulang hari ini.** Gate **29/29
   PASS** (re-run 28 Nov 13:48 WITA di kode terkini),
   `PAPER_PROPOSALS_ENABLED=False`, `decide()` tidak diubah (guard
   source-sha; perbaikan 24 Nov menyentuh guard-nya, bukan `decide()`),
   0 PAPER_PROPOSAL di semua hari.

## 4. Yang masih terbuka (keputusan review)

- **Nama proyek final:** rekomendasi chief "Exit Radar" (nama produk live
  di radar.omdanny.site). Opsi lain di `draft-form.md`.
- **Form halaman 2 (Telegram):** nama/link grup + ada tidaknya tombol
  Submit — belum dikonfirmasi.
- **Video demo:** siapa merekam + kapan (masuk ke post X, field 13 form).
- **Keputusan kunci:** (a) masih kejar jalur firm 28–30 Nov dengan rencana
  konkret, atau (b) terima (a2) — submit sebagai brief harian + prototipe
  read-only. Batas chief 24 Nov: jalur FIRM harus hidup paling lambat
  26 Nov — batas itu sudah lewat; bila sampai 30 Nov tetap 0 firm,
  kill-switch memerintahkan (a2).

## Linimasa

- Kill-switch 30 Nov; submit 4–5 Des (Septian sendiri); deadline
  5 Des 23:59 UTC = **6 Des 07:59 WITA**.
- Repo publik: https://github.com/rwnliwan/base-exit-radar
  (commit terakhir `38236c5`, 25 Nov).

## Bukti yang dicek chief hari ini

- `out/daily_manifest_2026-11-25_attempt1.json` (326/415, 24/24 PASS),
  `out/daily_manifest_2026-11-26_attempt1.json` (415/415, 24/24 PASS),
  `out/daily_manifest_2026-11-27_attempt1.json` (415/415, 24/24 PASS) —
  hitungan keputusan dibaca dari field `tokens` tiap manifest.
- `python3 verify_daily_runs.py` (26–27 Nov: 24/24 PASS tiap hari;
  24 Nov: dry_run, tidak dihitung).
- `python3 gate.py` (28 Nov 13:48 WITA): 29/29 PASS, `gate_results.json`
  diperbarui.
- `config.py`: `PAPER_PROPOSALS_ENABLED = False`.
- Pencarian tx Sepolia di `evidence/` + `out/`: tidak ada hash tx
  (hanya nilai placeholder); DECISION_MEMO-v0.3.3: registry Sepolia
  "spesifikasi saja; deploy menunggu gate + ACC".
