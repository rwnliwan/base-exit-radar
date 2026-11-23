# Base Stocks Maxxing — Rencana Ketat 13 Hari (22 Nov → 5 Des 2026)

> Rencana keputusan untuk Septian. Disusun 22 Nov 2026 ~10:15 WITA.
> Fakta hadiah/track diverifikasi live 16 Nov 2026 (lihat
> `~/workspace/research_notes/bug-bounty-platforms-check-20261116-1335/notes/base-tracks-live.md`).
> Belum ada keputusan "gas" — dokumen ini bahan keputusannya, bukan
> perintah mulai kerja.

## 1. Fakta yang mengikat

- Tenggat submit: **5 Des 2026**. Sisa **13 hari** dari hari ini.
- Perkiraan kerja scope ketat: **~3 minggu** (riset 16 Nov). Jadi scope
  harus dipangkas ke ~60% dari perkiraan awal — tidak ada ruang untuk
  fitur kedua.
- Hadiah: total Base **$50.000**; track **Agentic Stock Finance $20.000**
  (paling cocok) atau Programmable Stock Markets $20.000. Dibayar USDC
  di Base, umumnya ≤30 hari setelah verifikasi; pemenang wajib
  verifikasi ID + W-9/W-8.
- Eligibilitas: produk live yang sudah ada BOLEH ikut, asal ada fitur
  baru terkait saham yang dibangun selama quest (**13 Nov–5 Des**).
  Radar tidak punya token, jadi aturan token (5 Agu–4 Nov) tidak relevan.
- Penilaian: **50% traction / 25% kualitas produk / 25% build-in-public —
  DILAPORKAN CryptoBriefing 6 Nov, TIDAK terverifikasi di halaman resmi
  (Rules §7 tidak menyebut angka itu).** Perlakukan bobot traction
  sebagai belum terkonfirmasi, tapi asumsikan traction onchain nyata
  itu penting — Radar sekarang read-only, itu kelemahan struktural.

## 2. Scope ketat (satu fitur agen + coverage Base, titik)

1. **Coverage Base** — tokenized stock Coinbase di Base (mis. NVDAc/
   AAPLc) masuk poller + universe + web, metodologi sama seperti Solana
   (deviasi lintas-venue, redemption/PoR, Exit Score dikalibrasi ulang).
2. **Satu fitur agen** (pilih satu, jangan dua):
   - (a) research-to-portfolio agent: brief harian → usulan portofolio;
   - (b) agent-managed rebalancing: sinyal rebalance dari Exit Score.
   Rekomendasi chief: (a) — paling dekat dengan yang sudah ada (brief +
   skor), paling gampang didemo.
3. **Elemen onchain minimal** (bagian tersulit, belum ada desain):
   sesuatu yang tercatat/dieksekusi di Base, bukan sekadar monitor.
   Kandidat: prediksi/Exit Score dipublikasi onchain, atau aksi agen
   yang tercatat di Base. Keputusan desain ini harus diambil di hari
   pertama — tanpa ini, skor traction tidak bisa ditutup.

Yang DIPANGKAS: semua chain lain, semua fitur agen kedua, polish web
di luar demo, integrasi DEX Base di luar yang dibutuhkan scope 1.

## 3. Jadwal + kill-switch

| Kapan | Apa |
|---|---|
| 22–23 Nov | Keputusan gas/tidak + pilih fitur agen (a)/(b) + desain elemen onchain |
| 24–27 Nov | Scope 1 (data Base) jalan; kalibrasi Exit Score Base |
| 28–30 Nov | Fitur agen + elemen onchain; demo video direkam |
| **30 Nov** | **KILL-SWITCH: bila integrasi Base belum jalan, BERHENTI.** Jangan korbankan Ticko/Draft M |
| 1–3 Des | Uji akhir + QA (cara kerja chief: verifikasi dulu baru lapor) |
| 4–5 Des | Submit (form + post X + video demo) |

## 4. Yang hanya Septian yang bisa kerjakan

Post X + video demo + form submission; bila menang, verifikasi ID +
W-9/W-8. Video demo itu waktu Septian — tidak bisa didelegasikan.

## 5. Repo kerja Muse + Instinct (rencana Septian 22 Nov pagi)

Septian akan bangun repo agar chief dan Instinct bekerja simultan
(seperti Muse + Cue, tapi kali ini chief + Instinct). Blueprint:

- Repo privat baru (bukan repo bus Armada — itu untuk Muse-2/Muse-3/Cue).
  Pembuatan repo butuh koneksi GitHub Septian (Armada Fase 1 masih
  menunggu koneksi yang sama — belum tersambung).
- Struktur: `tasks/` (satu file per tugas, status di dalamnya),
  `reports/` (laporan final per tugas — status sah ditentukan laporan,
  bukan klaim chat), `briefs/` (brief chief → Instinct), `docs/`.
- Alur: chief tulis brief → Instinct kerjakan/review di branch-nya →
  chief verifikasi dari sumber (bukan dari klaim) → merge.
  Taksonomi status pakai pola Armada (14-status) agar konsisten.
- Aturan keras: **tidak ada token/secret/kunci di repo** (token DFX,
  kredensial Turso, dsb. tetap di file mode 600 di VM); push hanya
  setelah tree lokal ≥ remote untuk file tugas/laporan (pelajaran
  insiden push snapshot 20 Okt — sinkron dulu, baru push).
- Isi awal repo: file ini + brief Base untuk Instinct (setelah Septian
  pilih fitur agen).

## 6. Biaya peluang (jujur)

Tiga jalur hidup sekarang: Ticko (Draft M menunggu verifikasi Septian),
DFX (keputusan Ronde 2 — lihat `~/workspace/bug-bounty/dfx-swiss/keputusan-ronde-2.md`),
make.fun (catur tutup 25 Nov 01:00 WITA). Base jadi jalur keempat.
Yang tersulit buat Septian kemungkinan besar bukan teknisnya, tapi
menjaga fokus 13 hari tanpa mengorbankan jalur yang sudah terbukti.
