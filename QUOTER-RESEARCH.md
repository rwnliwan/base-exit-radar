# Riset kelayakan fase quoter — Base Stocks Maxxing

Tanggal: 22 November 2026 (WITA). Penulis: chief (riset read-only).
Status: **BUKAN STOP.** Ada jalur sell-quote read-only yang TERBUKTI jalan
dengan call nyata (bukan klaim). Jalur yang direkomendasikan di bawah.
File ini riset saja — TIDAK ada kode adapter yang ditulis, TIDAK ada
perubahan config/pipeline/gate.

## Verdict (satu baris)

**Quoter FEASIBLE read-only.** Jalur utama: **Dromos Metaquoter
`quoteExactInputSingleV3`** — satu `eth_call` ke RPC publik (tanpa key,
tanpa wallet, tanpa signing, tanpa gas) memberi quote jual NVDAc/AAPLc ->
USDC di venue TERDALAM, termasuk notional penuh $10.000 (slippage <0,2%).
Fallback terverifikasi: Uniswap V3 QuoterV2 (terbatas depth). Registry pause
Coinbase TERBACA read-only (`getOracleParams`) dan saat ini **tidak paused**
untuk kedua token. STOP CONDITION Septian tidak terpicu.

## Temuan kunci #1 — venue utama sebenarnya Dromos, bukan Aerodrome

DexScreener dan config prototipe menyebut pool NVDAc/USDC `0xF668...` dan
AAPLc/USDC `0xF5FC...` sebagai "Aerodrome Slipstream" (`dexId: aero`).
**On-chain, pool itu dibuat oleh factory Dromos, bukan Aerodrome.**

Bukti (semua via `eth_call` ke RPC publik `https://mainnet.base.org`):

| Cek | Hasil |
|---|---|
| `factory()` pool NVDAc/USDC `0xF668...` | `0x9cb220581b91b0c83223012fe69688b92ad07a76` |
| `factory()` pool AAPLc/USDC `0xF5FC...` | `0x9cb220581b91b0c83223012fe69688b92ad07a76` (sama) |
| BaseScan `0x9cb2...` | **"Dromos: CL Factory"**, kontrak `CLFactory` terverifikasi |
| `getPool(NVDAc, USDC, tickSpacing=10)` di factory Dromos | `0xF668...` (COCOK) |
| `getPool(AAPLc, USDC, tickSpacing=10)` di factory Dromos | `0xF5FC...` (COCOK) |
| `getPool(NVDAc, USDC, 10)` di Aerodrome CLFactory `0x5e7B...` | `0x0000...0000` (TIDAK ADA) |

Konteks: Dromos Labs adalah perusahaan dev di balik Aerodrome/Velodrome;
pada Nov 2025 mereka meluncurkan arsitektur MetaDEX ("Aero") dan deployment
Slipstream generasi baru di bawah nama Dromos. Repo publik
`dromos-labs/metadex-slipstream-public`, file
`deployment-addresses/cl-base.json`, mencantumkan
`clFactory = 0x9CB220581b91b0C83223012FE69688b92aD07a76` — cocok persis
dengan yang dibaca dari pool. Jadi label "aero" di DexScreener adalah
label keluarga (fork), bukan factory yang sebenarnya. **Implikasi: quoter
Aerodrome TIDAK BISA dipakai untuk pool ini** (lihat kandidat 3).

State pool Dromos (dibaca langsung, 22 Nov 2026 ~14:06–14:13 UTC):

| Pool | tickSpacing | fee() | token0 | token1 | liquidity | sqrtPriceX96 | tick |
|---|---|---|---|---|---|---|---|
| NVDAc/USDC `0xF668...` | 10 | 218 | USDC | NVDAc | `0x2b36a87d114c` | `68716643105003637282855827422` | -2847 |
| AAPLc/USDC `0xF5FC...` | 10 | 218 | USDC | AAPLc | — | `42357107110638028854583139713` | -12525 |

(Likuiditas DexScreener saat itu: NVDAc/USDC ~$1,56 juta; AAPLc/USDC
~$423 ribu. `slot0()` Slipstream mengembalikan 6 word, bukan 7 seperti
UniV3 standar — tidak ada word `unlocked`.)

## Kandidat sell-quote — verdict per kandidat

### 1. Dromos Metaquoter `quoteExactInputSingleV3` — DIREKOMENDASIKAN ✅

- **Alamat:** `0x1dDfeC5058180C207F55BB77D95AcDd0d8227868`
- **Sumber alamat:** file deployment resmi Dromos
  (`dromos-labs/metadex-slipstream-public`,
  `deployment-addresses/cl-base.json`, field `metaquoter`) +
  BaseScan melabeli **"Dromos: Metaquoter"**, nama kontrak `Metaquoter`,
  source terverifikasi.
- **Cara pakai (read-only):** satu `eth_call` ke
  `quoteExactInputSingleV3(address pool, address tokenIn, uint256 amountIn,
  uint160 sqrtPriceLimitX96)` (selector `0x0a674142`).
  Menerima **alamat pool langsung** — tidak perlu lookup factory, tidak
  perlu tahu fee/tickSpacing. Mengembalikan `(amountOut,
  sqrtPriceX96After, initializedTicksCrossed)` lewat pola
  revert-with-result (RPC publik mengembalikan data revert-nya — terbukti
  di bawah). `sqrtPriceLimitX96 = 0` = tanpa batas harga.
- **Bukti — quote NYATA, 22 Nov 2026 ~14:13 UTC** (RPC publik
  `mainnet.base.org`, `eth_call`, tanpa key/wallet/signing):

| Jual | amountOut (USDC) | Harga implisit | vs spot DexScreener | ticks |
|---|---|---|---|---|
| NVDAc 1 token | $133,04 | $133,04 | +0,20% (spot $132,77) | 1 |
| NVDAc 10 token | $1.330,39 | $133,04 | +0,20% | 1 |
| **NVDAc 75 token (~$10.000)** | **$9.977,09** | **$133,03** | **+0,19%** | 1 |
| AAPLc 1 token | $349,77 | $349,77 | -0,02% (spot $349,86) | 1 |
| AAPLc 10 token | $3.497,67 | $349,77 | -0,03% | 1 |
| **AAPLc 28 token (~$10.000)** | **$9.793,12** | **$349,75** | **-0,03%** | 1 |

  Notional penuh $10.000 (notional simulasi prototipe) lolos di KEDUA
  token dengan slippage <0,2% — jauh di dalam toleransi sanity validator
  (±10% dari median). Ini venue terdalam ($1,56 jt / $423 rb), jadi
  hasilnya konsisten di semua ukuran.
- **Catatan:** fungsi saudaranya `quoteExactInputSingleV2(pool, tokenIn,
  amountIn)` (selector `0x3c5ba2b9`, `view`) HANYA untuk pool V2
  (constant-product) — dipanggil pada pool CL ini ia revert `"PT"`
  (pool type). Jangan pakai V2 untuk pool CL; pakai V3.
- **Rate limit / key:** tidak ada API key. RPC publik yang dipakai
  (`mainnet.base.org`) sesekali memutus koneksi (1x `RemoteDisconnected`
  selama riset) — retry 2 detik menanganinya. Untuk pemakaian berkala
  prototipe (bukan high-frequency), ini cukup; bila polling diperketat,
  siapkan RPC cadangan.
- **Yang dikembalikan:** `amountOut` (USDC, 6 desimal), harga setelah
  swap (`sqrtPriceX96After`), jumlah tick terlewati
  (`initializedTicksCrossed`) — cukup untuk mengisi `exit_quote`
  (amount_out_min, fee/slippage implisit, dan bukti eksekusi).

### 2. Uniswap V3 QuoterV2 — FALLBACK, TERBUKTI jalan tapi depth terbatas ⚠️

- **Alamat:** `0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a`
- **Sumber alamat:** docs resmi Uniswap
  (`docs.uniswap.org/contracts/v3/reference/deployments/base-deployments`,
  kolom Base mainnet) + `factory()` di quoter mengembalikan
  `0x33128a8fC17869897dcE68Ed026d694621f6FDfD` (UniswapV3Factory resmi).
- **Peringatan F1:** sebuah blog (solvinc.io) mencantumkan QuoterV2 Base
  sebagai `0xC5290058841028F1614F3A6F0F5816cAd0df5E27` — **SALAH**.
  Alamat itu adalah kolom **Base Sepolia (testnet)** di halaman docs yang
  sama; di BaseScan mainnet ia hanya EOA berisi 0,00003 ETH, bukan
  kontrak. Jangan pakai alamat itu. (Blog yang sama, jujur, mencatat
  bahwa RPC publik mengembalikan "empty reverts" untuk QuoterV2 — lihat
  catatan di bawah; penyebab sebenarnya di kasus kami adalah pool tidak
  ada di factory, bukan RPC.)
- **Cara pakai (read-only):** `eth_call` ke
  `quoteExactInputSingle((address tokenIn, address tokenOut, uint256
  amountIn, uint24 fee, uint160 sqrtPriceLimitX96))` (selector
  `0xc6a5026a`). Pool dicari lewat factory + fee tier.
- **Bukti — quote NYATA, RPC publik yang sama:**

| Jual | amountOut | Harga implisit | Slippage | ticks |
|---|---|---|---|---|
| NVDAc 1 token, fee 3000 | $132,45 | $132,45 | — | 0 |
| NVDAc 10 token, fee 3000 | $1.320,94 | $132,09 | ~-0,5% | 1 |
| **NVDAc 75 token (~$10.000), fee 3000** | **$6.250,99** | **$83,35** | **-37,22%** | 17 |
| AAPLc 10 token, fee 3000 | $3.476,07 | $347,61 | ~-0,6% | 2 |
| **AAPLc 28 token (~$10.000), fee 3000** | **$9.641,18** | **$344,33** | **-1,58%** | 5 |
| NVDAc/AAPLc fee 500 & fee 10000 (10 token) | GAGAL | `"Unexpected error"` | — | — |

- **Verdict:** JALAN sebagai quoter, tapi **TIDAK LAYAK sebagai jalur
  utama** untuk notional $10.000: pool Uniswap NVDAc/USDC hanya ~$40–50
  ribu per tier (total ~$130 ribu), sehingga jual NVDAc $10.000
  slippage-nya -37% — validator E1 (±10%) akan MENOLAK quote itu.
  AAPLc $10.000 lolos (-1,58%), tapi NVDAc tidak. Cocok sebagai
  **cross-check / venue kedua** (ukuran kecil) atau bila ukuran posisi
  diperkecil, bukan sebagai bukti exit utama.
- Pool Uniswap yang terkonfirmasi via `getPool` di factory resmi:
  NVDAc/USDC fee 500 `0xd3085c0c2605cef89f02a742acdfac95dca79bcd`,
  fee 3000 `0x60661b315553eb81872deea9a66d567cf0ccd33b`,
  fee 10000 `0x9778aad868418ff6c996294ce62c9ed2b96896d1`;
  AAPLc/USDC fee 3000 `0x97f35d1e92795327614be000cd18cba1be2c1931`,
  fee 10000 `0x7cb5eb63cef446168eb29f892e5759789b29bfd4`.

### 3. Aerodrome Slipstream Quoter — TIDAK BISA untuk token ini ❌

- **Alamat:** `0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0`
  (BaseScan: "Aerodrome: SlipStream Quoter", kontrak `QuoterV2`,
  terverifikasi; `factory()` = CLFactory
  `0x5e7BB104d84c7CB9B682AaC2F3d509f5F406809A`).
- **Kenapa gagal:** quoter ini hanya bisa quote pool yang terdaftar di
  factory-nya. `getPool(NVDAc, USDC, 10)` di factory itu mengembalikan
  `0x0000...0000` — pool NVDAc/AAPLc TIDAK ADA di sana (mereka milik
  factory Dromos, lihat temuan kunci #1). Akibatnya `eth_call` ke quoter
  revert TANPA data (quoter memanggil swap di alamat 0, lalu gagal
  decode hasil kosong). Ini BUKAN salah RPC — RPC yang sama
  mengembalikan data revert untuk call lain (mis. custom error
  `AccessControlUnauthorizedAccount` dari registry, lengkap dengan
  datanya). Jadi quoter Aerodrome secara struktural tidak bisa dipakai
  untuk kedua token ini. Jangan buang waktu di sini.
- (Kandidat kedua `0x3d4C22254F86f64B7eC90ab8F7aeC1FBFD271c6C` dari
  DeepWiki juga QuoterV2, tapi `factory()`-nya menunjuk
  `0xaDe65c38CD4849aDBA595a4323a8C7DdfE89716a` (CLFactoryGaugeCaps,
  bukan factory pool) dan hanya punya 1 transaksi sepanjang hidup —
  bukan quoter live. Abaikan.)

### 4. 0x Swap API — v1 tidak ada rute; permit2 butuh API key ❌

- **v1 (tanpa key):** `GET
  https://api.0x.org/swap/v1/quote?sellToken=0xb200...&buyToken=0x8335...&sellAmount=1000000000`
  → `{"message":"no Route matched with those values"}`. Endpoint
  menjawab tanpa key, tapi tidak ada rute untuk pasangan ini (v1
  adalah mainnet-centric; tidak ada quote Base untuk NVDAc).
- **permit2 (Base):** `GET
  https://api.0x.org/swap/permit2/quote?chainId=8453&...` →
  `{"message":"No API key found in request"}`. Butuh registrasi +
  API key. Di luar batas read-only tanpa key; bukan jalur utama.
  (Bila suatu saat ada key, 0x mengembalikan `buyAmount` + estimasi
  harga — tapi tetap butuh key.)

### 5. 1inch Swap API — butuh API key ❌

- `GET
  https://api.1inch.dev/swap/v6.0/8453/quote?src=0xb200...&dst=0x8335...&amount=1000000000`
  → `{"success":false,"error":"Unauthorized"}`. Butuh API key
  (registrasi). Bukan jalur read-only tanpa key.

### 6. DexScreener / GeckoTerminal — bukan quote ❌ (sebagai quoter)

- Keduanya publik tanpa key dan SUDAH dipakai prototipe (harga median,
  likuiditas). Tapi mereka TIDAK punya endpoint quote per jumlah:
  yang dikembalikan hanya harga spot + likuiditas pool. Menghitung
  quote dari reserve secara off-chain (rumus CPMM) TIDAK berlaku untuk
  pool CL (concentrated liquidity) — harga eksekusi tergantung
  distribusi likuiditas per tick, bukan satu reserve. Jadi agregator
  ini tetap sumber harga/venue discovery, bukan quoter.

### 7. Coinbase tokenized-stocks API — tidak ada endpoint quote ❌

- `GET https://api.coinbase.com/v1/tokenized-stocks` (publik, tanpa
  key) mengembalikan daftar token dengan field identitas +
  `nav_price`, `nav_price_updated_at`, `multiplier`, `total_supply`
  (contoh NVDAc: multiplier `1.0005379395763694`, nav_price
  `129.82480034`, update `2026-11-20T23:42:40Z`). TIDAK ada field
  quote/harga jual/bid-ask. Docs Base
  (`docs.base.org/build-on-base/integrate-defi/list-tokenized-stocks`)
  juga tidak mencantumkan endpoint quote. API ini sumber NAV +
  multiplier, bukan exit.

### 8. Hitung quote off-chain dari state pool (slot0 + liquidity) — FEASIBLE tapi lebih banyak kerja (cadangan)

- Semua input-nya bisa dibaca read-only via `eth_call` (sudah terbukti
  di riset ini): `slot0()`, `liquidity()`, `tickBitmap()`, `ticks()`,
  `fee()`. Rumusnya adalah matematika swap UniV3 standar (whitepaper +
  SDK) — peneliti independen (solvinc.io, Nov 2026) sudah memverifikasi
  pendekatan ini di Base untuk pool UniV3, karena RPC publik yang sama
  "mengembalikan empty reverts untuk QuoterV2" di lingkungannya.
- Tapi: butuh implementasi matematika tick-by-tick + pembacaan tick
  (bila swap melewati tick), dan hasilnya harus divalidasi terhadap
  quoter on-chain. Karena Metaquoter V3 SUDAH memberi quote langsung
  (kandidat 1), jalur off-chain ini tidak perlu dibangun dulu — simpan
  sebagai cadangan bila Metaquoter berubah/tidak tersedia.

## Registry pause — TERBACA read-only, saat ini TIDAK paused

### Alamat + verifikasi

- **OracleRegistry:** `0x3f3E8cf41cdd3b1D118c16471aB0113DfDDd5CaD`
- **Sumber alamat (2):**
  1. Docs resmi Base
     (`docs.base.org/build-on-base/integrate-defi/list-tokenized-stocks`,
     bagian "Contract Addresses"): "…the List Protocol Contract
     Addresses endpoint for protocol contracts, including the Onchain
     Registry (`0x3f3E8cf41cdd3b1D118c16471aB0113DfDDd5CaD`)."
  2. BaseScan: nama kontrak **`OracleRegistry`**, source terverifikasi,
     compiler v0.8.30. Transaksi terakhirnya bernama
     "Set Oracle Pause…" (47 jam dan 2 hari lalu, dari admin
     `0x38467bE0...Ba91572B1`) — pause memang pernah di-toggle.
- Alamat ini SAMA dengan `ORACLE_REGISTRY` yang sudah ada di
  `config.py` (yang selama ini nilainya `unknown` karena belum dibaca).

### Cara membaca (read-only)

Satu `eth_call` (view, tanpa key/wallet/signing):

```
getOracleParams(address token) -> (uint256 multiplier, bool paused)
selector: 0xd4197e82
```

Contoh call (NVDAc): `to = 0x3f3E...CaD`,
`data = 0xd4197e82` + `token` (32 byte). Respons 64 byte: word pertama
= multiplier (WAD, 18 desimal), word kedua = paused (0/1).

### Hasil live (22 Nov 2026 ~14:06 UTC, RPC publik)

| Token | multiplier (raw) | multiplier | paused |
|---|---|---|---|
| NVDAc | `1000537939576369481` | 1,000538 | **false** |
| AAPLc | `1000500389301980219` | 1,000500 | **false** |

Multiplier on-chain COCOK dengan API Coinbase (NVDAc
`1.0005379395763694` — sama sampai 6 desimal; beda kecil karena waktu
fetch). Ini sekaligus cross-check independen bahwa registry yang dibaca
adalah registry yang benar.

### Apa arti pause — PENTING: ini pause ORACLE, bukan pause transfer

Dari docs resmi Base + Chainlink
(`docs.chain.link/data-feeds/tokenized-equity-feeds/coinbase`):

- **Normal (`paused = false`):** feed Chainlink mempublikasikan
  `harga saham × multiplier`.
- **Paused (`paused = true`):** feed BERHENTI mempublikasikan dan
  menahan nilai terakhir yang diketahui ("holds the last known good
  value"). Tujuannya mencegah harga inkonsisten saat corporate action
  (mis. split) ketika harga saham dan multiplier belum sinkron.
- **"Mint and redeem pause offchain, but the token is not paused
  onchain, so transfers are not blocked."** (docs Base, kata per kata.)
  Selama corporate action, mint/redeem berhenti di luar chain, feed
  membeku (NAV basi), TAPI token tetap bisa ditransfer/dijual di DEX.
- Jadi untuk prototipe: **`paused = true` artinya NAV basi/beku
  (perlakukan seperti NAV stale — sama seperti off-hours), BUKAN
  berarti exit tertutup.** Sell quote dari Metaquoter tetap valid
  sebagai bukti exit selama pause; yang tidak valid adalah memakai
  NAV beku sebagai referensi harga segar. Adapter yang membaca
  registry sebaiknya: bila `paused = true`, tandai NAV
  `nav_stale_off_hours`-sejenis (alasan `nav_paused_corporate_action`)
  dan tetap boleh memakai quote DEX sebagai bukti exit.
- Fungsi tulisnya (`setOraclePaused(address token, bool paused)`,
  selector `0x0dd9faaf`) HANYA bisa dipanggil pemegang `PAUSER_ROLE`
  — terbukti: `eth_call` tanpa role revert dengan custom error
  `AccessControlUnauthorizedAccount` (data revert dikembalikan RPC).
  Prototipe hanya MEMBACA; tidak pernah memanggil fungsi tulis.

### Sisa gap (bukan blocker)

- **B20 per-function pause:** docs Base ("Pauses") menyebut B20
  mengizinkan fungsi tertentu di dalam kontrak dipause ("Onchain pauses
  are unlikely, but be aware that B20s allow specific functions within
  a contract to be paused"). Token B20 adalah **precompile native**
  (bukan kontrak yang di-deploy per aset; "no per-address verified
  contract on Basescan"), jadi tidak ada `paused()` sederhana yang
  bisa dibaca seperti ERC-20 biasa. Riset ini TIDAK menemukan fungsi
  baca publik yang terdokumentasi untuk status pause per-fungsi B20.
  Ini dicatat sebagai gap yang diketahui, bukan blocker: (a) docs
  sendiri menyebut onchain pause "unlikely"; (b) pause yang berdampak
  ke NAV (oracle registry) sudah terbaca; (c) bila transfer benar-benar
  ter-pause, quoter akan gagal memberi quote (quote itu sendiri yang
  menjadi detektornya — gagal quote = tidak ada bukti exit).

## Tabel alamat kontrak terverifikasi (semua dicek ke BaseScan/GitHub/docs, bukan ingatan)

| Kontrak | Alamat | Diverifikasi lewat |
|---|---|---|
| Dromos Metaquoter | `0x1dDfeC5058180C207F55BB77D95AcDd0d8227868` | Deployment JSON resmi Dromos (`cl-base.json`, field `metaquoter`) + BaseScan "Dromos: Metaquoter" + quote live berhasil |
| Dromos CLFactory | `0x9cb220581b91b0c83223012fe69688b92ad07a76` | `factory()` pool on-chain + BaseScan "Dromos: CL Factory" + `cl-base.json` (`clFactory`) |
| Dromos CL pool NVDAc/USDC | `0xF668e21993f0ACd7ab00BB1cFbAeD0df28A3C8EC` | DexScreener + `getPool` factory Dromos (cocok) |
| Dromos CL pool AAPLc/USDC | `0xF5FCB9CDAFcE67d50AfEf298F88E709d2B946BA6` | DexScreener + `getPool` factory Dromos (cocok) |
| Uniswap V3 QuoterV2 (Base) | `0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a` | Docs resmi Uniswap (base-deployments) + `factory()` = factory resmi + quote live berhasil |
| UniswapV3Factory (Base) | `0x33128a8fC17869897dcE68Ed026d694621f6FDfD` | Docs resmi Uniswap (base-deployments) |
| Aerodrome SlipStream Quoter | `0x254cF9E1E6e233aa1AC962CB9B05b2cfeAaE15b0` | BaseScan "Aerodrome: SlipStream Quoter" + `factory()` = CLFactory (tapi TIDAK berisi pool ini) |
| Coinbase OracleRegistry | `0x3f3E8cf41cdd3b1D118c16471aB0113DfDDd5CaD` | Docs resmi Base + BaseScan "OracleRegistry" + `getOracleParams` live |
| USDC native (Base) | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | Sudah terverifikasi di F1 (BaseScan + CoinGecko) |
| NVDAc | `0xb20000000000000000000078ee7ce2fE4908108C` | Config prototipe + API Coinbase |
| AAPLc | `0xb200000000000000000000C2e324d24d7eEcd1fb` | Config prototipe + API Coinbase |

Selector fungsi yang dipakai (dihitung keccak-256 murni-Python,
diverifikasi terhadap 4 test vector sebelum dipakai):

| Fungsi | Selector |
|---|---|
| `quoteExactInputSingleV3(address,address,uint256,uint160)` (Metaquoter) | `0x0a674142` |
| `quoteExactInputSingleV2(address,address,uint256)` (Metaquoter, pool V2 saja) | `0x3c5ba2b9` |
| `quoteExactInputSingle((address,address,uint256,uint24,uint160))` (UniV3 QuoterV2) | `0xc6a5026a` |
| `quoteExactInputSingle((address,address,uint256,int24,uint160))` (Slipstream QuoterV2) | `0x9e7defe6` |
| `getOracleParams(address)` (OracleRegistry) | `0xd4197e82` |
| `setOraclePaused(address,bool)` (hanya baca selector; TIDAK dipanggil) | `0x0dd9faaf` |
| `getPool(address,address,int24)` | `0x28af8d0b` |
| `factory()` / `slot0()` / `tickSpacing()` / `fee()` | `0xc45a0155` / `0x3850c7bd` / (dihitung) / (dihitung) |

## RPC publik yang dipakai (bukti read-only)

- `https://mainnet.base.org` (RPC publik Base, tanpa key): `eth_blockNumber`
  OK; `eth_call` OK untuk view DAN quoter (data revert dikembalikan).
  `eth_getTransactionByHash` DIBLOKIR (HTTP 403) — tidak dibutuhkan.
  Sekali `RemoteDisconnected` selama riset (retry 2 dtk berhasil).
  RPC lain yang dicoba: `base.llamarpc.com` 403/525, `1rpc.io/base`
  limit habis, `base.meowrpc.com` tidak dukung `eth_call`,
  `base-mainnet.public.blastapi.io` menjawab tapi tidak dipakai untuk
  quote final. **Satu-satunya RPC yang dibutuhkan adapter: public
  Base RPC untuk `eth_call`.** Bila mainnet.base.org bermasalah,
  siapkan RPC cadangan (mis. BlastAPI) — tapi verifikasi dulu bahwa ia
  mengembalikan data revert quoter.

## Rekomendasi (untuk keputusan Septian / chief)

1. **Jalur utama quoter: Dromos Metaquoter `quoteExactInputSingleV3`.**
   Satu `eth_call` per token per ukuran. Pool diambil dari DexScreener
   (seperti sekarang) lalu quote di pool itu — alamat pool JANGAN
   di-hard-code sebagai satu-satunya sumber (tetap discovery via
   DexScreener; pool `0xF668...`/`0xF5FC...` hanya ekspektasi).
   Isi `exit_quote` dari `amountOut` (USDC) + `sqrtPriceX96After` +
   `initializedTicksCrossed` + timestamp call. Validator E1 yang sudah
   ada (kind firm, token_out allowlist USDC, sanity ±10%, notional)
   langsung bisa dipakai di atas quote ini — quote $10.000 lolos
   semuanya (slippage <0,2%).
2. **Jalur kedua / cross-check: Uniswap V3 QuoterV2** (ukuran kecil
   saja; jangan jadikan bukti exit $10.000 untuk NVDAc).
3. **Registry pause:** baca `getOracleParams(token)` tiap run; simpan
   `(multiplier, paused)` di snapshot. Bila `paused = true`, tandai NAV
   basi (alasan baru, mis. `nav_paused_corporate_action`) — quote DEX
   tetap jalan sebagai bukti exit. JANGAN jadikan pause sebagai
   "token tidak bisa dijual" (itu salah baca; docs resmi bilang transfer
   tidak diblokir).
4. **Perbaiki label venue di prototipe:** pool `0xF668...`/`0xF5FC...`
   adalah **Dromos CL**, bukan Aerodrome Slipstream. DexScreener
   `dexId: aero` menyesatkan di sini; kanonisasi venue sebaiknya
   membedakan Dromos dari Aerodrome (bila DexScreener tetap melabeli
   `aero`, catat pemetaan ini eksplisit).
5. **Tidak perlu:** API key 0x/1inch (butuh registrasi; quoter on-chain
   sudah cukup), quoter Aerodrome (struktural tidak bisa), endpoint
   quote Coinbase (tidak ada).

## Batasan riset ini

- Quote diuji pada 22 Nov 2026 ~14:13 UTC (sesi market tutup, NAV basi
  ~38 jam — sama seperti live run prototipe). Slippage diukur terhadap
  spot DexScreener yang di-fetch ~13:55 UTC (bukan spot detik yang
  sama) — selisih ±0,2% masih dalam toleransi.
- RPC publik bisa berubah perilakunya (rate limit, blokir method).
  Adapter harus punya retry + RPC cadangan + gagal-yang-jelas
  (bila quote gagal, `exit_quote = missing`, BUKAN angka karangan).
- Metaquoter adalah kontrak Dromos (MetaDEX) — bila Dromos mengganti
  deployment, alamat quoter harus diverifikasi ulang dari
  `deployment-addresses/cl-base.json` repo resmi (bukan dari ingatan).
- Riset ini TIDAK menguji eksekusi swap (tidak ada transaksi yang
  dikirim, tidak ada signing). Quote adalah simulasi read-only;
  eksekusi nyata tetap di luar scope (dan di luar batas keras audit).

## Lampiran — contoh call mentah (bisa diulang)

```bash
# 1) Quote jual NVDAc 10 token di Dromos (Metaquoter V3), via RPC publik.
#    data = selector 0x0a674142 || pool || tokenIn || amountIn || sqrtPriceLimitX96=0
curl -s -X POST https://mainnet.base.org -H 'Content-Type: application/json' -d '{
  "jsonrpc":"2.0","method":"eth_call",
  "params":[{"to":"0x1dDfeC5058180C207F55BB77D95AcDd0d8227868",
             "data":"0x0a674142000000000000000000000000f668e21993f0acd7ab00bb1cfbaed0df28a3c8ec000000000000000000000000b20000000000000000000078ee7ce2fe4908108c000000000000000000000000000000000000000000000000000000003b9aca000000000000000000000000000000000000000000000000000000000000000000"},
            "latest"],"id":1}'
# -> error code 3 "execution reverted" DENGAN data:
#    amountOut=0x... (1330390000 = $1.330,39) || sqrtPriceX96After || initializedTicksCrossed=1
#    (Pola revert-with-result: "error" di sini ADALAH hasil, bukan kegagalan.)

# 2) Baca registry pause + multiplier NVDAc.
#    data = selector 0xd4197e82 || token
curl -s -X POST https://mainnet.base.org -H 'Content-Type: application/json' -d '{
  "jsonrpc":"2.0","method":"eth_call",
  "params":[{"to":"0x3f3E8cf41cdd3b1D118c16471aB0113DfDDd5CaD",
             "data":"0xd4197e82000000000000000000000000b20000000000000000000078ee7ce2fe4908108c"},
            "latest"],"id":1}'
# -> result 64 byte: multiplier=0x... (1000537939576369481) || paused=0x...0 (false)
```
