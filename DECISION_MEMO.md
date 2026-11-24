# Decision memo — Prototipe kecil Base Stocks Maxxing

Tanggal: 23 November 2026 (WITA). Status: **gate 19/19 (18 lama + 1 baru
quoter_f1_f2_m1_m3)**, adapter quoter v0.3.3 selesai (minor M1-M3 re-audit
v7) dan terverifikasi chief (live run kedua token, layer B
simulated-verified, probe partial-fill sehat + probe_ok, factory di
exit_quote, replay RPC byte-exact 18/18). Memo ini untuk keputusan ACC
Alex (Septian) atas fase berikutnya. **Lolos gate bukan izin otomatis
melanjutkan.**

## UPDATE — 24 Nov 2026 (~12:00 WITA)

**Gate 27/27 PASS** (19 lama + 8 baru Scope 1: S1-B 43/43, S1-C 46/46,
S1-D 25/25, S1-G 5 tes integritas). Scope 1 S1-A–S1-D selesai; cron
harian `base-exit-radar-daily-run` terpasang (23:00 WITA, run pertama
yang dihitung 26 Nov; run 24–25 Nov rehearsal). **Re-audit Instinct
24 Nov 11:47 WITA: 8,5/10, 2 must-fix — keduanya diperbaiki dan
di-commit hari yang sama:** (1) guard decide() kini source-sha saja
(hash AST dihapus dari guard — ast.dump bergantung versi Python,
gate 26/27 di 3.10); (2) hasil gate diregenerasi (27/27) dan README
diperbarui. Bukti firm tetap 0/8 (0x 422 legal restriction, 1inch
swap 400); Uniswap Trading API di-skip (ACC 24 Nov). `decide()` TIDAK
berubah (source-sha 9fbaae01... cocok); `PAPER_PROPOSALS_ENABLED`
TETAP False. Deadline submit: halaman resmi Base menyebut 12 Des
2026 (submit), sementara rencana ini menarget 5 Des — Instinct sedang
memverifikasi; rencana TIDAK diubah sampai ada kabar (target 5 Des
lebih awal = aman).

## CURRENT_STATUS (23 Nov 00:15 WITA — v0.3.3, BELUM ACC)

**Re-audit v7 Instinct (22 Nov 23:52 WITA): 9,5/10 — ACC v0.3.2 untuk tahap
read-only, TIDAK ADA must-fix baru.** F1+F2 terverifikasi independen
(probe diuji adversarial di luar gate; F2 cap max_age diuji dua arah).
Gate 19/19 direpro auditor di Python 3.10; replay on-chain 18/18 cocok di
**3 RPC independen** pada block pin asli. Diff v6→v7 bersih; fix generik.
**Prasyarat "gate proposal boleh dinyalakan" dari v6 kini TERPENUHI secara
teknis — TAPI nyalain gate hari ini tetap TIDAK menghasilkan
PAPER_PROPOSAL**, karena `decide()` menahan simulasi di WATCH
(`exit_evidence_simulated_not_firm`); proposal baru terjangkau bila ada
quote FIRM. Jadi keputusan nyalain gate murni soal kesiapan proses, bukan
risiko baru.

**Minor M1-M3 (re-audit v7) — SEMUA SUDAH diperbaiki chief di v0.3.3, gate
tetap 19/19** (tes `quoter_f1_f2_m1_m3` 22/22; atas pilihan Septian 23 Nov
00:09 WITA):
M1 (MAX_SQRT_RATIO diganti ke KONSTANTA KONTRAK TickMath.sol
`1461446703485210103287273052203988822378723970342`, diverifikasi chief ke
Uniswap v3-core GitHub; nilai v0.3.2 adalah floor eksak RUMUS, beda
~2,9e-8 relatif), M2 (probe WAJIB sukses — probe gagal RPC = quote
DITOLAK, bukan dipakai inconclusive; `REQUIRE_PROBE_SUCCESS=True`), M3
(`factory` disimpan di exit_quote snapshot). **TIDAK ADA perubahan di luar
M1-M3.** `PAPER_PROPOSALS_ENABLED` TETAP False (gate mati).

**Live run v0.3.3 (23 Nov 00:12 WITA, block-pinned):** NVDAc → WATCH
(median $132,82; simulasi 78,99488414 token → estimate $10.498,34;
implisit $132,89895047, **+0,059%**; block 60867888; probe partial-fill
rasio **1,99991884** — sehat, probe_ok=True; oracle 1,000538,
paused=false; 11 pool/6 venue, 0 fallback; factory di exit_quote
`0x9cb2...7a76`). AAPLc → WATCH (median $349,565; simulasi 30,03346586
token → estimate $10.497,92; implisit $349,5407879, **−0,007%**; block
60868044; probe rasio **1,99983284** — sehat, probe_ok=True; oracle
1,000500, paused=false; 6 pool/4 venue, 0 fallback; factory di exit_quote
`0x9cb2...7a76`). Keduanya cash 1.0, gate proposal TETAP MATI. **RPC
transcript** (`evidence/rpc/`, 18 file + manifest, kini termasuk
`quote_probe`): replay byte-exact 18/18 + 4/4 amount_out snapshot —
amount_out, sqrt-price, ticks, probe amount_out, oracle multiplier, block
hash, factory, token0/token1, decimals (8/6) cocok persis dengan snapshot.

**Kill-switch 30 Nov = komitmen OPERASIONAL (bukan cutoff otomatis di
kode):** bila fase quoter tidak selesai / tidak feasible sebelum itu,
prototipe berhenti di situ — tidak ada kode yang mematikan prototipe
otomatis pada 30 Nov. Review 28 Nov tetap jalan. **v0.3.3 BELUM ACC —
menunggu audit diff Instinct atas fix M1-M3 (v8, audit cepat atas diff
saja, bukan re-audit penuh — perintah Septian 23 Nov 00:09 WITA).**
Persiapan submit (form + post X + video demo) TETAP DITUNDA sampai
prototipe lolos (perintah Septian 22 Nov 22:16 WITA).

## ARSIP — CURRENT_STATUS v0.3.2 (22 Nov 23:39 WITA — BELUM ACC, kini ACC read-only per re-audit v7)

**Re-audit v5 Instinct (22 Nov 22:50 WITA): 7,5/10 — BELUM ACC v5.**
Terverifikasi benar oleh Instinct (2 RPC, block 60.841.377): quote akurat,
registry benar, gate 17/17 asli, live WATCH + cash 1.0, kill-switch utuh,
16 file + hash cocok. Jalur read-only feasible, tak perlu wallet, proyek
tak perlu distop. **6 must-fix (G1-G6) — SEMUA SUDAH diperbaiki chief di
v0.3.1, gate kini 18/18** (tes baru `quoter_g1_g6` 44/44):
G1 (klaim "0 fallback" salah; factory `0x9cb2...` = Aero Slipstream, bukan
Dromos — venue NVDAc 6 / AAPLc 4, 0 fallback), G2 (guard eligibilitas pool
+ token_out/venue dari pool terperiksa), G3 (guard partial-fill via batas
sqrt-price), G4 (decoder fail-closed, hanya outer "result"), G5 (label
jujur: `onchain_simulation` + layer B `simulated_exit_quote_verified`),
G6 (registry unknown/stale/mismatch = proposal-blocking).

**Live run v0.3.1 (22 Nov 23:08 WITA, block-pinned):** NVDAc → WATCH
(median $133,13; simulasi 78,82882882 token → estimate $10.498,05;
implisit $133,17523175, **+0,03398%**; block 60848518; oracle 1,000538,
paused=false; 11 pool/6 venue, 0 fallback). AAPLc → WATCH (median
$350,06; simulasi 30,00171438 token → estimate $10.497,79; implisit
$349,90640508, **−0,04388%**; block 60848636; oracle 1,000500,
paused=false; 6 pool/4 venue, 0 fallback). Keduanya cash 1.0, gate
proposal TETAP MATI. **RPC transcript** (`evidence/rpc/`, 16 file +
manifest): replay byte-exact — amount_out, sqrt-price, ticks, oracle
multiplier, block hash cocok persis dengan snapshot.

**Kill-switch 30 Nov = komitmen OPERASIONAL (bukan cutoff otomatis di
kode):** bila fase quoter tidak selesai / tidak feasible sebelum itu,
prototipe berhenti di situ — tidak ada kode yang mematikan prototipe
otomatis pada 30 Nov. Review 28 Nov tetap jalan. **v0.3.1 kini RESMI ACC
(tahap read-only) — re-audit v6, 8,5/10, 22 Nov 23:28 WITA.** Persiapan
submit (form + post X + video demo) TETAP DITUNDA sampai prototipe lolos
(perintah Septian 22 Nov 22:16).

---

## ARSIP — bagian bawah memo ini (dari "Ringkasan satu kalimat" ke bawah)
adalah status PRA-QUOTER (v0.2.x) dan TIDAK LAGI berlaku sebagai status
terkini: quoter SUDAH terpasang (v0.3.0/v0.3.1), registry SUDAH dibaca tiap
run, gate kini 18/18 (bukan 16/16), dan pilihan A/B sudah diputuskan
(Septian pilih Opsi A, GO Terbatas, 22 Nov 22:03 WITA). Bagian arsip
disimpan sebagai riwayat audit, bukan sebagai dasar keputusan.

## Update 22 Nov 22:37 WITA — adapter quoter v0.3.0 SELESAI (ACC Septian 22:22)

**STOP CONDITION TIDAK terpicu — quoter feasible read-only.** Adapter
sell-quote Dromos Metaquoter V3 (`quoteExactInputSingleV3`, satu eth_call
ke RPC publik, tanpa key/wallet/signing/gas) + baca registry pause
`getOracleParams` tiap run + label venue dari factory on-chain. ACC
Septian "Ya, bangun adapter quoter" (22 Nov 22:22 WITA).

**Gate: 17/17 PASS** (9 lama + 7 pasca-audit + 1 baru quoter_adapter 20/20).
Versi policy/method/schema v0.3.0. **Live run v0.3.0 (22 Nov ~22:37 WITA):**
- NVDAc → WATCH, **layer B VERIFIED** (79,01 token → $10.500,54; harga
  implisit $132,88 vs median $132,89). Oracle: multiplier 1,000538 (cocok
  API Coinbase), paused=false, registry active. Coverage 11 pool/7 venue.
- AAPLc → WATCH, **layer B VERIFIED** (30,04 token → $10.498,14; harga
  implisit $349,43 vs median $349,80). Oracle: multiplier 1,000500,
  paused=false. Coverage 6 pool/5 venue.
- **KOREKSI (re-audit v5, 22 Nov 22:50):** angka implisit di atas SALAH.
  Yang benar dari evidence v5: NVDAc **132,90683259 (+0,01267%)**, AAPLc
  **349,44823226 (−0,10099%)**. Label "Dromos" juga SALAH — factory
  `0x9cb2...` = **Aero Slipstream**, venue NVDAc 6 / AAPLc 4 (bukan 7/5).
  Label layer B "VERIFIED" juga diganti di v0.3.1 menjadi
  `simulated_exit_quote_verified` (G5). Lihat CURRENT_STATUS di atas.
- Keduanya tetap WATCH (alasan: `dex_deviation_watch`,
  `nav_stale_off_hours`) + cash 1.0 — **gate proposal TETAP MATI**
  (PAPER_PROPOSALS_ENABLED = False). PAPER_PROPOSAL tidak terjangkau
  sampai review ulang, meski layer B sudah verified. By-design.
- **Venue utama = Dromos, bukan Aerodrome** (factory pool = Dromos
  CLFactory `0x9cb2...`; label `dexId: aero` DexScreener menyesatkan).
  Venue kini dari factory on-chain; semua pool berhasil dibaca factory-nya
  (0 fallback). Factory Aerodrome saat ini `0xf8f2...` (CLFactory,
  diverifikasi BaseScan 22 Nov) ditambahkan ke pemetaan — factory lama
  `0x5e7B...` tetap ada sebagai legacy.
  **(KOREKSI v0.3.1: "Dromos" = Aero Slipstream; lihat CURRENT_STATUS.)**
- **Arti pause (mengikat):** `paused = true` = pause ORACLE (feed Chainlink
  beku, NAV basi), BUKAN pause transfer. Bila paused, NAV ditandai basi
  (kode baru `nav_paused_corporate_action`, proposal-blocking → WATCH),
  tapi quote DEX tetap valid sebagai bukti exit.
- **kind "firm":** quote Metaquoter adalah simulasi on-chain eksak saat
  call (eth_call, deterministik dari state pool), BUKAN komitmen eksekusi
  bertanda tangan. Perlindungan sebenarnya = validator E1 (sanity ±10% +
  notional + allowlist USDC), bukan label kind semata. Eksekusi di luar
  scope; tidak ada transaksi yang dikirim.

**Sisa menuju review 28 Nov:** re-audit v5 (targeted: quoter + registry +
venue) oleh Instinct; kill-switch 30 Nov tetap jalan. Persiapan submit
(form + post X + video demo) TETAP DITUNDA sampai prototipe lolos
(perintah Septian 22 Nov 22:16).

## Update 22 Nov 22:03 WITA — re-audit v4 BERSIH (10/10) + Base RESMI masuk fase quoter (Opsi A)

Re-audit v4 Instinct: **BERSIH, 10/10 untuk scope ini.** F1 terbukti beres
(alamat dicocokkan sendiri ke CoinGecko; probe: USDC asli verified,
DAI/mangled/SCAMCOIN invalid). Gate 16/16 jalan dari code zip saja, repro
A-D tetap lolos, quoter tetap belum dipasang, live v0.2.2 WATCH semua.

**Keputusan Septian (22 Nov 22:03 WITA): syarat review 28 Nov SUDAH
terpenuhi (A-D ✅ E1-E3 ✅ F1 ✅). Base RESMI masuk fase quoter sesuai
Opsi A (GO Terbatas). Lane chief sekarang: riset sell-quote adapter +
baca registry pause.**

**STOP CONDITION (mengikat, dari Septian): quoter TIDAK feasible
read-only = STOP, jangan dipaksa.** Artinya: adapter sell-quote HANYA
boleh jalan read-only (eth_call/static call / API publik tanpa signing,
tanpa gas, tanpa wallet, tanpa transaksi). Bila tidak ada jalur read-only
yang layak → STOP, lapor, jangan bangun quoter yang butuh signing/transaksi.
**Kill-switch 30 Nov TETAP jalan** — bila fase quoter tidak selesai /
tidak feasible sebelum itu, prototipe berhenti di situ.

## Update 22 Nov 21:53+ WITA — re-audit v3 Instinct (8/10) + must-fix F1 selesai

Re-audit v3 Instinct (skor kejujuran **8/10**, turun dari 8,5 karena F1):
E1-E3 TERBUKTI semua (gate 16/16 di-run sendiri, repro A-D tetap lolos,
snapshot v0.2.1 self-consistent, README angka segar cocok, quoter tetap
belum dipasang, gate mati). **TAPI** 1 must-fix baru (F1) — sudah diperbaiki
chief di v0.2.2 (gate tetap **16/16**, quote validation naik jadi 31/31):
- **F1. KEDUA alamat USDC di allowlist v0.2.1 SALAH.** Alamat yang ditulis
  "native USDC" (`...bd029029`) berbeda di 8 hex terakhir dari yang asli
  (`...bda02913`) — alamat mangled, bukan token apa pun. Alamat yang
  ditulis "USDC.e" (`0x50c5...`) ternyata **DAI bridged**, bukan USDC.e.
  Efeknya bila quoter dipasang: quote yang dibayar USDC asli DITOLAK,
  quote yang dibayar DAI DITERIMA sebagai bukti exit USDC. Gate tidak
  menangkap karena fixture tes memakai alamat salah yang SAMA (self-referential).
  Fix: allowlist diganti 2 alamat yang **DIVERIFIKASI ke 2 sumber independen
  sebelum ditulis** (BaseScan token page + CoinGecko API, 22 Nov 2026):
  native USDC `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` (BaseScan: "USDC
  (USDC) | ERC-20", FiatTokenProxy Circle) + USDC.e/USDbC
  `0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA` (CoinGecko: "Bridged USDC
  (Base)"). Tes `_valid_quote` sekarang pakai alamat literal (bukan
  konstanta config) supaya kesalahan konstanta ketahuan, bukan dikonfirmasi.
  4 kasus regresi F1: USDC native asli + USDC.e asli -> verified; DAI +
  mangled lama -> invalid `exit_quote_token_out_not_usdc`. Probe independen
  (pakai config, bukan literal tes): USDC asli verified, DAI invalid.
  Pelajaran permanen: konstanta keamanan JANGAN PERNAH diketik dari ingatan.
- **Minor (re-audit v3):** zip code-v3 sendirian tidak bisa menjalankan
  gate (3 tes butuh folder evidence/). Fix: code zip v4 kini MEMBUNDLING
  evidence/ (gate jalan dari code zip saja). Manifest evidence di-refresh
  (capture 13:55 UTC, label v0.2.2, 7/7 HTTP 200).
- **Tambahan:** gate_results.json memuat run time, sha256 source, test
  config; evidence capture + manifest hash; raw GeckoTerminal AAPLc sudah
  ada. **Quoter TETAP belum dipasang; PAPER_PROPOSAL tetap tidak terjangkau
  (gate mati) — sesuai batas keras audit.** Setelah F1 beres + tes regresi
  alamat asli masuk, prototipe siap dibawa ke review 28 Nov untuk bahasan
  fase quoter.

## Update 22 Nov 21:40+ WITA — re-audit v2 Instinct (8,5/10) + must-fix E1-E3 selesai

Re-audit v2 Instinct (skor kejujuran **8,5/10**, naik dari 8): gate 15/15
di-run sendiri = PASS; A, B, D TERBUKTI bener (quote kosong sekarang WATCH
cash 1.0, freshness per jenis data, dedup error eksplisit + lock); batas
keras dipegang (quoter BELUM dipasang, gate mati, live NVDAc tetap WATCH).
**TAPI** 3 must-fix baru — semuanya sudah diperbaiki chief di v0.2.1
(gate kini **16/16**):
- **E1. Validator quote masih kelonggaran.** Tiga probe lolos sebagai
  `verified` di v0.2.0: quote tanpa field `kind` (default ke firm), token_out
  `"SCAMCOIN"`, dan `amount_out_min=1.0` + `notional_usd=1e12`. Fix: kind
  WAJIB (tanpa label -> `exit_quote_kind_missing`, tidak dianggap firm);
  token_out allowlist alamat USDC Base eksplisit (native USDC +
  USDC.e bridged; `"SCAMCOIN"` -> `exit_quote_token_out_not_usdc`); sanity
  harga (harga implisit amount_out_min/amount_in dalam ±10% median) +
  notional dihitung dari amount_in x median (harus >= nominal proposal) +
  konsistensi notional dinyatakan vs dihitung (rasio 2x). Tidak masalah
  SEKARANG selama gate mati, tapi WAJIB beres sebelum gate dinyalakan —
  sekarang sudah beres + 5 kasus baru di tes A (27/27).
- **E2. Bug baru — snapshot live v0.2 ASLI ditandai "transformed replay".**
  `build_snapshot` menghitung venue dari dex mentah (7, aero/aerodrome
  terpisah) dan hash atas nilai itu, lalu `assess_snapshot` menimpa
  coverage jadi 6 — hash != isi file. Fix: build hitung coverage dari venue
  KANONIS (hash atas nilai final); assess TIDAK LAGI mutasi snap["coverage"]
  (hasil hitung ulang hanya di assessment.coverage_recomputed; `explain`
  pakai nilai recomputed). Tes baru `snapshot_identity_live_build` (8/8):
  build -> assess -> public_snapshot -> replay, identitas cocok, stored ==
  recomputed. Catatan: file live v0.2.0 lama (snap-a7da34c2855e4e92) tetap
  tidak konsisten secara konstruksi — artefak historis, bukan target fix.
  Snapshot live BARU v0.2.1 (NVDAc + AAPLc) self-consistent, identitas cocok.
- **E3 (minor). Dokumen basi.** README masih angka run v0.1; AAPLc belum
  di-run di v0.2; out/ campur v0.1/v0.2 + file .lock. Fix: live run ulang
  NVDAc + AAPLc di v0.2.1 (22 Nov 13:45 UTC), README angka segar per token
  + tanggal run, zip evidence dipisah per versi (out/v0.2.1/ + evidence/,
  tanpa .lock).
- **Tambahan:** gate_results.json memuat run time, sha256 source, test
  config; evidence capture + manifest hash; raw GeckoTerminal AAPLc sudah
  ada. **Quoter TETAP belum dipasang; PAPER_PROPOSAL tetap tidak terjangkau
  (gate mati) — sesuai batas keras audit.**

## Update 22 Nov 21:20+ WITA — audit final Instinct + must-fix selesai

Audit final Instinct (skor kejujuran **8/10**, naik dari 7 setelah source
masuk): gate 9/9 di-re-run sendiri hasilnya **IDENTIK**; keempat koreksi
§3 terbukti ada di kode; live run jujur (WATCH semua, full cash).
**TAPI** ditemukan 4 must-fix yang lolos dari gate lama — semuanya sudah
diperbaiki chief + regression tests ditambahkan (gate kini **15/15**):
- **A. Quote kosong meloloskan proposal.** Guard exit-evidence hanya cek
  `exit_quote is None` — quote `{}` menghasilkan PAPER_PROPOSAL 9%.
  Fix: validator quote eksplisit (`verified`/`invalid`/`missing`/`stale`,
  cek chain/token/side/jumlah/output/notional/waktu/expiry/jenis quote) +
  feature gate `PAPER_PROPOSALS_ENABLED = False` (proposal TIDAK PERNAH
  keluar selama gate mati, apa pun isi quote). Invariant: PAPER_PROPOSAL
  selalu mensyaratkan layer B verified.
- **B. Freshness pool/quote belum diimplementasi.** `MAX_POOL_AGE_MIN` ada
  di config tapi tidak dipakai. Fix: freshness per-jenis-data (pool dari
  `fetched_at` + timestamp harga sumber; quote dari `quoted_at`/`expires_at`;
  NAV dari timestamp vs jam evaluasi + sesi pasar NYSE minimal), reason
  codes terpisah, `eval_at` injectable, replay berlabel replay.
- **C. Replay percaya chain + coverage turunan.** Chain tidak divalidasi,
  count tersimpan dipercaya. Fix: validasi chain+contract+symbol+decimals;
  coverage dihitung ulang dari pool tervalidasi (dedup case-insensitive,
  venue dikanonisasi: `aero` == `aerodrome`, min 2 venue kanonis);
  identitas snapshot divalidasi via hash payload awal (diubah -> ditandai
  `snapshot_transformed_replay`).
- **D. Dedup gagal diam-diam.** Error baca/tulis ditelan, emit dilaporkan
  sukses. Fix: error eksplisit terstruktur (`ok` + `error{stage,type,
  message}`), bedakan first-run vs corrupt vs permission; tulis atomik
  (temp + os.replace) + file lock (dua worker bersamaan -> tepat satu emit
  baru). Pemanggil WAJIB cek `ok` (run.py sudah diperbarui).
- **Tambahan §3:** happy-path parametrik NVDAc+AAPLc via adapter mock dari
  raw capture; test NAV/multiplier pada build; output gate memuat run time,
  identitas source (sha256), dan test config; evidence capture
  (`capture_evidence.py`) + manifest hash; raw GeckoTerminal AAPLc sudah
  ada. **Quoter TETAP belum dipasang; PAPER_PROPOSAL tetap tidak terjangkau
  (gate mati) — sesuai batas keras audit.**

## Ringkasan satu kalimat

Plumbing alert end-to-end terbukti jalan (9/9), tapi prototipe ini masih
**monitor indikatif** — belum ada bukti exit (sell quote) — sehingga
pembeda produk ("bisa keluar, dengan bukti harga seperti apa?") **belum
terbukti**.

## Apa yang lulus

- **Gate: 16/16 PASS** (9 lama + 7 baru pasca-audit; terverifikasi chief
  dengan `python3 gate.py`, 22 Nov ~21:56 WITA). Happy path 10/10, NAV
  weekend 8/8, multiplier 4/4, liquidity vs exit 5/5, quote validation
  31/31 (termasuk 4 kasus F1: USDC asli + USDC.e verified, DAI + mangled
  lama invalid), freshness 13/13, coverage recomputed 11/11, snapshot
  identity live-build 8/8, dedup persistence 10/10, happy-path kedua
  token 16/16, NAV/multiplier build 8/8. Hasil di `out/gate_log.md` +
  `out/gate_results.json` (memuat run time, sha256 source, dan test config).
- **Ingest live berfungsi.** NVDAc + AAPLc teridentifikasi via Coinbase API
  (tanpa key); pool nyata terkonfirmasi (Aerodrome Slipstream); proxy
  underlying `xyz:NVDA` / `xyz:AAPL` ditemukan di Hyperliquid
  (`metaAndAssetCtxs`). Respons mentah tersimpan di `evidence/`.
- **Keputusan jujur.** Live run: NVDAc → WATCH, AAPLc → WATCH. Keduanya
  menahan seluruh alokasi simulasi di cash (`cash_weight: 1.0`,
  `weights: {}`) karena tidak ada bukti exit. Tidak ada usulan beli palsu.
- **Koreksi Instinct §3 diterapkan dan terbukti:** NAV tidak dikali multiplier
  lagi (tes multiplier 4/4); dua agregator baca pool sama = satu pool
  (tes coverage); gap DEX-vs-NAV hanya deskripsi berlabel (bukan mispricing);
  TVL tidak dipakai sebagai bukti exit (tes liquidity vs exit); proxy
  dilabeli terpisah dan tidak memicu alert token-exit (tes proxy).
- **Replay + idempotensi berfungsi.** Snapshot publik dapat di-replay
  (`run.py --replay`), alert tidak terduplikasi, alert replay berlabel
  `TEST/REPLAY`. Bug replay (`KeyError: '_token_ok'`) ditemukan saat
  verifikasi chief dan sudah diperbaiki (lihat `DESIGN.md` §9).
- **Batas fase dipegang.** Tidak ada onchain, tidak ada deploy, tidak ada
  ubah Radar live, tidak ada kirim alert ke Telegram produksi, tidak ada
  pendaftaran kompetisi. Semua lokal/offline.

## Apa yang gagal / terbatas (jujur)

- **Tidak ada sell-quote adapter → tidak ada bukti exit.** Ini keterbatasan
  terbesar dan struktural, bukan bug. Status exit selalu
  `indicative_only/exit_quality_unverified`. Prototipe ini memonitor kondisi
  indikatif; **tidak cukup untuk mengklaim exit-quality atau mengizinkan
  usulan beli berbasis bukti exit.** (Sesuai §7 brief: ketiadaan executable
  quote tidak menggagalkan demonstrasi plumbing, tapi membatasi hasil menjadi
  monitor indikatif.)
- **Registry pause tidak dibaca.** `registry_pause_status: unknown`
  (butuh RPC read-only; di luar scope adapter HTTP). Bila registry ternyata
  pause, prototipe tidak akan tahu.
- **Coverage lintas-venue tipis.** Efektif 1 pool dominan per token
  (Aerodrome). Median dari 2 observasi rapuh. Belum ada sensus venue lengkap.
- **Threshold belum tervalidasi.** DEV_WATCH 2% / DEV_ABSTAIN 5% adalah
  tebakan awal versioned — tidak ada data false-positive / false-negative.
  Kalibrasi butuh seri historis + definisi outcome.
- **Tidak ada bukti kualitas prediktif.** Lolos test teknis bukan bukti
  kualitas prediktif atau keuntungan. Tidak ada backtest, tidak ada outcome.
- **PoR + redemption tetap `unknown`.** Tidak ada sumber otomatis. Ini
  batas jujur, bukan kegagalan — tapi artinya skor "exit-ability setara
  Solana" tidak bisa dibangun dari prototipe ini.

## Apa yang masih unknown

- Apakah sell-quote adapter feasible untuk token ini (quoter Aerodrome
  Slipstream / API quoter lain)? Belum diteliti. Ini penentu apakah
  pembeda produk bisa dibuktikan.
- Apakah registry pause bisa dibaca via RPC publik Base (read-only)?
  Belum dicoba.
- Apakah ada venue/pool lain yang material di luar Aerodrome? Belum disensus.
- Apakah rubrik kompetisi menghargai paper-portfolio / testnet? Masih
  terbuka (bukan diselesaikan gate teknis ini).
- Apakah bobot traction 50/25/25 adalah rules resmi? Tidak terverifikasi —
  jangan diasumsikan.

## Estimasi sisa pekerjaan (berdasarkan source yang benar-benar diperiksa)

| Pekerjaan | Estimasi | Keterangan |
|---|---|---|
| Riset + bangun sell-quote adapter (read-only) | 0,5–1 hari | Tentukan quoter (Aerodrome Slipstream / API). Bila quoter tidak ada / tidak bisa dipakai read-only → blocker, STOP untuk klaim exit-quality. |
| Baca registry pause via RPC publik Base | 1–2 jam | Butuh endpoint RPC publik read-only. |
| Sensus venue/pool tambahan | 2–3 jam | Cek DEX lain di Base untuk NVDAc/AAPLc. |
| Kalibrasi threshold (historis) | Di luar jendela | Butuh seri historis + definisi outcome; tidak bisa selesai sebelum 28 Nov secara kredibel. Threshold tetap eksperimen. |
| Desain hash registry Base Sepolia (§8) | Sudah ada di `DESIGN.md` §8 | Spesifikasi saja; deploy menunggu gate + ACC. |
| QA + submission (bila lanjut) | 1–3 Des QA, 4 Des submit (buffer) | Hanya sesudah gate + ACC eksplisit. Deadline resmi 5 Des 23:59 UTC = 6 Des 07:59 WITA. |

## Pilihan: GO terbatas atau STOP

**Opsi A — GO TERBATAS (rekomendasi chief).**
Lanjutkan **hanya** ke satu langkah berikutnya yang terdefinisi: riset +
bangun sell-quote adapter + baca registry pause, lalu jalankan ulang gate.
Batas waktu: selesai sebelum review 28 Nov. **Stop condition keras:** bila
quoter terbukti tidak feasible (tidak ada quoter read-only yang bisa
dipakai), berhenti — jangan klaim exit-quality dari monitor indikatif.
Bila quoter jalan, prototipe menjadi monitor bukti-exit yang jujur, dan
keputusan lanjut ke QA/submission dibahas lagi dengan ACC eksplisit.

Alasan: plumbing sudah terbukti (9/9). Quoter adalah satu-satunya blocker
untuk pembeda produk. Langkahnya kecil dan terdefinisi. Risiko terbatas
(kill-switch 30 Nov tetap berlaku).

**Opsi B — STOP.**
Berhenti di sini. Prototipe disimpan sebagai bukti teknis (plumbing +
gate) tanpa dilanjutkan ke kompetisi. Alasan yang sah: sisa waktu
(8 hari ke kill-switch 30 Nov) tidak cukup untuk quoter + kalibrasi +
onchain + QA + submission secara kredibel; atau Septian menilai monitor
indikatif saja tidak cukup kuat sebagai entry kompetisi.

**Yang tidak direkomendasikan:** lanjut ke build penuh / submission dengan
menganggap monitor indikatif ini sudah membuktikan exit-quality. Itu
overclaim — bertentangan dengan brief Instinct §7 dan dengan kejujuran
produk ("bisa keluar, dengan bukti harga seperti apa?").

## Keputusan yang diminta dari Alex

Pilih **Opsi A (GO terbatas, ke quoter + registry)** atau **Opsi B (STOP)**.
Bila Opsi A, chief lanjut ke riset quoter. Bila Opsi B, prototipe diarsipkan
dan tidak ada pekerjaan Base lebih lanjut sebelum keputusan baru.
