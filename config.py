"""Konfigurasi prototipe Base Stocks Maxxing (lokal/offline).

Sumber otoritatif: brief Instinct (brief-instinct-muse.md).
Semua endpoint publik, read-only, TANPA API key. Tidak ada secret/kunci/token.

KOREKSI YANG MENGIKAT (brief Instinct §3):
- nav_price SUDAH multiplier-adjusted / total-return. JANGAN dikali multiplier lagi.
  Rumus harga token = harga equity x multiplier hanya untuk harga saham MENTAH.
- Gap DEX-vs-NAV beku = deskripsi berlabel saja. Bukan diskon/mispricing/arbitrase.
- TVL/reserve/likuiditas pool BUKAN executable depth. Hanya filter kelayakan.
- Redemption: desain mengasumsikan TIDAK ADA jalur permissionless retail.
- PoR: tidak ada sumber otomatis. Hanya catatan manual atau `unknown`.
- Dua agregator yang membaca pool sama = SATU pool, bukan dua venue independen.
- Hyperliquid: perp TOKEN (NVDAc/AAPLc) tidak ada. Yang ada adalah perp
  UNDERLYING di dex lain: `xyz:NVDA` / `xyz:AAPL` (baseline) dan `io:NVDA` /
  `io:AAPL`. Funding/OI itu UNDERLYING EQUITY PERP PROXY, bukan ukuran
  exit-risk token Base. Jangan agregasi xyz: dan io: tanpa metodologi eksplisit.
"""

# ---------------------------------------------------------------- identitas
# Kunci identitas: chain + contract, BUKAN ticker saja (brief §3).
# Nilai ini adalah kunci lookup (fakta identitas), bukan data pasar.
# Data pasar (nav_price, multiplier, harga) TIDAK di-hard-code; diambil live.
CHAIN = "base"

TOKENS = {
    "NVDAc": {
        "chain": CHAIN,
        "token_address": "0xb20000000000000000000078ee7ce2fE4908108C",
        "symbol": "NVDAc",
        "name": "NVIDIA Corporation",
        "decimals": 8,
        # Pool Aerodrome Slipstream NVDAc/USDC (teramati saat validasi).
        # Dipakai HANYA sebagai cross-check ekspektasi, bukan sumber kebenaran.
        # Adapter menemukan pool dari DexScreener; bila pool ini tidak muncul,
        # itu temuan (bukan asumsi).
        "expected_pool": "0xF668e21993f0ACd7ab00BB1cFbAeD0df28A3C8EC",
        # Proxy underlying (baseline): instrumen Hyperliquid di dex "xyz".
        "proxy_instrument": "xyz:NVDA",
        "proxy_dex": "xyz",
    },
    "AAPLc": {
        "chain": CHAIN,
        "token_address": "0xb200000000000000000000C2e324d24d7eEcd1fb",
        "symbol": "AAPLc",
        "name": "Apple Inc.",
        "decimals": 8,
        "expected_pool": "0xF5FCB9CDAFcE67d50AfEf298F88E709d2B946BA6",
        "proxy_instrument": "xyz:AAPL",
        "proxy_dex": "xyz",
    },
}

# ---------------------------------------------------------------- sumber data
# Semua publik, read-only, tanpa key. Tidak ada pendaftaran/akun.
COINBASE_API_URL = "https://api.coinbase.com/v1/tokenized-stocks"
COINBASE_DOCS_URL = "https://docs.base.org/sdks/tokenized-stocks/overview"
COINBASE_B20_DOCS_URL = "https://docs.base.org/build-on-base/integrate-defi/list-tokenized-stocks"
DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/{address}"
GECKOTERMINAL_POOL_URL = "https://api.geckoterminal.com/api/v2/networks/base/pools/{pool}"
HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"
# Dex baseline untuk proxy underlying. Varian "io:" ada tapi TIDAK diagregasi
# (brief §5: hindari agregasi xyz: dan io: tanpa metodologi eksplisit).
PROXY_BASELINE_DEX = "xyz"
ORACLE_REGISTRY = "0x3f3E8cf41cdd3b1D118c16471aB0113DfDDd5CaD"
# Registry pause DIBACA di prototipe ini (v0.3.0, fase quoter) via RPC
# read-only: `getOracleParams(token)` -> (multiplier, paused). Lihat adapter.
# `paused = true` = pause ORACLE (feed Chainlink beku, NAV basi), BUKAN
# pause transfer — docs Base: "Mint and redeem pause offchain, but the
# token is not paused onchain, so transfers are not blocked."
# RPC publik Base (read-only, tanpa key). Urutan = prioritas fallback.
BASE_RPC_URLS = [
    "https://mainnet.base.org",
    "https://base-mainnet.public.blastapi.io",
]
# Quoter sell-quote (fase quoter, v0.3.0). DIVERIFIKASI 22 Nov 2026
# (QUOTER-RESEARCH.md) ke deployment resmi Dromos + BaseScan + quote live.
# KOREKSI G1 (re-audit v5, 22 Nov 2026): kontrak-kontrak ini adalah AERO
# (Aerodrome) — BUKAN venue independen bernama "Dromos". Sumber resmi Aero
# (app.aero.xyz/docs/security/, 22 Nov 2026): bagian "Aero Slipstream"
# mencantumkan Metaquoter 0x1dDf... DAN CLFactory Base 0x9CB2...; repo
# upstream-nya memang dromos-labs/metadex-slipstream-public (Dromos Labs
# adalah pengembang), tetapi venue/protokolnya adalah Aero. Label DexScreener
# `dexId: aero` untuk pool-pool ini BENAR (itu Aero Slipstream), dan factory
# 0x9cb2... adalah CLFactory Aero Slipstream — BUKAN venue baru.
# Konstanta di-rename dari DROMOS_* ke AERO_* di v0.3.1 agar label jujur.
# Aero Metaquoter: `quoteExactInputSingleV3(pool, tokenIn, amountIn,
# sqrtPriceLimitX96)` — satu eth_call, tanpa key/wallet/signing/gas.
AERO_METAQUOTER = "0x1dDfeC5058180C207F55BB77D95AcDd0d8227868"
# Aero Slipstream CLFactory (Base). Dulu salah dilabeli "Dromos".
AERO_SLIPSTREAM_CL_FACTORY = "0x9cb220581b91b0c83223012fe69688b92ad07a76"
AERODROME_CL_FACTORY = "0x5e7BB104d84c7CB9B682AaC2F3d509f5F406809A"
# CLFactory Aerodrome SAAT INI (bukan legacy 0x5e7B...): DIVERIFIKASI
# 22 Nov 2026 via BaseScan — kontrak `CLFactory` terverifikasi, punya
# `legacyCLFactory` + `factoryRegistry`. Pool Aerodrome NVDAc/AAPLc memakai
# factory ini (dibaca langsung dari pool saat live run v0.3.0).
AERODROME_CL_FACTORY_CURRENT = "0xf8f2eb4940cfe7d13603dddd87f123820fc061ef"
UNISWAP_V3_FACTORY = "0x33128a8fC17869897dcE68Ed026d694621f6FDfD"
# Factory lain yang terverifikasi (G1, re-audit v5, 22 Nov 2026) — SEMUA
# dicek ke BaseScan SEBELUM ditulis (kontrak + deployer):
#  - Nami: AlgebraFactory, deployer "nami: Deployer" (BaseScan).
#  - Hydrex: "Hydrex: Factory", kontrak AlgebraFactory (BaseScan).
#  - Topaz: CLFactory (Slipstream-fork, v0.7.6), deployment Topaz.
#  - Equalizer: TransparentUpgradeableProxy, deployer
#    "Equalizer (BASE): Deployer", transaksi "Create Pair" (BaseScan).
NAMI_ALGEBRA_FACTORY = "0xf4502a98a15e82d66d28d2381e2f3a407ea45b83"
HYDREX_ALGEBRA_FACTORY = "0x36077d39cdc65e1e3fb65810430e5b2c4d5fa29e"
TOPAZ_CL_FACTORY = "0xaa5865dc3a60b25d305226d66fd573021f0d8ffb"
EQUALIZER_FACTORY = "0xed8db60acc29e14bc867a497d94ca6e3ceb5ec04"
# Aerodrome V2 (basic) PoolFactory (F3, re-audit v6, 22 Nov 2026):
# DIVERIFIKASI chief ke BaseScan — label "Aerodrome: Pool Factory",
# kontrak PoolFactory, creator "Aerodrome: Deployer". Satu pool NVDAc
# memakainya (0xCcb9..., saat ini ter-reject karena tanpa harga).
AERODROME_V2_FACTORY = "0x420DD381b31aEf6683db6B902084cB0FFECE40Da"
# Batas sqrt-price Uniswap V3 / Slipstream (TickMath): quote exact-input
# yang terminal sqrt-price-nya menyentuh batas ini kemungkinan PARTIAL FILL
# (G3) — input tidak habis terjual. Guard di adapter/validator.
# KOREKSI M1 (re-audit v7, 22 Nov 2026): nilai v0.3.2 adalah floor eksak
# RUMUS sqrt(1.0001^887272)*2^96 (1461446703485210103244672773810124308346321380902)
# — BUKAN konstanta kontrak TickMath.sol. Konstanta on-chain yang benar
# (hasil bit-decomposition kontrak, getSqrtRatioAtTick(MAX_TICK)):
# DIVERIFIKASI chief ke sumber resmi — Uniswap v3-core TickMath.sol di
# GitHub (raw.githubusercontent.com/Uniswap/v3-core/main/contracts/
# libraries/TickMath.sol, L28): MAX_SQRT_RATIO =
# 1461446703485210103287273052203988822378723970342. Beda ~2,9e-8 relatif
# dari floor rumus (arah konservatif — nilai rumus lebih kecil, guard
# memicu sedikit lebih awal; dampak praktis ~nol, kata auditor). v0.3.3
# memakai KONSTANTA KONTRAK agar guard memeriksa batas yang benar-benar
# ditegakkan quoter di chain. MIN_SQRT_RATIO 4295128739 cocok TickMath
# (L24 sumber yang sama) dan tidak berubah.
MIN_SQRT_RATIO = 4295128739
MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342
# M2 (re-audit v7): probe partial-fill WAJIB sukses agar quote boleh
# dipakai sebagai bukti exit. Bila probe gagal RPC, quote DITOLAK (pool
# ditolak, bukan dipakai inconclusive) — pool tipis + kegagalan probe
# transien tidak boleh lolos hanya dengan sanity ±10%. Berlaku sejak
# v0.3.3; gate proposal tetap MATI, jadi perubahan ini hanya memperketat
# bukti exit (keputusan tetap maks WATCH), bukan mengaktifkan proposal.
REQUIRE_PROBE_SUCCESS = True
# CATATAN JUJUR F1 (re-audit v6): guard batas MIN/MAX di atas HANYA
# menangkap terminal sqrt-price TEPAT di batas. Signature partial-fill
# standar (terminal MIN+1/MAX−1 — quoter memakai itu sebagai limit saat
# sqrtPriceLimitX96=0) TIDAK tertangkap guard ini, dan probe empiris
# auditor (amount_in 10^18 wei) menunjukkan partial fill nyata dengan
# sqrtAfter 1,7359e38 yang BUKAN di batas. Deteksi partial-fill yang
# benar = DOUBLE-QUOTE PROBE di bawah + sanity implied-price ±10% di
# validator — BUKAN guard batas sqrt semata. Lihat pipeline.py.
# Double-quote probe (F1): sesudah quote pertama (amount_in) berhasil,
# ambil quote kedua dengan amount_in x MULTIPLIER. Bila output probe /
# output pertama < RATIO_MIN, quote pertama sudah di kapasitas pool
# (partial fill) -> ditolak sebagai bukti exit. Rasio sehat ~1,9
# (2x input, sedikit price impact). Ambang 1,5 = konservatif: pool yang
# hanya punya 1,2x likuiditas dari notional pun ikut tertandai (thin pool
# = bukti exit lemah, layak ditolak sebagai bukti).
PARTIAL_FILL_PROBE_MULTIPLIER = 2
PARTIAL_FILL_PROBE_RATIO_MIN = 1.5
# token_out quote jual: USDC native (paling likuid di Base). Alamat sama
# dengan anggota pertama USDC_BASE_ADDRESSES (F1-terverifikasi).
USDC_NATIVE_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
# Jendela max-age quote (detik) — ATURAN FRESHNESS INTERNAL, bukan expiry
# jaminan vendor (G5). Quote simulasi tidak punya expiry yang dijamin
# siapa pun; nilai ini hanya batas umur agar simulasi basi ditolak.
QUOTE_VALIDITY_SEC = 300
# Buffer ukuran quote (persen): amount_in = notional x (1 + buffer) / harga
# pool teratas, agar notional hitung (amount_in x median) >= nominal proposal
# meski harga pool teratas sedikit di atas median.
QUOTE_NOTIONAL_BUFFER_PCT = 5.0
# Freshness registry (detik, G6): data oracle (multiplier/paused) yang
# lebih tua dari ini saat evaluasi = stale -> proposal-blocking.
REGISTRY_MAX_AGE_SEC = 300
# Pemetaan factory on-chain -> protocol family kanonis. Dipakai bila factory
# pool berhasil dibaca (read-only); bila tidak, fallback ke label DexScreener
# (DITANDAI fallback, TIDAK dihitung sebagai independensi terverifikasi, G1).
# CATATAN G1: factory berbeda dari protokol yang SAMA (mis. dua CLFactory
# Aero) = SATU family, bukan dua venue independen. Keluarga dihitung dari
# protokol, bukan dari alamat factory.
FACTORY_VENUE = {
    AERO_SLIPSTREAM_CL_FACTORY.lower(): "aerodrome",
    AERODROME_CL_FACTORY.lower(): "aerodrome",
    AERODROME_CL_FACTORY_CURRENT.lower(): "aerodrome",
    AERODROME_V2_FACTORY.lower(): "aerodrome",
    UNISWAP_V3_FACTORY.lower(): "uniswap",
    NAMI_ALGEBRA_FACTORY.lower(): "nami",
    HYDREX_ALGEBRA_FACTORY.lower(): "hydrex",
    TOPAZ_CL_FACTORY.lower(): "topaz",
    EQUALIZER_FACTORY.lower(): "equalizer",
}

# ---------------------------------------------------------------- versi
SCHEMA_VERSION = "base-proto-schema v0.3.3"
METHODOLOGY_VERSION = "base-proto-method v0.3.3"
POLICY_VERSION = "base-proto-policy v0.3.3"
# Semua versi di atas adalah EKSPERIMEN, belum tervalidasi (brief §6).
# v0.2.0 (22 Nov 2026, pasca-audit Instinct): validator quote eksplisit +
# feature gate proposal, freshness per-jenis-data, coverage dihitung ulang
# dari pool tervalidasi, dedup persist eksplisit. Lihat DECISION_MEMO.md.
# v0.2.1 (22 Nov 2026, re-audit v2 Instinct, must-fix E1-E3): validator quote
# diperketat (kind wajib, token_out allowlist USDC, sanity harga + notional
# dari amount_in x median); build_snapshot hitung coverage dari venue
# kanonis; assess_snapshot tidak lagi mutasi snap["coverage"].
# v0.2.2 (22 Nov 2026, re-audit v3 Instinct, must-fix F1): allowlist USDC
# diperbaiki — KEDUA alamat v0.2.1 SALAH (native mangled, "USDC.e" ternyata
# DAI). Alamat di bawah DIVERIFIKASI ke 2 sumber independen (BaseScan +
# CoinGecko API, 22 Nov 2026) sebelum ditulis. Pelajaran F1: konstanta
# keamanan JANGAN PERNAH diketik dari ingatan — verifikasi ke sumber
# independen dulu, dan tes harus pakai alamat literal (bukan konstanta
# config) supaya kesalahan konstanta ketahuan, bukan dikonfirmasi.
# v0.3.0 (22 Nov 2026, fase quoter, ACC Septian): adapter quoter read-only
# Dromos Metaquoter V3 (sell quote NVDAc/AAPLc -> USDC, eth_call, tanpa
# key/wallet/signing/gas) + baca registry pause `getOracleParams` tiap run +
# label venue dari factory on-chain (Dromos CL, bukan Aerodrome).
# KOREKSI G1 (re-audit v5): label "Dromos" SALAH — itu Aero Slipstream.
# PAPER_PROPOSALS_ENABLED TETAP False (gate mati) sampai review ulang.
# v0.3.1 (22 Nov 2026, re-audit v5 Instinct, must-fix G1-G6): G1 venue =
# protocol family dari factory (Aero Slipstream = aerodrome, BUKAN "dromos";
# + Nami/Hydrex/Topaz/Equalizer terverifikasi BaseScan; fallback DITANDAI,
# tidak dihitung independensi terverifikasi); G2 guard quote (token0/token1,
# decimals, factory, pilih pool eligible); G3 guard partial-fill (terminal
# sqrt-price MIN/MAX); G4 decoder fail-closed (error RPC = error, panjang
# tepat, validasi uint160/uint32/bool/address); G5 label jujur
# (onchain_simulation, amount_out_estimate, block, max_age — BUKAN "firm"/
# amount_out_min/expires_at); G6 registry unknown/stale/mismatch =
# proposal-blocking. PAPER_PROPOSALS_ENABLED TETAP False.
# v0.3.2 (22 Nov 2026, re-audit v6 Instinct, 8,5/10, ACC read-only):
# F1 (dari G3) — deteksi partial-fill BUKAN yang diklaim: guard batas
# MIN/MAX tidak menangkap signature standar (MAX−1/MIN+1) dan probe
# empiris auditor (amount_in 10^18) menunjukkan partial fill nyata
# dengan sqrtAfter BUKAN di batas. Fix: MAX_SQRT_RATIO diperbaiki ke nilai
# EXACT TickMath (v0.3.1 salah 1e9x ke arah konservatif) + DOUBLE-QUOTE
# PROBE (quote 2x amount_in; rasio output < 1,5 = partial fill) sebagai
# deteksi yang benar; guard batas tetap ada tapi didokumentasikan jujur
# sebagai cek sekunder. F2 (dari G5) — validator TIDAK LAGI percaya
# max_age milik quote: max_age_efektif = min(quote.max_age_sec,
# QUOTE_VALIDITY_SEC). F3 — factory Aerodrome V2 (0x420D...) ditambahkan
# (terverifikasi BaseScan "Aerodrome: Pool Factory"). F4 — batasan Uniswap
# V4 (pairAddress = poolId 32-byte, bukan kontrak) didokumentasikan.
# F5 — README Python 3.10+ (gate + run lolos di 3.10 dan 3.12).
# PAPER_PROPOSALS_ENABLED TETAP False (ACC v0.3.1 hanya tahap read-only).
# v0.3.3 (23 Nov 2026, re-audit v7 Instinct, 9,5/10, ACC read-only):
# M1 — MAX_SQRT_RATIO diganti ke KONSTANTA KONTRAK TickMath.sol
# (1461446703485210103287273052203988822378723970342, diverifikasi chief
# ke Uniswap v3-core GitHub); nilai v0.3.2 adalah floor eksak RUMUS
# (beda ~2,9e-8 relatif, arah konservatif). M2 — probe WAJIB sukses
# (REQUIRE_PROBE_SUCCESS=True): probe gagal RPC = quote DITOLAK, bukan
# dipakai inconclusive. M3 — `factory` disimpan di exit_quote snapshot
# (transparansi). TIDAK ADA perubahan di luar M1-M3. PAPER_PROPOSALS_ENABLED
# TETAP False (gate mati).

# ---------------------------------------------------------------- policy
# Threshold eksperimen (versioned, jelas berlabel BELUM TERVALIDASI).
# Bukan kalibrasi; bukan warisan Solana (bobot / min-3-dari-5 / threshold 70
# Solana TIDAK dipakai di sini). Tradeoff FP/FN ada di DESIGN.md.
# - DEV_WATCH_PCT rendah (2%)  -> lebih sering WATCH (FP "watch" lebih tinggi).
# - DEV_ABSTAIN_PCT tinggi (5%) -> ABSTAIN hanya pada deviasi ekstrem.
# - REQUIRE_EXIT_QUOTE_FOR_PROPOSAL: tanpa sell quote, keputusan maks WATCH.
#   (Tanpa bukti exit, usulan beli tidak boleh keluar.)
DEV_WATCH_PCT = 2.0          # |deviasi vs median| > 2%  -> WATCH
DEV_ABSTAIN_PCT = 5.0        # |deviasi vs median| > 5%  -> ABSTAIN
MIN_INDEPENDENT_POOLS = 2    # butuh >=2 pool independen utk confidence lintas-venue
MIN_INDEPENDENT_VENUES = 2   # butuh >=2 venue kanonis (bukan hanya 2 pool)
NAV_STALE_HOURS = 24         # umur NAV > 24 jam = referensi basi (informasional)
MAX_FUTURE_SKEW_SEC = 300    # toleransi jam sumber maju (clock skew) 5 menit
MAX_POOL_AGE_MIN = 60        # observasi pool lebih tua dari ini = basi (informasional)
QUOTE_MAX_AGE_SEC = 300      # umur quote > 5 menit = stale (tidak bisa jadi bukti exit)
# Feature gate proposal (audit A, 22 Nov 2026): PAPER_PROPOSAL TIDAK PERNAH
# keluar selama gate ini False — apa pun isi exit_quote (null, kosong,
# valid sekalipun). Gate hanya dinyalakan eksplisit SETELAH quoter terpasang
# dan direview ulang. Jangan mengandalkan kebiasaan adapter mengisi None.
PAPER_PROPOSALS_ENABLED = False
# Allowlist alamat USDC di Base (re-audit v2 E1, diperbaiki re-audit v3 F1):
# token_out quote jual HARUS salah satu alamat ini — string "USDC"/
# "SCAMCOIN"/alamat lain DITOLAK.
# DIVERIFIKASI 22 Nov 2026 ke 2 sumber independen SEBELUM ditulis:
#  - BaseScan token page: 0x8335...A02913 = "USDC (USDC) | ERC-20",
#    FiatTokenProxy (Circle), 4,3M+ holder, harga $0,9995.
#  - CoinGecko API /coins/base/contract/<addr>: 0x8335...A02913 = USDC
#    (usd-coin); 0xd9aA...b6CA = "Bridged USDC (Base)" (usdbc);
#    0x50c5...0Cb = "L2 Standard Bridged DAI (Base)" (dai).
# PERINGATAN F1: alamat v0.2.1 SALAH — "native" ...bd029029 adalah alamat
# mangled (bukan token apa pun; CoinGecko: None) dan "USDC.e" 0x50c5...
# ternyata DAI bridged. Akibatnya USDC asli DITOLAK, DAI DITERIMA.
# Jangan pernah ketik konstanta keamanan dari ingatan.
USDC_BASE_ADDRESSES = {
    # USDC native (Circle, Base). JANGAN tertukar dengan ...bd029029 (mangled).
    "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    # USDC.e / USDbC bridged (Base bridge). BUKAN 0x50c5... (itu DAI).
    "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",
}
# Toleransi sanity quote (re-audit v2, E1). BUKAN kalibrasi — batas sanity
# eksplisit agar quote ngawur tertolak sebelum gate dinyalakan:
# - QUOTE_PRICE_TOLERANCE_PCT: harga implisit quote (amount_out_min /
#   amount_in) harus dalam ±10% dari median DEX. Quote yang menjamin harga
#   jauh di bawah/atas pasar = bukan bukti exit yang kredibel.
# - QUOTE_NOTIONAL_TOLERANCE_RATIO: notional_usd yang dinyatakan quote harus
#   dalam [computed/2, computed*2] dari notional hitung (amount_in x median).
#   Quote yang mengklaim nominal 1e12 untuk amount 76 token = tidak konsisten.
QUOTE_PRICE_TOLERANCE_PCT = 10.0
QUOTE_NOTIONAL_TOLERANCE_RATIO = 2.0
# Pemetaan alias venue -> nama kanonis (audit C). Dua label untuk venue yang
# sama TIDAK dihitung sebagai dua venue independen. Hanya alias yang
# tercantum di sini yang dipetakan; label lain dipakai apa adanya (lowercase).
VENUE_ALIASES = {
    "aero": "aerodrome",
    "aerodrome": "aerodrome",
    "aerodrome slipstream": "aerodrome",
    # "dromos" BUKAN venue independen (G1, re-audit v5): Dromos Labs adalah
    # pengembang MetaDEX Slipstream, venue-nya Aero. Label apa pun yang
    # tertulis "dromos"/"dromos cl" dipetakan ke aerodrome.
    "dromos": "aerodrome",
    "dromos cl": "aerodrome",
    "uniswap v2": "uniswap",
    "uniswap v3": "uniswap",
    "uniswap": "uniswap",
}
# Kalender pasar minimal (audit B): sesi AS (NYSE) untuk membedakan NAV basi
# saat market aktif vs market tutup. Daftar libur NYSE 2026 (tetap; wajib
# diperbarui tiap tahun — tanpa ini, sesi libur dibaca `unknown`, bukan tutup).
# Jam market 09:30-16:00 US/Eastern, Senin-Jumat. Early close tidak dimodelkan.
US_MARKET_HOLIDAYS_2026 = {
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # Martin Luther King Jr. Day
    "2026-02-16",  # Presidents' Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day (observed; 4 Jul = Sabtu)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas Day
}
# Parameter paper portfolio (EKSPERIMEN, bukan preferensi investasi Alex).
SIMULATION_NOTIONAL_USD = 10_000.0
MAX_WEIGHT_PER_ASSET = 0.50
HORIZON_DAYS = 7
EXPIRY_DAYS = 7

# ---------------------------------------------------------------- batas
HTTP_TIMEOUT_SEC = 30
USER_AGENT = "base-prototype/0.1.0 (read-only, no key; research prototype)"
