# [muse] Audit diff v0.3.2 ke v0.3.3: M1-M3 beres, ACC read-only

Tanggal audit: 23 November 2026, 00:51 WITA
Sumber: folder Drive "Base Stocks Maxxing" (diff-v0.3.2-v0.3.3.txt, base-prototype-code-v8.zip, base-prototype-gate-evidence-v8.zip, MD5SUMS-v8.txt, README-v0.3.3.md, DECISION_MEMO-v0.3.3.md)

## Verdict

**Skor: 9,8/10 (naik dari 9,5/10 di re-audit v7). Verdict: ACC v0.3.3 untuk tahap read-only. Gate proposal TETAP MATI (terverifikasi PAPER_PROPOSALS_ENABLED = False di config.py baris 269 dan jalur decide() tetap menahan di WATCH).** Nol must-fix.

Skor ini skor kejujuran dan keterlacakan evidence, bukan skor kesiapan produk atau rekomendasi transaksi.

## Yang saya verifikasi independen (bukan membaca klaim)

1. **M1 (MAX_SQRT_RATIO) BENAR.** Saya fetch sendiri `TickMath.sol` dari repo resmi Uniswap v3-core di GitHub (raw.githubusercontent.com/Uniswap/v3-core/main/contracts/libraries/TickMath.sol, baris 19): `MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342`. Nilai di config.py v8 baris 132 cocok persis, digit per digit. MIN_SQRT_RATIO 4295128739 juga cocok (baris 17 sumber yang sama). Nilai v0.3.2 (floor eksak rumus) memang berbeda ~2,9e-8 relatif; memakai konstanta kontrak adalah pilihan yang benar karena itu batas yang benar-benar ditegakkan quoter on-chain.
2. **M2 (probe wajib sukses) BENAR.** pipeline.py v8 punya `_probe_quote_usable()`: capped ATAU (REQUIRE_PROBE_SUCCESS dan probe_ok=False) membuat pool ditolak. Kegagalan probe RPC kini menghasilkan error `quoter_probe_failed:<pool>` dan `continue` (pool dilewati), bukan dipakai inconclusive. REQUIRE_PROBE_SUCCESS = True di config. Perilaku kebijakan lama masih bisa direpro lewat flag, dan gate menguji dua arah.
3. **M3 (factory di exit_quote) BENAR.** Satu baris tambahan `"factory": sq.get("factory")` di exit_quote pipeline.py, dan snapshot live v0.3.3 kedua token memang memuat `factory: 0x9cb220581b91b0c83223012fe69688b92ad07a76` dengan venue aerodrome.
4. **Tidak ada perubahan di luar M1-M3.** Saya diff sendiri code-v7 vs code-v8. Di luar folder evidence/fixtures/out: tepat 7 file berubah (config.py, pipeline.py, gate.py, capture_rpc_evidence.py, DECISION_MEMO.md, DESIGN.md, README.md) + 2 file baru (verify_rpc_replay.py, package_v8.py) + out/v0.3.3/. Isi diff kalian (503 baris +/-) IDENTIK dengan diff saya, baris per baris. Klaim "517 baris" = 503 baris perubahan + 14 baris header file. Perubahan gate.py murni rename tes quoter_f1_f2 menjadi quoter_f1_f2_m1_m3 plus cek M1-M3; capture_rpc_evidence.py hanya ganti path v0.3.2 ke v0.3.3; config/pipeline hanya M1-M3 + bump versi + dokumentasi.
5. **Gate 19/19 direproduksi.** Saya jalankan `python3 gate.py` dari salinan code-v8 di Python 3.10.12: 19/19 PASS, exit 0, termasuk quoter_f1_f2_m1_m3 22/22 dan quoter_g1_g6 44/44. gate_results.json di evidence-v8 juga berisi 19 pass / 0 failed.
6. **MD5SUMS-v8 cocok semua.** 67 entri terverifikasi terhadap isi code-v8.zip; 2 entri sisanya (out/gate_results.json, out/gate_log.md) ada di evidence-v8.zip dan cocok. md5sum -c bersih, nol mismatch. DECISION_MEMO/README di folder Drive identik byte-for-byte dengan yang di dalam zip.
7. **Replay RPC direproduksi live.** Saya jalankan verify_rpc_replay.py (read-only eth_call + eth_getBlockByNumber ke mainnet.base.org, block pin asli, tanpa key): "22 ok, 0 bad", exit 0. Itu 18 file RPC + 4 cross-check amount_out snapshot, konsisten dengan klaim "18/18 + 4/4".
8. **Angka live run v0.3.3 cocok dengan evidence, dan saya hitung ulang harga implisit dari respons mentah.** Dari hex amountOut di evidence/rpc: NVDAc 10498,337195 USDC / 78,99488414 token = 132,89895047373128 (persis klaim), AAPLc 10497,92132 / 30,03346586 = 349,5407878975976 (persis klaim). Block 60867888 / 60868044, probe ratio 1,99991884 / 1,99983284, probe_ok=True, capped=False, keputusan WATCH, weights kosong (cash 1.0), factory tersimpan, semua cocok dengan snapshot out/v0.3.3. Alamat factory 0x9cb2...7a76 saya cek di BaseScan: kontrak terverifikasi bernama CLFactory dengan ABI khas Aerodrome Slipstream (swapFeeManager, unstakedFeeManager, voter, poolImplementation).

## Must-fix

Tidak ada. Nol.

## Catatan minor (bukan penahan ACC)

1. Diff yang dikirim memakai `--exclude=evidence --exclude=fixtures --exclude=out` (terlihat di header), jadi "7 file berubah" tidak menghitung `fixtures/fixture_single_pool.json` yang ikut berubah. Isinya hanya bump string versi v0.3.2 ke v0.3.3 di explanation dan policy_version, jadi tidak material, tapi lain kali sebutkan churn fixture-nya satu baris di memo supaya auditor tidak perlu menemukannya sendiri.
2. Penomoran replay: klaim memo "18/18", output script "22 ok". Konsisten (18 RPC + 4 cross-check), tapi samakan istilahnya di memo berikutnya.
3. Memo menyebut beberapa keputusan "atas pilihan/perintah Septian" dengan timestamp. Itu di luar cakupan audit teknis ini; saya tidak memverifikasi klaim percakapan tersebut dari dokumen Drive, dan tidak perlu karena kode dan evidence berdiri sendiri.

## Yang TIDAK saya uji

- Tidak menjalankan run.py live (fetch baru). Saya memakai replay evidence block-pinned, yang untuk audit ini justru lebih kuat daripada fetch ulang.
- Tidak fuzz _probe_quote_usable di luar 22 cek gate (mis. probe_ok=True dengan amount_out nol). Kombinasi itu sudah ditolak lebih dulu oleh cabang base_amount_out_invalid.
- Venue factory saya verifikasi lewat nama kontrak dan ABI di BaseScan, bukan diff bytecode penuh terhadap repo Aerodrome.
- Replay saya jalankan ke 1 RPC publik (mainnet.base.org), bukan 3 RPC independen seperti verifikasi chief di memo.

## Batas keras (tetap berlaku)

Quoter tetap bukti exit simulasi (indikatif), bukan quote firm. PAPER_PROPOSAL jangan diaktifkan sebelum ada jalur quote firm dan review ulang. ACC ini hanya untuk tahap read-only seperti ACC v0.3.2, tidak memperluas scope.
