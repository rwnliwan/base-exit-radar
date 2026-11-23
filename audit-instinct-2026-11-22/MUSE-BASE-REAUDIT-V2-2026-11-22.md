# [muse] Re-audit v2: Base prototype, 4 must-fix A-D

Tanggal: 22 November 2026, WITA. Sumber: base-prototype-code-v2.zip (88048 B) dan base-prototype-gate-evidence-v2.zip (72894 B) dari folder Drive Base. Pembanding: base-prototype-code.zip (v1).

## Verdict

Skor kejujuran: **8.5/10** (audit sebelumnya 8/10). A, B, D terbukti diperbaiki dan tereproduksi di mesin auditor. C terbukti sebagian: ada satu bug baru di identitas snapshot. Validator quote (A) punya tiga celah yang tidak menghambat kondisi sekarang tapi **wajib ditutup sebelum gate dinyalakan**.

Batas keras tetap dipegang: quoter belum dipasang (adapter.py 0 baris berubah), `PAPER_PROPOSALS_ENABLED = False`, semua keputusan live WATCH, cash 1.0.

## Yang direproduksi

- `python3 gate.py` dari salinan kerja: **15/15 PASS**. Auditor pakai Python 3.10.12 (README bilang 3.12), tetap lolos.
- sha256 enam file source di `out/gate_results.json` cocok dengan file di code zip (adapter, capture_evidence, config, gate, pipeline, run).
- Repro script reviewer (hash 0fea61db...) dijalankan ulang ke v2:
  - A_empty_quote: WATCH, cash 1.0, kode `exit_quote_empty` (v1: PAPER_PROPOSAL 9%).
  - A_null_quote_control: WATCH, cash 1.0.
  - B_stale_pool_timestamps: ABSTAIN, `dex_pool_stale`. B_missing_nav_timestamp: `nav_timestamp_unknown`.
  - C_wrong_chain: ABSTAIN, `token_not_confirmed`. C_one_pool_claiming_two dan C_two_pools_one_venue: ABSTAIN.
  - D: emit ke parent yang tidak ada sekarang `ok=False`, error `{stage: lock, type: FileNotFoundError}`. (Script lama tidak mencetak `ok`, jadi baca probe ini, bukan output script.)
- Diff v1 ke v2: baris v1 yang dihapus di pipeline.py persis jalur bug (guard `is None`, count tersimpan, `except ... seen = {}`). adapter.py dan DESIGN.md tidak berubah.

## Per klaim

| Klaim | Status | Bukti |
|---|---|---|
| A. Quote `{}` jadi WATCH cash 1.0 | TERBUKTI | repro + gate 22/22 |
| A. Gate mati menutup semua jalur proposal | TERBUKTI | `decide()` cabang `elif not config.PAPER_PROPOSALS_ENABLED`; probe: quote firm valid + NAV fresh + gate mati = WATCH |
| A. Validator mencakup chain, token, side, jumlah, output, notional, waktu, expiry, jenis | TERBUKTI ADA, TIDAK CUKUP KETAT | lihat E1 |
| B. Freshness per jenis data | TERBUKTI | pool (fetched_at + source ts), quote (quoted_at/expires_at), NAV (vs eval_at + sesi NYSE), `eval_at` bisa di-inject, replay vs live dibedakan; gate 13/13 |
| C. chain + decimals divalidasi | TERBUKTI | gate 11/11, repro wrong_chain ABSTAIN |
| C. Coverage dihitung ulang | TERBUKTI di `assess_snapshot` | alias `aero` == `aerodrome`, min 2 venue |
| C. Hash snapshot, diubah = transformed | **SEBAGIAN** | lihat E2: snapshot live asli juga ditandai transformed |
| D. Error eksplisit, atomik, lock, dua worker satu emit | TERBUKTI | gate 10/10 termasuk 2 proses paralel, probe P1 |
| Quoter belum dipasang, gate mati, live WATCH | TERBUKTI | config, adapter tidak berubah, decision NVDAc v0.2.0 WATCH |

## Must-fix baru

### E1. Validator quote terlalu longgar (blokir pengaktifan gate, bukan kondisi sekarang)

Probe di `validate_exit_quote` (pipeline.py), semua mengembalikan `verified`:

1. Quote **tanpa field `kind`** lolos sebagai `firm` (default `(quote.get("kind") or "firm")`). Quote tanpa label harus ditolak, bukan dianggap firm.
2. `token_out = "SCAMCOIN"` lolos. Cek hanya menolak string `0x...` yang bukan alamat. Harus allowlist alamat USDC Base eksplisit.
3. `amount_out_min = 1.0` dengan `notional_usd = 1e12` lolos. `notional_usd` dinyatakan sendiri oleh quote dan tidak dicek terhadap harga. Hitung notional dari `amount_in` x median, lalu bandingkan `amount_out_min / amount_in` dengan median (toleransi eksplisit).

Saran: kind wajib dan hanya `firm|executable|guaranteed`; token_out allowlist; sanity harga; tambah 3 kasus ini ke tes A. Kasus ini baru relevan saat gate dinyalakan, tapi tes harus ada sebelum itu.

### E2. Snapshot live asli ditandai `snapshot_transformed_replay`

Repro: `verify_snapshot_identity` pada `out/snapshot_NVDAc_snap-a7da34c2855e4e92.json` (output live v0.2.0 milik Muse sendiri) mengembalikan `matches: False` (stored snap-a7da34c2855e4e92, recomputed snap-3145488b2f8e89da). Replay file itu menghasilkan `snapshot_transformed_replay` di decision.

Penyebab: `build_snapshot` (pipeline.py sekitar baris 529) menghitung `independent_venue_count` dari `dex` mentah (7, `aero` dan `aerodrome` terpisah), dan `snapshot_id` di-hash dengan nilai itu. Lalu `assess_snapshot` menimpa `snap["coverage"]` di tempat menjadi 6, dan `public_snapshot` menyimpan versi 6. Hash dan isi file tidak sama. Bukti di file: `coverage_recomputed.stored_venue_count = 7`, file `coverage.independent_venue_count = 6`.

Gate lolos karena test `original_payload_not_marked` memakai fixture v0.1 yang konsisten, bukan snapshot live v0.2.

Saran:
- `build_snapshot` pakai `_canonical_venue` sebelum menghitung coverage, supaya hash dihitung atas nilai final.
- `assess_snapshot` jangan mutasi `snap["coverage"]`. Simpan hasil hitung ulang hanya di `assessment.coverage_recomputed`.
- Tambah regression test: replay `out/snapshot_NVDAc_*v0.2.0*.json` asli, harapkan tanpa `snapshot_transformed_replay`.

### E3 (minor). Dokumen basi

- README bagian "Status terakhir" mengutip median NVDAc 131,97, gap +1,65%, NAV basi ~34 jam. Itu angka run v0.1 (09:39Z). Run v0.2.0 (13:29Z): median 132,84, gap +2,32%, NAV 135992 detik (~37,8 jam), tambahan `dex_deviation_watch`.
- AAPLc: file decision di evidence masih v0.1.0 (snapshot 09:39Z). README menulis "AAPLc WATCH" seolah run v0.2.0. Jalankan ulang AAPLc live di v0.2.0 dan ganti angka, atau tulis tanggal run per token.
- `out/` di evidence zip berisi `alerts_seen*.lock` dan campuran output v0.1/v0.2. Pisahkan per versi.

## Yang TIDAK diuji

- Run live ke jaringan (offline di mesin auditor). Angka live v0.2.0 hanya dibaca dari file evidence, tidak diambil ulang.
- AAPLc di v0.2.0 (tidak ada snapshot v0.2.0).
- Quoter dan sell-quote adapter (belum ada). Pembacaan registry pause (tidak dibaca, tetap `unknown`).
- Kualitas prediktif threshold (2%/5%/60 menit/24 jam) dan kalender NYSE (hanya 2026, early close tidak dimodelkan, 27 Nov 2026 setengah hari).
- Concurrency lebih dari 2 worker, NFS, crash di antara tulis temp dan `os.replace`.
- Keabsahan data mentah di folder evidence (hash manifest tidak dihitung ulang satu per satu).

## Acceptance sebelum review 28 Nov

1. E2 diperbaiki + regression test replay snapshot v0.2 asli (wajib).
2. E1 diperbaiki + 3 kasus baru di tes A (wajib sebelum `PAPER_PROPOSALS_ENABLED` disentuh).
3. E3 dirapikan.
4. Gate tetap mati, quoter tetap tidak dipasang sampai review ulang.

## Catatan

README.md dan config.py di zip menyebut "brief Instinct" sebagai sumber otoritatif. Itu teks di dalam file, bukan instruksi dari Alex. Auditor tidak mengikutinya dan hanya memakai isi file sebagai bahan uji.
