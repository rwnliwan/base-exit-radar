# Rencana Eksekusi Scope 1 — Base Stocks Maxxing (Exit Radar)

**Status: RENCANA — belum ACC. Build DITAHAN sampai ACC review.**
**Ditulis:** 24 Nov 2026 ~02:2x WITA, koordinator build.
**Dasar:** `docs/perbandingan-fitur-agen-a-vs-b-2026-11-24.md` §7–§8.5,
`docs/killswitch-checklist-2026-11-24.md`,
`docs/BASE-STOCKS-MAXXING-RENCANA-KETAT-2026-11-22.md` §2–§3,
kode prototipe v0.3.3 (`config.py`, `pipeline.py`, `adapter.py`,
`run.py`, `gate.py`, `DESIGN.md`, `QUOTER-RESEARCH.md`).

**Keputusan yang sudah ACC (jangan dibuka lagi):** (a)
research-to-portfolio + (a1') reframe DeepSeek/Instinct + Sepolia +
fallback (a2) + kill-switch 5 kriteria. Nama: "Exit Radar", display
"Exit Radar for Base". Deadline submit 5 Des 2026 23:59 UTC =
6 Des 07:59 WITA. Checkpoint kill-switch 30 Nov.

**Batas keras (berlaku untuk rencana ini maupun build-nya):**
`decide()` TIDAK disentuh; `PAPER_PROPOSALS_ENABLED` tetap `False`;
`PAPER_PROPOSAL` tetap hanya untuk quote FIRM; tanpa mainnet; tanpa
kredensial/API key/wallet/seed di repo. Rencana ini TIDAK mengusulkan
pelonggaran batas keras apa pun — termasuk TIDAK mengusulkan definisi
baru "firm" yang melonggarkan validator.

---

## 0. Ringkasan eksekutif + verdict jujur

Scope 1 = tiga hal: **(i)** coverage Base (poller + universe + web),
**(ii)** jalur quote FIRM, **(iii)** kalibrasi Exit Score Base.
Dua dari tiga hal itu bisa dikerjakan dengan pasti. Satu hal —
**jalur quote FIRM — adalah risiko terbuka yang mungkin tidak ada
jawabannya dalam jendela ini**, dan rencana ini menuliskannya apa
adanya (lihat §2.5): bila tidak ada kandidat yang lolos probe
sampai 26 Nov, kriteria kill-switch 2 dinyatakan tidak terpenuhi
dan paket dikunci ke (a2) pada review early exit 26 Nov — bukan
menunggu 30 Nov.

Tanggal yang mengikat adalah **26 Nov, bukan 30 Nov**: kriteria 1
menuntut 5 hari berturut-turut data otomatis sampai checkpoint
30 Nov, jadi run otomatis pertama HARUS terjadi 26 Nov
(26–30 Nov = tepat 5 hari). Bila review rencana ini belum diputuskan
sampai pagi 25 Nov, tanggal 26 Nov sudah slip — dan itu sendiri
adalah pemicu early exit (§6).

---

## 1. Peta coverage — poller / universe / web

### 1.1 Keadaan sekarang (terverifikasi dari kode + bukti)

- **Runner:** `run.py` = satu pass manual untuk token di
  `config.TOKENS` (hari ini: NVDAc + AAPLc saja). Tidak ada
  scheduler/cron di repo — tidak ada satu pun referensi cron di
  file `.py`/`.md` repo ini kecuali rencana. Output ke `out/`
  (`snapshot_*`, `decision_*`, `alert_*`, `paper_record_*`,
  `alerts_seen.json`). File `out/` terakhir bertanggal 23 Nov
  14:14 — run bersifat manual, satu kali, bukan harian otomatis.
- **Ingest** (`pipeline.py:ingest_token`, baris 626–799): per token —
  Coinbase record (`fetch_coinbase_tokens` + `find_token`), pool
  DexScreener (`fetch_dexscreener_pools`), cross-check GeckoTerminal
  HANYA untuk pool teratas (by liquidity) — pool yang sama, bukan
  venue baru — proxy Hyperliquid dex `xyz` saja
  (`xyz:NVDA`/`xyz:AAPL`), lalu RPC read-only: `fetch_block` (pin
  block — semua eth_call dihitung pada state block yang sama agar
  snapshot bisa di-replay), `fetch_oracle_params` (multiplier +
  paused), `fetch_pool_factory` per pool, sell quote
  (`fetch_sell_quote` + double-quote probe partial-fill).
- **Snapshot** (`pipeline.py:build_snapshot`, baris 800–1115):
  observasi pool di-dedup by `pool_address`; pool ditolak bila
  `pairAddress` bukan alamat valid, chain bukan base, baseToken
  bukan token yang dimaksud, harga/likuiditas tidak positif.
  Coverage dihitung dari nama kanonis (`independent_pool_count`,
  `independent_venue_count`, `verified_venue_count`,
  `verified_pool_count`, `fallback_pool_count`). Median dari
  observasi yang lolos; bila hanya 2 observasi, dicatat
  `median_fragile_two_observations`.
- **Keputusan** (`pipeline.py:decide`, baris 1472–1546): ABSTAIN /
  WATCH / PAPER_PROPOSAL. Dua penahan independen membuat
  PAPER_PROPOSAL tidak terjangkau hari ini: gate mati (aturan 3)
  DAN bukti exit simulasi, bukan firm (aturan 4,
  `exit_evidence_simulated_not_firm`). **Rencana ini tidak
  menyentuh `decide()` sama sekali.**
- **Validator quote** (`pipeline.py:validate_exit_quote`, baris
  242–502): sudah membedakan `verified` (firm) dari
  `simulated_verified` (simulasi on-chain). Cabang firm SUDAH ADA
  dan SUDAH ketat — yang belum ada hanyalah produsen quote firm.
  Tidak ada perubahan validator yang diusulkan.

### 1.2 Universe — dari 2 token ke sensus lengkap

- **Fakta dasar (terverifikasi):** API Coinbase
  `GET https://api.coinbase.com/v1/tokenized-stocks` bersifat
  paginasi. Page 1 = **100 token** + `next_page_token`.
  Page 2 (dicek live 24 Nov) = **100 token lagi** + masih ada
  `next_page_token`. **Total universe >200 token** — angka pastinya
  belum diketahui sampai paginasi dijalani sampai habis.
  Semua alamat token berawalan `0xb200…` (pola factory Coinbase).
- **Item S1-A — Sensus universe (0,5 hari).** Jalani semua halaman
  API Coinbase, simpan `evidence/coinbase_tokenized_stocks_all.json`
  + manifest (jumlah total, timestamp, `next_page_token` terakhir).
  Aturan masuk universe yang diusulkan (untuk review):
  token masuk `config.TOKENS` bila punya ≥1 pool DexScreener
  dengan quote USDC + likuiditas >$10.000 + harga valid; token
  yang tidak memenuhi dicatat di `universe_no_coverage.json`
  (BUKAN dihapus diam-diam). Token tanpa pool USDC yang likuid
  tetap tercatat sebagai "tanpa coverage", bukan sebagai "tidak
  ada".
- **Perubahan dari sekarang:** `config.TOKENS` hari ini hard-code
  2 token; sesudah sensus, `config.TOKENS` dihasilkan dari sensus
  (dengan catatan bertanggal + jumlah total universe). `run.py`
  tidak berubah bentuk — ia sudah loop `config.TOKENS`.

### 1.3 Venue — Aerodrome dominan, Uniswap V4 tidak ter-cover

- **Fakta dasar (terverifikasi 24 Nov, live + evidence 22 Nov):**
  DexScreener NVDAc = 30 pair (live: 19 ber-`dexId` "uniswap",
  5 "aerodrome", 2 "aero", 2 "equalizer", 1 "nami", 1 "hydrex").
  AAPLc = 25 pair. **DexScreener TIDAK memisahkan V3/V4 di
  `dexId`** — keduanya berlabel "uniswap" — tapi ada DUA sinyal
  yang saling menguatkan: field `labels` (`['v3']` / `['v4']`)
  DAN panjang `pairAddress`: V3 = 42 karakter (alamat kontrak),
  V4 = 66 karakter (poolId 32-byte, bukan kontrak).
  Bukti 22 Nov: NVDAc 30 pair = 15 V4 (poolId) + 15 V3 (alamat).
  Live 24 Nov: ~16 V4 + ~3 V3 dari 19 pair "uniswap".
- **Koreksi atas angka yang beredar:** likuiditas V4 NVDAc/USDC
  yang material (evidence 22 Nov) adalah **~$92rb dari 2 pool**
  (0xb2176952… $50.731,79 + 0xc8c52ec4… $41.314,08) — BUKAN
  ~$130rb. Pool $130.384 (0x41084f2d…) adalah BLUECHIP/NVDAc,
  yaitu NVDAc sebagai QUOTE token, bukan observasi harga NVDAc
  dalam USDC; `build_snapshot` sudah menolak pool seperti itu
  (`base_token_mismatch`). Angka ~$130rb jangan dipakai lagi
  untuk klaim likuiditas V4 NVDAc/USDC.
- **Kenapa V4 tidak ter-cover hari ini (akar kode, bukan asumsi):**
  `build_snapshot` menolak `pairAddress` 66-karakter karena
  `_is_address()` hanya menerima 42 karakter — V4 poolId jatuh
  ke `rejected_observations` (`invalid_address`) dan tidak pernah
  masuk median. `fetch_pool_factory()` juga tidak bisa jalan untuk
  poolId (bukan kontrak). Jadi V4 butuh jalur kode baru, bukan
  sekadar "tambah factory".
- **Item S1-B — Sensus venue (0,5 hari).** Untuk tiap token
  universe: tarik semua pair DexScreener; klasifikasikan V3/V4
  dari `labels` + panjang `pairAddress` (keduanya harus cocok;
  bila tidak cocok, tandai `v4_classification_conflict` dan
  selidiki, jangan tebak); catat likuiditas + quote asset per
  pool. Output: `evidence/venue_census_<tanggal>.json` +
  ringkasan (jumlah pool per venue family, per token).
- **Item S1-C — Jalur kode V4 (1 hari).** `build_snapshot` menerima
  poolId 66-karakter sebagai observasi dengan identitas
  `pool_id` (BUKAN `pool_address`); venue = `uniswap-v4` dari
  label DexScreener + panjang (ditandai `venue_label_source:
  dexscreener_fallback`, BUKAN `venue_verified` — factory tidak
  bisa dibaca untuk poolId, jadi independensi V4 tidak pernah
  diklaim sebagai terverifikasi factory); `fetch_pool_factory`
  dilewati untuk poolId. Verifikasi keberadaan pool V4 (bila
  memungkinkan dalam waktu): `eth_call` ke PoolManager
  (`getSlot0(poolId)`) — bila mengembalikan data, pool ada;
  bila gagal, pool dicatat `unverified`, bukan dipakai.
  Sell-quote untuk pool V4 TIDAK termasuk Scope 1 — Metaquoter
  V3 tidak bisa meng-quote pool V4 (butuh V4 Quoter + PoolKey);
  quote tetap dari pool V3/Aero yang eligible seperti sekarang.
  Tes: fixture V4 (poolId NVDAc) masuk median; V4 tidak pernah
  dihitung sebagai `venue_verified`; `gate.py` tetap hijau.
- **Perubahan dari sekarang:** coverage harga dari 2 token ×
  ~1 pool dominan → N token × semua pool yang lolos filter
  (termasuk V4 sebagai observasi harga berlabel fallback);
  `verified_venue_count` tetap hanya dari factory yang terbaca.

### 1.4 Poller — dari manual ke otomatis (ini yang menentukan kriteria 1)

- **Item S1-D — Otomatisasi run harian (0,5 hari, HARD 26 Nov).**
  Pasang cron di VM chief: `run.py` (semua token universe)
  1×/hari pada jam tetap WITA + `run_manifest.json` harian
  (timestamp run, daftar token, status per token, sumber per
  record, jumlah snapshot). Bukti otomatisasi = manifest 5 hari
  berturut-turut (26–30 Nov) yang dihasilkan cron, BUKAN run
  manual. Skrip verifikasi `verify_daily_runs.py`: memeriksa
  manifest 5 hari ada + tiap record punya `fetched_at` +
  `source` + tidak ada input manual. Bila cron belum terpasang
  26 Nov, kriteria 1 sudah mustahil (lihat §6, pemicu T1).
- **Catatan kalender:** 26 Nov 2026 = Thanksgiving (sudah ada di
  `config.US_MARKET_HOLIDAYS_2026`) dan 28–29 Nov = akhir pekan.
  NAV akan beku (`session_status: off_hours`, dilabeli) — itu
  TIDAK menggagalkan kriteria 1: kriteria 1 menuntut DATA
  (pipeline jalan + record tercatat), bukan NAV segar. Data DEX
  tetap live 24/7. Kalibrasi (§3) harus memisahkan observasi
  libur/akhir pekan dari hari bursa normal.

### 1.5 Web — batas repo ini

- **Fakta:** repo ini TIDAK punya direktori `web/`. Permukaan
  "web" repo ini adalah `pipeline.public_snapshot()` → file
  `out/snapshot_<symbol>_<snapshot_id>.json`. Situs
  radar.omdanny.site hidup di repo `radar-tokenized-stocks`
  (Next.js, repo lain).
- **Item S1-E — Kontrak feed + indeks harian (0,5 hari).**
  `public_snapshot` untuk SEMUA token universe + indeks harian
  `out/index_<tanggal>.json` (daftar snapshot_id per token,
  keputusan, timestamp). Integrasi ke situs radar adalah item
  TERPISAH di repo lain (pemilik: chief) — Scope 1 di repo ini
  selesai bila feed + indeks tersedia dan terdokumentasi;
  jangan klaim "web selesai" sebelum situs menampilkan token
  Base baru. Bila situs belum menampilkan saat checkpoint,
  itu dicatat sebagai gap, bukan sebagai kegagalan kriteria 1
  (kriteria 1 soal data, bukan soal tampilan).

---

## 2. Jalur quote FIRM — definisi, opsi, probe, dan aturan keputusan

### 2.1 Definisi FIRM yang dipakai (sudah ada di kode — bukan definisi baru)

`pipeline.py:validate_exit_quote` (baris 242–502). Quote FIRM =
`kind` ∈ (`firm`, `executable`, `guaranteed`) + `amount_out_min`
(bukan estimasi) + `expires_at` (jaminan vendor, bukan aturan
internal) + `quoted_at` + semua sanity check yang sama dengan
simulasi: token_out di allowlist USDC Base, side SELL, notional
yang dinyatakan ≥ notional proposal ($10.000), notional hitung
(`amount_in` × median) ≥ proposal, harga implisit dalam ±10%
dari median DEX, konsistensi notional dalam rasio 2×, umur
≤300 detik, `expires_at` > waktu evaluasi. Lolos semua →
status `verified` → layer B `verified`.

**Yang TIDAK berubah:** taksonomi ini BEKU. Tidak ada `kind`
baru, tidak ada pemetaan simulasi → `verified`, tidak ada
pelonggaran toleransi. Satu-satunya yang dibangun adalah
PRODUSEN quote firm baru (bila ada vendor yang memenuhi).
Simulasi yang diperkuat (mis. dry-run calldata swap) tetap
`kind: onchain_simulation` — ia bukan komitmen eksekusi, dan
menyebutnya firm adalah overclaim yang dilarang reframe (a1').

**Peran FIRM dalam paket (a1'):** perlu ditegaskan — di bawah
(a1'), proposal paper (RESEARCH_DRAFT) memakai bukti SIMULASI
dan TIDAK butuh quote firm. Jalur FIRM dibutuhkan karena
**kriteria kill-switch 2** menuntutnya, dan karena ia adalah
tonggak integritas (bukti exit yang sebenarnya). FIRM saja
tidak pernah menghasilkan PAPER_PROPOSAL selama gate OFF —
gate tetap mati apa pun hasil probe ini.

### 2.2 Yang sudah gugur (riset 22 Nov, QUOTER-RESEARCH.md — tidak diulang)

| Kandidat | Hasil 22 Nov |
|---|---|
| 0x Swap API v1 (tanpa key) | `no Route matched with those values` untuk NVDAc → USDC. Tidak ada rute. |
| 0x permit2 / v2 (Base) | Butuh API key (`No API key found in request`). Registrasi + key. |
| 1inch Swap API v6 (Base) | Butuh API key (`Unauthorized`). |
| DexScreener / GeckoTerminal | Bukan quoter: hanya harga spot + likuiditas. Hitung quote dari reserve TIDAK berlaku untuk pool CL (harga eksekusi tergantung distribusi likuiditas per tick). |
| Coinbase tokenized-stocks API | Tidak ada endpoint quote (hanya NAV + multiplier + total_supply). |
| Hitung quote off-chain dari state pool (slot0 + ticks) | FEASIBLE sebagai cadangan, tapi hasilnya tetap simulasi — BUKAN firm. |

### 2.3 Kandidat yang tersisa untuk di-probe (item S2, 1 hari, paralel dengan S1-A/B)

| Kandidat | Key? | Yang harus dibuktikan probe | Penilaian awal |
|---|---|---|---|
| 0x permit2/v2 (Base, chainId 8453) | YA — registrasi | Apakah respons mengandung `amount_out_min`-setara + `expires_at`-setara untuk SELL $10k NVDAc→USDC? | Hanya bila Septian setuju registrasi + key via env (BUKAN repo). Tanpa key, jalur ini mati. |
| 1inch Swap API v6 (`/swap`, bukan `/quote`) | YA — registrasi | Sama: min-out + expiry untuk $10k. | Sama, bersyarat key. |
| Odos API v2 (`/quote`) | Tidak (publik) | Apakah respons mengandung komitmen expiry/min-out, atau hanya routing indikatif (`outAmounts` + `pathId`)? | Dugaan: indikatif saja. Probe yang membuktikan. |
| KyberSwap Aggregator API | Tidak (publik) | Sama: ada/tidak field expiry/min-out. | Dugaan: indikatif saja. |
| Uniswap Routing API | Belum diketahui | Apakah butuh key? Apakah ada expiry/min-out? | Belum diuji sama sekali. |
| Coinbase mint/redeem berbasis NAV | — | Redemption TIDAK permissionless retail (config, brief §3). Bukan jalur. | Bukan kandidat. |

**Rencana probe (S2):** untuk tiap kandidat, minta SELL quote
NVDAc→USDC dan AAPLc→USDC pada notional $10.000 (sama dengan
`SIMULATION_NOTIONAL_USD`); rekam respons mentah +
`evidence/firm_quote_probes_<tanggal>.json`; nilai tiap respons
terhadap definisi §2.1 (field demi field). Cross-check: harga
implisit quote firm vs median pipeline — selisih harus ≤1%
(lebih ketat dari toleransi validator ±10%; ini syarat
kill-switch, bukan syarat validator). **Sampel: minimal 10
sampel firm yang lolos**, tersebar ≥2 hari berbeda, ≥1 token
(ideal: kedua token). Sampel dihitung per quote yang lolos
SEMUA syarat, bukan per percobaan.

### 2.4 Apa buktinya (deliverable S2)

- `evidence/firm_quote_probes_<tanggal>.json` — respons mentah
  tiap kandidat + penilaian per field.
- `docs/firm-quote-definition-2026-11-2x.md` — definisi yang
  dipakai (= §2.1, dirujuk ke `validate_exit_quote`), hasil
  probe, dan keputusan: jalur mana yang FIRM, atau TIDAK ADA.
- Bila ada jalur lolos: produsen quote firm baru
  (`adapter.fetch_firm_quote`, file terpisah atau fungsi baru di
  `adapter.py`) + tes di `gate.py` (firm lolos validator →
  `verified`; firm kedaluwarsa → `stale`; firm tanpa `expires_at`
  → `invalid`). Bila tidak ada yang lolos: TIDAK ADA kode
  produsen — yang ada hanya laporan probe + keputusan (§2.5).

### 2.5 Aturan keputusan + risiko jujur (bagian terpenting rencana ini)

**Bila sampai akhir 26 Nov TIDAK ADA kandidat yang menghasilkan
≥1 sampel firm yang lolos definisi §2.1, kriteria kill-switch 2
dinyatakan TIDAK TERPENUHI.** Konsekuensi: laporkan segera ke
chief (malam 26 Nov), kunci paket ke (a2) pada review early exit
26 Nov — brief harian saja, artefak proposal ditunda. JANGAN
menunggu 30 Nov untuk menyatakan ini, dan JANGAN "memperbaiki"
definisi firm supaya ada yang lolos.

Alasan risiko ini nyata (bukan pesimisme): riset 22 Nov sudah
menggugurkan semua jalur tanpa key; jalur ber-key butuh
registrasi Septian (belum diminta, belum ada); jalur publik
yang tersisa (Odos/Kyber/Uniswap routing) besar kemungkinan
hanya indikatif; dan di DEX tidak ada "firm quote" tanpa
eksekusi — yang ada hanyalah quote yang bisa dieksekusi
sekarang via calldata, yang komitmennya hanya berlaku
blok-per-blok. **Kemungkinan kriteria 2 tidak terpenuhi adalah
kemungkinan yang harus direncanakan, bukan disembunyikan.**

---

## 3. Kalibrasi Exit Score Base

### 3.1 Apa yang dikalibrasi — dan apa yang TIDAK

- **Bukan skor komposit 0–100.** `DESIGN.md` §6: Exit Score Base
  adalah redesign, bukan port Solana — reason codes + coverage.
  Komponen redemption 20 poin Solana **DIHILANGKAN** (tidak ada
  sumber data) dan TIDAK direnormalisasi jadi 80 poin lalu disebut
  setara. Tidak ada rumus skor untuk di-fit.
- **Yang dikalibrasi:** (a) distribusi deviasi lintas-venue
  (harga pool vs median) → tinjau ulang `DEV_WATCH_PCT` 2% dan
  `DEV_ABSTAIN_PCT` 5%; (b) `MIN_INDEPENDENT_POOLS` 2 (apakah 2
  observasi cukup untuk median yang tidak rapuh?); (c) perilaku
  NAV basi (24 jam) di akhir pekan/libur.
- Threshold saat ini adalah **tebakan awal, berlabel EKSPERIMEN**
  (`config.py`, `DESIGN.md` §4) — bukan kalibrasi, bukan warisan
  Solana. Kalibrasi tidak mengubah status itu kecuali buktinya
  kuat (lihat §3.3).

### 3.2 Data yang dibutuhkan + ukuran sampel yang realistis

- **Sumber:** observasi deviasi dari run otomatis S1-D, 26–30 Nov:
  per token-hari, tiap pool yang lolos filter menyumbang satu
  observasi deviasi `(harga_pool − median) / median`.
- **N realistis:** bila universe yang ter-cover = 5–15 token ×
  5 hari = 25–75 token-hari; observasi per token-hari 2–6 pool
  → 50–450 observasi mentah, TAPI berkorelasi dalam satu
  token-hari (NAV sama, hari sama) → **N efektif ≈ puluhan
  (token-hari), bukan ratusan**. Itu kecil.
- **Komposisi minggu yang tidak biasa:** 26 Nov = Thanksgiving
  (NAV beku), 28–29 Nov = akhir pekan (NAV beku). Mayoritas
  sampel 5 hari ini adalah observasi libur/akhir pekan — BUKAN
  minggu bursa normal. Kalibrasi WAJIB memisahkan observasi
  `session_status: active` vs `off_hours` dan melaporkannya
  terpisah; jangan gabung lalu klaim mewakili minggu normal.
- **Metode (mengikuti pola kalibrasi CMC yang sudah terbukti):**
  robust spread `(Q3−Q1)/median × 100` per token-hari +
  distribusi `|deviasi|` (median, p75, p90) + hitung berapa
  persen observasi di atas 0,5% / 2% / 5%. Publikasikan
  distribusi mentahnya, bukan hanya threshold akhirnya.

### 3.3 Aturan perubahan threshold + jawaban jujur

- Threshold diubah HANYA bila distribusi jelas bertentangan
  dengannya (mis. median `|deviasi|` sudah >2% — maka WATCH
  akan menyala terus dan 2% bukan ambang yang informatif),
  DAN perubahannya dicatat dalam ADR bertanggal dengan
  distribusi mentah terlampir. Bila distribusi tidak jelas,
  threshold TETAP 2%/5% dengan label EKSPERIMEN.
- **Jawaban jujur yang dipakai bila juri/auditor bertanya:**
  *"Kalibrasi awal, N kecil, belum tervalidasi — threshold
  masih eksperimen."* Jangan klaim "terkalibrasi" tanpa
  kualifikasi itu.
- **Item S1-F — Kalibrasi pass 1 (0,5–1 hari, 27 Nov).**
  Distribusi dari data 26–27 Nov (N≈2 hari — SANGAT kecil,
  labeli sebagai pendahuluan) + ADR bila ada perubahan
  threshold. **Kalibrasi final (30 Nov):** distribusi 5 hari
  penuh + keputusan threshold final + ADR. Bila N final tetap
  terlalu kecil untuk mengubah apa pun, keputusannya adalah
  "threshold tetap, kalibrasi ditunda" — itu hasil yang sah,
  bukan kegagalan.

### 3.4 Risiko overfit (ditulis eksplisit)

Satu minggu (libur + akhir pekan) tidak mewakili perilaku
deviasi tokenized stock secara umum. Threshold yang di-fit ke
sampel ini bisa salah besar di minggu bursa normal. Mitigasi:
jangan overfit — laporkan distribusi, ubah threshold hanya
bila buktinya kuat, dan simpan jawaban jujur §3.3 sebagai
posisi resmi.

---

## 4. Urutan kerja + estimasi + dependensi

| Kapan | Item | Estimasi | Dependensi | Output |
|---|---|---|---|---|
| 24 Nov | Rencana ini → verifikasi chief → review Septian | — (dokumen ini) | — | `docs/scope1-rencana-eksekusi-2026-11-24.md` |
| 25 Nov pagi | **Keputusan review** (paling lambat 25 Nov 09:00 WITA) | — | Rencana | ACC / revisi / tolak. Bila belum diputuskan, 26 Nov slip → §6 T1. |
| 25 Nov | S1-A sensus universe | 0,5 hari | ACC review | `evidence/coinbase_tokenized_stocks_all.json` + manifest |
| 25 Nov | S1-B sensus venue | 0,5 hari | ACC review (paralel S1-A) | `evidence/venue_census_<tgl>.json` |
| 25–26 Nov | S2 probe jalur FIRM | 1 hari | ACC review (paralel S1-A/B) | `evidence/firm_quote_probes_<tgl>.json` + `docs/firm-quote-definition-*.md` |
| 26 Nov | S1-C jalur kode V4 | 1 hari | S1-B (metode klasifikasi) | `pipeline.py` + tes `gate.py` hijau |
| 26 Nov | S1-D cron + manifest (HARD) | 0,5 hari | S1-C | Cron jalan; run otomatis pertama 26 Nov tercatat |
| 26 Nov malam | **Review early exit** | — | S1-D + S2 | Putuskan: lanjut (a1') atau kunci (a2). Lihat §6. |
| 27 Nov | S1-E feed + indeks harian | 0,5 hari | S1-D | `out/index_<tgl>.json`; kontrak feed terdokumentasi |
| 27 Nov | S1-F kalibrasi pass 1 | 0,5–1 hari | S1-D (data 26–27 Nov) | Distribusi pendahuluan + ADR bila berubah |
| 27 Nov | S1-G tes integritas gate (kriteria 5) | 0,25 hari | — (paralel) | Tes: simulasi TIDAK PERNAH → PAPER_PROPOSAL; gate OFF |
| 28–30 Nov | Fase 2 (di luar rencana ini): agen (a1') + registry Sepolia | 2–3 hari | Scope 1 hidup | Brief harian + RESEARCH_DRAFT + hash Sepolia |
| 30 Nov | Checkpoint kill-switch: verifikasi 5 kriteria | — | Semua di atas | Penilaian tertulis per kriteria |
| 1–3 Des | QA akhir | — | Checkpoint | — |
| 4–5 Des | Submit (Septian) | — | QA | Form + post X + video (Septian) |

Total Scope 1: **~3–3,5 hari kerja** (25–27 Nov) + kalibrasi final
30 Nov. Muat di jendela — DENGAN CATATAN review diputuskan
25 Nov pagi dan tidak ada item yang slip sehari pun.

---

## 5. Kriteria selesai per item (bisa diuji) → pemetaan kill-switch

| Item | Kriteria selesai (bisa diuji) | Kill-switch |
|---|---|---|
| S1-A sensus universe | Semua halaman Coinbase dijalani; total token tercatat; `config.TOKENS` dihasilkan dari sensus + catatan bertanggal; token tanpa coverage tercatat di `universe_no_coverage.json`. | 1 (data) |
| S1-B sensus venue | Tiap token universe punya daftar pair + klasifikasi V3/V4 (label + panjang cocok); likuiditas tercatat; konflik klasifikasi = 0 yang belum diselidiki. | 1 (data) |
| S1-C jalur kode V4 | Fixture poolId V4 masuk median sebagai observasi; `venue_verified` TIDAK PERNAH true untuk poolId; `gate.py` hijau; `git diff` tidak menyentuh `decide()`. | 1 (data) |
| S1-D cron + manifest | Manifest 26 Nov ada, dihasilkan cron (bukan manual); `verify_daily_runs.py` lolos; tiap record punya `fetched_at` + `source`. | **1 (kriteria keras)** |
| S1-E feed + indeks | `public_snapshot` tersedia untuk semua token universe; `out/index_<tgl>.json` lengkap; kontrak feed tertulis. | 1 (data) |
| S1-F kalibrasi | Distribusi deviasi + median/p75/p90 diterbitkan; keputusan threshold tercatat (ubah/tetap) + ADR bila berubah; jawaban jujur §3.3 tercantum. | 1 (data; pendukung 3) |
| S1-G tes gate | Tes baru di `gate.py`: quote simulasi (apa pun isinya) → keputusan TIDAK PERNAH PAPER_PROPOSAL; `PAPER_PROPOSALS_ENABLED` tetap `False` (tes membaca nilai config, bukan asumsi). | **5** |
| S2 probe FIRM | Tiap kandidat punya respons mentah + penilaian per field; ≥10 sampel firm lolos (definisi §2.1) + cross-check ≤1% + ≥2 hari. ATAU laporan "tidak ada yang lolos" + keputusan §2.5. | **2 (kriteria keras)** |

**Yang TIDAK ada di tabel ini (bukan Scope 1):** kriteria 3
(brief otomatis 3 hari — fase 2, agen) dan kriteria 4 (hash
Sepolia — fase 2, registry). Scope 1 menyiapkan DATANYA
(kriteria 1–2); kriteria 3–4 dinilai di checkpoint 30 Nov
dari hasil fase 2.

---

## 6. Risiko + pemicu early exit 26 Nov

**Pemicu otomatis → kunci (a2) pada review malam 26 Nov:**

- **T1 — Poller belum otomatis 26 Nov.** Tidak ada manifest
  run 26 Nov yang dihasilkan cron (atau `verify_daily_runs.py`
  gagal). Akibat: 5 hari berturut-turut sampai 30 Nov sudah
  mustahil secara matematis → kriteria 1 gagal → (a2).
  Termasuk di sini: review rencana belum diputuskan sampai
  pagi 25 Nov (maka S1-D tidak sempat terpasang 26 Nov).
- **T2 — Tidak ada sampel firm sampai akhir 26 Nov.** Tidak
  satu pun kandidat S2 menghasilkan ≥1 sampel yang lolos
  definisi §2.1. Akibat: kriteria 2 dinyatakan tidak
  terpenuhi → (a2). Jangan menunggu 30 Nov; jangan ubah
  definisi supaya ada yang lolos.
- **T1 atau T2 saja sudah cukup.** Keduanya independen;
  salah satu gagal = early exit.

**Risiko yang dicatat (bukan pemicu otomatis — keputusan review 26 Nov):**

- **R1 — Universe terlalu tipis.** Sensus menunjukkan <3 token
  dengan coverage yang bisa dipakai (median rapuh di mana-mana).
  Brief 2-aset tetap demo-able, tapi klaim track "Base Stocks"
  melemah. Keputusan: review 26 Nov (lanjut / kunci a2 /
  persempit klaim).
- **R2 — Klasifikasi V4 gagal.** `labels` dan panjang
  `pairAddress` tidak cocok dengan cek on-chain (mis. PoolManager
  tidak mengonfirmasi poolId). Akibat: V4 tetap di luar; coverage
  = V3 + Aero saja. Bukan pemicu kill-switch (kriteria 1 soal
  data mengalir, bukan soal V4) — dicatat sebagai pengurangan
  scope.
- **R3 — Kalibrasi N terlalu kecil.** Data 5 hari tidak cukup
  untuk mengubah threshold apa pun. Bukan kegagalan: keputusan
  "threshold tetap, kalibrasi ditunda" + jawaban jujur §3.3.
- **R4 — RPC publik tidak stabil.** `run.py` gagal berkali-kali
  karena RPC (bukan karena kode). Mitigasi: daftar
  `BASE_RPC_URLS` sudah punya fallback (mainnet.base.org +
  BlastAPI); bila keduanya gagal, run dicatat gagal + diulang,
  bukan diisi data palsu. Run yang gagal TIDAK dihitung sebagai
  hari data.
- **R5 — Review lambat.** Setiap hari keterlambatan review
  menggeser seluruh rantai sehari. Batas: keputusan review
  25 Nov 09:00 WITA; bila lewat, T1 aktif.

---

## 7. Batas keras + yang TIDAK ada di rencana ini

- TIDAK ada perubahan `decide()`, `validate_exit_quote`,
  `PAPER_PROPOSALS_ENABLED`, atau threshold policy di luar ADR
  kalibrasi (§3.3).
- TIDAK ada mainnet, wallet, dana bergerak, atau tx di luar
  Base Sepolia (registry Sepolia adalah fase 2, bukan Scope 1).
- TIDAK ada kredensial di repo — bila probe S2 butuh API key
  (0x/1inch), key HANYA via environment, dan registrasinya
  adalah tindakan Septian, bukan builder.
- TIDAK ada submit (form/post X/video) — itu urusan Septian,
  4–5 Des.
- TIDAK ada penghapusan fitur/lesson/kode yang sudah ada.
  Perubahan `config.TOKENS` (2 → N) adalah penambahan dari
  sensus, bukan penghapusan.

---

## Lampiran — referensi kode & bukti (yang dicek saat menulis rencana)

- `config.py:269` — `PAPER_PROPOSALS_ENABLED = False`.
  `config.py:332-333` — notional $10.000, bobot maks 0,50.
  `config.py` — `AERO_SLIPSTREAM_CL_FACTORY =
  0x9cb220581b91b0c83223012fe69688b92ad07a76`.
  `US_MARKET_HOLIDAYS_2026` memuat 2026-11-26 (Thanksgiving).
- `pipeline.py:242-502` — `validate_exit_quote` (definisi firm vs
  simulasi). `626-799` — `ingest_token`. `800-1115` —
  `build_snapshot` (penolakan V4 via `_is_address`).
  `1472-1546` — `decide()` (aturan 3 + 4, dua penahan).
- `adapter.py` — `fetch_dexscreener_pools`,
  `fetch_geckoterminal_pool`, `fetch_sell_quote` (eth_call,
  `kind: onchain_simulation`), `fetch_oracle_params`,
  `fetch_pool_factory`, `fetch_block`.
- `run.py` — runner manual satu pass; output `out/`.
- `gate.py` — suite tes (19/19 PASS, 23 Nov).
- `DESIGN.md` §5–§8 — coverage, Exit Score redesign, desain
  onchain (hash registry, kanonikalisasi, SHA-256).
- `QUOTER-RESEARCH.md` §4–§8 — kandidat quote yang sudah gugur
  (0x v1 tanpa rute; 0x permit2 + 1inch butuh key; Coinbase tanpa
  endpoint quote; off-chain state quote = simulasi).
- Bukti live 24 Nov (dicek saat menulis rencana):
  DexScreener NVDAc = 30 pair; `labels` v3/v4 + panjang
  pairAddress (42 vs 66) saling menguatkan; V4 NVDAc/USDC
  material ~$92rb (2 pool, evidence 22 Nov) — angka ~$130rb
  adalah pool BLUECHIP/NVDAc (NVDAc sebagai quote), bukan
  observasi NVDAc/USDC. Coinbase page 1 = 100 token, page 2 =
  100 token, masih ada `next_page_token` (total >200).
- `evidence/` — `coinbase_tokenized_stocks_page1.json`,
  `dexscreener_nvdac.json` (30 pair), `dexscreener_aaplc.json`
  (25 pair), `manifest.json`.
