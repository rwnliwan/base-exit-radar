# Rencana Eksekusi Scope 1 — Base Stocks Maxxing (Exit Radar)

**Status: RENCANA v1.1 — revisi atas review Instinct. Belum ACC. Build DITAHAN sampai ACC review atas v1.1.**
**Ditulis v1.0:** 24 Nov 2026 ~02:2x WITA, koordinator build.
**Direvisi v1.1:** 24 Nov 2026 08:18 WITA, reviser (atas ACC Septian 24 Nov 08:13 WITA).
**Dasar v1.1:** rencana v1.0 (commit `2ce2f36`) + review Instinct
24 Nov 2026 (7,5/10, "revisi dulu sebelum ACC penuh", 8 must-fix) +
verifikasi chief atas klaim-klaim review dari kode + sumber live
(docs 0x, source Uniswap, konversi zona waktu NYSE).
**Dasar v1.0:** `docs/perbandingan-fitur-agen-a-vs-b-2026-11-24.md` §7–§8.5,
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

## Changelog v1.1 (24 Nov 2026 — atas review Instinct 7,5/10)

Perubahan per must-fix (nomor = nomor must-fix review):

1. **Bukti FIRM + cross-check independen (§2.1b baru, §2.3, §2.4,
   §5):** sumber pembanding ditetapkan dan harus independen dari
   pool pipeline (GeckoTerminal baca pool YANG SAMA — bukan
   pembanding sah); expected-out / min-out / price impact / slippage
   dipisah; `expires_at` wajib provenance semantik vendor, dilarang
   dibentuk dari jam lokal; klaim absolut "firm tidak ada tanpa
   eksekusi" diganti "belum ditemukan quote yang memenuhi definisi
   proyek".
2. **Identitas V4 end-to-end (§1.1, §1.3, §1.5, §5):** migrasi
   `pool_id` mencakup build → assess → decide → public snapshot →
   replay/hash → feed (v1.0 hanya menyebut `build_snapshot`,
   padahal `assess_snapshot` mengakses `pool_address` langsung —
   `pipeline.py:1295` — dan `build_snapshot` di `:980`); koreksi
   RPC ke `StateView.getSlot0` (bukan PoolManager); validasi
   `sqrtPriceX96` ter-initialize + konsistensi PoolKey vs poolId;
   versi protokol dipisah dari family independensi.
3. **Cron dilepas dari V4 (§1.4, §4, §5, §6):** S1-D jalan dulu
   dengan pipeline V3/Aero yang sudah ada; V4 ditambah setelah tes;
   jam run dikunci 23:00 WITA; isi manifest, cut-off, retry,
   overlap lock, atomic write, alert gagal, dan minimum data usable
   per hari ditetapkan; 5 hari kalender ditegaskan (bukan 120 jam).
4. **Sesi bursa dipisah dari freshness NAV (§1.4, §3.2, §5):**
   `market_session` (kalender) disimpan terpisah dari
   `nav_age_seconds`; early close 27 Nov 13:00 EST dimodelkan
   (konversi terverifikasi: buka 27 Nov 22:30 WITA, tutup 28 Nov
   02:00 WITA, Senin 30 Nov buka 22:30 WITA); strata aktual
   dilaporkan, bila kosong dibilang kosong.
5. **Sensus fail-closed (§1.1, §1.2, §5):** acceptance mensyaratkan
   cursor terminal habis + `error` None + `ok` True; filter per-pool
   + alamat USDC terpercaya (bukan simbol); listed / covered /
   decision-eligible dibedakan; perbaikan kode `fetch_coinbase_tokens`
   (guard trip → `ok=False`, commit terpisah, gate hijau).
6. **Kontrak N-token (§1.2, §5):** metadata wajib, decimals
   tervalidasi, proxy optional/unknown, shared fetch cache per run,
   request budget, backoff, exception isolation per token,
   universe/config berversi.
7. **Metrik kalibrasi yang benar (§3, §5):** yang dikalibrasi adalah
   distribusi `max_dev` (metrik policy, `pipeline.py:1314-1316`),
   bukan median deviasi pool; N efektif TIDAK diklaim (korelasi
   lintas-token dalam hari yang sama; rezim hanya 5 hari); threshold
   DIBEKUKAN selama jendela kecuali bug metode/satuan yang jelas;
   hasil disebut "analisis deskriptif pendahuluan, belum validasi
   risiko exit".
8. **Tes integritas lebih awal + fase 2 diikat jam nyata (§4, §5, §6,
   §7):** S1-G pindah ke 25 Nov (sebelum setiap merge); dua penahan
   diuji terpisah; guard hash/AST untuk `decide()`; kesiapan fase 2
   diikat tenggat sebelum run 28 Nov; hash Sepolia = komitmen isi,
   bukan kebenaran data.
- **Reframing T1/T2 (§0, §2.5, §6):** T1 = tidak ada run otomatis
  valid pada 26 Nov (keterlambatan review = risiko jadwal, bukan
  bukti matematis); T2 = bar 26 Nov adalah SATU jalur memenuhi
  definisi beku + sumber cross-check yang sah + rencana sampling
  yang bisa dijalankan; tinjau kemajuan 27 Nov; checkpoint 30 Nov
  tetap 10 sampel lolos tersebar min 2 hari.

---

## 0. Ringkasan eksekutif + verdict jujur

Scope 1 = tiga hal: **(i)** coverage Base (poller + universe + web),
**(ii)** jalur quote FIRM, **(iii)** kalibrasi Exit Score Base.
Dua dari tiga hal itu bisa dikerjakan dengan pasti. Satu hal —
**jalur quote FIRM — adalah risiko terbuka yang mungkin tidak ada
jawabannya dalam jendela ini**, dan rencana ini menuliskannya apa
adanya (lihat §2.5): bar 26 Nov adalah SATU jalur yang memenuhi
definisi beku (§2.1) + sumber cross-check yang sah (§2.1b) +
rencana sampling yang bisa dijalankan; bila bar itu tidak
terpenuhi, paket dikunci ke (a2) pada review early exit 26 Nov —
bukan menunggu 30 Nov.

Tanggal yang mengikat adalah **26 Nov, bukan 30 Nov**: kriteria 1
menuntut 5 hari berturut-turut data otomatis sampai checkpoint
30 Nov, jadi run otomatis pertama HARUS terjadi 26 Nov
(26–30 Nov = tepat 5 hari). Bila review rencana ini belum diputuskan
sampai pagi 25 Nov, tanggal 26 Nov sudah slip — itu risiko jadwal
yang serius (§6, R5), dan bila sampai tidak ada run otomatis valid
pada 26 Nov, kriteria 1 sudah mustahil secara matematis (pemicu T1).

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
  venue baru — karena itu cross-check ini BUKAN pembanding
  independen untuk bukti FIRM (§2.1b) — proxy Hyperliquid dex `xyz`
  saja (`xyz:NVDA`/`xyz:AAPL`), lalu RPC read-only: `fetch_block`
  (pin block — semua eth_call dihitung pada state block yang sama
  agar snapshot bisa di-replay), `fetch_oracle_params` (multiplier +
  paused), `fetch_pool_factory` per pool, sell quote
  (`fetch_sell_quote` + double-quote probe partial-fill).
  `ingest_token` memanggil `fetch_coinbase_tokens()` per token
  (`pipeline.py:638`) — daftar penuh diambil ulang tiap token,
  tanpa cache bersama (diperbaiki §1.2c).
- **Snapshot** (`pipeline.py:build_snapshot`, baris 800–1115):
  observasi pool di-dedup by `pool_address`; pool ditolak bila
  `pairAddress` bukan alamat valid, chain bukan base, baseToken
  bukan token yang dimaksud, harga/likuiditas tidak positif.
  Coverage dihitung dari nama kanonis (`independent_pool_count`,
  `independent_venue_count`, `verified_venue_count`,
  `verified_pool_count`, `fallback_pool_count`). Median dari
  observasi yang lolos; bila hanya 2 observasi, dicatat
  `median_fragile_two_observations`.
  Akar V4 lebih dalam dari yang ditulis v1.0: `build_snapshot`
  menghitung dedup via `o["pool_address"]` (`pipeline.py:980`)
  dan `assess_snapshot` mengakses `pool_address` langsung sebagai
  key deviasi per-venue (`pipeline.py:1295`) — observasi yang hanya
  punya `pool_id` menimbulkan `KeyError` di kedua tempat (repro
  Instinct, terverifikasi chief). Migrasi identitas V4 harus
  end-to-end (§1.3 v1.1). `build_snapshot` memberi
  `session_status` dari umur NAV (`pipeline.py:855-864`: umur
  ≤24 jam → `active`) — itu label freshness, bukan bukti bursa
  sedang buka; v1.1 memisahkan `market_session` berbasis kalender
  (§1.4).
- **Keputusan** (`pipeline.py:decide`, baris 1472–1546): ABSTAIN /
  WATCH / PAPER_PROPOSAL. Dua penahan independen membuat
  PAPER_PROPOSAL tidak terjangkau hari ini: gate mati (aturan 3)
  DAN bukti exit simulasi, bukan firm (aturan 4,
  `exit_evidence_simulated_not_firm`). **Rencana ini tidak
  menyentuh `decide()` sama sekali.**
  Policy memakai **maksimum |deviasi| per snapshot** (`max_dev` vs
  `DEV_ABSTAIN_PCT` / `DEV_WATCH_PCT`, `pipeline.py:1314-1316`) —
  bukan median deviasi pool; kalibrasi §3 v1.1 memakai metrik ini.
- **Validator quote** (`pipeline.py:validate_exit_quote`, baris
  242–502): sudah membedakan `verified` (firm) dari
  `simulated_verified` (simulasi on-chain). Cabang firm SUDAH ADA
  dan SUDAH ketat — yang belum ada hanyalah produsen quote firm.
  Tidak ada perubahan validator yang diusulkan.
- **Bug sensus fail-open — DIPERBAIKI 24 Nov (commit terpisah):**
  `fetch_coinbase_tokens` menyetel `error=pagination_guard_10_pages`
  lalu tetap `ok=True` (`adapter.py:103-106`, repro Instinct,
  terverifikasi chief). Perbaikan: guard trip → `ok=False`
  (`ok` True hanya bila tidak ada error); pemanggil
  (`pipeline.py:638-641`) sudah memeriksa `ok` dan mencatat error —
  sensus terpotong kini gagal tertutup. Gate tetap hijau sesudah
  perbaikan (lihat commit perbaikan).

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
  + manifest (jumlah total, timestamp, `next_page_token` terakhir,
  jumlah halaman, `ok`, `error`).
  **Acceptance fail-closed (v1.1):** sensus dinyatakan lengkap HANYA
  bila cursor terminal habis (tidak ada `next_page_token` lagi) DAN
  `error` None DAN `ok` True DAN tidak ada loop/halaman malformed
  (halaman tanpa field `tokens`, token tanpa `contract_address`).
  Jangan hanya percaya `ok` — `verify_census.py` memeriksa keempat
  syarat itu dari manifest. Bug yang diperbaiki 24 Nov
  (`adapter.py`: guard trip menyetel `error` lalu tetap `ok=True`)
  adalah contoh persis kegagalan yang dicegah acceptance ini.
  Jangan sebut sensus lengkap sebelum memastikan endpoint bukan
  subset/top-pools: bila total token tampak dibatasi/dibulatkan
  atau paginasi berhenti tanpa cursor terminal, tandai
  `subset_suspected` dan selidiki sebelum mengklaim lengkap.
  Tiga tingkat cakupan (dibedakan, jangan dicampur):
  `listed` = token ada di respons Coinbase; `covered` = punya ≥1
  pool yang lolos filter per-pool (§1.2b); `decision-eligible` =
  covered + metadata lengkap (§1.2c) + memenuhi
  `MIN_INDEPENDENT_POOLS`. Token yang tidak memenuhi dicatat di
  `universe_no_coverage.json` (BUKAN dihapus diam-diam). Token
  tanpa pool USDC yang likuid tetap tercatat sebagai "tanpa
  coverage", bukan sebagai "tidak ada".
- **§1.2b — Filter per-pool (v1.1, baru).** Syarat "satu token punya
  satu pool USDC likuid >$10rb" adalah syarat MASUK universe,
  bukan filter semua pool yang masuk median. Filter per-pool untuk
  median: (a) quote asset adalah USDC berdasarkan ALAMAT terpercaya
  (`config.USDC_BASE_ADDRESSES`) — bukan simbol
  `quoteToken.symbol` saja; (b) likuiditas USD > 0 dan harga valid;
  (c) pool dengan likuiditas < $1.000 dilabeli `thin_pool`,
  dieksklusi dari median, dan dihitung terpisah (sensitivity §3
  menguji hasil tanpa pool tipis). Ambang $1.000 adalah parameter
  eksperimen (dicatat bertanggal di config), bukan kalibrasi. Pool
  yang gagal filter dicatat di `rejected_observations` dengan
  alasan, bukan hilang diam-diam.
- **§1.2c — Kontrak metadata N-token + ketahanan run (v1.1, baru).**
  Metadata wajib per token: `symbol`, `token_address` (pola
  `0xb200…`), `chain` = base, `decimals` tervalidasi (via RPC
  `fetch_token_decimals` bila memungkinkan; bila tidak, dari record
  Coinbase + dilabeli `decimals_unvalidated`). `proxy_instrument` /
  `proxy_dex` menjadi OPTIONAL: bila tidak ada pemetaan, proxy =
  `unknown` (layer C `unknown`, bukan crash — akses bracket
  `tok["proxy_instrument"]` di `pipeline.py:954` dan
  `tok["proxy_dex"]` di `:964` harus diganti `.get()` + penanganan
  unknown saat build). Shared fetch cache per run:
  `fetch_coinbase_tokens()` dipanggil SATU kali per run dan hasilnya
  dipakai bersama semua token (hari ini dipanggil per token,
  `pipeline.py:638`). Request budget + backoff eksponensial untuk
  semua fetch publik; exception isolation per token — satu token
  yang gagal ingest tidak menggagalkan run (token itu dicatat
  gagal + alasannya, run lanjut). Universe/config berversi:
  `universe_version` + hash config dicatat di manifest dan di
  snapshot, agar replay historis tidak berubah diam-diam bila
  universe/config berubah.
- **Perubahan dari sekarang:** `config.TOKENS` hari ini hard-code
  2 token; sesudah sensus, `config.TOKENS` dihasilkan dari sensus
  (dengan catatan bertanggal + jumlah total universe + versi).
  `run.py` tidak berubah bentuk — ia sudah loop `config.TOKENS`.

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
  sekadar "tambah factory". Lebih dalam lagi (§1.1): identitas
  pool di seluruh jalur memakai `pool_address` sebagai key —
  migrasi V4 harus end-to-end, bukan hanya di `build_snapshot`.
- **Item S1-B — Sensus venue (0,5 hari).** Untuk tiap token
  universe: tarik semua pair DexScreener; klasifikasikan V3/V4
  dari `labels` + panjang `pairAddress` (keduanya harus cocok;
  bila tidak cocok, tandai `v4_classification_conflict` dan
  selidiki, jangan tebak); catat likuiditas + quote asset per
  pool. Klasifikasi dikonfirmasi terhadap cek on-chain bila
  memungkinkan (StateView, §1.3 S1-C); konflik yang belum
  terselesaikan → pool dikecualikan dari hitungan V4 dan dilabeli.
  Output: `evidence/venue_census_<tanggal>.json` +
  ringkasan (jumlah pool per venue family, per token).
- **Item S1-C — Jalur kode V4, migrasi identitas end-to-end
  (1 hari, v1.1 diperluas).** Identitas pool = (chain,
  alamat PoolManager, poolId) — SATU identitas kanonis yang sama
  dipakai di SELURUH jalur: `build_snapshot` (dedup by identitas,
  bukan `pool_address`), `assess_snapshot` (deviasi per-venue dan
  coverage recompute by identitas; tidak ada akses bracket
  `pool_address`), `decide` (tidak berubah — memakai reason codes),
  `public_snapshot` (field identitas dipertahankan; `snapshot_id`
  hash mencakup identitas), replay/hash (identitas stabil lintas
  replay), feed (§1.5, indeks memuat identitas). Versi protokol
  (`v3`/`v4`) dicatat terpisah dari family independensi: pool V3
  dan V4 dari family protokol yang sama TIDAK otomatis dihitung
  sebagai dua venue independen — independensi dinilai dari
  deployment factory/PoolManager + sumber likuiditas yang berbeda.
  `fetch_pool_factory` dilewati untuk poolId; venue V4 dilabeli
  `venue_label_source: dexscreener_fallback`, BUKAN
  `venue_verified` — factory tidak bisa dibaca untuk poolId, jadi
  independensi V4 tidak pernah diklaim sebagai terverifikasi
  factory. Verifikasi keberadaan pool V4: `eth_call` ke kontrak
  **StateView** yang ter-deploy di Base
  (`StateView.getSlot0(poolId)`) — BUKAN ke PoolManager:
  PoolManager tidak punya fungsi eksternal `getSlot0`
  (`StateLibrary.getSlot0` bersifat internal dan membaca via
  `PoolManager.extsload`; koreksi atas v1.0, terverifikasi ke
  source Uniswap v4-periphery). Alamat StateView yang dipakai
  dicatat di config + evidence. Respons nonempty TIDAK cukup:
  validasi `sqrtPriceX96` ter-initialize (≠ 0), chain/deployment
  cocok, dan hubungan PoolKey (token0/token1/fee/tickSpacing/hooks)
  dengan poolId konsisten (poolId = keccak256 dari PoolKey —
  dihitung ulang dan dibandingkan). Bila respons gagal atau
  validasi gagal, pool dicatat `unverified`, bukan dipakai.
  Labels + panjang identifier hanya heuristik awal, bukan bukti.
  Sell-quote untuk pool V4 TIDAK termasuk Scope 1 — Metaquoter
  V3 tidak bisa meng-quote pool V4 (butuh V4 Quoter + PoolKey);
  quote tetap dari pool V3/Aero yang eligible seperti sekarang.
  Tes (acceptance §5): fixture V4 (poolId NVDAc, tanpa
  `pool_address`) lolos build → assess → decide → public snapshot
  → replay → feed tanpa `KeyError`; dedup, count, dan deviasi
  benar; V4 tidak pernah dihitung sebagai `venue_verified`;
  `gate.py` tetap hijau. **Bila tidak sempat, V4 boleh dipotong**
  (pengurangan scope, bukan pemicu kill-switch — kriteria 1 soal
  data mengalir, bukan soal V4).
- **Perubahan dari sekarang:** coverage harga dari 2 token ×
  ~1 pool dominan → N token × semua pool yang lolos filter
  (termasuk V4 sebagai observasi harga berlabel fallback);
  `verified_venue_count` tetap hanya dari factory yang terbaca.

### 1.4 Poller — dari manual ke otomatis (ini yang menentukan kriteria 1)

- **Item S1-D — Otomatisasi run harian (0,5 hari, HARD 26 Nov).
  DILEPAS dari V4 (v1.1):** S1-D TIDAK lagi bergantung pada S1-C.
  Cron dipasang 26 Nov dengan pipeline V3/Aero yang sudah ada;
  V4 ditambah setelah tes S1-C lolos. Ini melindungi tanggal
  26 Nov: keterlambatan V4 tidak lagi menggagalkan run otomatis
  pertama.
  Pasang cron di VM chief: `run.py` (semua token universe)
  1×/hari, **jam tetap 23:00 WITA**. Jam ini dipilih agar run jatuh
  di dalam regular session NYSE pada hari bursa normal (09:30–16:00
  EST = 22:30–05:00 WITA); cron pagi WITA berpotensi tidak mengambil
  satu pun observasi saat regular session terbuka (§1.4b). Cut-off
  checkpoint: manifest hari D harus ada paling lambat 23:59 WITA
  hari D. Retry: maks 2×, jeda 30 menit, dalam hari yang sama;
  overlap lock (flock/pidfile) agar dua run tidak pernah tumpang
  tindih; atomic write (tulis file temp + rename); alert gagal ke
  chief via log cron + laporan (cron yang gagal = kabari, bukan
  diam). Bukti otomatisasi = manifest 5 hari berturut-turut
  (26–30 Nov) yang dihasilkan cron, BUKAN run manual. Manifest
  kosong/error TIDAK dihitung sebagai hari sukses.
  **Isi manifest (v1.1):** scheduler config (baris cron + zona
  waktu) + cuplikan log scheduler, run ID, commit hash, versi
  skema, hash config, hash input (hash manifest universe, hash
  file evidence), waktu mulai/selesai, status per sumber per token
  (`ok`/`error`), status per token. **Minimum data usable per
  hari:** manifest lolos `verify_daily_runs.py` DAN ≥1 token punya
  snapshot lengkap (keputusan + coverage + `fetched_at` + `source`
  ada, tanpa error ingest fatal untuk token itu). Skrip verifikasi
  `verify_daily_runs.py`: memeriksa manifest 5 hari ada + tiap
  record punya `fetched_at` + `source` + tidak ada input manual.
  **Lima hari kalender (26–30 Nov), BUKAN 120 jam** — keduanya
  tidak sama: yang dihitung adalah 5 tanggal kalender, masing-masing
  dengan manifest sebelum cut-off hari itu.
- **§1.4b — Sesi bursa dipisah dari freshness NAV (v1.1, baru).**
  `market_session` (berbasis kalender: hari bursa + jam regular
  session + libur + early close) disimpan TERPISAH dari
  `nav_age_seconds` di snapshot dan di manifest. `session_status`
  lama (dari umur NAV, `pipeline.py:855-864`) dipertahankan sebagai
  label freshness NAV saja, bukan sebagai bukti bursa buka: NAV
  satu jam lalu tetap fresh ketika pasar sudah tutup. Kalender
  config dimodelkan lengkap: `US_MARKET_HOLIDAYS_2026` (sudah ada,
  memuat 2026-11-26 Thanksgiving) + `US_MARKET_EARLY_CLOSE_2026`
  (baru — tanggal + jam tutup awal). Early close yang berdampak
  pada jendela ini: **Jumat 27 Nov 2026 NYSE tutup 13:00 EST**
  (konversi terverifikasi dengan `date`: buka 27 Nov 09:30 EST =
  **22:30 WITA**, tutup 13:00 EST = **Sabtu 28 Nov 02:00 WITA**;
  **Senin 30 Nov buka 09:30 EST = 22:30 WITA**). Run 23:00 WITA
  pada 27 Nov jatuh di dalam sesi singkat itu; run 28–29 Nov
  (akhir pekan) dan 26 Nov (Thanksgiving) dilabeli `off_hours`
  dari kalender, apa pun umur NAV-nya. Kalibrasi (§3) memakai
  `market_session` untuk strata, bukan `session_status` lama.
  Laporkan strata aktual per hari; bila suatu hari tidak punya
  satu pun observasi saat regular session terbuka, bilang kosong
  — jangan gabung diam-diam lalu klaim mewakili minggu normal.
- **Catatan kalender:** 26 Nov 2026 = Thanksgiving (sudah ada di
  `config.US_MARKET_HOLIDAYS_2026`) dan 28–29 Nov = akhir pekan.
  NAV akan beku — itu TIDAK menggagalkan kriteria 1: kriteria 1
  menuntut DATA (pipeline jalan + record tercatat), bukan NAV
  segar. Data DEX tetap live 24/7. Kalibrasi (§3) harus memisahkan
  observasi libur/akhir pekan dari hari bursa normal — memakai
  `market_session` (§1.4b).

### 1.5 Web — batas repo ini

- **Fakta:** repo ini TIDAK punya direktori `web/`. Permukaan
  "web" repo ini adalah `pipeline.public_snapshot()` → file
  `out/snapshot_<symbol>_<snapshot_id>.json`. Situs
  radar.omdanny.site hidup di repo `radar-tokenized-stocks`
  (Next.js, repo lain).
- **Item S1-E — Kontrak feed + indeks harian (0,5 hari).**
  `public_snapshot` untuk SEMUA token universe + indeks harian
  `out/index_<tanggal>.json` (daftar snapshot_id per token,
  keputusan, timestamp). Kontrak feed (v1.1) memuat identitas pool
  kanonis (chain + PoolManager + poolId, §1.3) dan `market_session`
  per snapshot (§1.4b). Integrasi ke situs radar adalah item
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

### 2.1b Bukti silang independen (v1.1, baru — must-fix 1)

Membandingkan quote SELL $10rb terhadap median spot pipeline
BELUM otomatis memenuhi verifikasi silang independen: vendor
quote dapat memakai pool yang sama dengan pipeline, sementara
cross-check GeckoTerminal di kode sengaja membaca pool yang sama
dengan DexScreener (§1.1) — karena itu GeckoTerminal BUKAN
pembanding yang sah untuk bukti FIRM. Sumber pembanding harus
ditetapkan SEBELUM probe (bukan dipilih post-hoc) dan harus
independen dari pool pipeline:

- **Primer:** quote independen dari vendor LAIN untuk pair, arah,
  dan ukuran yang sama (mis. bila kandidatnya 0x, pembandingnya
  quote 1inch/Odos untuk SELL $10k yang sama; begitu sebaliknya).
- **Fallback (bila hanya satu vendor merespons):** harga referensi
  NAV-implied (NAV × multiplier, dari OracleRegistry) + harga proxy
  Hyperliquid (`xyz`) — keduanya dilabeli REFERENSI, bukan harga
  eksekusi, dan dicatat dengan caveat-nya masing-masing.
- **Spesifikasi perbandingan (dicatat per sampel):** sumber
  pembanding, rute/pool, arah (SELL), ukuran ($10.000), waktu/block
  sebanding (quote dan pembanding dalam jendela evaluasi 300 detik
  yang sama; idealnya pada block yang sama yang di-pin
  `fetch_block`), fee (dinyatakan eksplisit apakah fee sudah
  termasuk di min-out, per dokumentasi vendor), dan rumus selisih:
  `|P_implied_execution − P_ref| / P_ref × 100 ≤ 1%`, dengan
  `P_implied_execution = min-out / amount_in` (harga terburuk yang
  dikomitmenkan vendor). Band ±10% validator adalah sanity check
  terpisah — BUKAN cross-check ini.
- **Empat kuantitas dipisah di setiap record probe:**
  `expected-out` (bruto, sebelum slippage/fee), `min-out`
  (sesudah toleransi slippage/fee — jumlah yang dikomitmenkan vendor
  sebagai lantai), `price impact` (expected-out vs spot), dan
  `slippage` (realisasi vs ekspektasi). **Min-out sesudah slippage
  BUKAN objek yang identik dengan spot median** — cross-check ≤1%
  membandingkan harga eksekusi yang dikomitmenkan (min-out) dengan
  referensi independen, dan harus dilabeli demikian.
- **`expires_at` — provenance semantik wajib:** nilai harus berasal
  dari respons vendor dengan provenance yang didokumentasikan per
  vendor (nama field + arti menurut dokumentasi vendor). DILARANG
  membentuk `expires_at` dari jam lokal (`now + TTL`) dan DILARANG
  menaikkan kelas bukti hanya dengan mengisi `kind=firm`. Bila
  vendor tidak memberi semantik expiry, quote itu TIDAK dapat
  diklasifikasikan firm — ia gagal memenuhi definisi.
- **0x `minBuyAmount` (terverifikasi ke docs 0x, 24 Nov):** 0x
  menyebut endpoint Permit2-nya "firm quote", tetapi dokumentasi
  troubleshooting 0x sendiri menyatakan quote dirancang untuk
  *revert* bila perubahan likuiditas membuat harga jatuh di bawah
  ambang yang dipilih ("transactions are designed to revert if a
  change in liquidity causes the price to drop below a chosen
  threshold"). Artinya `minBuyAmount` adalah **batas revert yang
  ditegakkan saat settlement, bukan jaminan pasti fill** — trade
  bisa gagal/revert; yang dijamin (bila tereksekusi) hanyalah
  jumlah minimum yang diterima. Probe WAJIB mengonfirmasi semantik
  field ini dari respons mentah 0x sebelum memakai field itu
  sebagai bukti min-out. Bila vendor tidak memenuhi definisi
  proyek, hasil sahnya tetap tidak lolos — jangan memaksa.

### 2.2 Yang sudah gugur (riset 22 Nov, QUOTER-RESEARCH.md — tidak diulang)

| Kandidat | Hasil 22 Nov |
|---|---|
| 0x Swap API v1 (tanpa key) | `no Route matched with those values` untuk NVDAc → USDC. Tidak ada rute. |
| 0x permit2 / v2 (Base) | Butuh API key (`No API key found in request`). Registrasi + key. |
| 1inch Swap API v6 (Base) | Butuh API key (`Unauthorized`). |
| DexScreener / GeckoTerminal | Bukan quoter: hanya harga spot + likuiditas. Hitung quote dari reserve TIDAK berlaku untuk pool CL (harga eksekusi tergantung distribusi likuiditas per tick). GeckoTerminal juga membaca pool yang sama — bukan pembanding independen (§2.1b). |
| Coinbase tokenized-stocks API | Tidak ada endpoint quote (hanya NAV + multiplier + total_supply). |
| Hitung quote off-chain dari state pool (slot0 + ticks) | FEASIBLE sebagai cadangan, tapi hasilnya tetap simulasi — BUKAN firm. |

### 2.3 Kandidat yang tersisa untuk di-probe (item S2, 1 hari, paralel dengan S1-A/B)

| Kandidat | Key? | Yang harus dibuktikan probe | Penilaian awal |
|---|---|---|---|
| 0x permit2/v2 (Base, chainId 8453) | YA — registrasi | Apakah respons mengandung `amount_out_min`-setara + `expires_at`-setara untuk SELL $10k NVDAc→USDC? Periksa semantik `minBuyAmount` dari respons mentah (§2.1b). | Hanya bila Septian setuju registrasi + key via env (BUKAN repo). Tanpa key, jalur ini mati. |
| 1inch Swap API v6 (`/swap`, bukan `/quote`) | YA — registrasi | Sama: min-out + expiry untuk $10k. | Sama, bersyarat key. |
| Odos API v2 (`/quote`) | Tidak (publik) | Apakah respons mengandung komitmen expiry/min-out, atau hanya routing indikatif (`outAmounts` + `pathId`)? | Dugaan: indikatif saja. Probe yang membuktikan. |
| KyberSwap Aggregator API | Tidak (publik) | Sama: ada/tidak field expiry/min-out. | Dugaan: indikatif saja. |
| Uniswap Routing API | Belum diketahui | Apakah butuh key? Apakah ada expiry/min-out? | Belum diuji sama sekali. |
| Coinbase mint/redeem berbasis NAV | — | Redemption TIDAK permissionless retail (config, brief §3). Bukan jalur. | Bukan kandidat. |

**Rencana probe (S2):** untuk tiap kandidat, minta SELL quote
NVDAc→USDC dan AAPLc→USDC pada notional $10.000 (sama dengan
`SIMULATION_NOTIONAL_USD`); rekam respons mentah +
`evidence/firm_quote_probes_<tanggal>.json`; nilai tiap respons
terhadap definisi §2.1 (field demi field) + spesifikasi cross-check
§2.1b (sumber pembanding ditetapkan sebelum probe, bukan post-hoc).
Setiap record probe memisahkan expected-out, min-out, price impact,
dan slippage (§2.1b), serta mencatat provenance `expires_at` per
vendor. Cross-check: harga eksekusi yang dikomitmenkan (min-out /
amount_in) vs referensi independen — selisih harus ≤1% (lebih ketat
dari toleransi validator ±10%; ini syarat kill-switch, bukan syarat
validator). **Sampel: minimal 10 sampel firm yang lolos**, tersebar
≥2 hari berbeda, ≥1 token (ideal: kedua token). Sampel dihitung per
quote yang lolos SEMUA syarat, bukan per percobaan.

### 2.4 Apa buktinya (deliverable S2)

- `evidence/firm_quote_probes_<tanggal>.json` — respons mentah
  tiap kandidat + penilaian per field + empat kuantitas terpisah
  (§2.1b) + provenance `expires_at` + hasil cross-check (sumber,
  rumus, selisih).
- `docs/firm-quote-definition-2026-11-2x.md` — definisi yang
  dipakai (= §2.1, dirujuk ke `validate_exit_quote`), spesifikasi
  cross-check (§2.1b), hasil probe, dan keputusan: jalur mana yang
  FIRM, atau TIDAK ADA.
- Bila ada jalur lolos: produsen quote firm baru
  (`adapter.fetch_firm_quote`, file terpisah atau fungsi baru di
  `adapter.py`) + tes di `gate.py` (firm lolos validator →
  `verified`; firm kedaluwarsa → `stale`; firm tanpa `expires_at`
  → `invalid`). Bila tidak ada yang lolos: TIDAK ADA kode
  produsen — yang ada hanya laporan probe + keputusan (§2.5).

### 2.5 Aturan keputusan + risiko jujur (bagian terpenting rencana ini)

**Bar 26 Nov (v1.1, reframing Instinct atas T2):** pada akhir
26 Nov harus terpenuhi ketiganya: (a) SATU jalur yang memenuhi
definisi beku §2.1 (≥1 sampel firm yang lolos SEMUA syarat,
termasuk cross-check §2.1b); (b) sumber cross-check yang sah sudah
berjalan (bukan sekadar dinamai); (c) rencana sampling yang bisa
dijalankan untuk mencapai 10 sampel lolos sampai 30 Nov (jadwal
pengambilan sampel per hari, per token). **Bila bar ini tidak
terpenuhi, kunci paket ke (a2) pada review early exit 26 Nov** —
brief harian saja, artefak proposal ditunda. JANGAN menunggu 30 Nov
untuk menyatakan ini, dan JANGAN "memperbaiki" definisi firm supaya
ada yang lolos. **Catatan jujur atas reframing ini:** nol sampel
pada 26 Nov belum membuktikan nol pada 30 Nov, dan satu sampel
belum cukup membuktikan jalur menuju 10 sampel — karena itu bar
26 Nov adalah keputusan early-stop yang konservatif (jalur +
cross-check + rencana sampling), bukan bukti matematis kegagalan.
Checkpoint 30 Nov tetap mensyaratkan 10 sampel lolos tersebar
min 2 hari. Bila bar 26 Nov terpenuhi, tinjau kemajuan pada
27 Nov (apakah sampling berjalan sesuai rencana); bila sampling
tertinggal dari rencana, review 27 Nov memutuskan lanjut atau
kunci (a2) lebih awal.

Alasan risiko ini nyata (bukan pesimisme): riset 22 Nov sudah
menggugurkan semua jalur tanpa key; jalur ber-key butuh
registrasi Septian (belum diminta, belum ada); jalur publik
yang tersisa (Odos/Kyber/Uniswap routing) besar kemungkinan
hanya indikatif; dan sampai hari ini **belum ditemukan quote yang
memenuhi definisi proyek (§2.1) tanpa eksekusi** — klaim ini adalah
status pencarian, bukan teorema: yang ada hanyalah quote yang bisa
dieksekusi sekarang via calldata, yang komitmennya hanya berlaku
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
- **Yang dikalibrasi:** (a) distribusi **`max_dev` per snapshot**
  (v1.1 — metrik yang benar: policy memakai maksimum |deviasi| per
  snapshot, `max_dev > DEV_ABSTAIN_PCT` / `DEV_WATCH_PCT`,
  `pipeline.py:1314-1316`) → tinjau ulang `DEV_WATCH_PCT` 2% dan
  `DEV_ABSTAIN_PCT` 5%; (b) `MIN_INDEPENDENT_POOLS` 2 (apakah 2
  observasi cukup untuk median yang tidak rapuh?); (c) perilaku
  NAV basi (24 jam) di akhir pekan/libur. Distribusi deviasi
  pool-level (harga pool vs median) diterbitkan sebagai detail
  pendukung, BUKAN sebagai metrik keputusan — pooling pool-level
  membuat token dengan banyak pool mendapat bobot lebih besar.
- Threshold saat ini adalah **tebakan awal, berlabel EKSPERIMEN**
  (`config.py`, `DESIGN.md` §4) — bukan kalibrasi, bukan warisan
  Solana. Kalibrasi tidak mengubah status itu kecuali buktinya
  kuat (lihat §3.3).

### 3.2 Data yang dibutuhkan + ukuran sampel yang realistis

- **Sumber:** observasi `max_dev` dari run otomatis S1-D, 26–30 Nov:
  per token-hari, SATU observasi `max_dev` = maksimum
  `|harga_pool − median| / median` atas pool yang lolos filter.
- **N realistis:** bila universe yang ter-cover = 5–15 token ×
  5 hari = **25–75 token-hari** observasi `max_dev`; observasi
  pool-level mentah 50–450 adalah detail pendukung saja.
  **N efektif TIDAK diklaim:** korelasi terjadi dalam satu
  token-hari (NAV sama, hari sama) DAN lintas-token dalam hari
  yang sama (rezim pasar yang sama) — N efektif belum diketahui,
  dan rezim waktunya hanya 5 hari. Jangan menyebut "puluhan
  token-hari" sebagai estimasi N efektif. Itu kecil, dan
  ketidakpastiannya harus ditulis apa adanya.
- **Komposisi minggu yang tidak biasa:** 26 Nov = Thanksgiving
  (NAV beku), 28–29 Nov = akhir pekan (NAV beku). Mayoritas
  sampel 5 hari ini adalah observasi libur/akhir pekan — BUKAN
  minggu bursa normal. Kalibrasi WAJIB memisahkan observasi
  menurut `market_session` (kalender, §1.4b) — `active` vs
  `off_hours` — dan melaporkannya terpisah; jangan gabung lalu
  klaim mewakili minggu normal.
- **Metode (mengikuti pola kalibrasi CMC yang sudah terbukti):**
  distribusi `max_dev` (median, p75, p90) + proporsi snapshot
  WATCH/ABSTAIN + strata jumlah pool/venue/liquidity + sensitivity
  tanpa pool tipis (likuiditas < $1.000, §1.2b). Robust spread
  `(Q3−Q1)/median × 100` per token-hari tetap diterbitkan sebagai
  detail pendukung. Publikasikan distribusi mentahnya, bukan hanya
  threshold akhirnya.

### 3.3 Aturan perubahan threshold + jawaban jujur

- **Threshold DIBEKUKAN selama jendela ini (v1.1)** — diubah HANYA
  bila ada bug metode/satuan yang jelas (mis. satuan salah, rumus
  salah). Jangan menaikkan threshold hanya karena WATCH sering
  menyala: alert yang sering bisa mencerminkan risiko nyata, bukan
  threshold yang salah. Bila distribusi jelas bertentangan dengan
  threshold (mis. median `max_dev` sudah >2% — maka WATCH akan
  menyala terus dan 2% bukan ambang yang informatif), itu dicatat
  sebagai temuan untuk kalibrasi lanjutan SETELAH jendela (dengan
  ADR + distribusi mentah terlampir + pengujian pada hari baru,
  out-of-sample) — BUKAN diubah di dalam jendela ini, karena di
  dalam jendela 5 hari tidak ada hari baru untuk memvalidasi
  perubahan tersebut. Bila distribusi tidak jelas, threshold TETAP
  2%/5% dengan label EKSPERIMEN.
- **Jawaban jujur yang dipakai bila juri/auditor bertanya:**
  *"Analisis deskriptif pendahuluan, belum validasi risiko exit —
  threshold masih eksperimen."* Jangan klaim "terkalibrasi" tanpa
  kualifikasi itu.
- **Item S1-F — Kalibrasi pass 1 (0,5–1 hari, 27 Nov).**
  Distribusi `max_dev` dari data 26–27 Nov (N≈2 hari — SANGAT kecil,
  labeli sebagai pendahuluan) + ADR bila ada perubahan threshold
  (di luar pembekuan, hanya untuk bug metode/satuan).
  **Kalibrasi final (30 Nov):** distribusi 5 hari penuh + keputusan
  threshold final + ADR. Bila N final tetap terlalu kecil untuk
  mengubah apa pun, keputusannya adalah "threshold tetap, kalibrasi
  ditunda" — itu hasil yang sah, bukan kegagalan.

### 3.4 Risiko overfit (ditulis eksplisit)

Satu minggu (libur + akhir pekan) tidak mewakili perilaku
deviasi tokenized stock secara umum. Threshold yang di-fit ke
sampel ini bisa salah besar di minggu bursa normal. Mitigasi:
jangan overfit — laporkan distribusi, ubah threshold hanya
bila buktinya kuat (dan di luar pembekuan §3.3, hanya untuk bug
metode/satuan), dan simpan jawaban jujur §3.3 sebagai
posisi resmi.

---

## 4. Urutan kerja + estimasi + dependensi

| Kapan | Item | Estimasi | Dependensi | Output |
|---|---|---|---|---|
| 24 Nov | Rencana v1.0 → verifikasi chief → review Instinct (7,5/10) → revisi v1.1 (dokumen ini) + perbaikan `adapter.py` (pagination guard; commit terpisah) | — (dokumen ini) | — | `docs/scope1-rencana-eksekusi-2026-11-24.md` v1.1 |
| 25 Nov pagi | **Keputusan review v1.1** (paling lambat 25 Nov 09:00 WITA) | — | Rencana v1.1 | ACC / revisi / tolak. Bila belum diputuskan, 26 Nov terancam slip → §6 R5. |
| 25 Nov | S1-A sensus universe (fail-closed) | 0,5 hari | ACC review | `evidence/coinbase_tokenized_stocks_all.json` + manifest |
| 25 Nov | S1-B sensus venue | 0,5 hari | ACC review (paralel S1-A) | `evidence/venue_census_<tgl>.json` |
| 25–26 Nov | S2 probe jalur FIRM | 1 hari | ACC review (paralel S1-A/B) | `evidence/firm_quote_probes_<tgl>.json` + `docs/firm-quote-definition-*.md` |
| 25 Nov | **S1-G tes integritas gate — DIPINDAH LEBIH AWAL (v1.1)** | 0,25 hari | — (paralel; sebelum setiap merge mulai hari ini) | Tes gate hijau + guard hash/AST `decide()`; simulasi TIDAK PERNAH → PAPER_PROPOSAL; gate OFF |
| 26 Nov | S1-C jalur kode V4 (identitas end-to-end) | 1 hari | S1-B (metode klasifikasi) | `pipeline.py` + tes `gate.py` hijau |
| 26 Nov | S1-D cron + manifest (HARD) — DILEPAS dari S1-C | 0,5 hari | ACC review (bukan S1-C); jalan dulu V3/Aero | Cron jalan 23:00 WITA; run otomatis pertama 26 Nov tercatat |
| 26 Nov malam | **Review early exit** | — | S1-D + S2 | Putuskan: lanjut (a1') atau kunci (a2). Lihat §6 (T1/T2 v1.1). |
| 27 Nov | S1-E feed + indeks harian | 0,5 hari | S1-D | `out/index_<tgl>.json`; kontrak feed terdokumentasi |
| 27 Nov | S1-F kalibrasi pass 1 | 0,5–1 hari | S1-D (data 26–27 Nov) | Distribusi `max_dev` pendahuluan + ADR bila berubah |
| 27 Nov | **Tinjau kemajuan FIRM (v1.1)** | — | S2 | Sampling berjalan sesuai rencana? Lanjut / kunci (a2) lebih awal. |
| 27 Nov | **Kesiapan fase 2 — freeze generator (v1.1)** | — | S1-D | Generator brief + skrip registry siap; dry-run atas data 27 Nov |
| 28 Nov siang | **Gerbang kesiapan fase 2 (v1.1)** | — | Kesiapan 27 Nov | Generator + registry HARUS siap sebelum run 28 Nov 23:00 WITA |
| 28–30 Nov | Fase 2 (di luar rencana ini): agen (a1') + registry Sepolia | 2–3 hari | Scope 1 hidup + gerbang kesiapan lolos | Brief harian + RESEARCH_DRAFT + hash Sepolia |
| 30 Nov | Checkpoint kill-switch: verifikasi 5 kriteria | — | Semua di atas | Penilaian tertulis per kriteria |
| 1–3 Des | QA akhir | — | Checkpoint | — |
| 4–5 Des | Submit (Septian) | — | QA | Form + post X + video (Septian) |

Total Scope 1: **~3–3,5 hari kerja** (25–27 Nov) + kalibrasi final
30 Nov. Muat di jendela — DENGAN CATATAN review diputuskan
25 Nov pagi dan tidak ada item yang slip sehari pun. S1-G yang
pindah lebih awal tidak menambah total (0,25 hari yang sama,
dikerjakan 25 Nov, bukan 27 Nov).

---

## 5. Kriteria selesai per item (bisa diuji) → pemetaan kill-switch

| Item | Kriteria selesai (bisa diuji) | Kill-switch |
|---|---|---|
| S1-A sensus universe | Cursor terminal habis + `error` None + `ok` True + tidak ada loop/halaman malformed (`verify_census.py` lolos); total token tercatat; `config.TOKENS` dihasilkan dari sensus + catatan bertanggal + versi; listed/covered/decision-eligible dibedakan; token tanpa coverage tercatat di `universe_no_coverage.json`; kontrak metadata §1.2c terpenuhi; shared fetch cache dipakai; exception isolation per token. | 1 (data) |
| S1-B sensus venue | Tiap token universe punya daftar pair + klasifikasi V3/V4 (label + panjang cocok); likuiditas tercatat; konflik klasifikasi = 0 yang belum diselidiki; klasifikasi dikonfirmasi on-chain bila memungkinkan. | 1 (data) |
| S1-C jalur kode V4 | Fixture poolId V4 (tanpa `pool_address`) lolos build → assess → decide → public snapshot → replay → feed tanpa `KeyError`; dedup, count, dan deviasi benar; `venue_verified` TIDAK PERNAH true untuk poolId; versi protokol terpisah dari family independensi; validasi StateView (`sqrtPriceX96` ter-initialize, PoolKey konsisten dengan poolId); `gate.py` hijau; `git diff` tidak menyentuh `decide()`. | 1 (data) |
| S1-D cron + manifest | Cron jalan 23:00 WITA (dilepas dari S1-C, V3/Aero dulu); manifest 26 Nov ada, dihasilkan cron (bukan manual), berisi scheduler config/log, run ID, commit/schema/config hash, input hashes, waktu mulai/selesai, status per sumber; `verify_daily_runs.py` lolos per hari; tiap record punya `fetched_at` + `source`; minimum data usable per hari terpenuhi (≥1 snapshot lengkap); manifest kosong/error TIDAK dihitung; 5 hari kalender (26–30 Nov), bukan 120 jam. | **1 (kriteria keras)** |
| S1-E feed + indeks | `public_snapshot` tersedia untuk semua token universe; `out/index_<tgl>.json` lengkap; kontrak feed tertulis (memuat identitas kanonis + `market_session`). | 1 (data) |
| S1-F kalibrasi | Distribusi `max_dev` + proporsi WATCH/ABSTAIN + strata pool/venue/liquidity + sensitivity tanpa pool tipis diterbitkan; keputusan threshold tercatat (beku kecuali bug metode/satuan) + ADR bila berubah; jawaban jujur §3.3 tercantum ("analisis deskriptif pendahuluan, belum validasi risiko exit"); TIDAK ada klaim N efektif. | 1 (data; pendukung 3) |
| S1-G tes gate | Dikerjakan 25 Nov + sebelum setiap merge (bukan 27 Nov); dua penahan diuji terpisah (gate OFF menahan semua quote; gate ON hanya dalam tes terisolasi tetap menahan simulasi); guard hash/AST `decide()` ada dan hijau; quote simulasi (apa pun isinya) → keputusan TIDAK PERNAH PAPER_PROPOSAL; `PAPER_PROPOSALS_ENABLED` tetap `False` (tes membaca nilai config, bukan asumsi). | **5** |
| S2 probe FIRM | Tiap kandidat punya respons mentah + penilaian per field; expected-out/min-out/price impact/slippage dipisah; provenance `expires_at` per vendor tercatat; cross-check §2.1b (sumber dinamai sebelum probe + rumus + hasil) lolos ≤1%; ≥10 sampel firm lolos (definisi §2.1) + ≥2 hari. ATAU laporan "tidak ada yang lolos" + keputusan §2.5. Bar 26 Nov: ≥1 jalur memenuhi definisi beku + cross-check sah berjalan + rencana sampling bisa dijalankan. | **2 (kriteria keras)** |
| Fase 2 siap (28 Nov) | Generator brief + skrip registry siap sebelum run 28 Nov 23:00 WITA; owner, cut-off checkpoint, versi generator/prompt/model, input/output hash, dan arti reproducible ditetapkan; dry-run 27 Nov lolos. | 3–4 (pendukung) |

**Yang TIDAK ada di tabel ini (bukan Scope 1):** kriteria 3
(brief otomatis 3 hari — fase 2, agen) dan kriteria 4 (hash
Sepolia — fase 2, registry). Scope 1 menyiapkan DATANYA
(kriteria 1–2); kriteria 3–4 dinilai di checkpoint 30 Nov
dari hasil fase 2.

---

## 6. Risiko + pemicu early exit 26 Nov

**Pemicu → kunci (a2) pada review malam 26 Nov (v1.1):**

- **T1 — Tidak ada run otomatis valid pada 26 Nov.** Tidak ada
  manifest run 26 Nov yang dihasilkan cron (atau
  `verify_daily_runs.py` gagal, atau manifest kosong/error).
  Akibat: 5 hari berturut-turut sampai 30 Nov sudah mustahil
  secara matematis → kriteria 1 gagal → (a2). **Reframing
  (v1.1):** keterlambatan review melewati 25 Nov 09:00 adalah
  risiko jadwal, bukan bukti matematis bahwa cron pasti tidak
  sempat dipasang — pisahkan target review dari kegagalan data
  yang benar-benar terjadi. Bila review terlambat, tanggal
  26 Nov harus direncanakan ulang secara eksplisit (lihat R5),
  bukan diasumsikan selamat.
- **T2 — Bar 26 Nov tidak terpenuhi.** Tidak ada SATU jalur pun
  yang memenuhi definisi beku §2.1, ATAU sumber cross-check yang
  sah belum berjalan, ATAU tidak ada rencana sampling yang bisa
  dijalankan. Akibat: kunci (a2) pada review 26 Nov. Jangan
  menunggu 30 Nov; jangan ubah definisi supaya ada yang lolos.
  Bar ini adalah keputusan early-stop yang konservatif, bukan
  bukti matematis kegagalan (nol sampel 26 Nov belum membuktikan
  nol 30 Nov) — tetapi bar ini yang disepakati sebagai titik
  henti dini. Tinjau kemajuan 27 Nov; bila sampling tertinggal
  dari rencana, kunci (a2) lebih awal.
- **T1 atau T2 saja sudah cukup.** Keduanya independen;
  salah satu gagal = early exit.

**Risiko yang dicatat (bukan pemicu otomatis — keputusan review 26 Nov):**

- **R1 — Universe terlalu tipis.** Sensus menunjukkan <3 token
  dengan coverage yang bisa dipakai (median rapuh di mana-mana).
  Brief 2-aset tetap demo-able, tapi klaim track "Base Stocks"
  melemah. Keputusan: review 26 Nov (lanjut / kunci a2 /
  persempit klaim).
- **R2 — Klasifikasi V4 gagal.** `labels` dan panjang
  `pairAddress` tidak cocok dengan cek on-chain (StateView tidak
  mengonfirmasi poolId, atau PoolKey tidak konsisten dengan
  poolId). Akibat: V4 tetap di luar; coverage = V3 + Aero saja.
  Bukan pemicu kill-switch (kriteria 1 soal data mengalir, bukan
  soal V4) — dicatat sebagai pengurangan scope.
- **R3 — Kalibrasi N terlalu kecil.** Data 5 hari tidak cukup
  untuk mengubah threshold apa pun. Bukan kegagalan: keputusan
  "threshold tetap, kalibrasi ditunda" + jawaban jujur §3.3.
  Threshold dibekukan selama jendela (§3.3).
- **R4 — RPC publik tidak stabil.** `run.py` gagal berkali-kali
  karena RPC (bukan karena kode). Mitigasi: daftar
  `BASE_RPC_URLS` sudah punya fallback (mainnet.base.org +
  BlastAPI); bila keduanya gagal, run dicatat gagal + diulang,
  bukan diisi data palsu. Run yang gagal TIDAK dihitung sebagai
  hari data.
- **R5 — Review lambat.** Setiap hari keterlambatan review
  menggeser seluruh rantai sehari. Batas: keputusan review
  25 Nov 09:00 WITA; bila lewat, tanggal 26 Nov terancam — T1
  dinilai dari ada/tidaknya run otomatis valid 26 Nov, bukan dari
  keterlambatan review itu sendiri. Bila review terlambat,
  susun ulang jadwal secara eksplisit sebelum melanjutkan.
- **R6 — Cross-check independen tidak tersedia (v1.1, baru).**
  Tidak ada vendor kedua yang merespons DAN referensi NAV/proxy
  tidak dapat dipakai (mis. NAV basi, proxy mati). Akibat: bar T2
  bagian (b) tidak terpenuhi → kunci (a2) 26 Nov. Mitigasi:
  tetapkan sumber pembanding sebelum probe (§2.1b) dan uji
  ketersediaan referensi fallback pada 25 Nov.
- **R7 — Generator fase 2 belum siap sebelum run 28 Nov (v1.1,
  baru).** Tiga brief otomatis 28–30 Nov hanya muat bila generator
  siap sebelum run 28 Nov 23:00 WITA. Mitigasi: freeze generator
  akhir 27 Nov + dry-run atas data 27 Nov + gerbang kesiapan
  28 Nov siang (§4). Bila gerbang tidak lolos, kriteria 3 dinilai
  dari hari yang tersisa (kurang dari 3 hari = tidak terpenuhi)
  — jangan memalsukan brief dari data yang tidak ada.

---

## 7. Batas keras + yang TIDAK ada di rencana ini

- TIDAK ada perubahan `decide()`, `validate_exit_quote`,
  `PAPER_PROPOSALS_ENABLED`, atau threshold policy di luar ADR
  kalibrasi (§3.3). Guard hash/AST memastikan `decide()` tidak
  berubah (S1-G, §5).
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
- V4 boleh dipotong bila tidak sempat (pengurangan scope, §1.3)
  — bukan pemicu kill-switch dan bukan penghapusan fitur yang
  sudah ada.
- S1-G (tes integritas gate) jalan sebelum setiap merge mulai
  25 Nov, bukan menunggu 27 Nov.

---

## Lampiran — referensi kode & bukti (yang dicek saat menulis rencana)

- `config.py:269` — `PAPER_PROPOSALS_ENABLED = False`.
  `config.py:332-333` — notional $10.000, bobot maks 0,50.
  `config.py` — `AERO_SLIPSTREAM_CL_FACTORY =
  0x9cb220581b91b0c83223012fe69688b92ad07a76`.
  `US_MARKET_HOLIDAYS_2026` memuat 2026-11-26 (Thanksgiving).
  `NAV_STALE_HOURS = 24` (`config.py:261`).
- `pipeline.py:242-502` — `validate_exit_quote` (definisi firm vs
  simulasi). `626-799` — `ingest_token` (per token; `fetch_coinbase_tokens`
  per token di `:638`; `proxy_instrument` di `:954`, `proxy_dex` di
  `:964`). `800-1115` — `build_snapshot` (penolakan V4 via
  `_is_address`; dedup via `o["pool_address"]` di `:980`).
  `855-864` — `session_status` dari umur NAV. `1115+` —
  `assess_snapshot` (akses `pool_address` langsung di `:1295`).
  `1314-1316` — policy memakai `max_dev` (bukan median deviasi).
  `1472-1546` — `decide()` (aturan 3 + 4, dua penahan).
- `adapter.py` — `fetch_dexscreener_pools`,
  `fetch_geckoterminal_pool` (cross-check pool YANG SAMA, bukan
  venue independen), `fetch_sell_quote` (eth_call,
  `kind: onchain_simulation`), `fetch_oracle_params`,
  `fetch_pool_factory`, `fetch_block`, `fetch_coinbase_tokens`
  (guard pagination: guard trip → `ok=False`, diperbaiki 24 Nov —
  sebelumnya `ok=True` sesudah `error` diset, `adapter.py:103-106`).
- `run.py` — runner manual satu pass; output `out/`.
- `gate.py` — suite tes (19/19 PASS, 23 Nov; hijau sesudah perbaikan
  `adapter.py`, 24 Nov).
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
- **Referensi v1.1 (dicek saat revisi, 24 Nov):**
  - Uniswap v4-periphery `StateView.sol` — `getSlot0(PoolId)`
    eksternal ada di StateView (bukan PoolManager);
    `StateLibrary.getSlot0` internal, membaca via
    `PoolManager.extsload`.
  - docs.0x.org troubleshooting Swap API — quote dirancang revert
    bila likuiditas berubah dan harga jatuh di bawah ambang yang
    dipilih; `minBuyAmount` adalah batas revert, bukan jaminan
    pasti fill.
  - NYSE early close Jumat 27 Nov 2026 13:00 EST — konversi
    terverifikasi (`date`): buka 27 Nov 22:30 WITA, tutup 28 Nov
    02:00 WITA, Senin 30 Nov buka 22:30 WITA; 26 Nov = Kamis
    (Thanksgiving), 28–29 Nov = Sabtu–Minggu.
