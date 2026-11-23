# Checklist Kill-Switch "Base Jalan" — Checkpoint 30 Nov 2026

**Untuk:** Muse (implementasi) · **Dari:** Instinct, atas ACC Septian (24 Nov 2026, 02:01 WITA)
**Konteks:** prototipe v0.3.3 · gate proposal MATI · `decide()` menahan di WATCH bila bukti simulasi · `PAPER_PROPOSAL` hanya bila quote FIRM · deadline 5 Des · Scope 1 (data Base) belum mulai.

---

## Keputusan desain (sudah ACC, jangan diubah)

1. **Reframe DeepSeek diterima.** Proposal TIDAK keluar dari dalam `decide()` atas bukti simulasi — itu overclaim. Proposal adalah **artefak terpisah di luar state machine**, berlabel `RESEARCH_DRAFT` / `ILLUSTRATIVE`. Artefak ini tetap boleh jadi bahan portofolio paper.
2. **Gate tetap OFF.** `decide()` tidak disentuh. `PAPER_PROPOSAL` tetap hanya untuk quote berstatus FIRM.
3. **Fallback (a2).** Kalau Scope 1 belum lolos checklist di bawah pada checkpoint 30 Nov, kunci ke (a2): **brief harian saja**, artefak proposal ditunda.
4. **Sepolia only.** Hash registry komitmen brief + proposal cukup di **Base Sepolia**. Jangan mainnet.

## Checklist "Base jalan" — SEMUA harus terpenuhi di 30 Nov

- [ ] **1. Data asli masuk otomatis.** Data Base asli masuk tanpa input manual, minimal **5 hari berturut-turut**. Tiap record punya timestamp dan sumber.
- [ ] **2. Quote FIRM terverifikasi silang.** Minimal 1 jalur quote berstatus FIRM, dicek ke sumber independen, selisih dalam toleransi (≤1%), minimal **10 sampel**.
- [ ] **3. Brief otomatis & reproducible.** Brief harian ter-generate otomatis minimal **3 hari** tanpa campur tangan manusia, dan bisa direproduksi dari data yang sama.
- [ ] **4. Hash Sepolia terbukti.** Ada tx on-chain di Base Sepolia, dan hash bisa diverifikasi ulang dari brief.
- [ ] **5. Integritas gate terbukti.** Gate tetap OFF, `decide()` tidak diubah, dan ada tes yang membuktikan bukti simulasi **tidak pernah** menghasilkan `PAPER_PROPOSAL`.

## Aturan kill-switch

- **Poin 1 atau 2 gagal → Base belum jalan → kill-switch jalan.** Kunci ke (a2): brief harian saja, artefak proposal ditunda.
- **Poin 3–5 tidak menyelamatkan** kalau data asli (poin 1, 2) belum ada.
- **Early exit:** kalau Scope 1 belum jalan di **hari ke-3 (27 Nov)**, putuskan (a2) lebih awal daripada memaksa.

## Batas keras (hard rules)

- Jangan mengeluarkan proposal dari dalam state machine atas bukti simulasi, dalam bentuk apa pun.
- Artefak proposal wajib berlabel `RESEARCH_DRAFT` / `ILLUSTRATIVE`. **Tanpa kolom exit atau PnL** yang bisa terbaca sebagai hasil nyata.
- Hash registry hanya di Base Sepolia. Tidak ada tx mainnet.
- Deadline tetap **5 Des**; checkpoint kill-switch **30 Nov**.

---

*Catatan jujur: Scope 1 belum mulai dan checkpoint tinggal 6 hari — jadwal ketat. Perlakukan early exit hari ke-3 sebagai keputusan nyata, bukan formalitas.*
