# DRAFT — Form Submit Base Stocks Maxxing

> **DRAFT — keputusan submit 28 Nov 2026.** Ini draf isi, BUKAN submit.
> Form resmi: https://docs.google.com/forms/d/1zotYvkeAtDjR2MKk3qNxyNIAfJ_IPQtzTtjNhOAF8js/viewform
> (link "Apply Now" di https://www.base.org/stocksmaxxing).
> Field form TIDAK terlihat dari fetch halaman (Google Form tidak
> menampilkan field-nya sebagai teks) — **sesuaikan isi di bawah dengan
> field form saat submit**. Bila ada field yang tidak ada di form, hapus
> bagiannya; bila ada field tambahan, isi dari bagian yang relevan.
>
> Tenggat: form tertulis "Ends December 5, 2026, 11:59pm EST".
> Working deadline yang dipakai rencana: **5 Des 2026 23:59 UTC
> (= 6 Des 07:59 WITA)** — lebih awal, jadi aman. Kill-switch
> operasional: **30 Nov 2026**.

---

## Project name (NAMA PROYEK — butuh keputusan Septian)

**Draf: "Radar — Exit Radar for Base Tokenized Stocks"**

Alternatif (pilih satu sebelum submit):
- "Exit Radar" (nama produk yang sudah live di radar.omdanny.site)
- "Radar: Research-to-Paper-Portfolio Agent for Base Tokenized Stocks"

## Track

**Agentic Stock Finance** — $20.000 (pool total Stocks Maxxing $50.000+).

## One-line description

Research-to-paper-portfolio agent untuk saham tokenized di Base yang
menjawab satu pertanyaan sebelum memberi sinyal apa pun: *"Bisa keluar,
dengan bukti harga seperti apa?"* — dengan sell-quote simulasi on-chain
sebagai bukti exit, bukan janji likuiditas.

## What we built (apa yang dibangun selama 13 Nov–5 Des)

Prototipe v0.3.3 (Python stdlib saja, read-only, tanpa key/wallet/
transaksi on-chain) yang:

1. **Coverage Base** — NVDAc + AAPLc (tokenized stock Coinbase di Base)
   masuk pipeline Radar: median harga lintas-venue, deviasi per venue,
   NAV + oracle multiplier, dan coverage pool/venue yang dihitung ulang
   dari data tervalidasi (bukan dipercaya dari sumber).
2. **Sell-quote adapter (read-only)** — Aero Metaquoter V3
   (`0x1dDfeC5058180C207F55BB77D95AcDd0d8227868`), satu `eth_call`
   per quote, dipin ke satu block agar snapshot bisa di-replay
   byte-exact. Double-quote probe (quote kedua 2x amount) untuk
   deteksi partial fill; probe gagal RPC = quote ditolak, bukan
   dipakai inconclusive.
3. **Oracle registry dibaca tiap run** — OracleRegistry
   (`0x3f3E8cf41cdd3b1D118c16471aB0113DfDDd5CaD`), `getOracleParams`:
   multiplier + status pause. `paused = true` = pause ORACLE (feed
   beku, NAV basi), BUKAN pause transfer — quote DEX tetap valid
   sebagai bukti exit.
4. **Keputusan paper portfolio yang jujur** — WATCH / ABSTAIN /
   PAPER_PROPOSAL, dengan alasan yang tercatat. Gate proposal
   (`PAPER_PROPOSALS_ENABLED`) TETAP MATI: tanpa quote firm, simulasi
   ditahan di WATCH dan seluruh alokasi simulasi di cash.

## How it works (cara kerja — quoter + oracle + deviasi)

1. **Ingest** — harga pool dari sumber publik (Coinbase, DexScreener,
   GeckoTerminal, Hyperliquid proxy) + snapshot on-chain via RPC
   publik Base (read-only `eth_call`).
2. **Validate** — chain, kontrak, symbol, decimals (8/6), token_out
   harus USDC (native `0x8335…A02913` atau USDC.e `0xd9aA…710b6CA —
   diverifikasi ke BaseScan + CoinGecko, bukan dari ingatan);
   sanity harga implisit ±10% dari median.
3. **Assess** — median lintas-venue, deviasi per venue, freshness
   per jenis data (pool / quote / NAV + sesi pasar NYSE), coverage
   dihitung ulang dari pool tervalidasi.
4. **Exit evidence (Layer B)** — simulasi sell via Metaquoter V3:
   amount_out, sqrt-price, tick, oracle multiplier, block hash —
   semua tercatat di snapshot + transcript RPC mentah
   (`evidence/rpc/`, 18 file + manifest).
5. **Decide** — WATCH bila deviasi / NAV basi / tidak ada quote firm;
   PAPER_PROPOSAL hanya bila layer B terverifikasi DAN gate proposal
   menyala. Gate saat ini MATI, jadi keputusan maksimal adalah WATCH.

## Validation results (angka persis — terverifikasi)

- **Gate: 19/19 PASS** (`python3 gate.py`, v0.3.3).
- **Audit independen Instinct, 23 Nov 2026: 9,8/10 — ACC v0.3.3 untuk
  tahap read-only, NOL must-fix.** Auditor mereproduksi gate 19/19
  dan replay RPC 22/22 secara independen; diff v0.3.2→v0.3.3 hanya
  M1–M3 (7 file + 2 baru), tidak ada perubahan lain.
- **Live run v0.3.3, 23 Nov 2026 00:12 WITA (block-pinned):**
  - **NVDAc → WATCH.** Median $132,82. Simulasi 78,99488414 token →
    estimasi $10.498,34; harga implisit $132,89895047 vs median
    **+0,059%**. Block 60867888. Probe partial-fill rasio
    **1,99991884** (sehat, probe_ok=True). Oracle multiplier
    1,0005379395763696, paused=false. Coverage 11 pool / 6 venue,
    0 fallback. Factory di exit_quote:
    `0x9cb220581b91b0c83223012fe69688b92ad07a76` (Aero Slipstream
    CLFactory).
  - **AAPLc → WATCH.** Median $349,565. Simulasi 30,03346586 token →
    estimasi $10.497,92; harga implisit $349,5407879 vs median
    **−0,007%**. Block 60868044. Probe rasio **1,99983284** (sehat,
    probe_ok=True). Oracle multiplier 1,0005003893019802,
    paused=false. Coverage 6 pool / 4 venue, 0 fallback.
  - Keduanya: seluruh alokasi simulasi di cash (`cash_weight: 1.0`)
    karena gate proposal mati — by-design, bukan bug.
- **Replay RPC: 22/22** (18 transcript RPC + 4 cross-check amount_out
  snapshot) — amount_out, sqrt-price, ticks, probe amount_out,
  oracle multiplier, block hash, factory, token0/token1, decimals
  cocok persis dengan snapshot. Chief memverifikasi di 3 RPC
  independen; Instinct mereproduksi di 1 RPC publik
  (mainnet.base.org).

## Links

- Produk live (Radar): https://radar.omdanny.site
- Halaman kompetisi: https://www.base.org/stocksmaxxing
- Paket evidence v0.3.3 (Drive, publik): folder "Base Stocks Maxxing"
  di folder `funding` — 32 file, md5 terverifikasi.
  Repo publik: https://github.com/rwnliwan/base-exit-radar
  (diputuskan 23 Nov 2026 — prototipe dipindah ke repo sendiri, publik;
  paket Drive tetap sebagai arsip, radar.omdanny.site sebagai showcase.)
- Demo video: *(link diisi setelah video direkam — lihat
  `script-demo-video.md`)*

## Honest limitations (batasan yang jujur — JANGAN dihapus dari submit)

- **Quote adalah simulasi on-chain (`eth_call`), BUKAN quote firm /
  komitmen eksekusi bertanda tangan.** Layer B berlabel
  `simulated_exit_quote_verified`, bukan "verified". Tidak ada
  transaksi yang dikirim; eksekusi di luar scope.
- **Gate proposal tetap mati** — PAPER_PROPOSAL tidak terjangkau
  sampai ada jalur quote firm + review ulang. Prototipe ini
  read-only dan tidak memberi sinyal beli.
- **Threshold policy adalah eksperimen, belum tervalidasi** (bukan
  kalibrasi). Lolos test teknis bukan bukti kualitas prediktif atau
  keuntungan. Tidak ada backtest.
- **Coverage terbatas:** NVDAc + AAPLc saja; pool Uniswap V4 tidak
  masuk coverage (pairAddress V4 adalah poolId 32-byte, bukan alamat
  kontrak); PoR + redemption tetap `unknown` (tidak ada sumber
  otomatis).
- **Tidak ada klaim return / profit.** Tidak ada live trading.

## Team / contact

- Septian Panjaya — Data Analyst (finance risk analytics).
- *(Email + X/Threads handle diisi Septian saat submit.)*
- Proyek tidak memakai token sendiri; tidak ada token yang
  diluncurkan 5 Agu–4 Nov (aturan token tidak relevan).

---

## Catatan untuk Septian (bukan bagian form)

1. **Nama proyek final** — pilih sebelum submit (lihat opsi di atas).
2. **Link repo/evidence** — DIPUTUSKAN 23 Nov 2026: repo GitHub publik
   https://github.com/rwnliwan/base-exit-radar (+ paket Drive publik
   sebagai arsip; radar.omdanny.site sebagai showcase).
3. **Field form** — cek langsung form-nya saat submit; struktur di
   atas mengikuti isi yang umum ditanya (nama, track, deskripsi,
   cara kerja, validasi, link, batasan). Bila form minta video/post
   X, pakai `draft-post-x.md` + `script-demo-video.md`.
4. **"Enable trading for U.S. users"** — form menyatakan proyek yang
   mengaktifkan trading untuk pengguna AS tidak in scope. Prototipe
   ini read-only, tanpa trading, jadi tidak kena klausul itu.
5. **Verifikasi ID + W-9/W-8** hanya bila menang (≤30 hari setelah
   verifikasi, dibayar USDC di Base).
