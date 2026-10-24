BOT HADIST v2 - CATATAN PEMASANGAN
======================================================================
Folder ini berisi versi perbaikan. File lama di folder induk TIDAK diubah.

ISI
  main.py, handlers.py, api_client.py, config.py, requirements.txt
  (index_hadist.json dan bot.lock dibuat otomatis saat bot berjalan)

YANG DIPERBAIKI
  1. /cari berfungsi (indeks judul, disimpan ke index_hadist.json) dan
     terdaftar sebagai perintah. Tombol "Cari" meminta kata kunci lalu
     memprosesnya dari pesan berikutnya.
  2. Token tidak lagi tertulis di log (httpx dibungkam + filter redaksi).
  3. /hadist 2962 atau /hadist 2962-id dan bahasa default Indonesia.
  4. Tanpa parse_mode Markdown, jadi teks API tidak membuat pesan gagal.
  5. Pesan panjang dipecah per potongan (batas Telegram 4096).
  6. API gagal -> pesan "server tidak bisa dihubungi" (bukan "kosong").
  7. Token kosong -> keluar dengan kode 1 (bukan loop restart diam-diam).
  8. Pidfile diganti flock (bot.lock), aman saat crash.
  9. Navigasi tombol mengedit pesan, ada halaman berikutnya/sebelumnya,
     tombol Teks Arab, peringatan jika derajat bukan shahih, dan
     footer "Sumber: HadeethEnc.com".
  10. Satu session HTTP bersama, cache 1 jam, retry otomatis.
  Alias perintah lama (/hadist_start, /hadist_kategori, /hadist_list,
  /hadist_detail) tetap bekerja.

PENGUJIAN (sudah dilakukan di lingkungan saya)
  Kompilasi lolos, dan uji dengan server API tiruan + objek Telegram
  tiruan lolos: indeks dan pencarian, pemecahan pesan panjang, navigasi
  callback, pesan error saat API mati.
  BELUM diuji: koneksi ke Telegram dan API HadeethEnc yang asli.

LANGKAH PEMASANGAN
  1. Cadangkan:   cp -r /home/bams/bot-toko/hadeethenc-bot /home/bams/bot-toko/hadeethenc-bot.bak
  2. Hentikan:    systemctl --user stop bot-hadist
  3. Pasang dependensi dengan Python yang dipakai service:
       /home/bams/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3 \
         -m pip install -r /home/bams/bot-toko/hadeethenc-bot/v2/requirements.txt
  4. Uji manual dari folder v2 (satu instance saja):
       cd /home/bams/bot-toko/hadeethenc-bot/v2
       <python di atas> main.py
     Kirim /start, /kategori, /hadist 2962, /cari niat dari chat pribadi.
     Hentikan dengan Ctrl+C setelah semuanya berjalan.
  5. Jika baik, ubah service:
       WorkingDirectory=/home/bams/bot-toko/hadeethenc-bot/v2
       ExecStart=<python di atas> /home/bams/bot-toko/hadeethenc-bot/v2/main.py
     lalu: systemctl --user daemon-reload && systemctl --user start bot-hadist
  6. Pantau: journalctl --user -u bot-hadist -f

CATATAN
  - .env dicari di folder v2 lalu folder induknya. Nama variabel:
    TELEGRAM_BOT_TOKEN (TELEGRAM_TOKEN juga diterima). ADMIN_ID opsional,
    untuk perintah /perbarui.
  - Pembuatan indeks pertama kali bisa beberapa menit.
  - Cek apakah log lama memuat token:
       grep -c 'api.telegram.org/bot' ../bot-service.err ../bot_hadeeth.log
    Jika hasilnya lebih dari 0, revoke token di @BotFather, ganti di .env,
    lalu hapus atau putar file log lama.
  - Pencarian hanya pada judul hadist (API tidak menyediakan pencarian teks).
