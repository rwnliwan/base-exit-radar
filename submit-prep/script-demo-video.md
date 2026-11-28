# DRAFT — Script Video Demo Base Stocks Maxxing (±2–3 menit)

> **DRAFT — keputusan submit 28 Nov 2026.** Video direkam oleh Septian
> (waktu Septian — tidak bisa didelegasikan). Script ini bahan rekaman.
> Gaya: Bahasa Indonesia santai + istilah teknis English (gaya Septian).
> Total target: ±2–3 menit. Narasi di bawah ditulis sebagai ucapan
> Septian; **[LAYAR]** = apa yang tampil.

---

## Scene 1 — Hook (0:00–0:20)

**[LAYAR]** Judul: "Radar — Bisa keluar, dengan bukti harga seperti apa?"
+ logo/screenshot radar.omdanny.site.

**Narasi:**
> "Saham tokenized di Base itu gampang dibeli. Yang susah: pas mau
> jual, harganya beneran segitu nggak? Radar jawab itu dulu, sebelum
> kasih sinyal apa pun."

## Scene 2 — Apa yang dibangun (0:20–0:50)

**[LAYAR]** Diagram sederhana: Ingest → Validate → Assess → Exit
evidence → Decide. Tampilkan dua token: NVDAc, AAPLc.

**Narasi:**
> "Ini prototipe v0.3.3, buat track Agentic Stock Finance di Base
> Stocks Maxxing. Agent research-to-paper-portfolio untuk NVDAc dan
> AAPLc. Python stdlib doang, read-only, tanpa wallet, tanpa
> transaksi. Alurnya: data masuk, divalidasi, dinilai, terus diuji
> bukti exit-nya, baru diputusin: WATCH, ABSTAIN, atau paper proposal."

## Scene 3 — Live run (0:50–1:30)

**[LAYAR]** Terminal: `python3 run.py` jalan live, lalu tampilkan
hasil snapshot/decision NVDAc + AAPLc (atau screenshot output yang
sudah ada di `out/v0.3.3/`).

**Narasi:**
> "Ini live run 23 November. NVDAc: WATCH. Median 132,82 dolar.
> AAPLc: WATCH. Median 349,56 dolar. Dua-duanya WATCH — dan itu
> sengaja. Gate proposal-nya mati, jadi simulasi nahan semua alokasi
> di cash. Bukan bug, by-design: tanpa bukti exit yang firm, kita
> nggak ngarang sinyal beli."

## Scene 4 — Bukti exit (1:30–2:05)

**[LAYAR]** Sorot angka-angka kunci di snapshot: simulasi Metaquoter,
probe ratio, oracle multiplier, block number, factory.

**Narasi:**
> "Bukti exit-nya dari mana? Sell-quote simulasi on-chain, pakai Aero
> Metaquoter V3 — satu eth_call, dipin ke satu block, jadi bisa
> di-replay byte-exact. NVDAc: 79 token disimulasi jual, estimasi
> 10.498 dolar, harga implisit 132,90 — cuma 0,059 persen dari median.
> Probe partial-fill rasionya 1,9999 — sehat, nggak capped. Oracle
> registry juga dibaca tiap run: multiplier 1,0005, paused false.
> Replay RPC-nya 22 dari 22 cocok. Gate 29 dari 29 lolos, audit
> independen 9,8 dari 10, nol must-fix."

## Scene 5 — Batasan jujur (2:05–2:30)

**[LAYAR]** Teks di layar, satu per satu: "Simulasi, bukan firm" /
"Gate proposal MATI" / "Threshold eksperimen" / "NVDAc + AAPLc saja".

**Narasi:**
> "Tapi jujur aja soal batasnya. Quote ini simulasi, bukan quote firm
> — bukan komitmen eksekusi. Gate proposal tetap mati sampai ada
> jalur quote firm. Threshold-nya masih eksperimen, belum tervalidasi.
> Dan cakupannya baru dua token. Ini prototipe read-only, bukan mesin
> cuan."

## Scene 6 — Penutup + CTA (2:30–2:45)

**[LAYAR]** radar.omdanny.site + base.org/stocksmaxxing + "Track:
Agentic Stock Finance".

**Narasi:**
> "Radar — buat Base Stocks Maxxing. Detail validasi lengkap ada di
> deskripsi. Terima kasih."

---

## Catatan produksi (bukan bagian script)

- **Durasi:** 6 scene, total ±2:45. Bila kepanjangan, pangkas Scene 2
  (diagram) — jangan pangkas Scene 5 (batasan jujur).
- **Rekaman layar:** Scene 3 paling bagus direkam dari `python3 run.py`
  live (atau replay `run.py --replay fixtures/...` bila koneksi
  lambat — hasil sama, berlabel replay). Scene 4 pakai snapshot
  `out/v0.3.3/` yang sudah ada — jangan ketik ulang angka.
- **Angka yang tampil di layar (cek ulang sebelum rekam):**
  NVDAc median $132,82 / implisit $132,89895047 (+0,059%) / block
  60867888 / probe 1,99991884 / oracle 1,0005379395763696 /
  11 pool 6 venue. AAPLc median $349,565 / implisit $349,5407879
  (−0,007%) / block 60868044 / probe 1,99983284 / oracle
  1,0005003893019802 / 6 pool 4 venue. Gate 29/29 (re-run 28 Nov),
  audit 9,8/10, replay 22/22. Daily brief otomatis: 25–27 Nov
  (26–27 Nov 415/415, ABSTAIN 405/WATCH 10).
- **Jangan ucapkan:** "pasti cuan", "dijamin", "live trading",
  "sudah terbukti menguntungkan". Bila salah ucap saat rekam, ulang
  scene-nya.
- **Audio:** suara Septian langsung (tanpa voice-over AI) — ini
  video demo Septian, bukan video agen.
