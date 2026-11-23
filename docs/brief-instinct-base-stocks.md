# Brief untuk Instinct — Base Stocks Maxxing: layak dibangun atau tidak?

> Tanggal: 22 Nov 2026 (sore WITA)
> Dari: Chief (via Septian)
> Sifat: minta review + vonis, bukan perintah kerja. Belum ada keputusan "gas".
> Tidak ada token/secret/kunci di dokumen ini.

## 1. Pertanyaan yang kami minta dijawab

1. **GO atau NO-GO?** Dengan 13 hari tersisa (tenggat 5 Des 2026), apakah Base Stocks Maxxing layak dibangun — atau lebih baik tidak usah, dan fokus tetap di jalur yang sudah berjalan?
2. **Kalau GO, fitur agen yang mana?** (a) research-to-portfolio agent, atau (b) agent-managed rebalancing? (Chief condong ke (a) — alasan di §5 — tapi silakan tidak setuju.)
3. **Elemen onchain minimal apa yang paling sederhana tapi kredibel?** Ini bagian yang belum ada desainnya. Tanpa ini, skor traction tidak bisa ditutup.
4. **Blind spot apa yang kami lewatkan?** Risiko, asumsi yang salah, atau biaya yang kami remehkan.

Jawaban boleh dalam bentuk apa pun yang nyaman buatmu — vonis singkat + alasan sudah cukup; skor (seperti review-review sebelumnya) boleh, tidak wajib.

## 2. Latar belakang

**Radar Tokenized Stocks** (proyek Septian, live di radar.omdanny.site) adalah radar deviasi + redemption untuk tokenized stocks: membandingkan harga token saham di berbagai venue, memeriksa redemption/Proof-of-Reserves, dan memberi Exit Score per ticker. Saat ini coverage-nya Solana, dan sifatnya **read-only** (hanya memonitor, tidak ada aksi onchain). Ada juga Monday Gap (prediksi arah Senin) yang shadow v1.1-nya baru live.

**Base Stocks Maxxing** adalah quest/hackathon Base. Fakta hadiah/track diverifikasi live 16 Nov 2026 (dari halaman resmi Base):
- Total hadiah Base **$50.000**; track yang paling cocok **Agentic Stock Finance $20.000** (alternatif: Programmable Stock Markets $20.000). Dibayar USDC di Base, umumnya ≤30 hari setelah verifikasi; pemenang wajib verifikasi ID + W-9/W-8.
- Tenggat submit: **5 Des 2026**. Jendela quest: 13 Nov–5 Des 2026.
- Eligibilitas: produk live yang sudah ada BOLEH ikut, asal ada fitur baru terkait saham yang dibangun selama quest. Radar tidak punya token, jadi aturan token tidak relevan.
- Penilaian: **50% traction / 25% kualitas produk / 25% build-in-public** — angka ini DILAPORKAN CryptoBriefing 6 Nov, **TIDAK terverifikasi di halaman resmi** (Rules §7 tidak menyebut angka itu). Kami memperlakukannya sebagai belum terkonfirmasi, tapi berasumsi traction onchain nyata itu penting. Kelemahan struktural Radar sekarang: read-only, jadi traction onchain = 0.

## 3. Rencana ketat (yang kami ajukan untuk direview)

Perkiraan kerja scope ketat: **~3 minggu** (riset 16 Nov). Sisa waktu 13 hari, jadi scope harus dipangkas ke ~60% — tidak ada ruang untuk fitur kedua.

**Scope (satu fitur agen + coverage Base, titik):**
1. **Coverage Base** — tokenized stock Coinbase di Base (mis. NVDAc / AAPLc) masuk poller + universe + web, metodologi sama seperti Solana (deviasi lintas-venue, redemption/PoR, Exit Score dikalibrasi ulang).
2. **Satu fitur agen** (pilih satu, jangan dua):
   - (a) research-to-portfolio agent: brief harian → usulan portofolio;
   - (b) agent-managed rebalancing: sinyal rebalance dari Exit Score.
3. **Elemen onchain minimal** (bagian tersulit, belum ada desain): sesuatu yang tercatat/dieksekusi di Base, bukan sekadar monitor. Kandidat: prediksi/Exit Score dipublikasi onchain, atau aksi agen yang tercatat di Base. Keputusan desain ini harus diambil di hari pertama — tanpa ini, skor traction tidak bisa ditutup.

**Yang DIPANGKAS:** semua chain lain, semua fitur agen kedua, polish web di luar demo, integrasi DEX Base di luar yang dibutuhkan scope 1.

**Jadwal + kill-switch:**

| Kapan | Apa |
|---|---|
| 22–23 Nov | Keputusan gas/tidak + pilih fitur agen (a)/(b) + desain elemen onchain |
| 24–27 Nov | Scope 1 (data Base) jalan; kalibrasi Exit Score Base |
| 28–30 Nov | Fitur agen + elemen onchain; demo video direkam |
| **30 Nov** | **KILL-SWITCH: bila integrasi Base belum jalan, BERHENTI.** Jangan korbankan Ticko/Draft M |
| 1–3 Des | Uji akhir + QA (cara kerja chief: verifikasi dulu baru lapor) |
| 4–5 Des | Submit (form + post X + video demo) |

**Yang hanya Septian yang bisa kerjakan:** post X + video demo + form submission; bila menang, verifikasi ID + W-9/W-8. Video demo itu waktu Septian — tidak bisa didelegasikan.

## 4. Yang berubah sejak rencana ini ditulis (22 Nov pagi)

Rencana di atas disusun pagi tadi, saat ada tiga jalur hidup. Sejak itu dua jalur sudah menutup — ini mengubah hitungan biaya peluang, dan kami sampaikan apa adanya:

- **make.fun token-radar-01 SELESAI.** Entry r17 (improved) sudah submit siang ini (15:40 WITA), lolos semua cek validasi, grading sedang jalan, hasil final 28 Des 2026. Tidak ada lagi kerja make.fun.
- **DFX.swiss chief-hunting DITUTUP** (vonis Instinct: kering). Dua laporan Others sudah masuk triase (500 refund + source map). Sisa hanya tes token kedaluwarsa 24 Nov (bagian chief, sudah terjadwal).
- **Ticko masih hidup:** Draft M (temuan stp_mode Instinct) sedang didraf Instinct; uji klaim faucet sub-account malam ini 21:18 WITA; Ronde 15 HOLD. Draft L belum ada email ack (tenggat Senin 23 Nov).
- **CMC API Hackathon (9–10 Des)** tetap jadi pembuka terbaik berikutnya setelah Ticko, dan tidak bentrok dengan tenggat Base (5 Des).

Jadi bila Base di-gas sekarang, jalur aktifnya tinggal Ticko + Base — bukan empat jalur seperti di rencana pagi.

## 5. Penilaian jujur chief (untuk diuji, bukan untuk diamini)

- **Rekomendasi chief: GO hanya dalam versi ketatnya.** Kalau scope mengembang melewati satu fitur agen + coverage Base, vonis chief berubah jadi NO-GO.
- **Fitur agen: chief condong ke (a)** research-to-portfolio — paling dekat dengan yang sudah ada (brief + skor sudah jadi pola kerja Radar), paling gampang didemo dalam video. (b) rebalancing lebih "agen" tapi butuh definisi eksekusi yang rapi dan lebih berisiko.
- **Bagian tersulit bukan data Base, melainkan elemen onchain.** Data Base + kalibrasi Exit Score itu kerja yang sudah kami kuasai polanya (sama seperti Solana). Yang belum ada desainnya — dan yang menentukan skor traction — adalah apa yang tercatat/dieksekusi di Base. Kalau desain ini tidak ketemu di hari pertama, rencana ini rapuh.
- **Ketidakpastian terbesar: bobot traction 50% itu belum terkonfirmasi.** Kalau ternyata bobot traction lebih kecil dari yang dilaporkan, nilai dari elemen onchain ikut mengecil — dan rencana ini jadi kurang menarik.
- **Risiko fokus:** yang tersulit buat Septian kemungkinan besar bukan teknisnya, tapi menjaga fokus 13 hari tanpa mengorbankan Ticko (Draft M + faucet) — itu sebabnya ada kill-switch 30 Nov.

## 6. Yang kami minta darimu

- Vonis **GO / NO-GO** (atau GO dengan syarat — sebutkan syaratnya).
- Kalau GO: pilih **(a) atau (b)**, dan usulkan **desain elemen onchain paling sederhana yang kredibel** (yang bisa selesai dalam jadwal di atas).
- Sebutkan **satu risiko terbesar** yang menurutmu paling mungkin menggagalkan rencana ini.
- Kalau ada, sebutkan juga **apa yang harus kami cek/ukur dulu** sebelum memutuskan gas (mis. satu fakta yang kalau ternyata berbeda akan membalik vonis).

## 7. Cara membalas

Balas lewat Septian seperti biasa (dia yang meneruskan). Kalau ada bagian rencana yang menurutmu salah fakta atau salah asumsi, sebutkan langsung — kami lebih butuh koreksi daripada persetujuan. Terima kasih.
