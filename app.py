import os
import sqlite3
from functools import wraps
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("ABSENKU_SECRET_KEY", "ganti-secret-key-absenku-sebelum-deploy")
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "absensi.db")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            nama TEXT NOT NULL DEFAULT 'Administrator'
        );
        CREATE TABLE IF NOT EXISTS siswa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nis TEXT NOT NULL UNIQUE,
            nama TEXT NOT NULL,
            kelas TEXT NOT NULL,
            jurusan TEXT NOT NULL DEFAULT '-',
            alamat TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS absensi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            siswa_id INTEGER NOT NULL,
            tanggal TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Hadir','Izin','Sakit','Alpa')),
            waktu TEXT NOT NULL,
            UNIQUE(siswa_id, tanggal),
            FOREIGN KEY(siswa_id) REFERENCES siswa(id) ON DELETE CASCADE
        );
    """)
    existing = db.execute("SELECT id FROM admin LIMIT 1").fetchone()
    if not existing:
        username = os.environ.get("ABSENKU_ADMIN_USER", "admin")
        password = os.environ.get("ABSENKU_ADMIN_PASSWORD", "AbsenKu123!")
        db.execute(
            "INSERT INTO admin (username, password_hash, nama) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), "Administrator")
        )
    db.commit()
    db.close()

@app.before_request
def ensure_database():
    if not os.path.exists(DB_PATH):
        init_db()

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Silakan login sebagai administrator terlebih dahulu.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    # Halaman publik hanya untuk mengisi absensi, tidak menampilkan daftar siswa.
    return redirect(url_for("absen_public"))


@app.route("/absen", methods=["GET", "POST"])
def absen_public():
    if request.method == "POST":
        nama = request.form.get("nama", "").strip()
        status = request.form.get("status", "").strip()
        tanggal_hari_ini = date.today().isoformat()

        if not nama or status not in ("Hadir", "Izin", "Sakit", "Alpa"):
            flash("Masukkan nama dan pilih status kehadiran yang benar.", "danger")
            return redirect(url_for("absen_public"))

        db = get_db()

        # Cari siswa menggunakan nama yang terdaftar
        siswa_list = db.execute(
            "SELECT id FROM siswa WHERE nama = ? COLLATE NOCASE",
            (nama,)
        ).fetchall()

        if not siswa_list:
            flash("Nama tidak terdaftar. Periksa nama lengkap kamu.", "danger")
            return redirect(url_for("absen_public"))

        # Cegah absensi salah jika ada nama yang sama
        if len(siswa_list) > 1:
            flash(
                "Nama kamu sama dengan siswa lain. "
                "Hubungi administrator untuk memastikan data.",
                "danger"
            )
            return redirect(url_for("absen_public"))

        siswa = siswa_list[0]
        waktu = datetime.now().strftime("%H:%M:%S")

        # Simpan absensi. Jika sudah absen hari ini,
        # statusnya diperbarui, bukan membuat data ganda.
        db.execute("""
            INSERT INTO absensi (siswa_id, tanggal, status, waktu)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(siswa_id, tanggal)
            DO UPDATE SET
                status = excluded.status,
                waktu = excluded.waktu
        """, (siswa["id"], tanggal_hari_ini, status, waktu))

        db.commit()
        flash("Absensi berhasil dikirim.", "success")
        return redirect(url_for("absen_public"))

    return render_template(
        "absen_public.html",
        today=date.today().strftime("%d-%m-%Y")
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_id"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = get_db().execute("SELECT * FROM admin WHERE username = ?", (username,)).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            flash("Berhasil login.", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("admin_dashboard"))
        flash("Username atau password salah.", "danger")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@admin_required
def logout():
    session.clear()
    flash("Kamu sudah logout.", "success")
    return redirect(url_for("login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    total_siswa = db.execute("SELECT COUNT(*) n FROM siswa").fetchone()["n"]
    total_kelas = db.execute("SELECT COUNT(DISTINCT kelas) n FROM siswa").fetchone()["n"]
    hadir_hari_ini = db.execute(
        "SELECT COUNT(*) n FROM absensi WHERE tanggal = ? AND status = 'Hadir'",
        (date.today().isoformat(),)
    ).fetchone()["n"]
    recent = db.execute("""
        SELECT a.tanggal, a.status, a.waktu, s.nis, s.nama, s.kelas
        FROM absensi a JOIN siswa s ON s.id = a.siswa_id
        ORDER BY a.tanggal DESC, a.waktu DESC LIMIT 8
    """).fetchall()
    return render_template("admin_dashboard.html", total_siswa=total_siswa,
                           total_kelas=total_kelas, hadir_hari_ini=hadir_hari_ini,
                           recent=recent)

@app.route("/admin/siswa", methods=["GET"])
@admin_required
def data_siswa():
    db = get_db()
    cari = request.args.get("cari", "").strip()
    if cari:
        like = f"%{cari}%"
        siswa = db.execute("""
            SELECT * FROM siswa WHERE nis LIKE ? OR nama LIKE ? OR kelas LIKE ?
            ORDER BY nama COLLATE NOCASE
        """, (like, like, like)).fetchall()
    else:
        siswa = db.execute("SELECT * FROM siswa ORDER BY nama COLLATE NOCASE").fetchall()
    return render_template("data_siswa.html", siswa=siswa, cari=cari)

@app.route("/admin/siswa/tambah", methods=["POST"])
@admin_required
def tambah_siswa():
    nis = request.form.get("nis", "").strip()
    nama = request.form.get("nama", "").strip()
    kelas = request.form.get("kelas", "").strip()
    jurusan = request.form.get("jurusan", "").strip() or "-"
    alamat = request.form.get("alamat", "").strip()
    if not all([nis, nama, kelas]):
        flash("NIS, nama, dan kelas wajib diisi.", "danger")
        return redirect(url_for("data_siswa"))
    try:
        get_db().execute(
            "INSERT INTO siswa (nis, nama, kelas, jurusan, alamat) VALUES (?, ?, ?, ?, ?)",
            (nis, nama, kelas, jurusan, alamat)
        )
        get_db().commit()
        flash("Data siswa berhasil ditambahkan.", "success")
    except sqlite3.IntegrityError:
        flash("NIS sudah terdaftar. Gunakan NIS yang berbeda.", "danger")
    return redirect(url_for("data_siswa"))

@app.route("/admin/siswa/edit/<int:siswa_id>", methods=["POST"])
@admin_required
def edit_siswa(siswa_id):
    nis = request.form.get("nis", "").strip()
    nama = request.form.get("nama", "").strip()
    kelas = request.form.get("kelas", "").strip()
    jurusan = request.form.get("jurusan", "").strip() or "-"
    alamat = request.form.get("alamat", "").strip()
    if not all([nis, nama, kelas]):
        flash("NIS, nama, dan kelas wajib diisi.", "danger")
        return redirect(url_for("data_siswa"))
    try:
        db = get_db()
        db.execute("UPDATE siswa SET nis=?, nama=?, kelas=?, jurusan=?, alamat=? WHERE id=?",
                   (nis, nama, kelas, jurusan, alamat, siswa_id))
        db.commit()
        flash("Data siswa berhasil diperbarui.", "success")
    except sqlite3.IntegrityError:
        flash("NIS sudah digunakan siswa lain.", "danger")
    return redirect(url_for("data_siswa"))

@app.route("/admin/siswa/hapus/<int:siswa_id>", methods=["POST"])
@admin_required
def hapus_siswa(siswa_id):
    db = get_db()
    db.execute("DELETE FROM siswa WHERE id=?", (siswa_id,))
    db.commit()
    flash("Data siswa dan riwayat absensinya dihapus.", "success")
    return redirect(url_for("data_siswa"))

@app.route("/admin/absensi", methods=["GET", "POST"])
@admin_required
def absensi_harian():
    tanggal = request.values.get("tanggal", date.today().isoformat())
    try:
        datetime.strptime(tanggal, "%Y-%m-%d")
    except ValueError:
        tanggal = date.today().isoformat()
    db = get_db()
    if request.method == "POST":
        status_data = request.form
        for key, value in status_data.items():
            if key.startswith("status_") and value in ("Hadir", "Izin", "Sakit", "Alpa"):
                try:
                    siswa_id = int(key.split("_", 1)[1])
                except ValueError:
                    continue
                db.execute("""
                    INSERT INTO absensi (siswa_id, tanggal, status, waktu)
                    SELECT id, ?, ?, ?
                    FROM siswa WHERE id = ?
                    ON CONFLICT(siswa_id, tanggal)
                    DO UPDATE SET status=excluded.status, waktu=excluded.waktu
                """, (tanggal, value, datetime.now().strftime("%H:%M:%S"), siswa_id))
        db.commit()
        flash("Absensi harian berhasil disimpan.", "success")
        return redirect(url_for("absensi_harian", tanggal=tanggal))
    cari = request.args.get("cari", "").strip()
    params = [tanggal]
    sql = """
        SELECT s.id, s.nis, s.nama, s.kelas, a.status, a.waktu
        FROM siswa s LEFT JOIN absensi a ON a.siswa_id=s.id AND a.tanggal=?
    """
    if cari:
        sql += " WHERE s.nis LIKE ? OR s.nama LIKE ? OR s.kelas LIKE ?"
        like = f"%{cari}%"
        params.extend([like, like, like])
    sql += " ORDER BY s.kelas, s.nama COLLATE NOCASE"
    rows = db.execute(sql, params).fetchall()
    return render_template("absensi_harian.html", rows=rows, tanggal=tanggal, cari=cari)

@app.route("/admin/profil", methods=["GET", "POST"])
@admin_required
def profil_admin():
    db = get_db()
    admin = db.execute("SELECT * FROM admin WHERE id=?", (session["admin_id"],)).fetchone()
    if not admin:
        session.clear()
        return redirect(url_for("login"))
    if request.method == "POST":
        nama = request.form.get("nama", "").strip()
        username = request.form.get("username", "").strip()
        password_lama = request.form.get("password_lama", "")
        password_baru = request.form.get("password_baru", "")
        if not nama or not username:
            flash("Nama dan username tidak boleh kosong.", "danger")
            return redirect(url_for("profil_admin"))
        if not check_password_hash(admin["password_hash"], password_lama):
            flash("Password lama tidak sesuai.", "danger")
            return redirect(url_for("profil_admin"))
        try:
            if password_baru:
                if len(password_baru) < 8:
                    flash("Password baru minimal 8 karakter.", "danger")
                    return redirect(url_for("profil_admin"))
                db.execute("UPDATE admin SET nama=?, username=?, password_hash=? WHERE id=?",
                           (nama, username, generate_password_hash(password_baru), admin["id"]))
            else:
                db.execute("UPDATE admin SET nama=?, username=? WHERE id=?",
                           (nama, username, admin["id"]))
            db.commit()
            session["admin_username"] = username
            flash("Profil administrator berhasil diperbarui.", "success")
        except sqlite3.IntegrityError:
            flash("Username sudah digunakan.", "danger")
        return redirect(url_for("profil_admin"))
    return render_template("profil_admin.html", admin=admin)

@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5001, debug=False)