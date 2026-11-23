# [muse] Review teknis: Base prototype, gate 9/9 dan empat must-fix

Tanggal audit: 22 November 2026, WITA  
Status: **9/9 gate bawaan ter-reproduksi identik. Belum lulus acceptance untuk integrasi quoter/proposal.**

## Batas keras

**Quoter JANGAN dipasang dan PAPER_PROPOSAL JANGAN diaktifkan sebelum A-D selesai, regression tests ditambahkan, dan hasilnya direview ulang.** Riset kelayakan quoter secara terpisah dapat berjalan, tanpa menghubungkannya ke jalur keputusan ini. Tidak ada rekomendasi transaksi riil dari audit ini.

## 1. Verdict dan cakupan

Skor kejujuran evidence: **8/10**. Ini skor transparansi dan keterlacakan evidence, bukan skor kesiapan produk atau kualitas investasi.

Yang sudah terverifikasi:

- Kelima source Python dibaca: `adapter.py`, `config.py`, `pipeline.py`, `run.py`, `gate.py`. Tujuh fixture tersedia.
- `gate.py` dijalankan offline pada salinan kerja, 22 November 2026 21:14:16 WITA. Hasil **9/9 PASS, exit code 0**. Objek JSON `gate_results.json` hasil audit identik dengan hasil yang dikirim.
- Kedua fixture live identik byte-for-byte dengan snapshot pada ZIP evidence. Kedua `snapshot_id` cocok ketika direkonstruksi dari payload awal menurut implementasi hash.
- Output live NVDAc dan AAPLc benar `WATCH`, `cash_weight=1.0`, `weights={}`. Tidak ada proposal beli dalam output live yang diserahkan.
- Jalur `build_snapshot -> assess -> decide` juga diuji dengan raw Coinbase, DexScreener dan Hyperliquid yang diserahkan. Keduanya tetap WATCH/all-cash.
- NAV tidak dikali multiplier lagi, terverifikasi di `pipeline.py:173-178,202-207`. Uji tambahan untuk kedua aset: input NAV 200 dan multiplier 3 menghasilkan NAV 200, bukan 600.
- Gap DEX-vs-NAV hanya deskripsi berlabel di `pipeline.py:375-386`. Pemicu deviasi di `388-393` memakai pool-vs-median, bukan gap NAV.
- TVL hanya filter/sorting, tidak dipakai sebagai bukti executable exit. Proxy berada di layer C terpisah, `400-416`; funding/OI tidak dipakai sebagai pemicu token-exit.

Namun, PASS menurut assertion suite saat ini tidak sama dengan semua invariant risiko benar. Empat kelompok temuan di bawah direproduksi dengan input terkontrol. Tidak satu pun menyatakan bahwa run live asli melakukan pembelian.

Nomor baris mengacu source ZIP yang diaudit, sebelum perubahan. Setelah perubahan, nomor akan bergeser.

## 2. Cara menjalankan reproduksi

Lampiran pendamping:

- `repro-base-audit-2026-11-22.py`: reproduksi A-D, offline, tidak menulis source/fixtures.
- `null_quote_fresh_nav.json`: kontrol, NAV fresh dan quote null, hasil WATCH.
- `empty_quote_fresh_nav.json`: kontrol identik kecuali quote kosong, hasil PAPER_PROPOSAL.
- `gate_results.json`: hasil rerun gate bawaan.

Jalankan script pada folder hasil ekstrak **source ZIP yang diaudit**:

```bash
python3 repro-base-audit-2026-11-22.py /path/to/base-prototype > audit-negative-results.json
```

Argumen folder harus berisi `pipeline.py`, `config.py`, dan `fixtures/`. Script menonaktifkan koneksi jaringan dan memakai direktori sementara untuk tes dedup. Gunakan source yang sudah diperiksa, bukan paket lain.

Untuk mengulang gate bawaan, gunakan **salinan kerja terpisah**, karena gate menulis ulang beberapa fixture dan output:

```bash
cp -R /path/to/base-prototype /tmp/base-prototype-gate-check
cd /tmp/base-prototype-gate-check
python3 gate.py
```

Audit ini tidak mengubah file asli atau isi Drive. Seluruh hasil eksekusi ditulis pada salinan kerja.

## A. Quote kosong meloloskan proposal tanpa bukti exit

**Prioritas: must-fix sebelum integrasi quoter atau aktivasi proposal.**

Lokasi:

- `pipeline.py:349-351`: layer B selalu diinisialisasi sebagai exit unverified.
- `pipeline.py:395-398`: ketiadaan adapter ditentukan hanya oleh `exit_quote is None`.
- `pipeline.py:468-497`: tidak ada reason code berarti PAPER_PROPOSAL.

### Reproduksi

1. Muat fixture live NVDAc.
2. Buat NAV fresh secara konsisten: `nav_price_updated_at = fetched_at - 1 detik`, `age_seconds=1`, session active.
3. Pertahankan input lain. Bandingkan `exit_quote=null` dengan `exit_quote={}`.
4. Jalankan `assess_snapshot -> decide -> explain`.

Hasil aktual:

| Input quote | Keputusan | Bobot NVDAc | Cash | Status layer B |
|---|---|---:|---:|---|
| null | WATCH | kosong | 1.0 | exit_quality_unverified |
| objek kosong | PAPER_PROPOSAL | 0.0909 | 0.9091 | exit_quality_unverified |

Bukti penentu: `empty_quote_fresh_nav.json`, dibandingkan dengan `null_quote_fresh_nav.json`. Keduanya adalah **fixture kontrol audit, bukan kejadian pasar live**. Pada kasus gagal, layer B tetap menampilkan `exit_quote=null`, tetapi proposal mengklaim bukti exit tersedia.

### Fix konkret

- Tambahkan validator quote yang mengembalikan status eksplisit, misalnya `verified`, `invalid`, `missing`, `stale`, beserta reason codes.
- Validasi chain, token in/out, side SELL, jumlah dan unit, notional yang dinilai, output minimum, route/venue, waktu quote, expiry, serta hasil/error dari sumber quote. Objek non-null bukan bukti valid.
- Bedakan quote indikatif, simulasi/quoter read-only, dan jaminan eksekusi. Jangan menamai quote sebagai jaminan fill.
- Keputusan proposal harus bergantung pada hasil validator yang valid, relevan dengan nominal, belum kedaluwarsa dan konsisten dengan layer B. Semua kegagalan harus menahan cash.
- Selama validator/quoter belum tersedia, buat feature gate eksplisit yang menolak PAPER_PROPOSAL pada live maupun replay. Jangan mengandalkan kebiasaan adapter mengisi None.

### Regression tests wajib

- null, objek kosong, string, list dan payload tanpa field wajib tidak boleh menghasilkan proposal.
- Wrong-chain/token/side/unit/amount, output nonpositif, NaN/Infinity, quote stale/future/error semuanya ditolak.
- Quote valid untuk nominal kecil tidak boleh dianggap memverifikasi nominal proposal yang lebih besar.
- Invariant: `PAPER_PROPOSAL` selalu mensyaratkan status layer B verified, bukan unverified.
- Uji kontrol null-vs-empty dari lampiran harus sama-sama cash-only setelah fix.

## B. Freshness diklaim terpisah, tetapi pool/quote belum benar-benar diuji

Lokasi:

- `config.py:88`: `MAX_POOL_AGE_MIN` didefinisikan tetapi tidak dipakai.
- `pipeline.py:192-201`: active/off_hours hanya ditentukan umur NAV 24 jam.
- `pipeline.py:423-425`: NAV lebih tua dari 24 jam selalu menjadi `nav_stale_off_hours`.
- `gate.py:239-241`: assertion untuk klaim freshness terpisah hanya memeriksa string status layer B.

### Reproduksi

- Pada fixture NVDAc, ubah seluruh `pools[].fetched_at` dan `source_updated_at` menjadi 1 Januari 2026. Assessment tetap WATCH dengan alasan lama, tanpa reason stale DEX.
- Hapus timestamp NAV dan ubah umur menjadi unknown. Assessment masih WATCH, tanpa reason eksplisit timestamp reference invalid.
- Inspeksi classifier: NAV lebih tua dari 24 jam akan disebut off_hours tanpa melihat apakah pasar seharusnya sedang aktif. Feed macet pada hari bursa tidak dibedakan dari market close.

### Fix konkret

- Pisahkan waktu fetch, waktu observasi harga sumber, umur snapshot replay dan sesi pasar. Fetch baru tidak membuktikan harga baru.
- Terapkan freshness policy per jenis data. Timestamp harga unknown harus tetap unknown, bukan dianggap fresh.
- Pakai jam evaluasi eksplisit/injectable. Untuk replay historis, evaluasi historis harus berlabel replay, bukan dipresentasikan sebagai data live sekarang.
- Tentukan sesi pasar dari sumber/kalender yang relevan dan tervalidasi. Jika tidak tersedia, gunakan unknown, jangan menyimpulkan off_hours hanya karena feed tua.
- Stale saat market aktif, stale yang wajar saat market close, timestamp invalid, future timestamp dan data unknown harus punya reason codes terpisah.
- Sebelum proposal, kegagalan freshness quote/reference/DEX yang diwajibkan harus memblokir, tidak hanya memberi label.

### Regression tests wajib

- DEX stale, source timestamp unknown, fetch baru dengan harga sumber tua.
- Quote stale terpisah dari NAV stale.
- NAV stale pada sesi aktif vs weekend/holiday dengan kalender yang benar.
- Batas tepat threshold, future skew, timestamp hilang/invalid, replay historis vs evaluasi live.
- Test harus mengubah input waktu dan menguji keputusan/reason codes, bukan hanya memeriksa string status tetap.

## C. Replay mempercayai chain dan coverage turunan yang belum divalidasi ulang

Lokasi:

- `pipeline.py:335-345`: fallback replay memeriksa symbol/contract tetapi tidak chain.
- `pipeline.py:354-359`: assessment mempercayai count pada `coverage`.
- `gate.py:254-283`: tes coverage hanya menguji satu pool dengan count diubah manual.

### Reproduksi

Tiga variasi terpisah pada fixture NVDAc:

1. Ganti chain menjadi ethereum, contract/symbol tetap. Hasil WATCH tanpa `token_not_confirmed`.
2. Sisakan satu pool tetapi isi `independent_pool_count=2`. Hasil WATCH, tidak diblokir coverage.
3. Sisakan dua pool dengan DEX sama dan venue_count=1. Tetap WATCH dengan label median rapuh, bukan insufficient cross-venue coverage.

### Fix konkret

- Buat satu jalur validasi yang dipakai build live dan replay. Validasi chain + contract + symbol + decimals yang diharapkan.
- Hitung ulang coverage dari pool yang lolos validasi, termasuk dedup address case-insensitive. Jangan percaya count tersimpan.
- Definisikan pool independence dan venue independence secara terpisah. Jika kebijakan menjanjikan cross-venue, enforce minimum canonical venue, bukan hanya minimum pool.
- Definisikan pemetaan label seperti aero/aerodrome secara eksplisit. Jangan menganggap setiap string dexId adalah venue independen.
- Validasi identity/hash snapshot saat replay. Fixture sintetis harus punya identity/hash baru atau metadata transformasi yang jelas, bukan membawa ID lama seolah payload tidak berubah.
- Pool sangat kecil atau timestamp unknown jangan menambah confidence hanya karena jumlahnya banyak. Kriteria kelayakan harus dinyatakan, belum boleh disebut terkalibrasi.

### Regression tests wajib

- Wrong chain/contract/symbol/decimals ditolak.
- Count palsu terlalu tinggi/rendah tidak mengubah hasil hitung ulang.
- Duplicate address dengan casing berbeda tidak menambah pool.
- Dua agregator pool sama, dua pool venue sama, alias venue, satu pool valid setelah filter.
- Payload berubah dengan ID/hash lama ditolak atau ditandai sebagai transformasi replay.

## D. Persist dedup gagal, tetapi emit tetap dilaporkan sukses

Lokasi:

- `pipeline.py:595-599`: error baca/corrupt store diubah menjadi store kosong.
- `pipeline.py:625-629`: error tulis ditelan.
- `gate.py:358-382`: tes hanya membuktikan dedup normal dan menerima exception mentah sebagai structured error.

### Reproduksi

1. Gunakan snapshot sama, mode TEST/REPLAY sama.
2. Beri `seen_path` pada file di dalam parent directory yang tidak ada.
3. Panggil `emit_alert` dua kali.

Aktual: ID sama, tetapi pemanggilan pertama **dan kedua** mengembalikan `duplicate=False`; file dedup tidak ada. Tidak ada error persist yang dinaikkan ke pemanggil.

### Fix konkret

- Error baca/tulis harus eksplisit. Bedakan first-run store belum ada dari permission error atau JSON corrupt.
- Gunakan write atomik melalui temporary file + replace, dengan sinkronisasi/locking jika ada akses bersamaan.
- Jangan kembalikan status sukses bila dedup belum durable. Kembalikan hasil/error terstruktur dan hentikan jalur emit terkait.
- Untuk fase pengiriman eksternal, gunakan idempotency key dan status/outbox yang mendefinisikan perilaku saat crash sebelum/sesudah delivery. Jangan menganggap penulisan seen file saja menjamin exactly-once.

### Regression tests wajib

- Direktori tidak ada, permission denied, simulated disk full, store corrupt dan write/replace gagal.
- Replay setelah restart tetap duplicate.
- Dua worker bersamaan tidak sama-sama mendapat izin emit baru untuk ID sama.
- Failure tidak boleh terlihat sebagai empty success atau emit berhasil.
- Input malformed mengembalikan error terstruktur yang diuji field-nya, bukan PASS hanya karena KeyError/TypeError/AttributeError.

## 3. Perbaikan suite dan syarat acceptance ulang

Suite saat ini bertumpu NVDAc, termasuk happy-path yang docstring-nya menyebut dua token. Mayoritas tes hanya reassess fixture, bukan adapter/normalisasi. Test multiplier menguji konstanta fixture dan identitas aritmetika, bukan jalur build atau histori effective multiplier.

Sebelum review ulang:

- [ ] A-D diperbaiki dan seluruh negative tests di atas ditambah.
- [ ] Happy-path parametrik NVDAc dan AAPLc melewati adapter mock/raw capture -> build -> assess -> decide -> explain -> emit -> paper record.
- [ ] Test NAV memakai variasi NAV/multiplier pada build, bukan hanya konstanta fixture.
- [ ] Gate lama tetap PASS dan hasil negative tests menunjukkan penolakan yang diharapkan.
- [ ] Output memuat waktu run, versi schema/policy/method, identitas source/commit dan konfigurasi test.
- [ ] Raw response dari run yang sama disimpan beserta request, timestamp/status dan manifest hash. Raw GeckoTerminal AAPLc ikut disertakan.
- [ ] Tidak ada status atau narasi yang mengklaim quote/exit verified ketika bukti belum valid.
- [ ] Review ulang selesai sebelum quoter dipasang atau proposal diaktifkan.

## 4. Caveat evidence dan sumber

Enam raw JSON evidence valid dan berisi data, bukan file kosong. Akan tetapi raw capture diambil terpisah dari snapshot output: contoh harga pool utama NVDAc 132.054 pada raw vs 131.99 pada snapshot. Perbedaan Hyperliquid juga ada. Ini masuk akal untuk fetch berbeda, bukan bukti pemalsuan, tetapi belum memberi rantai raw-ke-snapshot exact-run. Timestamp NAV, umur NAV, median snapshot dan gap sudah dihitung ulang dan konsisten.

Waktu run asli didukung oleh snapshot sekitar 17:39 WITA dan artefak gate sekitar 17:44:55 WITA, 22 November 2026. `gate_results.json` asli tidak menyimpan waktu run eksplisit. Ketiadaan deploy/transaksi/pengiriman produksi tidak dapat dibuktikan hanya dari ZIP ini.

Sumber yang diaudit:

- Folder: https://drive.google.com/drive/folders/1LeVeb9dscDH5xMkEsOZgtXJc25-ClH9m
- Evidence ZIP: https://drive.google.com/file/d/1818PNUkqQdJf8g-KU2NWPIwfyuBAEz-S/view?usp=drivesdk&authuser=dannytungadi5%40gmail.com
- Source ZIP: https://drive.google.com/file/d/1yRerJUkk8SqmdejWYvvjDan6NSHyoXM_/view?usp=drivesdk&authuser=dannytungadi5%40gmail.com
- SHA-256 source ZIP: `a9a957411bc871566a66a139fe7422d4ae1042eab57e71eb35bad5813285297b`

**Ringkasnya: output live jujur dan empat koreksi utama benar. Gate 9/9 benar ter-reproduksi, tetapi tidak cukup untuk menyatakan semua guard lulus. Selesaikan A-D dahulu.**
