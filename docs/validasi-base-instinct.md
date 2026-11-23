# Validasi Teknis Read-Only — Base Stocks Maxxing (per review Instinct)

> Tanggal validasi: Minggu, 22 Nov 2026 (observasi ~09:21 UTC / 17:21 WITA)
> Sifat: validasi 4–6 jam, read-only, BUKAN komitmen membangun.
> Semua klaim diverifikasi dari respons API live atau docs resmi, bukan dari ingatan.
> Tidak ada yang onchain, tidak ada perubahan pada web Radar yang live, tidak ada pendaftaran/akun, tidak ada API key.

## Ringkasan vonis

| # | Item | Vonis |
|---|---|---|
| 1 | Identifikasi NVDAc + AAPLc lewat API resmi Base (tanpa key) | **LOLOS** |
| 2 | Pahami datanya (multiplier, nav_price vs market, oracle diam) | **LOLOS** |
| 3 | Buktikan 1 harga venue nyata + timestamp | **LOLOS** |
| 4 | Dokumentasi perbedaan dari kalibrasi Solana | **LOLOS** (terdokumentasi, dengan caveat) |

**Vonis keseluruhan: keempatnya LOLOS → siap bahas komit 13 hari.**
Caveat yang wajib masuk ke pembahasan itu (detail di §4): Exit Score versi Base TIDAK bisa sekadar port dari Solana — komponen redemption (20 poin) tidak punya sumber data, PoR tidak punya sumber otomatis, dan funding/OI (25 poin) bergantung pada ada/tidaknya perp Hyperliquid untuk token itu (belum dicek). Kalau nav_price dipakai mentah-mentah sebagai referensi, skornya MENYESATKAN tiap akhir pekan (bukti: §3).

---

## 1. Identifikasi 2 token saham resmi di Base — LOLOS

### Sumber (resmi, publik, tanpa key)
- **API resmi:** `GET https://api.coinbase.com/v1/tokenized-stocks` (List Tokenized Stocks).
- **Docs:** https://docs.base.org/sdks/tokenized-stocks/overview — tertulis eksplisit: *"Use the public Tokenized Stocks API to retrieve reference data for Coinbase-issued tokenized stocks on Base. The API is read-only and does not require an API key."*
- **Hasil panggilan (22 Nov 2026 ~09:21 UTC):** HTTP **200**, 243.577 byte, 100 token di halaman pertama (+ `next_page_token` untuk halaman berikut). Tidak ada API key, tidak ada akun, tidak ada pendaftaran.

### NVDAc — NVIDIA Corporation
| Field | Nilai persis |
|---|---|
| contract_address | `0xb20000000000000000000078ee7ce2fE4908108C` |
| symbol | NVDAc |
| name | NVIDIA Corporation |
| decimals | 8 |
| total_supply | 62019.73777574 (token-unit, ternormalisasi desimal) |
| isin | US67066G1040 |
| adgm_isin | AE000A4AV8A0 |
| multiplier | 1.0005379395763694 |
| nav_price | 129.82480034 |
| nav_price_updated_at | 2026-11-20T23:42:40Z (Jumat) |
| first_mint_date | 2026-08-12T12:40:59Z |
| paused_features | tidak ada (field tidak muncul = default/kosong) |

### AAPLc — Apple Inc.
| Field | Nilai persis |
|---|---|
| contract_address | `0xb200000000000000000000C2e324d24d7eEcd1fb` |
| symbol | AAPLc |
| name | Apple Inc. |
| decimals | 8 |
| total_supply | 6067.1390882 |
| isin | US0378331005 |
| adgm_isin | AE000A4AV8C6 |
| multiplier | 1.0005003893019802 |
| nav_price | 345.29769685 |
| nav_price_updated_at | 2026-11-20T23:12:02Z (Jumat) |
| first_mint_date | 2026-08-12T12:54:19Z |
| paused_features | tidak ada (field tidak muncul = default/kosong) |

### Status availability
- Kedua token **terdaftar di API resmi**, punya `total_supply > 0` dan `nav_price`, dan **tidak ada `paused_features`**. Itu bukti tokennya eksis dan live.
- Catatan jujur dari docs-nya sendiri: *"Presence in the response does not imply trading availability or eligibility."* Jadi daftar di API saja TIDAK membuktikan bisa diperdagangkan. Bukti perdagangannya ada di §3 (harga venue nyata untuk keduanya, volume jutaan dolar/24 jam). Gabungan keduanya = availability terkonfirmasi.
- Kedua token diterbitkan oleh Coinbase Onchain SPV Ltd (ADGM), underlying shares di segregated custody; mint/redeem hanya untuk Authorized Participants (KYC). Perdagangan secondary market permissionless.

---

## 2. Pahami datanya — LOLOS

Sumber utama: https://docs.base.org/build-on-base/integrate-defi/list-tokenized-stocks dan https://docs.base.org/sdks/tokenized-stocks/overview (keduanya dibaca live 22 Nov 2026), plus record API di §1.

### (a) Multiplier dividen/split — bagaimana tercermin
- **Definisi (docs API):** *"`multiplier` is the current scaling factor between token units and underlying shares. It can change for corporate actions such as dividends or stock splits, so always apply the current value when converting token units to shares."*
- **Definisi (docs B20):** *"An underlying real-world asset may undergo events that change the redemption ratio of a B20 token. For tokenized stocks, these events include dividends or stock splits... The multiplier variable instantly updates the redemption ratio... After a dividend on a tokenized equity, the multiplier increases to 1.02, representing that 1 B20 token is redeemable for 1.02 shares of the equity. At this time, for tokenized stocks, cash dividends are converted to shares of the underlying equity and reflected via a multiplier update rather than distributed as cash to the B20 holder. This allows B20 holder balances to automatically reflect corporate actions without changing their balance of the B20 token."*
- **Mekanisme update:** Scheduled (ERC-8056 `updateUIMultiplier`, perubahan bertanggal ke depan, ada pemberitahuan onchain di muka — untuk corporate action rutin) dan Instant (`updateMultiplier`, deprecated, failsafe darurat, langsung berlaku dan menghapus perubahan terjadwal yang pending). Pembatalan via `cancelUIMultiplierUpdate`.
- **Deskripsi token (API):** *"Each token initially represents a 1:1 beneficial interest... The applicable share-to-token ratio may change over time to reflect reinvested distributions, fees, taxes, corporate actions, and other adjustments... Dividends and other distributions received on the underlying shares are generally reinvested, after applicable taxes, fees, and expenses, with the resulting economic benefit reflected through an adjustment to the share-to-token ratio."*
- **Rumus harga token:** harga token = harga pasar equity underlying × multiplier. Multiplier onchain ber-skala WAD (18 desimal); bagi dengan `1e18` untuk faktor sebenarnya.
- **Nilai saat ini (bukti dividen sudah tercermin):** NVDAc multiplier **1.0005379395763694** (+0,0538% di atas 1), AAPLc **1.0005003893019802** (+0,0500% di atas 1). Keduanya sedikit di atas 1 — konsisten dengan dividen yang sudah di-reinvestasikan sejak listing (Agustus 2026), bersih dari pajak/biaya. Artinya 1 token NVDAc saat ini dapat ditebus untuk 1,0005379 saham (bukan tepat 1).
- **Implikasi riwayat:** untuk merekonstruksi seri historis yang konsisten, wajib memakai riwayat multiplier dari event `UIMultiplierUpdated` (diberi tanggal dari `effectiveAtTimestamp`, BUKAN block time; buang update terjadwal yang kemudian dibatalkan oleh `UIMultiplierUpdateCancelled`).

### (b) nav_price (referensi) vs harga market beneran
- **nav_price (docs API):** *"`nav_price` is the most recently published Chainlink-based NAV/reference value for the token. It is not a live bid/ask or execution price."*
- **nav_price_updated_at:** kapan `nav_price` terakhir diperbarui onchain. *"Feeds update only on price deviation or heartbeat and hold their last value outside market hours, so check this timestamp and apply staleness bounds before relying on `nav_price`."*
- **Sumber harga (docs B20):** *"A tokenized stock's price is available from both onchain and offchain sources. In every case, the price is derived from the same relationship: the underlying equity's market price scaled by the token's multiplier."*
- **Onchain (Chainlink):** setiap token punya Chainlink feed. Feed melaporkan **Total Return Values**, BUKAN harga equity mentah — *"so the price reflects the underlying's total return including corporate-action adjustments."* Harga underlying bersumber dari Chainlink equity price feeds (data market tradisional), **BUKAN dari perdagangan onchain/DEX token itu; harga DEX token tidak masuk ke oracle.**
- **Offchain (market):** aggregator (CoinGecko, CoinMarketCap, RWA) melacak harga market live token dari DEX tempat B20 diperdagangkan, yang berjalan 24/7 selama secondary market aktif.
- **Jadi bedanya:** `nav_price` = nilai referensi/NAV dari Chainlink (total-return, berbasis data market tradisional, bukan harga eksekusi). Harga market = harga DEX yang benar-benar terbentuk dari perdagangan (24/7). Keduanya sah, tapi bukan hal yang sama — dan `nav_price` TIDAK BOLEH dipakai sebagai harga eksekusi atau sebagai referensi live.

### (c) Kapan oracle-nya diam (weekend/holiday)
- **Jadwal feed (docs B20):** *"Each tokenized equity has a Chainlink feed that runs 24/5, holds the last close on weekends and holidays, and freezes during corporate actions."* Semua feed mengembalikan 8 desimal, mencakup ekuitas AS (jam market 24/5), dan update pada deviasi harga 0,5% atau heartbeat 24 jam.
- **Pause flag (oracle registry):** feed membaca multiplier + pause flag dari satu kontrak oracle registry Coinbase (alamat `0x3f3E8cf41cdd3b1D118c16471aB0113DfDDd5CaD`). Normal (`paused = false`): feed mempublikasikan harga underlying × multiplier. Paused (`paused = true`): feed berhenti mempublikasikan dan menahan nilai terakhir yang diketahui baik.
- **Saat corporate action:** mint dan redeem pause offchain, tapi token TIDAK di-pause onchain (transfer tidak diblokir). Feed membeku (pause flag diset) dan harganya basi. Karena feed bersifat total-return, tidak ada diskontinuitas harga: multiplier dan harga underlying bergerak berlawanan arah dan saling meniadakan (split 10:1 menurunkan harga ~10x dan menaikkan multiplier ~10x). **Fail-safe:** feed hanya lanjut setelah Coinbase mengonfirmasi harga underlying DAN multiplier keduanya sudah mencerminkan nilai baru; kalau satu update duluan, feed tetap beku di harga pra-pause daripada mempublikasikan nilai yang baru diterapkan separuh.
- **BUKTI LIVE (diukur saat validasi):** hari ini Minggu, 22 Nov 2026. `nav_price_updated_at` NVDAc = **Jumat, 20 Nov 2026 23:42:40 UTC** dan AAPLc = **Jumat, 20 Nov 2026 23:12:02 UTC**. Pada saat observasi (Minggu 09:21:18 UTC), `nav_price` NVDAc sudah basi **33,64 jam** dan AAPLc **34,15 jam** — keduanya adalah harga close Jumat yang ditahan sepanjang akhir pekan, persis seperti yang didokumentasikan. Ini BUKAN error; ini perilaku feed yang by-design.

---

## 3. Buktikan 1 harga venue nyata + timestamp — LOLOS

Token yang dibuktikan: **NVDAc** (AAPLc juga dibuktikan sebagai konfirmasi kedua).

### Bukti utama — NVDAc di Aerodrome Slipstream (Base)
- **Venue:** Aerodrome Slipstream, pair NVDAc/USDC, pair address `0xF668e21993f0ACd7ab00BB1cFbAeD0df28A3C8EC`.
- **Sumber 1 — DexScreener (API publik, tanpa key), diobservasi 2026-11-22T09:21:18Z:**
  - Harga: **$132,47** (priceNative 132,4769 USDC)
  - Likuiditas: **$1.299.063,84**
  - Volume 24 jam: **$13.459.878,62**
  - Transaksi 24 jam: **8.116 beli / 6.536 jual** (14.652 transaksi)
  - URL: https://dexscreener.com/base/0xf668e21993f0acd7ab00bb1cfbaed0df28a3c8ec
- **Sumber 2 — GeckoTerminal (API publik, tanpa key), diobservasi 2026-11-22T09:21:45Z (27 detik kemudian):**
  - Harga: **$132,1726**
  - Reserve: **$1.297.665,20**
  - Volume 24 jam: **$13.323.650,54**
  - Transaksi 24 jam: **8.029 beli / 6.456 jual** (1.357 trader unik)
  - Pool dibuat: 2026-10-22T02:50:49Z
- **Selisih kedua sumber: $0,30 (0,22%)** — konsisten dengan pasar live yang bergerak di antara dua panggilan yang berselang 27 detik di pool yang sangat aktif. Keduanya mengonfirmasi harga berada di kisaran $132,2–132,5 — BUKAN harga NAV yang beku ($129,82).
- **Ini harga market yang benar-benar teramati** (dari perdagangan DEX yang sedang berjalan), bukan referensi/NAV. Pool-nya dalam ($1,3 juta likuiditas) dan sangat aktif ($13,5 juta volume/24 jam).

### Konfirmasi kedua — AAPLc di Aerodrome Slipstream
- Pair AAPLc/USDC `0xF5FCB9CDAFcE67d50AfEf298F88E709d2B946BA6`.
- DexScreener (09:21:18Z): **$349,13**, likuiditas $411.107,46, volume 24 jam $6.555.704,86, transaksi 24 jam 2.294 beli / 2.363 jual.
- GeckoTerminal (09:21:45Z): **$348,6173**, reserve $411.552,20, volume 24 jam $6.492.966,12, transaksi 24 jam 2.263 beli / 2.339 jual (604 trader unik).
- Selisih $0,51 (0,15%) — lagi-lagi pergerakan pasar antar panggilan.

### Perbandingan harga DEX vs NAV (ini penting — lihat §4)
Pada saat observasi (Minggu pagi, NAV masih close Jumat):
- NVDAc: DEX $132,47 vs NAV $129,8248 → **+2,04%** (GeckoTerminal: +1,81%).
- AAPLc: DEX $349,13 vs NAV $345,2977 → **+1,11%** (GeckoTerminal: +0,96%).
- Ini BUKAN mispricing. Ini gap akhir pekan: DEX berdagang 24/7 sementara NAV beku di close Jumat. Kalau Radar menghitung "deviasi vs NAV" tanpa memperhatikan ini, ia akan salah mengira ada deviasi +1–2% setiap akhir pekan.

---

## 4. Apa yang BEDA dari kalibrasi Solana kita — LOLOS (terdokumentasi)

### Cara kerja kalibrasi Solana (diringkas dari `poller.py`, `bot.py`, `README.md`)
- **Sumber harga:** DexScreener, batch `/latest/dex/tokens/{s.d. 30 alamat}` per chain, polling 5 menit 24/7 (jendela ketat 1 menit untuk Tier 1 di ±30 menit sekitar buka/tutup NYSE). Pool lolos bila reserve ≥ $100.000 (LIQ_MIN); universe butuh depth gabungan ≥ $500.000 + ≥ 2 venue.
- **Harga acuan:** **cross-venue median saja.** `dev_vs_median_pct` = deviasi harga depth-weighted terhadap median lintas-venue. **`dev_vs_close_pct` SENGAJA selalu NULL** (di-insert sebagai `None`, method `v1-median-only`) — tidak ada sumber harga equity berlisensi yang dikonfigurasi, jadi Radar tidak pernah membandingkan ke equity close.
- **Price guard:** bila ≥ 3 pool, buang pool yang harganya menyimpang >25% dari median lintas-venue (pool yang dibuang tidak menyumbang harga maupun depth).
- **Exit Score v2 (0–100, threshold alert ≥ 70, 1x/ticker/24 jam, hanya bila ≥ 3 dari 5 komponen hadir — aturan M5):**
  | Komponen | Maks | Rumus |
  |---|---|---|
  | deviation | 30 | min(|dev_vs_median_pct| × 10, 30) |
  | depth | 25 | depth_usd / median_depth_7d (rasio ≥1 → 0; ≤0,5 → 25) |
  | redemption | 20 | status jendela redemption + jam ke tutup/buka berikut (≤24 jam → 20; ≤72 jam → 10; paused/gated → 10; unknown → tidak dihitung) |
  | funding | 15 | |funding rate| per-jam Hyperliquid perp (≤0,00125% → 0; ≥0,0125% → 15) |
  | oi | 10 | perubahan open interest 24 jam (≤0% → 0; ≥20% → 10) |
  Normalisasi parsial: komponen tanpa data TIDAK dihitung dan TIDAK di-nol-kan; skor = total / maks-yang-tersedia × 100.
- **Redemption (Solana):** status diturunkan dari jadwal (aturan 24/5 xStocks + kalender NYSE) + cek pause/supply onchain per jam atas 13 mint via PUBLIC Solana RPC (tanpa key).
- **PoR (Solana):** API publik xStocks `api.xstocks.fi/api/v2/public/proof-of-reserves/{symbol}` (tanpa auth), per jam; v1 freshness, v2 per-token `sharesHeld` / `circulatingSupply` / `holdings`. Umur PoR ditentukan token paling basi.
- **Stale gate:** bila siklus poller terakhir yang sukses sudah lebih dari 30 menit, TIDAK ada alert baru yang dikirim.
- **Monday Gap v1:** D = deviasi akhir pekan % (dev_vs_median Minggu), R = drift harga DEX close Jumat → Minggu malam (harga depth-weighted DEX, BUKAN equity close). Gap = clamp(0,6·D + 0,4·R, ±10%). Kode secara eksplisit memperingatkan `previousClose` Yahoo adalah jebakan — jangan pernah dipakai.
- **Catatan plumbing:** poller SUDAH punya batching DexScreener multichain (per chain: Solana + Base + BSC + Robinhood, masing-masing di-chunk 30 alamat). Seed multichain (30 ticker, 115 pool) ada untuk dry-run; live DB masih 0 baris multichain (seed --live belum jalan). Jadi pipa ingesti Base sudah ada — yang belum ada adalah universe + kalibrasi Base.

### Perbedaan material untuk Base

**1. Harga referensi — JANGAN pakai nav_price sebagai referensi live (risiko menyesatkan, paling penting).**
Solana tidak punya harga referensi sama sekali (dev_vs_close NULL by design). Base PUNYA nav_price — dan itu justru jebakannya. nav_price adalah referensi Chainlink (total-return), beku di akhir pekan/libur dan saat corporate action, update hanya pada deviasi 0,5% atau heartbeat 24 jam. Bukti live dari validasi ini: di Minggu pagi, harga DEX NVDAc **+2,04%** dan AAPLc **+1,11%** di atas NAV close Jumat — padahal itu hanya gap akhir pekan, bukan mispricing. Threshold alert Radar adalah deviasi 1,0%. Kalau Exit Score Base memakai nav_price sebagai referensi, ia akan false-positive setiap akhir pekan (komponen deviation langsung mentok 30 poin dari data basi). **Keputusan yang benar: pertahankan dev_vs_close NULL (median-only, sama seperti Solana).** nav_price hanya boleh dipakai sebagai sanity check kasar DENGAN batas basi yang ketat pada `nav_price_updated_at` — dan tidak pernah sebagai referensi live. Kalau aturan ini dipegang, komponen deviation tetap benar. Kalau dilanggar, skornya menyesatkan.

**2. Multiplier / corporate actions — pipeline data baru yang wajib ada.**
Solana: tidak ada konsep multiplier di model Radar (harga DEX dipakai langsung, tidak ada penyesuaian). Base: multiplier BERUBAH seiring waktu (dividen di-reinvestasikan → merayap naik; split → melonjak ~10x). Harga token = harga equity × multiplier. Untuk deviasi lintas-venue (median), multiplier tidak relevan — semua venue memberi harga token yang sama, multiplier sudah tertanam di harga DEX. TAPI untuk SETIAP perbandingan terhadap referensi (nav_price, equity close, harga historis), multiplier WAJIB diterapkan, dan seri historis wajib merekonstruksi riwayat multiplier dari event `UIMultiplierUpdated` (diberi tanggal dari `effectiveAtTimestamp`, buang update yang dibatalkan). Kalau ini diabaikan, sebuah split akan tampak seperti kejatuhan harga yang katastrofal dalam perbandingan referensi. Selain itu feed membeku selama corporate action (pause flag), jadi nav_price juga basi di momen itu. **Ini dependensi data baru yang tidak ada di Solana.**

**3. Oracle diam / kebasian referensi — konsep basi baru yang tidak ada di Solana.**
Solana tidak punya harga referensi, jadi tidak ada konsep "referensi basi" — yang ada hanya stale gate poller (30 menit). Base: NAV basi by-design di akhir pekan (terukur **33,64 jam** untuk NVDAc dan **34,15 jam** untuk AAPLc pada Minggu pagi ini) dan selama corporate action. Stale gate 30 menit Radar TIDAK mencakup kebasian NAV. Kalau Exit Score Base memakai nav_price, ia butuh pemeriksaan kebasian TERPISAH pada `nav_price_updated_at` (plus flag pause dari oracle registry `0x3f3E8cf41cdd3b1D118c16471aB0113DfDDd5CaD`). Radar saat ini tidak punya mekanisme itu. Tanpa itu, skor menyesatkan di akhir pekan.

**4. Redemption (20 poin) — TIDAK ADA sumber datanya di Base; komposisi skor berubah.**
Solana: komponen redemption memakai status jendela yang diturunkan dari jadwal (aturan 24/5 xStocks + kalender NYSE) + cek onchain per jam. Base: mint/redeem HANYA untuk Authorized Participants (KYC) — holder biasa TIDAK BISA redeem langsung; mereka keluar dengan menjual di DEX. Tidak ada API/jadwal jendela redemption publik untuk token Coinbase. Field `paused_features` di API ada (saat ini kosong untuk kedua token), tapi itu soal pause fungsi token, bukan jendela redemption. **Akibatnya komponen redemption (20 poin) akan bernilai None (tidak dihitung) untuk Base.** Skor akan dihitung atas maksimal 4 komponen (maks 80, bukan 100). Aturan M5 (butuh ≥ 3 komponen) masih bisa terpenuhi, tapi makna skor berubah: kaki "exit via redemption" hilang, skor menjadi dominan soal deviasi + depth DEX. **Skor Base 70 TIDAK sebanding dengan skor Solana 70** (komponen dan maks berbeda) — threshold dan bobot perlu dikalibrasi ulang, atau komponen redemption diganti dengan ukuran "exit" berbasis likuiditas DEX. Ini perbedaan struktural terbesar.

**5. PoR (proof of reserve) — TIDAK ADA sumber otomatisnya di Base.**
Solana: API publik xStocks memberi `sharesHeld` / `circulatingSupply` / `holdings` + timestamp, per jam, tanpa auth. Base: API Coinbase memberi `total_supply` (dan endpoint `/total-supply/{contract_address}`), tapi **tidak ditemukan sumber publik untuk "shares yang disimpan di custody"** (separuh lain dari rasio PoR). Backing-nya adalah saham di segregated custody (broker Alpaca) yang dipegang dalam trust (Coinbase Onchain SPV Ltd). Tanpa sumber shares-held, cek PoR (sharesHeld vs circulatingSupply) tidak bisa dihitung. Radar harus membuang PoR untuk Base, atau memakai sumber non-live (laporan attestasi periodik). **Kaki PoR yang ada di Solana hilang di Base.**

**6. Funding / OI (15 + 10 = 25 poin) — bergantung pada ada/tidaknya perp; BELUM DIVERIFIKASI.**
Kedua komponen ini bergantung pada adanya perp Hyperliquid untuk ticker itu (di Solana, SPY/QQQ/GLD tidak punya perp → komponennya None, tidak pernah difabrikasi). Untuk NVDAc/AAPLc, ada/tidaknya perp Hyperliquid **belum dicek dalam validasi ini** (bukan bagian dari 4 item). Skenario:
- Terbaik (perp ada): 4 komponen hadir (deviation, depth, funding, oi) → maks 80; M5 (≥3) terpenuhi, alert masih bisa menyala.
- Terburuk (perp tidak ada): hanya 2 komponen hadir (deviation, depth) → maks 55; M5 (≥3) TIDAK terpenuhi, jadi **Exit Score tidak akan pernah menyalakan alert "high"** — ia jadi angka pajangan, bukan sinyal alerting.
**Ini dependensi yang menentukan apakah Exit Score Base berguna sebagai alat alerting atau tidak.** Cek perp Hyperliquid untuk NVDAc/AAPLc adalah follow-up 5 menit yang wajib dilakukan sebelum memutuskan desain skor — bukan bagian dari validasi ini, tapi harus selesai sebelum komit.

**7. Struktur venue / depth — mekanik sama, konsentrasi lebih tinggi.**
Solana: 13 ticker / 35 pool di beberapa venue DEX. Base: NVDAc 30 pair, AAPLc 24 pair, didominasi Aerodrome Slipstream (liquidity provider hari pertama; pool NVDAc/USDC $1,3 juta, AAPLc/USDC $411 ribu). Pendekatan median lintas-venue tetap bekerja, tapi konsentrasinya tinggi (satu pool mendominasi depth; harga depth-weighted praktis = harga Aerodrome). Kriteria universe (≥2 venue, depth gabungan ≥ $500 ribu, pool ≥ $100 ribu) TERPENUHI untuk kedua token. Price guard (>25% dari median) tetap berlaku. Ini perbedaan kecil — mekaniknya transfer, tapi konsentrasinya perlu dicatat.

**8. Monday Gap — logika DEX-only tetap benar; nav_price adalah jebakan di sini juga.**
Solana memakai harga DEX saja (D = deviasi Minggu, R = drift harga DEX close Jumat → Minggu malam) dan secara eksplisit menolak `previousClose`. Untuk Base, logika DEX-only yang sama tetap benar. nav_price sebagai "close Jumat" adalah jebakan (total-return, beku). Jadi Monday Gap Base harus memakai harga DEX saja, sama seperti Solana — dengan guardrail agar tidak ada yang "memperbaikinya" dengan nav_price.

### Penilaian: apakah Exit Score versi Base akan benar atau menyesatkan?
- **Jika di-port mentah-mentah dari Solana (terutama bila nav_price dipakai sebagai referensi): MENYESATKAN.** Komponen deviation akan false-positive tiap akhir pekan (bukti: +2,04% / +1,11% vs NAV di Minggu pagi), dan komponen redemption akan hilang diam-diam sehingga skor 70 Base tidak sebanding dengan skor 70 Solana.
- **Jika dibangun dengan rekalibrasi berikut, BENAR (dengan batas yang jujur):** (i) dev_vs_close tetap NULL (median-only), nav_price hanya sanity check dengan batas basi; (ii) multiplier diterapkan di setiap perbandingan referensi + riwayat multiplier direkonstruksi; (iii) komponen redemption dibuang/diganti dan threshold dikalibrasi ulang untuk komposisi baru; (iv) PoR dibuang untuk Base (atau diganti sumber non-live); (v) funding/OI hanya dipakai bila perp Hyperliquid terverifikasi ada — bila tidak ada, akui bahwa Exit Score Base tidak bisa menyalakan alert "high" di bawah aturan M5.
- Dengan rekalibrasi itu, Exit Score Base tetap berguna sebagai ukuran kondisi DEX (deviasi + depth), tapi **bukan** ukuran exit-ability yang setara dengan Solana — karena kaki redemption dan PoR-nya memang tidak ada. Itu harus dinyatakan terus-terang di dashboard, bukan disembunyikan.

---

## Vonis keseluruhan

**Keempat item LOLOS → siap bahas komit 13 hari.**

Validasi ini membuktikan: kedua token resmi teridentifikasi lewat API publik tanpa key; datanya (multiplier, nav_price, perilaku oracle) dipahami dari docs resmi dan dikonfirmasi bukti live (NAV basi 33–34 jam di akhir pekan); harga venue nyata terbukti dari dua sumber independen; dan perbedaan kalibrasi dari Solana sudah didokumentasikan lengkap dengan penilaian benar/menyesatkan.

Yang HARUS masuk ke pembahasan komit (bukan alasan NO-GO, tapi syarat desain):
1. **Cek perp Hyperliquid untuk NVDAc/AAPLc** (follow-up 5 menit) — ini yang menentukan apakah Exit Score Base bisa menyalakan alert atau hanya jadi angka pajangan.
2. **Keputusan desain Exit Score Base** (median-only, buang/ganti redemption, kalibrasi ulang threshold) harus diambil di hari pertama — ini pekerjaan desain, bukan sekadar port.
3. **Kill-switch 30 Nov tetap berlaku** — bila integrasi Base belum jalan, berhenti.

Tidak ada temuan dalam validasi ini yang membenarkan NO-GO. Mentok di #1 atau #2 tidak terjadi.

---

## Lampiran — sumber

- API resmi: `GET https://api.coinbase.com/v1/tokenized-stocks` (HTTP 200, 243.577 byte, 22 Nov 2026 ~09:21 UTC)
- Docs API: https://docs.base.org/sdks/tokenized-stocks/overview
- Docs B20 / price feeds / multiplier: https://docs.base.org/build-on-base/integrate-defi/list-tokenized-stocks
- Harga venue: DexScreener `https://api.dexscreener.com/latest/dex/tokens/{address}` (tanpa key); GeckoTerminal `https://api.geckoterminal.com/api/v2/networks/base/pools/{pool}` (tanpa key)
- Kalibrasi Solana: `~/workspace/radar-tokenized-stocks/poller.py` (Exit Score v2, deviasi median-only, redemption, PoR), `bot.py` (threshold alert ≥70, aturan M5, stale gate 30 menit), `README.md`, `schema.sql`
- Waktu observasi: Minggu, 22 Nov 2026 09:21:18–09:22:46 UTC (17:21–17:22 WITA). 20 Nov 2026 = Jumat; 22 Nov 2026 = Minggu (dicek via `date`).
