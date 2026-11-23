# Keputusan yang menahan jadwal Base — fitur agen + elemen onchain

Ditulis chief, 23 Nov 2026 ~22:40 WITA. Tujuannya satu: supaya keputusan ini
bisa diambil SEKARANG, bukan menunggu 28 Nov, agar jendela kerja bisa maju
dari jadwal rencana ketat (submit 4–5 Des, deadline 5 Des 23:59 UTC).

## Status jujur hari ini (23 Nov malam)

SUDAH ADA + JALAN (prototipe read-only, terverifikasi):
- Sell-quote adapter Aero Metaquoter V3 (v0.3.3): NVDAc + AAPLc → USDC,
  live run 23 Nov 00:12 keduanya WATCH, gate 19/19 PASS, replay RPC 22/22.
- Audit Instinct re-audit v7: 9,5/10, ACC tahap read-only, nol must-fix.
- Batas jujur: quote masih simulasi `eth_call`, BUKAN firm/komitmen eksekusi.
  Gate proposal MATI (`PAPER_PROPOSALS_ENABLED = False`).

BELUM ADA SAMA SEKALI:
- Scope 1 — coverage Base di poller + universe + web, kalibrasi ulang Exit
  Score Base (jadwal rencana: 24–27 Nov).
- Fitur agen (lihat di bawah) + elemen onchain (lihat di bawah).
- Video demo, post X, nama proyek final, cek halaman 2 form.

Jadi: integrasi DATA + QUOTE sudah jalan. Integrasi PENUH (agen + onchain)
belum mulai — itu kerjaan jendela 28–30 Nov. Submit lebih awal = majukan
jendela itu, bukan melewatinya.

## Keputusan 1 — pilih satu fitur agen (jangan dua)

- (a) Research-to-portfolio agent: brief harian → usulan portofolio.
  Rekomendasi chief: (a) — paling dekat dengan yang sudah ada (brief +
  skor), paling gampang didemo.
- (b) Agent-managed rebalancing: sinyal rebalance dari Exit Score.
  Lebih "agen", tapi lebih berat: butuh eksekusi/simulasi + kontrol risiko.

## Keputusan 2 — desain elemen onchain minimal (bagian tersulit)

Harus sesuatu yang tercatat/dieksekusi di Base, bukan sekadar monitor.
Kandidat:
- (i) Prediksi / Exit Score dipublikasi onchain (hash registry — brief
  Instinct menyebut Base Sepolia hash registry sebagai DESAIN fase sesudah
  gerbang; perlu wallet + gas, belum ada desain).
- (ii) Aksi agen tercatat di Base.

Konteks jujur: bobot traction dilaporkan 50% (CryptoBriefing 6 Nov, TIDAK
terverifikasi di halaman resmi). Asumsikan traction onchain nyata itu
penting. Radar sekarang read-only — itu kelemahan struktural yang elemen
ini harus tutup, setidaknya sebagian.

## Keputusan 3 — nama proyek final (bisa bareng keputusan 1–2)

Draf: "Radar — Exit Radar for Base Tokenized Stocks". Rekomendasi Claude:
"Exit Radar" saja. Nama live di radar.omdanny.site: "Exit Radar".

## Arti kill-switch 30 Nov

"Integrasi Base jalan" = Scope 1 + fitur agen + elemen onchain minimal
JALAN (bukan sekadar quote adapter). Bila belum jalan 30 Nov: BERHENTI,
jangan korbankan Ticko/Draft M.

## Yang hanya Septian yang bisa kerjakan (tetap)

Post X + video demo + form submission; bila menang, verifikasi ID + W-9/W-8.
Video demo itu waktu Septian — tidak bisa didelegasikan.
