# Design note — Prototipe kecil Base Stocks Maxxing

Versi: `base-proto-schema v0.1.0` / `base-proto-method v0.1.0` /
`base-proto-policy v0.1.0`. Semua versi adalah **eksperimen, belum
tervalidasi**. Sumber otoritatif: brief Instinct
(`../brief-instinct-muse.md`). Bila bertentangan dengan laporan validasi awal
(`../validasi-base-instinct.md`), koreksi §3 brief Instinct yang berlaku.

## 1. Flow

```
ingest (adapter.py)
  -> build_snapshot (pipeline.py): validasi identitas + normalisasi
  -> assess_snapshot: tiga lapis (§6) -> reason codes + coverage
  -> decide: ABSTAIN / WATCH / PAPER_PROPOSAL
  -> explain: rangkum alasan + sumber (tanpa menciptakan harga/alasan baru)
  -> emit_alert: payload lokal, ID deterministik, dedup
  -> paper record: usulan + snapshot yang mendasarinya
```

Hanya NVDAc + AAPLc. Ingest memakai snapshot live (Coinbase + DexScreener +
GeckoTerminal + Hyperliquid) atau replay fixture tersimpan (mode TEST/REPLAY).
Semua output ke `out/` (lokal). Tidak ada yang menyentuh Radar produksi.

## 2. Data mapping (kontrak §5 brief)

| Field | Sumber | Catatan |
|---|---|---|
| `asset` (chain, token_address, symbol, decimals) | `config.TOKENS` (kunci lookup) | Kunci identitas: chain + contract, bukan ticker saja. Nilai ini fakta identitas, bukan data pasar. |
| `reference.nav_price` | Coinbase API `nav_price` | **Sudah multiplier-adjusted / total-return. Jangan dikali multiplier lagi.** Ditampilkan apa adanya + `nav_price_updated_at`, `age_seconds`, `session_status`. |
| `reference.session_status` | Ditentukan dari umur NAV + hari | `off_hours` saat weekend/libur (NAV menahan nilai terakhir, by-design). Bukan tebakan weekday semata. |
| `reference.registry_pause_status` | — | **`unknown`.** Registry pause (`0x3f3E…CaD`) tidak dibaca di prototipe ini (butuh RPC read-only; di luar scope adapter HTTP). Ketiadaan field bukan bukti semua fungsi aktif. |
| `multiplier.value` | Coinbase API `multiplier` | Disimpan sebagai observasi. **Tidak dipakai mengalikan nav_price.** Dipakai hanya bila mengonversi harga saham underlying mentah, dan rekonstruksi histori memakai multiplier yang efektif saat itu, bukan multiplier hari ini. |
| `pools[]` | DexScreener (primer) + GeckoTerminal (cross-check pool) | `pool_address, dex, quote_asset, indicative_price_usd, liquidity_usd, source_updated_at?, fetched_at, source`. **Dedup:** dua agregator yang membaca pool sama = **satu** pool, bukan dua venue. |
| `coverage` | Dihitung dari pools yang lolos filter | `independent_pool_count`, `independent_venue_count`, `missing_fields[]`, `rejected_observations[]`. Bila hanya 1 pool valid → `insufficient_cross_venue_coverage`, bukan deviasi nol. |
| `exit_quote` | — | **`None`.** Tidak ada sell-quote adapter di prototipe ini. Status selalu `indicative_only/exit_quality_unverified` (§6B). TVL tidak boleh menggantikannya. |
| `underlying_proxy` | Hyperliquid `metaAndAssetCtxs` | Baseline dex `xyz`: `xyz:NVDA` / `xyz:AAPL`. Varian `io:` **tidak diagregasi** (tanpa metodologi eksplisit). Funding/OI dilabeli `UNDERLYING EQUITY PERP PROXY` — proxy sentimen underlying, **bukan** ukuran exit-risk token Base. `oi_change_24h` = `null` sebelum baseline cukup (`insufficient_history`, bukan 0%). |
| `assessment` | `assess_snapshot` | Tiga lapis (§6): status + `reason_codes[]` + `confidence_basis`. Bukan angka 0-100. |
| `proposal` | `decide` | `weights`, `cash_weight`, `simulation_notional`, `expiry`. Batas bobot/nominal adalah parameter policy eksperimen, bukan preferensi investasi Alex. |
| `alert` | `emit_alert` | `alert_id` (deterministik), `mode` (`live` / `TEST/REPLAY`), `rule_version`, `reasons`, `emitted_at`. Dedup via `alerts_seen.json`. |

Ketentuan penting yang diterapkan:
- `fetched_at` ≠ waktu transaksi terakhir / update harga sumber / update NAV.
  Bila sumber tidak memberi timestamp harga, tulis `unknown`.
- OI raw dan USD notional bukan unit yang sama. Unit dinyatakan dari schema
  sumber. Funding bukan OI change.
- PoR: tidak ada sumber otomatis. Hanya catatan manual/kualitatif dengan
  sumber + tanggal, atau `unknown`. Supply saja bukan bukti reserve.
- Redemption: desain mengasumsikan **tidak ada jalur permissionless retail**.
  Jangan turunkan status dari jam bursa atau ketiadaan `paused_features`.

## 3. Policy / rule version

`base-proto-policy v0.1.0` (eksperimen, belum tervalidasi). Keputusan:
`ABSTAIN` / `WATCH` / `PAPER_PROPOSAL`.

- **ABSTAIN** bila: token tidak terkonfirmasi, referensi tidak valid,
  coverage lintas-venue tidak cukup, atau deviasi ekstrem
  (`|deviasi vs median| > 5%`). Kondisi tanpa bukti exit tidak boleh
  menghasilkan usulan beli.
- **WATCH** bila: ada reason code non-blocking (mis. tidak ada sell quote,
  NAV basi off-hours, deviasi watch `> 2%`). Menahan seluruh alokasi di cash
  simulasi adalah hasil yang sah.
- **PAPER_PROPOSAL** hanya bila: tidak ada blocking code **dan** ada bukti
  exit (sell quote). Karena prototipe ini tidak punya sell-quote adapter,
  **PAPER_PROPOSAL tidak pernah keluar** — keputusan maks WATCH. Ini by-design
  dan jujur, bukan bug.

## 4. Threshold eksperimen (belum tervalidasi)

| Parameter | Nilai | Makna |
|---|---|---|
| `DEV_WATCH_PCT` | 2,0% | `|deviasi vs median| > 2%` → WATCH |
| `DEV_ABSTAIN_PCT` | 5,0% | `|deviasi vs median| > 5%` → ABSTAIN |
| `MIN_INDEPENDENT_POOLS` | 2 | Butuh ≥ 2 pool independen untuk confidence lintas-venue |
| `NAV_STALE_HOURS` | 24 jam | Umur NAV > 24 jam = referensi basi (informasional) |
| `MAX_FUTURE_SKEW_SEC` | 300 dtk | Toleransi jam sumber maju (clock skew) |
| `MAX_POOL_AGE_MIN` | 60 mnt | Observasi pool lebih tua dari ini = basi (informasional) |
| `SIMULATION_NOTIONAL_USD` | $10.000 | Nominal simulasi paper portfolio |
| `MAX_WEIGHT_PER_ASSET` | 0,50 | Bobot maks per aset (eksperimen) |
| `HORIZON_DAYS` / `EXPIRY_DAYS` | 7 / 7 | Horizon + expiry proposal |

**Bukan warisan Solana.** Bobot / aturan minimum 3-dari-5 / threshold 70 Solana
tidak dipakai. Threshold di atas adalah tebakan awal yang versioned dan jelas
berlabel belum tervalidasi — bukan kalibrasi.

**Tradeoff false-positive / false-negative (belum terukur):**
- `DEV_WATCH_PCT` rendah (2%) → WATCH lebih sering (FP "watch" lebih tinggi,
  tapi aman: WATCH tidak menghasilkan usulan beli).
- `DEV_ABSTAIN_PCT` tinggi (5%) → ABSTAIN hanya pada deviasi ekstrem (FN
  lebih tinggi bila deviasi moderat ternyata bermasalah — tapi tanpa sell
  quote, keputusan sudah maks WATCH, jadi risikonya terbatas).
- Tanpa data historis, tradeoff ini **tidak bisa dikalibrasi** di jendela
  prototipe. Kalibrasi butuh seri historis + definisi outcome — pekerjaan
  riset terpisah, bukan bagian gate ini.

## 5. Coverage

- **Token:** 2 (NVDAc, AAPLc). Keduanya teridentifikasi via Coinbase API
  (tanpa key) dan terkonfirmasi punya pool nyata (Aerodrome Slipstream).
- **Venue:** efektif 1 pool dominan per token (Aerodrome). DexScreener +
  GeckoTerminal membaca pool yang sama → dihitung **satu** pool, bukan dua
  venue. `MIN_INDEPENDENT_POOLS = 2` terpenuhi secara hitungan (pool lain
  kecil), tapi median dari 2 observasi rapuh — dicatat sebagai
  `median_fragile_two_observations` bila hanya 2.
- **Underlying proxy:** `xyz:NVDA` / `xyz:AAPL` (Hyperliquid, dex `xyz`).
  Varian `io:` ada tapi tidak diagregasi. Proxy tidak memicu alert token-exit
  dan tidak memperbaiki coverage data token yang hilang.
- **Yang tidak ter-cover:** sell quote (tidak ada adapter), registry pause
  (tidak dibaca), PoR otomatis (tidak ada sumber), redemption retail (tidak
  ada jalur terverifikasi), histori OI (belum ada baseline lokal).

## 6. Exit Score Base: redesign, bukan port

Prioritas: reason codes + coverage, bukan angka komposit 0-100.

- **Lapisan A (kondisi DEX token):** deviasi vs median hanya dari observasi
  independen yang lolos filter, dalam unit sebanding dan jendela waktu yang
  dinyatakan. Per-venue deviation disimpan agar agregat tidak menyembunyikan
  outlier. Bila hanya 1 venue/pool valid → `insufficient_cross_venue_coverage`.
- **Lapisan B (bukti exit):** tanpa sell quote → status
  `indicative_only/exit_quality_unverified`. TVL/likuiditas bukan bukti exit.
  Adapter quote yang belum terbukti bekerja dilaporkan sebagai gap, bukan
  dependensi yang dianggap selesai.
- **Lapisan C (konteks underlying):** funding + OI tampil terpisah sebagai
  `UNDERLYING EQUITY PERP PROXY`. Sinyal proxy tidak boleh sendirian memicu
  alert token-exit.
- Komponen redemption 20 poin (Solana) **dihilangkan** — tidak ada sumber
  data. Tidak sekadar renormalisasi 80 poin dan menyebutnya setara Solana.
  Ketiadaan redemption / PoR / histori ditampilkan sebagai
  `unknown/not_applicable` + coverage eksplisit, bukan skor nol.

## 7. Asumsi yang belum terbukti

1. Pool Aerodrome adalah venue utama yang cukup mewakili harga token (belum
   ada sensus venue lengkap; pool lain kecil / belum terverifikasi).
2. Threshold 2% / 5% adalah tebakan awal — belum ada data FP/FN.
3. `xyz:NVDA` / `xyz:AAPL` adalah proxy underlying yang relevan (belum ada
   validasi korelasi proxy vs kondisi token).
4. NAV yang basi di weekend adalah referensi yang aman dipakai sebagai
   pembanding berlabel (bukan harga live) — ini mengikuti §3 brief, bukan
   bukti empiris baru.
5. Tidak ada asumsi tentang rubrik kompetisi (bobot traction 50/25/25 tidak
   dianggap rules resmi) atau nilai paper-portfolio/testnet.

## 8. Desain onchain (sesudah gerbang, belum dijalankan)

Kandidat minimum (spesifikasi saja): Base Sepolia hash registry untuk komitmen
snapshot + keputusan paper portfolio + versi metodologi. Tujuan: membuktikan
catatan sudah ada sebelum evaluasi hasil — bukan membuktikan data benar,
return, compliance, atau traction.

Spesifikasi yang disiapkan:
- **Canonical serialization:** JSON kanonis dari snapshot publik
  (`public_snapshot`, key terurut, tanpa field internal `_`), + `decision` +
  `methodology_version` + `policy_version`.
- **Hash algorithm:** SHA-256 dari serialisasi kanonis (sama seperti
  `snapshot_id` yang sudah dipakai di prototipe: `snap-<sha256[:16]>`).
- **Schema/methodology version:** `base-proto-schema v0.1.0` /
  `base-proto-method v0.1.0` / `base-proto-policy v0.1.0` (naik versi bila
  berubah; hash mengikat versi itu).
- **Timestamp observasi:** `fetched_at` (UTC) + `snapshot_id` dari snapshot.
- **Expiry:** proposal paper punya `expiry` (7 hari, `EXPIRY_DAYS`); hash
  tidak berlaku sesudah expiry proposal.
- **Prosedur verifikasi:** ambil payload lengkap (snapshot + decision) →
  serialisasi kanonis → SHA-256 → bandingkan dengan hash yang tercatat di
  registry. Payload lengkap harus tetap tersedia untuk pihak yang berhak
  memverifikasi; **hash tanpa payload tidak cukup untuk audit.**
- Jangan taruh identitas atau isi portfolio privat onchain. Hash bukan
  jaminan anonimitas — jangan hash data sensitif tanpa desain privasi.

Deploy, transaksi, akses wallet, publikasi payload, dan receipt pengguna
menunggu gerbang + ACC eksplisit Alex. Kelayakan akhir integrasi untuk
kompetisi tetap keputusan panitia; registry bukan jalan pintas untuk menjamin
eligibility atau traction.

## 9. Perbaikan saat verifikasi (chief, 22 Nov 2026)

Bug: `assess_snapshot` membaca `snap["_token_ok"]` langsung. Field internal
`_token_ok` hanya ada di snapshot internal; `public_snapshot` (yang disimpan
dan di-replay) men-strip semua field `_`, sehingga replay snapshot publik
gagal `KeyError: '_token_ok'` (gate 1/9). Perbaikan di `pipeline.py`:
`token_ok` kini diturunkan ulang dari identitas aset (contract cocok dengan
`config.TOKENS`) + tidak ada penolakan `contract_address`/`symbol` di
`coverage.rejected_observations` bila field internal absen. Gate sesudah
perbaikan: **9/9 PASS**. Perilaku live tidak berubah (snapshot internal tetap
memakai `_token_ok` asli).

## 10. Deteksi partial-fill yang jujur (v0.3.2, re-audit v6, 22 Nov 2026; diperketat v0.3.3, re-audit v7)

**Klaim v0.3.1 yang SALAH:** guard batas sqrt-price MIN/MAX disebut
"deteksi partial-fill". Yang benar (temuan F1 re-audit v6): guard batas
HANYA menangkap terminal sqrt-price TEPAT di batas. Signature partial-fill
standar — terminal MIN+1/MAX−1 (quoter memakai itu sebagai limit saat
`sqrtPriceLimitX96=0`) — TIDAK tertangkap. Probe empiris auditor
(amount_in 10^18 wei, jauh di atas kapasitas) mengembalikan partial fill
nyata dengan sqrtAfter 1,7359e38 yang BUKAN di batas dan tidak konsisten
dengan ticks_crossed (115). Yang menangkap saat itu hanya sanity
implied-price ±10% di validator.

**Deteksi yang benar (v0.3.2), tiga lapis:**
1. **Double-quote probe (utama):** sesudah quote pertama berhasil, ambil
   quote kedua dengan amount_in x 2 di pool yang sama (block sama). Bila
   output probe / output pertama < 1,5, quote pertama sudah di kapasitas
   pool (partial fill) → pool ditolak sebagai bukti exit. Rasio sehat
   ~1,9–2,0 (live run v0.3.3: NVDAc 1,99991884, AAPLc 1,99983284).
   **M2 (v0.3.3): probe WAJIB sukses** (`REQUIRE_PROBE_SUCCESS=True`) —
   probe yang gagal RPC membuat quote TIDAK usable, pool ditolak
   (`quoter_probe_failed:<pool>`), bukan dipakai inconclusive. (Perilaku
   v0.3.2: probe gagal = inconclusive, quote tetap dipakai — diubah atas
   temuan M2 re-audit v7: pool tipis + kegagalan probe transien tidak
   boleh lolos hanya dengan sanity ±10%.) Helper `_probe_quote_usable`:
   usable bila tidak capped DAN probe_ok. Hasil probe tercatat transparan
   di snapshot (`exit_quote.partial_fill_probe` + transcript
   `quote_probe`).
   Ambang 1,5 konservatif: pool yang hanya punya 1,2x likuiditas dari
   notional pun ikut tertandai (thin pool = bukti exit lemah).
2. **Sanity implied-price ±10% di validator** (sudah ada sejak v0.2.1):
   harga implisit quote harus dalam ±10% median DEX. Partial fill berat
   (implied jauh dari median) tertangkap di sini — seperti probe auditor
   (implied $0,000042 vs median $133).
3. **Guard batas sqrt MIN/MAX (sekunder):** terminal sqrt-price TEPAT di
   batas → error `quote_possible_partial_fill`. Bukan deteksi utama.
   Konstanta MAX_SQRT_RATIO v0.3.1 SALAH (1e9x terlalu kecil); v0.3.2
   memakai floor eksak RUMUS sqrt(1.0001^887272)·2^96
   `1461446703485210103244672773810124308346321380902`. **M1 (v0.3.3):
   nilai itu ternyata floor rumus, BUKAN konstanta kontrak** — v0.3.3
   memakai KONSTANTA KONTRAK TickMath.sol
   `1461446703485210103287273052203988822378723970342` (diverifikasi ke
   Uniswap v3-core GitHub, L28; beda ~2,9e-8 relatif, arah konservatif).
   MIN_SQRT_RATIO 4295128739 cocok TickMath (L24) dan tidak berubah.

**M3 (v0.3.3):** `factory` kini disimpan di `exit_quote` snapshot
(dari sell_quote) — transparansi: venue + factory keduanya terlihat di
snapshot, bukan hanya venue.

**Residual yang diakui:** partial fill RINGAN (implied masih dalam ±10%
median, probe ratio di atas 1,5 tapi di bawah ~1,9) masih bisa lolos
sebagai `simulated_verified`. Selama gate proposal MATI, ini tidak
berbahaya (keputusan maks WATCH). Sebelum gate nyala, residual ini
perlu ditutup (mis. perketat ambang probe atau tambah lapis deteksi).

**Validator cap max_age (F2, v0.3.2):** validator TIDAK LAGI percaya
`max_age_sec` milik quote. Untuk firm, `expires_at` adalah komitmen
vendor; untuk simulasi, max_age adalah klaim diri sendiri. Yang dipakai:
`max_age_efektif = min(quote.max_age_sec, QUOTE_VALIDITY_SEC)` (300 dtk).
Simulasi dengan max_age raksasa + observed_at 5 jam lalu kini STALE
(direpro auditor di v0.3.1 sebagai lolos).

**Batasan metodologi (F4):** pool Uniswap V4 tidak masuk coverage —
pairAddress V4 adalah poolId 32-byte, bukan alamat kontrak, sehingga
ter-reject `invalid_address` (terlihat di `rejected_observations`). ~11
pool NVDAc di evidence (termasuk ~$130rb likuiditas) adalah V4. Bukan
bug — batasan yang didokumentasikan.
