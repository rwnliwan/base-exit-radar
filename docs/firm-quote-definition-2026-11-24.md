# Definisi Quote FIRM + Hasil Probe Jalur Tanpa Key (S2)

**Tanggal probe:** 24 Nov 2026, round 1 pukul 08:35–08:38 WITA, round 2 pukul 08:42–08:44 WITA
(00:35–00:44 UTC). **Status: TIDAK ADA kandidat yang lolos — hasil sah (§2.5).**
**Skrip:** `probe_firm_quotes.py` · **Evidence mentah:**
`evidence/firm_quote_probes_2026-11-24.json` (12 sampel, 2 round).
**Probe ber-key 24 Nov 2026 ~09:10–09:15 WITA (01:10–01:15 UTC): 0x + 1inch — JUGA
TIDAK ADA yang lolos (lihat §8).** Skrip: `probe_firm_quotes_keyed.py` +
`probe_firm_quotes_keyed_round2.py` · Evidence:
`evidence/firm_quote_probes_keyed_2026-11-24.json` (8 sampel round 1 + 8 probe
karakterisasi round 2).
**Rencana yang dipakai:** `docs/scope1-rencana-eksekusi-2026-11-24.md` §2.1, §2.1b, §2.3, §2.4, §2.5.
**Tidak ada kode produsen yang ditulis** (sesuai §2.4: bila tidak ada yang lolos, hanya laporan + keputusan).

---

## 1. Definisi FIRM yang dipakai (§2.1 — dibekukan, bukan definisi baru)

Sumber definisi: `pipeline.py:validate_exit_quote` (baris 242–502). Quote FIRM =

- `kind` ∈ (`firm`, `executable`, `guaranteed`) — label wajib; quote tanpa `kind`
  DITOLAK validator (`exit_quote_kind_missing`), tidak pernah diasumsikan firm;
- `amount_out_min` — jumlah minimum yang dikomitmenkan vendor (bukan estimasi);
- `expires_at` — jaminan expiry dari vendor, dengan provenance semantik
  (nama field + arti menurut dokumentasi vendor). DILARANG dibentuk dari jam
  lokal (`now + TTL`); bila vendor tidak memberi semantik expiry, quote itu
  TIDAK dapat diklasifikasikan firm;
- `quoted_at` + semua sanity check yang sama dengan simulasi: `token_out` di
  allowlist USDC Base, side SELL, notional yang dinyatakan ≥ $10.000, notional
  hitung (`amount_in` × median) ≥ $10.000, harga implisit dalam ±10% dari
  median DEX, konsistensi notional dalam rasio 2×, umur ≤ 300 detik,
  `expires_at` > waktu evaluasi.

Lolos semua → status `verified` → layer B `verified`. Taksonomi ini BEKU:
tidak ada `kind` baru, tidak ada pemetaan simulasi → `verified`, tidak ada
pelonggaran toleransi. Simulasi yang diperkuat (mis. dry-run calldata swap)
tetap `kind: onchain_simulation` — bukan komitmen eksekusi, dan menyebutnya
firm adalah overclaim yang dilarang reframe (a1').

**Peran FIRM dalam paket (a1'):** proposal paper (RESEARCH_DRAFT) memakai bukti
SIMULASI dan TIDAK butuh quote firm. Jalur FIRM dibutuhkan karena **kriteria
kill-switch 2** menuntutnya, dan karena ia tonggak integritas (bukti exit yang
sebenarnya). FIRM saja tidak pernah menghasilkan PAPER_PROPOSAL selama gate
OFF — gate tetap mati apa pun hasil probe ini.

## 2. Spesifikasi cross-check independen (§2.1b)

Sumber pembanding **ditetapkan SEBELUM probe** (bukan dipilih post-hoc) dan harus
independen dari pool pipeline (GeckoTerminal membaca pool YANG SAMA — bukan
pembanding sah):

- **Primer:** quote independen dari vendor LAIN untuk pair, arah, dan ukuran
  yang sama (SELL $10.000, NVDAc→USDC / AAPLc→USDC).
- **Fallback (bila hanya satu vendor merespons):** harga NAV-implied (NAV ×
  multiplier, dari OracleRegistry / API Coinbase — `nav_price` SUDAH
  multiplier-adjusted) + harga proxy Hyperliquid (`xyz:NVDA` / `xyz:AAPL`) —
  keduanya dilabeli **REFERENSI**, bukan harga eksekusi, dicatat dengan
  caveat-nya masing-masing.
- **Spesifikasi perbandingan (dicatat per sampel):** sumber pembanding,
  rute/pool, arah (SELL), ukuran ($10.000), waktu/block sebanding (quote dan
  pembanding dalam jendela evaluasi 300 detik yang sama; idealnya pada block
  yang sama yang di-pin `fetch_block`), fee (dinyatakan eksplisit apakah fee
  sudah termasuk di min-out, per dokumentasi vendor), dan rumus selisih:
  `|P_implied_execution − P_ref| / P_ref × 100 ≤ 1%`, dengan
  `P_implied_execution = min-out / amount_in` (harga terburuk yang
  dikomitmenkan vendor). Band ±10% validator adalah sanity check terpisah —
  BUKAN cross-check ini.
- **Empat kuantitas dipisah di setiap record probe:** `expected-out` (bruto,
  sebelum slippage/fee), `min-out` (sesudah toleransi slippage/fee — jumlah
  yang dikomitmenkan vendor sebagai lantai), `price impact` (expected-out vs
  spot), dan `slippage` (realisasi vs ekspektasi). Min-out sesudah slippage
  BUKAN objek yang identik dengan spot median — cross-check ≤1% membandingkan
  harga eksekusi yang dikomitmenkan (min-out) dengan referensi independen, dan
  harus dilabeli demikian.
- **Konsekuensi yang dicatat eksplisit di sini:** cross-check §2.1b
  membandingkan harga yang **dikomitmenkan** (min-out). Bila vendor tidak
  memberi min-out, `P_implied_execution` tidak ada dan cross-check komitmen
  **TIDAK DAPAT dihitung** — apa pun kedekatan harga indikatifnya. Perbandingan
  harga indikatif antar vendor/referensi dicatat terpisah dengan label
  **INDIKATIF SAJA** dan tidak dapat meloloskan sampel ke bar 10.

### 2.1 Angka "cross-check fallback berjalan" (nice-to-have #3 review Instinct ronde 2)

**Angka yang ditetapkan: fallback dinyatakan BERJALAN bila, dari seluruh sesi
sampling yang dijalankan sampai 30 Nov, ≥ 8 dari 10 sesi (≥80%) memiliki
KEDUA referensi tersedia (NAV-implied ok + proxy Hyperliquid ok, masing-masing
dengan nilai untuk kedua token), DAN tidak ada 2 sesi berturut-turut di mana
kedua referensi hilang bersamaan, DAN setiap sampel firm yang dihitung menuju
bar 10 memiliki ≥1 referensi yang tersedia pada saat sampel itu diambil.**

Alasan angka ini (terkait bar 10 sampel lolos + ≥2 hari):

1. **80% (8/10), bukan 100%:** referensi fallback adalah API publik tanpa SLA
   (Coinbase, Hyperliquid). Outage sesekali (1–2 sesi) adalah noise operasional
   yang wajar; menuntut 100% akan menggagalkan bar karena satu gangguan
   jaringan yang tidak ada hubungannya dengan kualitas jalur firm. 8/10
   menuntut ketersediaan **sistematis** — bila referensi mati lebih dari 2
   sesi dari 10, itu pola, bukan noise.
2. **Penyebut 10 sesi = penyebut bar 10 sampel:** tiap sampel firm butuh 1
   sesi cross-check. Ambang 8/10 berarti: dari 10 sampel yang dibutuhkan,
   paling banyak 2 boleh mengandalkan pembanding primer saja (vendor lain)
   tanpa fallback; sisanya harus punya fallback yang hidup. Bila fallback
   hanya hidup 5/10 sesi, separuh sampel tidak punya jaring pengaman kedua —
   bar T2(b) tidak terpenuhi secara substansi meski angka rata-rata terlihat
   "cukup".
3. **Larangan 2 sesi berturut-turut gagal total:** sampel harus tersebar
   ≥2 hari. Tanpa larangan ini, ambang 80% bisa lolos sambil menyembunyikan
   satu hari penuh yang buta (mis. 2 sesi gagal berurutan pada hari ke-2 =
   hari itu tidak menghasilkan satu pun sampel tervalidasi). Larangan ini
   memaksa ketersediaan merata lintas hari, bukan hanya rata-rata.
4. **Syarat per-sampel ≥1 referensi:** mencegah rata-rata menutupi sampel
   tanpa pembanding. Sampel yang diambil saat kedua referensi mati tidak
   dihitung menuju bar 10 — ia dicatat sebagai percobaan tanpa cross-check,
   bukan sebagai sampel lolos.

**Status 24 Nov (2 sesi): belum dapat dinyatakan BERJALAN.** NAV-implied ok
2/2 sesi; proxy Hyperliquid: fetch ok 2/2 sesi, tetapi nilai usable hanya
1/2 sesi (round 1 gagal ekstrak karena bug lookup skrip — lihat §5; diperbaiki
round 2). Dengan n=2, ambang 8/10 belum teruji; status yang jujur adalah
"berjalan sebagian, belum memenuhi ambang". Catatan: karena saat ini TIDAK ADA
kandidat firm, pertanyaan fallback ini untuk sementara moot terhadap T2(b) —
T2(b) butuh sumber cross-check yang sah **berjalan**, dan cross-check yang sah
butuh quote firm untuk dibandingkan. Fallback saja tidak dapat menghidupkan
T2(b) tanpa kandidat firm.

---

## 3. Metode probe

- **Skrip:** `probe_firm_quotes.py` (baru, hanya menambah file; tidak mengubah
  `pipeline.py`/`adapter.py`/`config.py`/`gate.py`/`run.py`/`decide()`).
- **Arah + ukuran:** SELL NVDAc→USDC dan AAPLc→USDC, notional $10.000
  (= `SIMULATION_NOTIONAL_USD`). `amount_in` dihitung dari median spot
  DexScreener saat probe (ceil ke base unit, 8 desimal) agar notional hitung
  ≥ $10.000: NVDAc ±60,16 token (spot ±$166,2), AAPLc ±28,62 token
  (spot ±$349,5). Notional hitung tercatat per sampel (±$10.000,00).
- **Toleransi slippage yang diminta (klien):** 0,5% seragam (Odos
  `slippageLimitPercent: 0.5`, Kyber `slippageTolerance: 50` bps). Ini
  parameter permintaan, BUKAN komitmen vendor. Lantai turunan klien
  (expected-out × 0,995) dicatat terpisah sebagai "client-derived floor (NOT
  vendor-committed)" — bukan `amount_out_min`.
- **Block pin:** `fetch_block` (RPC publik Base) per round — round 1 block
  61450790, round 2 block 61453051. Semua quote satu round dinilai dalam
  jendela evaluasi 300 detik yang sama.
- **Waktu probe vs sesi bursa:** probe jalan 08:35–08:44 WITA = 00:35–00:44 UTC
  = 19:35–19:44 EST Senin 23 Nov — **di luar regular session NYSE**
  (09:30–16:00 EST). NAV adalah harga Senin (lihat §5); quote DEX live 24/7.
- **Round 1** (timeout HTTP 30 dtk, tanpa retry) menghasilkan timeout untuk
  Odos/Uniswap dan 429 untuk Kyber-NVDAc — karena itu **round 2** dijalankan
  (timeout 60 dtk + 1 retry atas timeout/5xx) agar kegagalan transport
  dibedakan dari kegagalan skema vendor. Total: 12 sampel (2 round × 3 vendor
  × 2 token), 0 firm.
- **Yang TIDAK di-probe di sini:** 0x permit2/v2 + 1inch v6 — keduanya butuh
  API key; key sudah di-ACC Septian tapi BELUM diterima. Probe itu menyusul
  bila chief meneruskan key via env. Tanpa key, jalur itu mati (§2.2).
- **Lingkungan:** semua hasil diamati dari VM chief lewat egress proxy yang
  sama. Kegagalan transport (Odos 530, Kyber 429) adalah hasil dari
  lingkungan ini; kemungkinan penyebab egress-spesifik dicatat apa adanya di
  §4 — tetapi kesimpulan skema (tidak ada field firm) tidak bergantung pada
  transport, karena skema respons didokumentasikan vendor (lihat §4).

## 4. Hasil per kandidat

### 4.1 Odos API v2 (`POST https://api.odos.xyz/soroban/quote/v2`) — TIDAK FIRM

| | Round 1 | Round 2 |
|---|---|---|
| NVDAc $10k | Timeout 30 dtk (tanpa retry) | HTTP 530 ×2 (retry), body `error code: 1033` (Cloudflare), ~3,4–3,6 dtk |
| AAPLc $10k | Timeout 30 dtk (tanpa retry) | `RemoteDisconnected` ×2 (retry), ~3,4 + ~2,1 dtk |

**Tidak satu pun respons quote teramati** (9 percobaan total termasuk 3 cek
manual via curl, 0 respons JSON). Verdict TIDAK_FIRM dengan alasan
`no_parseable_response` — tetapi alasan ini **lebih lemah** daripada verdict
Kyber di bawah, dan harus dibaca dengan dua lapis:

1. **Lapis transport (yang teramati):** endpoint tidak terjangkau dari egress
   VM ini — Cloudflare error 1033 (Argo Tunnel) yang reproduksibel 3/3 kali
   via curl + 2/2 kali di round 2, dan koneksi diputus untuk AAPLc. Mungkin
   ini egress-spesifik; dari jaringan lain Odos bisa saja menjawab. Probe ini
   **tidak membuktikan** Odos tidak bisa memberi quote — ia membuktikan Odos
   tidak memberi quote **dari lingkungan ini**.
2. **Lapis skema (yang didokumentasikan vendor, independen dari transport):**
   struktur respons quote Odos v2 (`SingleQuoteResponse`, sumber SDK
   `odos-sdk`, merujuk docs.odos.xyz) berisi: `blockNumber`, `gasEstimate`,
   `gasEstimateValue`, `gweiPerGas`, `inAmounts`, `inTokens`, `inValues`,
   `netOutValue`, `outAmounts`, `outTokens`, `outValues`,
   `partnerFeePercent`, `pathId`, `pathViz`, `percentDiff`, `priceImpact`.
   **Tidak ada field expiry dan tidak ada field min-out.** `outputMin` hanya
   ada sebagai parameter yang dipasok CALLER saat eksekusi (`swapTokenInfo`
   di `OdosRouterV2`) — bukan field quote vendor. Jadi sekalipun Odos
   terjangkau, responsnya tidak mengandung dua dari tiga field wajib §2.1
   (`amount_out_min`, `expires_at`), dan tidak memberi label `kind`.
   **Kesimpulan gabungan: Odos TIDAK dapat memenuhi definisi FIRM proyek —
   bukan karena satu kegagalan transport, melainkan karena skema responsnya
   tidak mengenal min-out/expiry.**

- Fee: `outAmounts` = expected output; gas dilaporkan terpisah
  (`gasEstimate`/`gasEstimateValue`). Tidak ada pernyataan vendor bahwa
  `outAmounts` adalah minimum yang dijamin.
- Validator (pemetaan jujur — `kind: None`, tanpa min-out/expires_at):
  `invalid / exit_quote_kind_missing` untuk keempat sampel Odos.
  Pemetaan hipotetis "generous" tidak dapat diterapkan (tidak ada
  expected-out untuk dipetakan).
- Cross-check §2.1b: TIDAK DAPAT dihitung (tidak ada min-out → tidak ada
  `P_implied_execution`; tidak ada expected-out → tidak ada pula perbandingan
  indikatif).

### 4.2 KyberSwap Aggregator API (`GET https://aggregator-api.kyberswap.com/base/api/v1/routes`) — TIDAK FIRM

Satu-satunya kandidat yang memberi quote teramati. Respons sukses 3 dari 4
percobaan (NVDAc round 1 = HTTP 429 `Forbidden`, reproduksibel 2/2 kali via
curl; round 2 lolos 200).

| Sampel | HTTP | expected-out (USDC) | Harga indikatif | vs NAV-implied | vs proxy xyz | Rute |
|---|---|---|---|---|---|---|
| NVDAc R1 | 429 | — | — | — | — | — (rate-limit) |
| AAPLc R1 | 200 | $9.998,84 | $349,42 | 0,306% | n/a (bug lookup, §5) | aero-cl `0xF5FC…` langsung |
| NVDAc R2 | 200 | $9.996,66 | $166,13 | 0,155% | 0,057% | split 5 leg: aero-cl NVDAc→WETH, flux-prop, aero-cl `0xF668…` langsung, flux-prop + manta-prop WETH→USDC |
| AAPLc R2 | 200 | $9.998,96 | $349,43 | 0,303% | 0,048% | aero-cl `0xF5FC…` langsung |

- **Empat kuantitas (R2, per token):** expected-out = angka di atas
  (field `data.routeSummary.amountOut`); **min-out = TIDAK ADA** (tidak ada
  field min-out di `routeSummary`); price impact = TIDAK DIBERIKAN vendor
  (tidak ada field `priceImpact` di respons; selisih harga indikatif vs spot
  tercatat sebagai `slippage_pct` hitung klien: NVDAc −0,033%, AAPLc −0,010%);
  slippage = toleransi yang diminta 0,5% (parameter, bukan realisasi).
  Lantai turunan klien: NVDAc $9.946,67; AAPLc $9.948,96 — dicatat terpisah,
  BUKAN min-out vendor.
- **Skema vendor (didokumentasikan):** `routeSummary` (OpenAPI v2.13.0,
  docs.kyberswap.com, dibaca 24 Nov 00:33 UTC) field wajibnya: `tokenIn`,
  `amountIn`, `amountInUsd`, `tokenOut`, `amountOut`, `amountOutUsd`, `gas`,
  `gasPrice`, `gasUsd`, `l1FeeUsd`, `route`, `routeID`, `checksum`,
  `timestamp`. **Tidak ada field min-out, tidak ada field expiry.**
  `deadline` hanya ada di `POST /route/build` sebagai parameter **yang dipilih
  klien** (default +20 menit) — bukan jaminan expiry vendor atas quote
  `GET /routes`. Anjuran docs "jangan cache route >5–10 detik, refetch sebelum
  swap" adalah anjuran refetch, bukan semantik expiry field. `timestamp`
  routeSummary (R2: NVDAc 1795481021, AAPLc 1795481051) dicatat mentah sebagai
  `vendor_timestamp_raw` — BUKAN `quoted_at` firm.
- **Fee:** `amountOut` = expected output sesudah fee pool; gas dilaporkan
  terpisah (`gasUsd` NVDAc $0,035, AAPLc $0,006). Tidak ada fee yang
  "termasuk di min-out" karena tidak ada min-out.
- **Validator, pemetaan jujur** (`kind: None`): `invalid /
  exit_quote_kind_missing` (semua sampel Kyber). **Pemetaan hipotetis
  "generous"** (seandainya expected-out dipakai seolah min-out DAN kind
  diasumsikan `firm` — dicatat terpisah, BUKAN pemetaan sah): validator tetap
  `invalid / exit_quote_missing_fields: [expires_at]`. Ini demonstrasi yang
  menentukan: **bahkan di bawah pemetaan paling murah hati yang masih bisa
  ditulis, Kyber gagal — karena tidak ada expiry.**
- **Cross-check §2.1b:** TIDAK DAPAT dihitung — tidak ada min-out sehingga
  `P_implied_execution` tidak ada. Perbandingan **indikatif** (expected-price
  vs referensi) semuanya dalam ±1% (NAV 0,155–0,306%; proxy 0,048–0,057%) —
  tetapi ini perbandingan harga indikatif, BUKAN cross-check §2.1b, dan
  **tidak dapat meloloskan sampel ke bar 10**. Kedekatan harga indikatif
  menunjukkan likuiditas rute itu sehat; ia tidak menunjukkan adanya komitmen
  eksekusi.
- **Verdict: TIDAK FIRM.** Alasan: `kind` absent; `amount_out_min` absent
  (expected-out bukan min-out); `expires_at` absent (tidak ada field expiry
  dengan semantik vendor; kunci bertema expiry yang ditemukan: tidak ada).

### 4.3 Uniswap Routing API — TIDAK FIRM (jalur tanpa key mati di auth)

| | Round 1 | Round 2 |
|---|---|---|
| Trading API `POST https://trade-api.gateway.uniswap.org/v1/quote` (tanpa `x-api-key`) | Timeout 30 dtk | **HTTP 401** ×2 token: `{"errorCode":"Unauthorized","detail":"Unauthenticated api key or session"}` |
| Routing API lama `GET https://api.uniswap.org/v1/quote` (tanpa key) | (tercatat di evidence) | **HTTP 409** ×2 token: `{"errorCode":"ACCESS_DENIED"}` |

- **Definitif:** Trading API Uniswap saat ini WAJIB `x-api-key` (dokumen
  developers.uniswap.org: "All requests require an API key" + FAQ autentikasi;
  terkonfirmasi live 401). Endpoint lama juga menolak tanpa key (409
  ACCESS_DENIED). **Tidak ada respons quote yang dapat dinilai; tidak ada
  field firm yang dapat diperiksa.** Berbeda dengan Odos, ini bukan flake
  transport — ini penolakan auth yang didokumentasikan dan reproduksibel.
- Validator (pemetaan jujur): `invalid / exit_quote_kind_missing`.
- Cross-check §2.1b: TIDAK DAPAT dihitung.
- **Verdict: TIDAK FIRM** — kandidat ini membutuhkan registrasi + API key
  (di luar scope probe tanpa key ini; Septian hanya meng-ACC registrasi key
  0x + 1inch, bukan Uniswap — bila Uniswap mau di-probe ber-key, butuh
  keputusan/registrasi terpisah).

## 5. Uji ketersediaan referensi fallback — mitigasi R6

| Referensi | Round 1 | Round 2 |
|---|---|---|
| NAV-implied (Coinbase `nav_price`, sudah multiplier-adjusted) | ok, kedua token: NVDAc $166,39306128 (update 24 Nov 00:28:48Z, umur ±7 mnt saat probe); AAPLc $350,49029387 (update 23 Nov 19:31:58Z, umur ±5 jam — sesi Senin, pasar tutup saat probe) | ok, nilai sama (NAV tidak berubah antar round, ±9 menit) |
| Proxy Hyperliquid `xyz` (`xyz:NVDA` / `xyz:AAPL` markPx) | **Fetch ok, tetapi nilai tidak terekstrak — BUG SKRIP, bukan outage.** Skrip lookup `"NVDA"` padahal adapter mengunci instrumen dengan nama lengkap `"xyz:NVDA"`. Universe xyz lengkap terverifikasi sesudahnya via curl (148 instrumen, termasuk `xyz:NVDA`, `xyz:AAPL`). | ok, kedua token: NVDAc markPx $166,23 / oraclePx $166,23; AAPLc markPx $349,26 / oraclePx $349,35 |

- **Caveat NAV:** `nav_price` adalah harga saham × multiplier (sudah
  multiplier-adjusted — JANGAN dikali multiplier lagi, koreksi §3 pipeline).
  NAV AAPLc berumur ±5 jam saat probe (update terakhir Senin 19:31 UTC =
  14:31 EST, dalam sesi Senin; probe Senin 19:35 EST, sesudah tutup). Umur
  dicatat per sampel; NAV basi tetap REFERENSI yang sah untuk perbandingan
  indikatif, tetapi bukan harga segar — selisih indikatif vs NAV basi harus
  dibaca dengan caveat itu.
- **Caveat proxy:** `xyz:NVDA`/`xyz:AAPL` adalah **underlying equity perp
  proxy**, bukan harga token Base (brief §3, §6C). Funding/OI proxy tidak
  memicu alert token-exit. Sebagai REFERENSI harga, proxy ini berguna karena
  independen dari pool pipeline — tetapi ia mengukur underlying, bukan token.
- **Insiden adapter konkuren (dicatat jujur):** saat round 2 dijalankan,
  `adapter.py` di working tree yang sama sedang diedit agen S1 dan merujuk
  `config.HTTP_MAX_RETRIES` / `HTTP_REQUEST_BUDGET_PER_RUN` yang belum ada di
  `config.py` → `fetch_*` adapter melempar `AttributeError`. Skrip probe
  memakai fallback lokal (`probe-local`: urllib langsung ke endpoint yang
  sama dari `config`, bentuk respons sama) untuk fetch referensi round 2 —
  kecuali `fetch_block`, yang masih lewat adapter dan berhasil. Metode fetch
  per round tercatat di `references.fetch_method` dan `reference_rounds`.
  `pipeline.validate_exit_quote` tidak terdampak (pipeline import normal;
  diff S1 atas `pipeline.py` tidak menyentuh validator). Tidak ada file
  produksi yang diubah oleh tugas ini.

## 6. Keputusan (§2.5)

1. **Odos — TIDAK FIRM.** Tidak ada quote teramati dari lingkungan ini
   (transport gagal reproduksibel) DAN skema respons vendor tidak mengenal
   min-out/expiry. Bahkan bila transport pulih, Odos tidak dapat memenuhi
   definisi §2.1 tanpa perubahan skema dari vendor.
2. **KyberSwap — TIDAK FIRM.** Quote indikatif teramati dan sehat (harga
   indikatif dalam 0,31% dari NAV, 0,06% dari proxy), tetapi respons tidak
   mengandung `kind` firm, tidak mengandung `amount_out_min`, dan tidak
   mengandung `expires_at` dengan semantik vendor. Validator menolak bahkan
   di bawah pemetaan hipotetis paling murah hati (`missing_fields:
   [expires_at]`). Kedekatan harga indikatif ≠ komitmen eksekusi.
3. **Uniswap Routing API — TIDAK FIRM (tanpa key).** Membutuhkan API key;
   jalur tanpa key mati di auth (401 Trading API, 409 Routing API lama).
4. **Tidak ada produsen `adapter.fetch_firm_quote` yang ditulis, dan tidak
   ada tes gate untuk firm yang ditambahkan** — sesuai §2.4. Menulis produsen
   di atas salah satu kandidat di atas berarti mengemas expected-out indikatif
   sebagai `amount_out_min` dan mengarang `expires_at` dari jam lokal — dua
   hal yang dilarang eksplisit oleh §2.1b.
5. **Implikasi terhadap bar 26 Nov (T2):** bar (a) SATU jalur memenuhi
   definisi beku — **tidak terpenuhi** dari jalur tanpa key; bar (b) sumber
   cross-check yang sah berjalan — **tidak terpenuhi** (tidak ada quote firm
   untuk dibandingkan; fallback §2.1 hanya berjalan sebagian, §2.1); bar (c)
   rencana sampling yang bisa dijalankan — **ada, tetapi bergantung pada
   jalur ber-key** (lihat §7). Bila sampai review 26 Nov tidak ada jalur
   ber-key yang terbukti, keputusan §2.5 adalah **kunci paket ke (a2)** pada
   review early exit 26 Nov — brief harian saja, artefak proposal ditunda.
   Jangan menunggu 30 Nov, dan JANGAN "memperbaiki" definisi firm supaya ada
   yang lolos. Nol sampel pada 26 Nov belum membuktikan nol pada 30 Nov —
   bar ini adalah keputusan early-stop yang konservatif, bukan bukti
   matematis kegagalan.
6. **Definisi FIRM tidak diubah.** Hasil "tidak ada yang lolos" adalah hasil
   yang sah, bukan kegagalan probe. Simulasi on-chain (Dromos/Aero
   Metaquoter, QUOTER-RESEARCH.md) tetap `onchain_simulation` — bukan firm —
   dan tidak dipakai sebagai pengganti.

## 7. Rencana sampling bila jalur ber-key terbuka (untuk bar 10 sampel)

Rencana ini hanya dapat dijalankan bila 0x permit2/v2 dan/atau 1inch v6
terbukti memberi min-out + expiry setelah key diterima (probe menyusul,
di luar tugas ini):

- **Target:** 10 sampel firm yang lolos SEMUA syarat (§2.1 + cross-check
  §2.1b ≤1%), tersebar ≥2 hari berbeda, ≥1 token (ideal kedua token),
  sampai 30 Nov.
- **Jadwal yang bisa dijalankan:** 2 sesi/hari (pagi + malam WITA) × 2 token
  × 2 vendor ber-key = maksimal 8 sampel/hari; dengan 5 hari (26–30 Nov)
  tersedia, 10 sampel lolos membutuhkan tingkat kelolosan ≥25% dari
  percobaan — realistis bila salah satu vendor memang memberi field firm.
  Tiap sesi memakai skrip probe yang sama (round baru di-append ke evidence
  yang sama), dengan `expires_at` provenance + cross-check primer (vendor
  lain) + fallback (NAV/proxy) per sampel, dan ambang fallback §2.1
  (≥8/10 sesi, tanpa 2 sesi gagal total berurutan).
- **Bila probe ber-key juga menunjukkan tidak ada field firm** (mis. 0x
  `minBuyAmount` ternyata hanya batas revert, seperti didokumentasikan 0x
  sendiri — §2.1b), maka bar 26 Nov diputuskan gagal pada review 26 Nov dan
  paket dikunci ke (a2). Keputusan itu diambil dari bukti, bukan dari
  asumsi.

## 8. Probe ber-key 0x + 1inch (S2, 24 Nov 2026 ~09:10–09:15 WITA / 01:10–01:15 UTC)

**Key SUDAH terverifikasi jalan di Base hari ini oleh chief sebelum probe**
(helper read-only: 0x price 1 USDC→WETH HTTP 200 `liquidityAvailable: true`;
1inch quote 10 USDC→WETH HTTP 200 `dstAmount: 5839361162514238`). Key via
konektor terdaftar (`custom.0x` / `custom.1inch`, surrogate — tidak ada key di
repo/log/chat/evidence; grep `hsurr` di evidence = 0). Taker: wallet EVM
Septian `0x7164...b9f3` (quote read-only; tidak ada
signing/broadcast/dana bergerak). Slippage yang diminta: 0,5% seragam
(0x `slippageBps: 50`, 1inch `slippage: 0.5`). Block pin:
**61461903** (`0x9269ebf0…f6d80`, 01:12:30Z). Spot median DexScreener saat
probe: NVDAc **$168,27** (11 pool USDC), AAPLc **$349,81** (6 pool USDC).
`amount_in` = `ceil(10000 / median_spot × 10^8)`: NVDAc **59,42829976 token**
(5.942.829.976 base units), AAPLc **28,5869472 token** (2.858.694.720 base
units); notional hitung **$10.000,00** keduanya. Waktu probe di luar regular
session NYSE (Senin 23 Nov 19:10–19:15 EST); NAV AAPLc berumur ±5,7 jam (lihat
§8.3). **Hasil: 0 dari 8 sampel firm; 0 dari 2 vendor lolos.**

### 8.1 0x Swap API v2 — TIDAK FIRM: token diblokir vendor (422, kedua arah, semua endpoint, bukan ukuran)

| Panggilan | NVDAc | AAPLc |
|---|---|---|
| `price` allowance-holder | 422 | 422 |
| `quote` allowance-holder (taker + slippageBps 50) | 422 | 422 |
| `quote` permit2 (fallback) | 422 | 422 |

Semua 422 bernama **`SELL_TOKEN_NOT_AUTHORIZED_FOR_TRADE`** — *"The sell
token is not authorized for trade due to legal restrictions"* (zid tercatat
per respons di evidence). Karakterisasi round 2 membuktikan ini bukan soal
ukuran, arah, atau token spesifik:

- **Bukan ukuran:** price dengan sellAmount 0,01 token tetap 422, nama error
  yang sama.
- **Bukan hanya SELL:** arah BELI (USDC→token, $10rb) juga 422 —
  **`BUY_TOKEN_NOT_AUTHORIZED_FOR_TRADE`** — *"The buy token is not
  authorized for trade due to legal restrictions"*.
- **Bukan hanya NVDAc/AAPLc:** GOOGLc (token ketiga, `0xb200…2D0BA3164cc74f58B7`)
  SELL dan BUY juga 422 dengan nama error yang sama. Blokir berlaku umum
  untuk tokenized stock Coinbase di 0x.

**Konsekuensi:** TIDAK ADA satu pun respons quote 0x yang dapat dinilai —
tidak ada `buyAmount`, tidak ada `minBuyAmount`, tidak ada expiry, tidak ada
rute. Semantik `minBuyAmount` (batas revert vs jaminan fill, §2.1b) **TIDAK
DAPAT dikonfirmasi dari respons mentah**, karena tidak ada satu pun respons
sukses yang mengandung field itu; pernyataan docs 0x (§2.1b) tetap berdiri
sebagai dokumentasi vendor yang belum terkonfirmasi respons. Jalur 0x untuk
tokenized stock Base = **MATI di level vendor (legal restriction)**, bukan di
level key/kuota/routing — key-nya sendiri terbukti jalan (USDC→WETH 200).
Validator: tidak ada pemetaan jujur yang dapat dibangun (alasan `http_422` /
`no_parseable_response`).

### 8.2 1inch Swap API v6 — TIDAK FIRM: `/quote` indikatif saja; `/swap` tak dapat dibangun untuk taker ini

| Panggilan | NVDAc | AAPLc |
|---|---|---|
| `GET /swap/v6.0/8453/quote` | 200, `dstAmount: 9941235611` (= **$9.941,24**, implied **$167,28**) | 200, `dstAmount: 9967307179` (= **$9.967,31**, implied **$348,67**) |
| `GET /swap/v6.0/8453/swap` (from = taker Septian) | 400 `NOT_ENOUGH_BALANCE` (saldo taker 0 token) | 400 `NOT_ENOUGH_BALANCE` (saldo taker 0 token) |

- **`/quote`:** respons hanya berisi `dstAmount` — tidak ada min-out, tidak
  ada expiry, tidak ada label `kind`. Validator (pemetaan jujur): `invalid /
  exit_quote_kind_missing` (kedua token). Ini sesuai dokumentasi vendor:
  `/quote` bersifat indikatif.
- **`/swap` (taker Septian):** 1inch memvalidasi saldo `from` SEBELUM
  membangun tx — taker memegang 0 NVDAc/AAPLc, jadi tidak ada tx yang
  dikembalikan untuk taker ini.
- **Schema probe round 2** (`from` = alamat pool Aerodrome pemegang token,
  parameter read-only untuk mengungkap skema respons — BUKAN quote untuk
  wallet Septian, TIDAK dihitung sebagai sampel firm): lolos cek saldo, lalu
  400 **`NOT_ENOUGH_ALLOWANCE`** (pool tidak pernah approve router 1inch
  `0x111111125421ca6dc452d289314280a0f8842a65`). Jadi skema `/swap` untuk pair
  ini tidak dapat diobservasi lewat respons sukses dari jalur mana pun; yang
  teramati adalah `/swap` memvalidasi saldo + allowance dulu. Catatan skema
  dari dokumentasi vendor: respons `/swap` berisi `dstAmount` + `tx` +
  `protocols` — **tidak ada field min-out/expiry top-level**; minimum
  eksekusi hanya terkode di dalam calldata router (`minReturnAmount`), bukan
  sebagai field respons. Itu BUKAN `amount_out_min` vendor dalam arti §2.1
  (tidak ada expiry yang menyertainya; dan untuk pair ini calldata itu
  sendiri tidak pernah terbit).
- **Cross-check §2.1b:** KOMITMEN **tidak dapat dihitung** (tidak ada min-out
  → tidak ada `P_implied_execution`). Perbandingan **INDIKATIF**
  (expected-price 1inch vs referensi): vs NAV NVDAc **0,537%**, AAPLc
  **0,520%**; vs proxy xyz NVDAc **0,517%**, AAPLc **0,290%** — semuanya dalam
  ±1%, tetapi ini harga indikatif, BUKAN cross-check §2.1b, dan **tidak dapat
  meloloskan sampel ke bar 10**. Cross-check primer 0x vs 1inch tidak dapat
  dihitung: 0x tidak memberi harga apa pun (422).

### 8.3 Referensi fallback sesi ini (sesi sampling ke-3)

NAV-implied ok 2/2: NVDAc **$168,18363844** (update 24 Nov 01:08:20Z, umur
±4 mnt saat probe); AAPLc **$350,49029387** (update 23 Nov 19:31:58Z, umur
±5,7 jam — sesi Senin, pasar tutup saat probe; NAV basi tetap REFERENSI sah
dengan caveat itu). Proxy Hyperliquid xyz ok 2/2: NVDAc markPx **$168,15**,
AAPLc **$349,68**. Kumulatif sesi sampling sampai kini: **3 sesi** (2 tanpa
key + 1 ber-key): NAV ok 3/3, proxy usable 2/3 (round 1 tanpa key gagal
ekstrak karena bug skrip, bukan outage). Ambang §2.1 (≥8/10 sesi, tanpa 2
sesi gagal total berurutan) **belum teruji (n=3)** — status "berjalan sebagian,
belum memenuhi ambang". Moot terhadap T2(b) untuk sementara: tanpa kandidat
firm, tidak ada cross-check yang sah untuk dihidupkan.

### 8.4 Keputusan (§2.5) — diperbarui atas probe ber-key

1. **0x — TIDAK FIRM, dan lebih kuat dari "tidak ada field":** vendor
   MENOLAK token ini (legal restriction), kedua arah, semua endpoint, semua
   ukuran yang diuji, tiga token. Jalur 0x untuk tokenized stock Base
   tertutup sampai 0x mengubah kebijakan — bukan sesuatu yang bisa diperbaiki
   dari sisi kita.
2. **1inch — TIDAK FIRM.** `/quote` indikatif sehat (dalam 0,54% dari NAV)
   tetapi tanpa min-out/expiry/kind; `/swap` tidak dapat dibangun untuk
   taker tanpa saldo + allowance (dan skema `/swap`-nya sendiri tidak
   mengenal field min-out/expiry).
3. **Tidak ada produsen `adapter.fetch_firm_quote` yang ditulis**, dan tidak
   ada tes gate untuk firm yang ditambahkan — sesuai §2.4.
4. **Implikasi terhadap bar 26 Nov (T2):** bar (a) SATU jalur memenuhi
   definisi beku — **tidak terpenuhi** dari jalur ber-key; bar (b) sumber
   cross-check yang sah berjalan — **tidak terpenuhi** (tidak ada quote firm
   untuk dibandingkan; primer 0x vs 1inch mati di sisi 0x); bar (c) rencana
   sampling yang bisa dijalankan — **ada, tetapi tidak ada jalur yang dapat
   di-sample**. Bila tidak ada jalur baru, keputusan §2.5 adalah **kunci
   paket ke (a2)** pada review early exit 26 Nov. Satu-satunya pintu yang
   belum diuji ber-key adalah Uniswap Trading API (butuh `x-api-key`,
   registrasi terpisah yang belum di-ACC Septian) — dan skema responsnya
   menurut dokumentasi juga tidak mengenal expiry; peluangnya kecil, tetapi
   itu satu-satunya jalur tersisa bila Septian mau dicoba.
5. **Definisi FIRM tidak diubah.** Hasil "tidak ada yang lolos" adalah hasil
   yang sah, bukan kegagalan probe.

## Lampiran — bukti yang dapat diverifikasi ulang

- `evidence/firm_quote_probes_2026-11-24.json` — respons mentah tiap
  kandidat (12 sampel), penilaian per field, empat kuantitas terpisah,
  provenance `expires_at` (absent di semua sampel), hasil cross-check
  (komitmen: tidak dapat dihitung; indikatif: lengkap dengan rumus + selisih),
  hasil validator (`validate_exit_quote`, pemetaan jujur + hipotetis),
  referensi fallback per round, block pin per round, dan catatan transport
  manual (curl: Odos 530 ×3, Uniswap 401, Kyber-NVDAc 429 ×2).
- `probe_firm_quotes.py` — skrip probe (dapat dijalankan ulang;
  `--append-round` menambah round baru tanpa menghapus round lama).
- Pemeriksaan independen yang dapat diulang tanpa key: `curl` Kyber
  `GET /base/api/v1/routes` (mengembalikan `routeSummary` tanpa min-out /
  expiry); `curl` Uniswap Trading API tanpa key (401); dokumentasi vendor —
  Kyber OpenAPI v2.13.0 (`routeSummary`), Odos `SingleQuoteResponse`
  (docs.rs/odos-sdk), Uniswap FAQ autentikasi (developers.uniswap.org).
