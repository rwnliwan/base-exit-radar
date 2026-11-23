# Perbandingan detail: (a) research-to-portfolio vs (b) agent-managed rebalancing

Ditulis chief, 24 Nov 2026 ~01:xx WITA. Diminta Septian 23 Nov 22:38
("Iya perbandingan detail a vs b dlu"). Semua klaim faktual dicek ke
sumber saat menulis: `DESIGN.md`, `README.md`, `config.py`,
`pipeline.py`, `docs/keputusan-fitur-agen-onchain-2026-11-23.md`,
`docs/BASE-STOCKS-MAXXING-RENCANA-KETAT-2026-11-22.md`.
Bila ada angka/link di dokumen ini yang tidak ada sumbernya di bawah,
itu tebakan — laporkan ke chief.

## 0. Ringkasan eksekutif

**Rekomendasi chief: (a) research-to-portfolio, dipasangkan dengan
elemen onchain (i) hash registry — yang dalam praktiknya sama dengan
(ii) aksi agen tercatat, karena output agen (a) adalah brief +
proposal yang di-hash.**

Alasan satu kalimat: (a) adalah penyambungan dari mesin yang sudah
ada dan sudah diaudit; (b) adalah mesin baru dari nol yang
bertentangan dengan batas tertulis prototipe sendiri, dan tidak muat
di jendela 28–30 Nov — apalagi Scope 1 (data Base) sampai dokumen ini
ditulis belum mulai, padahal slotnya 24–27 Nov.

Yang TIDAK diputuskan oleh pilihan (a) vs (b): soal traction. Keduanya
sama-sama simulasi paper selama quote masih simulasi `eth_call`.
Pembeda yang benar-benar menyentuh rubrik traction (dilaporkan 50%,
belum terverifikasi di halaman resmi) adalah elemen onchain, bukan
nama fiturnya.

## 1. Titik awal bersama — apa yang sudah ada

Prototipe v0.3.3, terverifikasi (audit Instinct 9,5/10, ACC tahap
read-only, nol must-fix; live run 23 Nov 00:12: NVDAc + AAPLc keduanya
WATCH, gate 19/19 PASS):

```
ingest (adapter.py)
  -> build_snapshot (pipeline.py)
  -> assess_snapshot: tiga lapis (DESIGN §6) -> reason codes + coverage
  -> decide: ABSTAIN / WATCH / PAPER_PROPOSAL
  -> explain: rangkum alasan + sumber
  -> emit_alert: payload lokal, ID deterministik, dedup
  -> paper record: usulan + snapshot yang mendasarinya
```

Parameter policy (`config.py`, `DESIGN.md` §4 — semuanya eksperimen,
belum tervalidasi): `SIMULATION_NOTIONAL_USD` $10.000,
`MAX_WEIGHT_PER_ASSET` 0,50, `HORIZON_DAYS` / `EXPIRY_DAYS` 7 / 7,
`DEV_WATCH_PCT` 2%, `DEV_ABSTAIN_PCT` 5%, `MIN_INDEPENDENT_POOLS` 2,
`NAV_STALE_HOURS` 24 jam.

Sell-quote adapter v0.3.3 (Aero Metaquoter V3) sudah jalan — TAPI
quote-nya simulasi `eth_call`, BUKAN firm/komitmen eksekusi. Deteksi
partial-fill tiga lapis sudah ada (double-quote probe, sanity
implied-price ±10%, guard batas sqrt TickMath).

Coverage: hanya NVDAc + AAPLc. Venue efektif 1 pool dominan per token
(Aerodrome Slipstream). Pool Uniswap V4 TIDAK ter-cover (~11 pool
NVDAc termasuk ~$130rb likuiditas — batasan yang didokumentasikan,
DESIGN §10).

Exit Score Base adalah redesign, bukan port Solana (DESIGN §6):
reason codes + coverage, bukan angka komposit 0–100; komponen
redemption 20 poin Solana DIHILANGKAN (tidak ada sumber data).

### 1.1 Dua penahan yang sama untuk (a) DAN (b)

`PAPER_PROPOSAL` hari ini tidak terjangkau karena DUA alasan yang
independen — bukan satu. Ini kunci seluruh perbandingan, dan sudah
tertulis di kode (`pipeline.py:1472-1493`, docstring `decide()`):

1. **Gate mati:** `PAPER_PROPOSALS_ENABLED = False`
   (`config.py:269`). Aturan 3 `decide()`: gate mati → WATCH.
2. **Bukti exit simulasi, bukan firm:** aturan 4 `decide()`: layer B
   `simulated_exit_quote_verified` → WATCH
   (`exit_evidence_simulated_not_firm`). Aturan 5: PAPER_PROPOSAL
   HANYA bila quote FIRM verified + semua bersih + gate nyala.
   Invariant tertulis: PAPER_PROPOSAL SELALU mensyaratkan layer B
   verified (firm), bukan simulasi.

Konsekuensinya, sudah tertulis di `README.md:196`: keputusan tetap
**WATCH (`exit_evidence_simulated_not_firm`) meski gate ON.**
Menyalakan gate saja TIDAK menghasilkan satu pun proposal. Siapa pun
yang bilang "(a) tinggal nyalain gate" atau "(b) tinggal tambah
rebalance" sedang mengabaikan penahan kedua.

### 1.2 Yang belum ada sama sekali (untuk keduanya)

- **Scope 1** — coverage Base di poller + universe + web, kalibrasi
  ulang Exit Score Base. Slot rencana: 24–27 Nov. Status saat dokumen
  ini ditulis (24 Nov ~01:xx): BELUM MULAI. Ini berarti jendela
  28–30 Nov sekarang juga menanggung risiko slip Scope 1.
- Fitur agen (a) atau (b). Elemen onchain (baru ada DESAIN, DESIGN §8).
- Video demo, post X, nama proyek final, cek halaman 2 form.
- Materi submit-prep SUDAH ada dan diparkir (`submit-prep/`:
  `draft-form.md`, `draft-post-x.md` 2 varian, `script-demo-video.md`
  6 scene, `form-fields-2026-11-23.md`). Halaman 1 form dicek live
  23 Nov (17 field); halaman 2 belum kelihatan.

## 2. (a) Research-to-portfolio agent

**Definisi:** agen membaca radar setiap hari, menulis brief harian,
dan mengeluarkan usulan portofolio (paper) — bobot per aset, bobot
cash, nominal simulasi, expiry — lengkap dengan alasan yang merujuk
ke snapshot yang mendasarinya.

### 2.1 Yang sudah ada untuk (a)

Hampir seluruh mesinnya:

- `decide()` sudah mengeluarkan struktur PAPER_PROPOSAL
  (`weights`, `cash_weight`, `simulation_notional`, `expiry`) —
  kodenya ada, hanya tidak terjangkau karena dua penahan di §1.1.
- `explain()` sudah merangkum alasan + sumber tanpa menciptakan
  harga/alasan baru — itu isi brief.
- `paper record` sudah menyimpan usulan + snapshot yang
  mendasarinya — itu arsip brief yang bisa diverifikasi.
- `emit_alert` sudah punya payload deterministik + dedup — itu
  ritme harian.
- Parameter portofolio sudah ada sebagai policy: notional $10.000,
  bobot maks 0,50, horizon/expiry 7 hari.

Jadi (a) BUKAN fitur baru dari nol. (a) adalah: ambil output
`decide()` + `explain()` yang sudah ada, bungkus jadi brief harian,
jadwalkan, tampilkan.

### 2.2 Yang harus dibangun untuk (a)

1. **Penyajian brief harian** — format brief (apa yang berubah sejak
   kemarin, keputusan hari ini, alasan + sumber) + penjadwalan
   (cron harian) + tampilan web. Perkiraan: 1 hari kerja.
2. **Keputusan sub-kebijakan (a1) vs (a2)** — lihat §2.3. Ini
   keputusan, bukan kode.
3. **Elemen onchain (i)** — hash brief + proposal ke registry
   (DESIGN §8 sudah ada spesifikasinya). Perkiraan: 0,5–1 hari
   (kontrak registry sederhana + skrip publish + verifikasi).
4. **Demo** — skrip video sudah ada 6 scene; scene brief → proposal
   tinggal diisi dengan output nyata. Perkiraan: 0,5 hari (di luar
   waktu rekam Septian).

Total: ~2–3 hari kerja — muat di jendela 28–30 Nov, dengan catatan
Scope 1 tidak slip jauh.

### 2.3 Sub-keputusan yang tidak bisa dihindari: (a1) vs (a2)

Karena penahan kedua (§1.1) tidak hilang dengan menyalakan gate,
(a) punya dua varian — dan varian ini harus dipilih eksplisit,
bukan dibiarkan implisit:

- **(a1) Brief + proposal di atas bukti simulasi, dilabeli paper
  secara eksplisit.** Proposal dikeluarkan meski quote simulasi,
  dengan label jujur di setiap tampilan: "paper proposal, bukti exit
  simulasi, bukan komitmen eksekusi". Ini butuh perubahan policy
  yang disengaja (relaksasi invariant `decide()` aturan 4–5 untuk
  jalur paper, dengan pencatatan alasan) + ACC eksplisit Septian.
  Demo-able: brief → proposal dengan bobot dan expiry nyata.
- **(a2) Brief saja; proposal tetap terkunci sampai ada quote firm.**
  Tidak ada perubahan policy. Demo menunjukkan brief + keputusan
  WATCH + "belum ada proposal karena bukti exit belum firm".
  Paling konservatif — tapi demo-nya lemah: agen yang tidak pernah
  mengusulkan apa-apa sulit dibedakan dari monitor yang sudah ada.

Rekomendasi chief: **(a1), dengan label paper yang tidak bisa
dilepas.** Alasannya kejujuran, bukan kemudahan: (a1) jujur karena
labelnya melekat di output; (a2) jujur tapi tidak mendemonstrasikan
apa pun yang baru. Yang TIDAK boleh: (a1) tanpa label — itu
mengubah simulasi jadi klaim eksekusi, dan itu overclaim yang sama
kelasnya dengan skor "86/100" yang sudah kita hapus dari Build CMC.

### 2.4 Risiko (a)

- **Risiko utama: label paper dianggap lemah oleh juri.** Mitigasi:
  yang dijual bukan return, melainkan disiplin: setiap proposal
  bisa dilacak ke snapshot + hash onchain (§6). Itu keunggulan yang
  bisa diverifikasi, bukan janji.
- **Risiko jadwal: Scope 1 slip.** (a) butuh data Base yang benar
  dulu; tanpa Scope 1, brief-nya hanya NVDAc + AAPLc (2 aset).
  Mitigasi: brief 2-aset tetap demo-able; kalibrasi ulang bisa
  menyusul sebagai catatan.
- **Risiko kebijakan: relaksasi invariant (a1) harus dicatat
  sebagai keputusan sadar** — bukan diam-diam. Bila Instinct
  keberatan, jatuh ke (a2) dan terima demo yang lebih tipis.

### 2.5 Klaim yang boleh dan tidak boleh dibuat (a)

- BOLEH: "agen membaca radar, menulis brief harian, mengusulkan
  paper portfolio, dan setiap brief + proposal di-hash onchain
  sebelum dievaluasi."
- TIDAK BOLEH: "agen mengelola portofolio", "return", "eksekusi",
  "quote firm" — selama quote masih simulasi.

## 3. (b) Agent-managed rebalancing

**Definisi:** agen mengelola sebuah portofolio (paper atau nyata):
menghitung bobot target dari Exit Score, memicu rebalance saat sinyal
berubah, mengeksekusi/mensimulasikan trade, dan mencatat aksi +
hasilnya dari waktu ke waktu.

### 3.1 Yang sudah ada untuk (b)

**Tidak ada — dan ada satu kalimat yang melarangnya.**

`README.md:252` menulis batas prototipe dengan eksplisit:
"tidak ada autonomous rebalancing." Memilih (b) berarti menulis
ulang batas itu dan DESIGN §3 (policy) — bukan sekadar menambah
fitur, melainkan mengubah apa yang prototipe ini nyatakan tentang
dirinya sendiri.

Yang bisa dipakai ulang dari yang ada: `decide()` (keputusan per
aset), parameter policy (notional, bobot maks), dan sell-quote
adapter (simulasi). Itu komponen, bukan mesin rebalance.

### 3.2 Yang harus dibangun untuk (b) — semuanya baru

1. **Mesin rebalance:** bobot target dari Exit Score → daftar trade
   (jual/beli, ukuran) → eksekusi/simulasi → state portofolio baru.
   Tidak ada satu pun dari ini di repo.
2. **Pemicu + kontrol risiko:** kapan rebalance (ambang deviasi?
   jadwal? perubahan reason code?), cooldown antar rebalance,
   batas drawdown, penegakan bobot maks lintas waktu. Threshold
   2%/5% yang ada adalah threshold *keputusan per aset*, bukan
   pemicu rebalance — pemicu rebalance butuh desain sendiri +
   kalibrasi yang tidak ada datanya.
3. **State lintas waktu:** portofolio yang berevolusi dari hari ke
   hari (holdings, cash, histori aksi). Prototipe hari ini stateless
   per snapshot; `paper record` menyimpan usulan, bukan posisi
   yang berjalan.
4. **Penahan firm-quote, lebih berat:** rebalance adalah *tindakan*
   atas quote. Di atas quote simulasi, setiap "aksi rebalance"
   adalah trade simulasi — dua lapis paper (proposal paper +
   eksekusi paper). Menyebutnya "agent-managed" tanpa eksekusi
   adalah overclaim yang sama yang kita hindari di (a1).
5. **Demo:** butuh bukti deret waktu — portofolio sebelum/sesudah,
   logika pemicu, histori aksi. Dalam video 2–3 menit, (b) jauh
   lebih sulit dibuat terbaca daripada (a), dan deret waktunya
   belum ada: jendela 28–30 Nov hanya memberi 3 hari observasi,
   itu pun kalau mesinnya sudah jalan di hari pertama.

Perkiraan jujur: **4–6 hari kerja** untuk versi minimal yang tidak
malu-maluin — lebih dari jendela 28–30 Nov. Dan itu sebelum Scope 1
+ elemen onchain + QA + submit.

### 3.3 Risiko (b)

- **Risiko jadwal: paling besar.** (b) tidak muat di jendela.
  Konsekuensi realistis: kill-switch 30 Nov terpicu ("integrasi
  Base belum jalan → BERHENTI"), atau submit dengan mesin setengah
  jadi yang tidak lolos QA chief (verifikasi dulu baru lapor).
- **Risiko overclaim: paling besar.** "Agent-managed" tanpa
  eksekusi dan tanpa firm quote adalah klaim yang tidak bisa
  dipertahankan di depan juri yang membaca repo — dan repo ini
  publik.
- **Risiko scope creep:** sekali ada "portofolio yang berjalan",
  pertanyaan berikutnya adalah drawdown, biaya, slippage, pajak,
  dan rebalancing di pasar tutup — semuanya di luar scope dan
  tidak ada datanya.
- **Risiko biaya peluang:** 4–6 hari untuk (b) adalah 4–6 hari yang
  tidak dipakai untuk Scope 1, onchain, QA, dan submit — dan
  Ticko/Draft M menunggu di belakang kill-switch.

### 3.4 Klaim yang boleh dan tidak boleh dibuat (b)

- BOLEH (bila jadi): "agen mensimulasikan rebalance paper dari
  Exit Score, dengan log aksi lengkap."
- TIDAK BOLEH: "agen mengelola portofolio", "rebalancing live",
  "eksekusi di Base" — selama tidak ada eksekusi nyata dan quote
  firm.

## 4. Head-to-head

| Sumbu | (a) research-to-portfolio | (b) agent-managed rebalancing |
|---|---|---|
| Kesesuaian dgn yang sudah ada | Tinggi: `decide()` + `explain()` + `paper record` sudah mengeluarkan proposal | Rendah: tidak ada mesinnya; bertentangan dgn batas tertulis "tidak ada autonomous rebalancing" (`README.md:252`) |
| Pekerjaan yang dibutuhkan | ~2–3 hari: penyajian brief + penjadwalan + onchain hash | ~4–6 hari: mesin rebalance + pemicu + kontrol risiko + state lintas waktu + onchain |
| Muat di jendela 28–30 Nov? | Ya, bila Scope 1 tidak slip jauh | Tidak — dan Scope 1 belum mulai |
| Pasangan elemen onchain | (i) hash registry: brief + proposal di-hash (DESIGN §8 sudah ada spesifikasinya). Ini SEKALIGUS (ii): aksi agen = proposalnya | (ii) aksi rebalance di-hash — tapi aksinya simulasi di atas simulasi; registry membuktikan catatan ada, bukan bahwa sesuatu terjadi |
| Kemudahan demo (video 2–3 mnt) | Mudah: brief → proposal → alasan → hash. Skrip 6 scene sudah ada | Sulit: butuh deret waktu + log aksi yang belum ada |
| Risiko kill-switch 30 Nov | Rendah | Tinggi — kemungkinan besar terpicu |
| Kejujuran klaim | Bisa jujur penuh dgn label paper (a1) | Rawan overclaim ("managed" tanpa eksekusi) |
| Efek ke traction (dilaporkan 50%) | Tidak langsung; traction datang dari elemen onchain, bukan dari nama fitur | Tidak langsung juga — "rebalance" tanpa eksekusi nyata bukan traction |
| Yang dibutuhkan dari Septian | ACC (a1) + wallet/gas untuk registry + video/post/form | Sama + keputusan yang lebih besar soal eksekusi (paper vs nyata) |
| Jalan mundur bila gagal | Jatuh ke (a2): brief saja, tetap demo-able | Tidak ada jalan mundur yang murah — mesin setengah jadi |

## 5. Elemen onchain: (i) vs (ii) — dan kenapa ini keputusan yang lebih penting

Kandidat dari brief keputusan 23 Nov:

- **(i) Prediksi / Exit Score dipublikasi onchain (hash registry).**
  Spesifikasi SUDAH ADA (DESIGN §8): Base Sepolia hash registry
  untuk komitmen snapshot + keputusan paper portfolio + versi
  metodologi. Serialisasi JSON kanonis, SHA-256 seperti
  `snapshot_id`, hash mengikat versi metodologi, expiry 7 hari.
  Tujuan tertulis: membuktikan catatan sudah ada sebelum evaluasi
  hasil — BUKAN membuktikan data benar, return, compliance, atau
  traction. Deploy, transaksi, wallet menunggu gerbang + ACC
  eksplisit.
- **(ii) Aksi agen tercatat di Base.** Ini bukan alternatif dari
  (i) — ini (i) yang diterapkan ke output agen. Untuk (a): setiap
  brief + proposal harian di-hash. Untuk (b): setiap aksi rebalance
  di-hash.

**Jadi pasangan yang koheren adalah (a) + (i)/(ii):** agen
mengeluarkan brief + proposal setiap hari, dan setiap keluaran
dicatat hash-nya onchain. Satu alur, satu cerita untuk juri:
"agen yang bisa diaudit".

### 5.1 Sepolia vs mainnet — jujur soal nilainya

- **Base Sepolia (sesuai DESIGN §8):** gratis, aman, bisa didemo.
  Kelemahan jujur: testnet. Bila rubrik traction menghitung
  aktivitas onchain nyata, hash di Sepolia hampir tidak berbobot.
- **Base mainnet:** registry hanya menyimpan hash — tidak ada dana
  yang bergerak, biayanya hanya gas. Jadi mainnet layak secara
  biaya DAN memberi sinyal traction yang nyata. Yang dibutuhkan:
  wallet Septian (chief tidak pernah pegang seed/private key) +
  gas kecil + ACC eksplisit. Keputusan ini milik Septian, bukan
  chief.
- **Yang tidak boleh diklaim di kedua jaringan:** hash bukan bukti
  data benar, bukan bukti return, bukan bukti traction. Hash
  membuktikan *kapan* catatan itu ada — itu saja, dan itu sudah
  cukup sebagai cerita audit.

## 6. Rencana kerja 28–30 Nov bila (a) dipilih

| Kapan | Apa |
|---|---|
| 28 Nov | Scope 1 selesai (poller + universe + web + kalibrasi Exit Score Base) — ini prasyarat, bukan opsional |
| 28–29 Nov | Penyajian brief harian + penjadwalan; kontrak registry + skrip publish (Sepolia dulu; mainnet bila Septian ACC) |
| 29–30 Nov | Demo video direkam (skrip 6 scene sudah ada); QA chief (verifikasi dulu baru lapor) |
| **30 Nov** | **Kill-switch: Scope 1 + (a) + registry JALAN, atau BERHENTI** |
| 1–3 Des | Uji akhir + QA |
| 4–5 Des | Submit (form + post X + video) |

Bila (a2) yang dipilih (bukan a1), ganti baris 28–29 Nov dengan:
brief saja, proposal tetap terkunci — dan terima demo yang lebih
tipis.

## 7. Keputusan yang dibutuhkan dari Septian

1. **Pilih (a)** — rekomendasi chief. (b) ditolak dengan alasan di
   §3–§4, bukan karena "tidak keren".
2. **Pilih (a1) atau (a2)** — rekomendasi chief: (a1) dengan label
   paper yang melekat. (a1) butuh ACC eksplisit untuk relaksasi
   invariant `decide()` aturan 4–5 khusus jalur paper, dicatat
   sebagai keputusan sadar.
3. **Pilih pasangan onchain: (i) hash registry** — rekomendasi
   chief: ya, dan itu sekaligus (ii).
4. **Sepolia atau mainnet untuk registry** — rekomendasi chief:
   Sepolia dulu untuk membuktikan alur; mainnet bila Septian
   bersedia pakai wallet + gas (biaya hanya gas, tidak ada dana
   bergerak).
5. **Nama proyek final** — draf: "Radar — Exit Radar for Base
   Tokenized Stocks"; rekomendasi Claude: "Exit Radar" saja; nama
   live di radar.omdanny.site: "Exit Radar".

Keputusan 1–2 inilah yang menahan jadwal maju dari 28 Nov
(brief keputusan 23 Nov). Begitu diputuskan, jendela 28–30 Nov
bisa jalan.
