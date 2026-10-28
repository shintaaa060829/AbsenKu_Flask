# AbsenKu - Flask

## Menjalankan di Windows / VS Code

1. Ekstrak folder `AbsenKu_Flask`.
2. Buka folder tersebut di VS Code.
3. Buka Terminal -> New Terminal.
4. Jalankan:
   ```powershell
   py -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python app.py
   ```
   Jika PowerShell menolak aktivasi venv, jalankan `python -m pip install -r requirements.txt` lalu `python app.py` tanpa aktivasi.
5. Buka `http://127.0.0.1:5000`.

## Akun awal administrator
- Username: `admin`
- Password: `AbsenKu123!`

Login di `/login`, lalu buka Profil Admin untuk mengganti nama, username, dan password. Jangan bagikan akun admin kepada siswa.

## Alur
- Publik: `/absen` hanya menampilkan formulir pengiriman absensi (NIS + status). Tidak menampilkan daftar siswa atau rekap.
- Admin: `/login`, lalu dapat mengakses Dashboard, Data Siswa, Absensi Harian, dan Profil Admin.
- Database SQLite dibuat otomatis sebagai `absensi.db` pada folder proyek.
- Data absensi per siswa per tanggal hanya satu baris; pengiriman ulang pada hari yang sama memperbarui statusnya.

Catatan: aplikasi ini cocok untuk tugas/proyek lokal. Sebelum dipakai di internet, atur `ABSENKU_SECRET_KEY` yang kuat, matikan debug mode, dan tambahkan perlindungan CSRF serta HTTPS.
