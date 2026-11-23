# Brief untuk MUSE: prototipe kecil Base Stocks Maxxing

Tanggal: 22 November 2026, WITA  
Produk: Exit Radar, radar.omdanny.site  
Arah: research-to-paper-portfolio agent dengan kontrol risiko exit  
Status: brief desain dan prototipe lokal/offline. BUKAN ACC komitmen 13 hari.

## 1. Keputusan yang diminta

Buktikan satu alur kecil: data token Base -> validasi data -> evaluasi kondisi DEX -> keputusan paper portfolio atau ABSTAIN -> satu alert lokal yang dapat direproduksi.

Pembeda produk tetap pertanyaan Exit Radar: "Bisa keluar, dengan bukti harga seperti apa?" Bukan agent pembuat basket generik, bukan janji exit liquidity, dan bukan auto-trading.

Gerbang sebelum membahas komitmen build penuh: satu pengujian alert Base end-to-end yang dapat dijalankan ulang, dengan pemisahan tegas antara sinyal token dan proxy saham underlying. Gerbang lolos bukan izin otomatis melanjutkan. Alex tetap memberi ACC eksplisit untuk fase berikutnya.

## 2. Batas fase ini

Boleh disiapkan untuk prototipe: adapter data publik read-only, snapshot lokal, replay fixture, policy deterministik, output paper portfolio, dan alert ke file/console lokal. Pisahkan konfigurasi, data, dan output dari Radar produksi.

Tidak termasuk dan jangan dilakukan dalam fase ini:

- Pendaftaran kompetisi, akun baru, deploy, atau perubahan Radar live.
- Transaksi onchain, termasuk testnet; funding wallet, approval token, swap, custody, leverage, atau penggunaan uang sungguhan.
- Mengirim alert ke channel Telegram produksi, post publik, atau menghubungi panitia tanpa persetujuan terpisah.
- Port Exit Score Solana mentah-mentah, perluasan banyak ticker, Monday Gap Base, atau autonomous rebalancing.

Elemen Base Sepolia hash registry hanya DESAIN untuk fase sesudah gerbang dan ACC Alex. Tidak perlu wallet atau private key untuk membuktikan alur lokal ini.

## 3. Fakta dasar dan koreksi yang mengikat desain

Angka di bawah adalah snapshot verifikasi independen 22 November 2026 sekitar 09:27 UTC, bukan quote saat brief dibaca. Jangan hard-code angka snapshot sebagai data terkini.

| Bagian | Fakta dan konsekuensi |
|---|---|
| Identitas token | NVDAc: `0xb20000000000000000000078ee7ce2fE4908108C`; AAPLc: `0xb200000000000000000000C2e324d24d7eEcd1fb`. Kunci identitas dengan chain + contract, bukan ticker saja. |
| Coinbase API | Publik, read-only, tanpa API key. Mendapat record bukan bukti trading availability, eligibility, atau jalur redemption. Ikuti pagination sebelum menyimpulkan token tidak ada. |
| NAV NVDAc | `129.82480034`, diperbarui `2026-11-20T23:42:40Z`; multiplier snapshot `1.0005379395763694`. |
| NAV AAPLc | `345.29769685`, diperbarui `2026-11-20T23:12:02Z`; multiplier snapshot `1.0005003893019802`. |
| Normalisasi | `nav_price` SUDAH multiplier-adjusted/total-return. Jangan dikalikan multiplier lagi. Harga saham underlying mentah perlu scaling; harga token yang sama antar-DEX tidak perlu scaling. Rekonstruksi dari raw share history memerlukan multiplier historis yang efektif saat itu, bukan multiplier hari ini untuk seluruh seri. |
| NAV di luar jam feed | NAV menahan nilai terakhir pada weekend/libur dan dapat membeku saat corporate action. Tampilkan sebagai referensi terakhir beserta umur dan status sesi, bukan harga live atau harga eksekusi. |
| Venue | Harga agregator saat verifikasi: NVDAc sekitar $132.47; AAPLc sekitar $349.11. Pool Aerodrome teramati. Ini observasi agregator, bukan bid/ask atau jaminan fill. Dua agregator yang membaca pool sama bukan dua venue independen. |
| Hyperliquid | Tidak ditemukan perp token NVDAc/AAPLc dalam pemeriksaan seluruh dex. Yang tersedia adalah `xyz:NVDA`, `xyz:AAPL`, juga varian `io:`: perp saham UNDERLYING. Funding/OI hanya proxy sentimen underlying, bukan ukuran exit-risk token Base. |
| Liquidity | Pool TVL/reserve/liquidity bukan executable depth, khususnya concentrated liquidity. Boleh menjadi filter kelayakan data/pool, tidak boleh dijadikan bukti bisa menjual nominal tertentu. |
| Redemption | Belum ada jalur permissionless retail yang terverifikasi. Desain mengasumsikan tidak ada jalur itu. Jangan turunkan status retail redemption dari jam bursa atau ketiadaan `paused_features`. |
| PoR | Belum ada sumber otomatis yang terverifikasi. Supply saja bukan bukti reserve. Hanya catatan manual/kualitatif dengan sumber dan tanggal, atau `unknown`. |

Selisih DEX terhadap NAV beku boleh dilaporkan sebagai deskripsi berlabel. Jangan menyebutnya diskon, mispricing, arbitrase, tidak bisa dieksploitasi, atau pasti false-positive. Penyebab dan exploitability belum terbukti. Jangan memakai contoh aritmatika/rationale weekend dari laporan sebelumnya sebagai dasar kalibrasi.

## 4. Alur produk minimum

1. **Ingest:** hanya NVDAc dan AAPLc. Ambil metadata/reference Coinbase serta pool observations Base. Ambil proxy underlying hanya bila diperlukan, tanpa menjadikannya syarat agar alert token bisa berfungsi.
2. **Validate:** cocokkan chain, contract, quote asset, unit, timestamp, dan identitas pool. Tolak nilai nonpositif, timestamp masa depan yang tidak wajar, atau respons tidak lengkap. Error sumber menjadi `unknown`, bukan nol risiko.
3. **Assess:** keluarkan status data dan kondisi DEX. Jangan tampilkan score 0-100 yang seolah sudah dikalibrasi.
4. **Decide:** policy dapat menghasilkan `ABSTAIN`, `WATCH`, atau `PAPER_PROPOSAL`. Kondisi yang tidak memenuhi bukti exit tidak boleh menghasilkan usulan beli. Menahan seluruh alokasi di cash simulasi adalah hasil yang sah.
5. **Explain:** agent merangkum alasan dan sumber dari objek tervalidasi; tidak menciptakan harga, quote, atau alasan finansial baru. Jika memakai LLM, policy tetap menentukan hasil akhir dan memvalidasi output-nya.
6. **Alert:** serialisasi payload ke file/console lokal, dengan ID deterministik dan dedup. Alert yang menyala dalam replay harus berlabel `TEST/REPLAY`, bukan kejadian pasar live.
7. **Paper record:** simpan usulan dan snapshot yang mendasarinya. Tidak ada transaksi dan tidak ada klaim fill/return jika hanya ada indicative price.

Usulan portfolio harus mencantumkan cash simulasi, bobot per aset, horizon, expiry, nominal simulasi, dan alasan menahan diri. Batas bobot/nominal adalah parameter policy eksperimen, bukan preferensi investasi Alex. Jangan mengisi toleransi risiko Alex secara diam-diam.

## 5. Kontrak data minimum

Simpan nilai asli, nilai hasil normalisasi, dan metode normalisasi agar kesalahan unit bisa diaudit. Gunakan UTC untuk timestamp mesin dan tampilkan WITA bila perlu di presentasi.

```text
snapshot_id, schema_version, methodology_version, fetched_at
asset: chain, token_address, symbol, decimals
reference: nav_price, nav_price_updated_at, age_seconds,
           session_status, registry_pause_status, source
multiplier: value, observed_at, source
pools[]: pool_address, dex, quote_asset, indicative_price_usd,
         liquidity_usd, source_updated_at?, fetched_at, source
coverage: independent_pool_count, independent_venue_count,
          missing_fields[], rejected_observations[]
exit_quote?: sell_size_token, amount_out, quote_asset,
             fees_scope, route, block_or_timestamp, expires_at, source
underlying_proxy?: instrument, dex, funding_raw, funding_unit,
                   funding_interval, open_interest_raw, oi_unit,
                   observed_at, source, label
assessment: status, reason_codes[], confidence_basis
proposal?: weights, cash_weight, simulation_notional, expiry
alert: alert_id, mode, rule_version, reasons, emitted_at
```

Ketentuan penting:

- `fetched_at` tidak sama dengan waktu transaksi terakhir, update harga sumber, atau update NAV. Jika sumber tidak memberi timestamp harga, tulis `unknown`; jangan sebut harga pasti fresh hanya karena fetch baru sukses.
- `session_status`: misalnya `off_hours`, `active`, `corporate_action_pause`, atau `unknown`. Gunakan kalender/sumber sesi yang dinyatakan, bukan menebak dari weekday saja. Jangan menyamakan jam feed 24/5 dengan jam regular NYSE.
- Jika pause registry belum dibaca, nilainya `unknown`. Ketiadaan field tidak membuktikan semua fungsi aktif.
- OI raw dan USD notional bukan unit yang sama. Nyatakan unit dari schema sumber. Hindari agregasi `xyz:` dan `io:` sebagai satu seri tanpa metodologi eksplisit; pilih satu instrument untuk baseline dan simpan mapping-nya.
- `OI change 24h` memerlukan snapshot pada horizon pembanding. Mulai koleksi lokal bila dipakai; sebelum baseline cukup, nilainya `null/insufficient_history`, bukan 0%. Jangan memperlakukan funding sebagai OI change.
- Dokumen/sumber manual PoR disimpan terpisah dengan tanggal. Jangan menghasilkan rasio backing dari `total_supply` saja.

## 6. Exit Score Base: redesign, bukan port

Untuk prototipe ini, utamakan reason codes dan coverage, bukan angka komposit. Pisahkan tiga lapisan:

**A. Kondisi DEX token.** Deviasi terhadap median hanya dari observasi independen yang lolos filter, dalam unit sebanding dan jendela waktu yang dinyatakan. Dedup pool yang dibaca dua agregator. Bila hanya satu venue/pool valid, keluarkan `insufficient_cross_venue_coverage`, bukan deviasi nol. Dengan hanya dua observasi, median rapuh; jelaskan keterbatasannya. Simpan per-venue deviations agar angka agregat tidak menyembunyikan outlier.

**B. Bukti exit.** Jika tersedia, gunakan read-only sell quote untuk nominal simulasi yang eksplisit, lengkap dengan rute, waktu/block, biaya yang sudah/belum termasuk, dan expiry. Quote tetap bukan fill. Tanpa quote, status `indicative_only/exit_quality_unverified`; TVL tidak boleh menggantikannya. Adapter quote yang belum terbukti bekerja harus dilaporkan sebagai gap, bukan dependensi yang dianggap selesai.

**C. Konteks underlying.** Funding dan OI dipajang terpisah sebagai `UNDERLYING EQUITY PERP PROXY`. Sinyal proxy tidak boleh sendirian memicu alert token-exit atau memperbaiki coverage data token yang hilang.

Untuk rancangan skor selanjutnya:

- Hilangkan komponen redemption 20 poin atau usulkan pengganti yang benar-benar punya sumber data. Jangan sekadar renormalisasi 80 poin dan tetap menyebutnya setara Solana.
- Jangan mewarisi bobot, aturan minimum 3/5 komponen, threshold 70, atau cutoffs Solana. MUSE perlu mengusulkan kalibrasi Base, dasar data, dan tradeoff false-positive/false-negative.
- Ketiadaan redemption, PoR, atau histori bukan skor nol. Tampilkan `unknown/not_applicable` dan coverage secara eksplisit.
- Gunakan threshold eksperimen yang versioned dan jelas berlabel belum tervalidasi. Lolos test teknis bukan bukti kualitas prediktif atau keuntungan.

## 7. Gerbang alert end-to-end yang harus dibuktikan

Satu run harus membuktikan pipeline memakai snapshot Base nyata, dan replay terkontrol harus membuktikan kondisi alert beserta guardrail-nya. Tidak perlu menunggu peristiwa pasar berbahaya sungguhan.

| Tes | Kriteria lulus |
|---|---|
| Happy path Base | Dua token resmi terbaca, identitas tepat, nilai/timestamp/source tersimpan. Keputusan policy bisa dijelaskan sampai ke input. |
| Trigger terkontrol | Ubah satu fixture kondisi DEX yang relevan secara eksplisit. Seluruh pipeline menghasilkan satu alert lokal `TEST/REPLAY`; perubahan input, rule version, dan expected result tercatat. Jangan mengklaim trigger sintetis sebagai alert pasar nyata. |
| NAV weekend | Replay nilai NAV Jumat dan snapshot Minggu. NAV tampil sebagai last published reference + age/off-hours, tidak dipakai sebagai live-price alarm atau dasar mispricing. |
| Multiplier | Test membuktikan NAV tidak dikalikan lagi. Raw share conversion memakai multiplier yang sesuai waktu/unit. |
| Missing/stale | Putuskan sumber atau buat data basi. Usulan baru diblokir/ABSTAIN sesuai policy; tidak ada risiko nol palsu. Freshness gate quote, observasi DEX, dan NAV terpisah. |
| Coverage | Dua agregator untuk satu pool dihitung satu pool. Satu venue tidak menghasilkan cross-venue confidence palsu. |
| Proxy | Funding ekstrem atau perubahan OI saja tidak memicu klaim token-exit. Label proxy bertahan sampai payload alert/paper proposal. Histori belum cukup menghasilkan `null`, bukan perubahan 24h rekaan. |
| Liquidity vs exit | TVL besar tanpa sell quote tetap `exit_quality_unverified`; tidak ada klaim bisa menjual nominal tertentu. |
| Idempotensi | Replay snapshot/rule sama tidak menduplikasi alert. Input buruk menghasilkan error terstruktur, bukan output sukses kosong. |

Bukti gerbang: perintah run/replay, dependency versions, snapshot asli, fixture yang dimodifikasi, output yang diharapkan vs aktual, payload alert, dan log test. Satu screenshot boleh melengkapi, tetapi bukan pengganti file dan langkah reproduksi.

Tidak adanya executable quote tidak otomatis menggagalkan demonstrasi plumbing alert. Namun itu MEMBATASI hasil menjadi monitor indikatif; tidak cukup untuk mengklaim exit-quality atau mengizinkan usulan beli berbasis bukti exit. Status ini harus dibawa ke keputusan ACC, bukan disembunyikan.

## 8. Desain onchain sesudah gerbang, belum dijalankan

Kandidat minimum: Base Sepolia hash registry untuk komitmen snapshot + keputusan paper portfolio + versi metodologi. Tujuannya membuktikan catatan sudah ada sebelum evaluasi hasil, bukan membuktikan data benar, return, compliance, atau traction.

Siapkan spesifikasi saja: canonical serialization, hash algorithm, schema/methodology version, timestamp observasi, expiry, dan prosedur verifikasi dari payload ke hash. Payload lengkap harus tetap tersedia untuk pihak yang berhak memverifikasi; hash tanpa payload tidak cukup untuk audit. Jangan taruh identitas atau isi portfolio privat onchain. Hash juga bukan jaminan anonimitas, jadi jangan hash data sensitif tanpa desain privasi.

Deploy, transaksi, akses wallet, publikasi payload, dan receipt pengguna menunggu gerbang + ACC eksplisit Alex. Kelayakan akhir integrasi untuk kompetisi tetap keputusan panitia; registry bukan jalan pintas untuk menjamin eligibility atau traction.

## 9. Output yang diminta dari MUSE

Kirim satu paket ringkas untuk review, tidak perlu menambah fitur:

- Design note: flow, data mapping, policy/rule version, threshold eksperimen, coverage, dan asumsi yang belum terbukti.
- Adapter/prototipe lokal serta README run/replay; pisahkan dari produksi dan tunjukkan file yang berubah.
- Evidence bundle publik: respons yang relevan, source URL, waktu observasi, normalisasi/unit, dan hasil test §7. Tidak ada secret atau data akun pengguna.
- Contoh paper decision dan satu payload alert lokal yang berlabel jujur. ABSTAIN diperbolehkan dan lebih baik daripada proposal tanpa bukti.
- Decision memo: apa yang lulus, apa yang gagal, apa yang masih unknown, estimasi sisa pekerjaan berdasarkan source yang benar-benar diperiksa, serta pilihan GO terbatas atau STOP.

Jangan menyatakan "tidak ada alasan NO-GO" atau "siap 13 hari" hanya karena data publik bisa dibaca. Laporkan blocker dan dampaknya.

## 10. Waktu dan aturan berhenti

Ini urutan checkpoint, bukan persetujuan komitmen waktu atau instruksi memulai seluruh build:

- Berikutnya: prototipe kecil dan satu gate alert yang dapat direproduksi. Kerja Base tidak mengambil alih lane mendesak yang sudah berjalan.
- Target review alur end-to-end: sebelum 28 November 2026. Bila fondasi belum jalan, bawa keputusan STOP, bukan menambah fitur untuk menutupi gap.
- Kill-switch tetap 30 November 2026. Bila integrasi Base belum berjalan secara jujur dan dapat diverifikasi, berhenti. Jangan menunggu tanggal ini untuk mengangkat blocker fondasi.
- Hanya setelah gate + ACC: pertimbangkan tester/QA 1-3 Desember dan target submission 4 Desember sebagai buffer.
- Deadline resmi yang diperiksa ulang: Sabtu, 5 Desember 2026 23:59 UTC = Minggu, 6 Desember 2026 07:59 WITA. Form harus diterima; post/demo saja belum lengkap.

Jangan mengasumsikan bobot traction 50/25/25 sebagai rules resmi. Jangan memakai transaksi internal sebagai pengguna/traction. Pertanyaan rubrik dan nilai paper-portfolio/testnet tetap terbuka untuk keputusan prize-hunting; tidak diselesaikan oleh gate teknis ini.

## 11. Provenance dan sumber

Brief ini menyatukan laporan validasi MUSE, review GO bersyarat, dan koreksi verifikasi independen 22 November 2026 sekitar 09:27 UTC. Bila bertentangan, koreksi di §3 mengungguli kesimpulan laporan validasi awal. Snapshot harga bukan hasil trade execution.

Sumber resmi yang dibaca ulang saat penyusunan brief:

- API semantics, pagination, timestamp dan availability caveat: https://docs.base.org/sdks/tokenized-stocks/overview
- Multiplier, total-return reference, jam feed/freeze, dan histori corporate action: https://docs.base.org/build-on-base/integrate-defi/list-tokenized-stocks
- Deadline dan cara submit: https://www.base.org/stocksmaxxing
- Rules, penggunaan testnet, judging, larangan manipulasi dan automated submission: https://www.base.org/stocksmaxxing/rules

Sumber snapshot dari verifikasi sebelumnya:

- Token reference API: https://api.coinbase.com/v1/tokenized-stocks
- Pool NVDAc yang teramati: https://dexscreener.com/base/0xf668e21993f0acd7ab00bb1cfbaed0df28a3c8ec
- Pemeriksaan Hyperliquid: respons `metaAndAssetCtxs` lintas dex, 22 November 2026 sekitar 09:27 UTC, dengan instrumen `xyz:NVDA`/`xyz:AAPL` dan varian `io:`. Ini bukti proxy underlying saat pemeriksaan, bukan janji listing permanen. Revalidasi mapping sebelum menjalankan adapter.

Tidak ada klaim bahwa source code Radar, quote routing, atau deployment sudah diaudit dalam brief ini. Itu harus dibuktikan oleh hasil kerja MUSE, bukan diasumsikan dari laporan data publik.
