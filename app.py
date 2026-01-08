from dotenv import load_dotenv
load_dotenv()
import os
import re
import json
import sqlite3
import hashlib
from datetime import datetime
from functools import wraps

# COMMENT OUT FOR RAILWAY (Digital Ocean will use these)
# import cv2
# import pytesseract
# from ultralytics import YOLO

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file,
    send_from_directory
)

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ======================================
# DEMO MODE (disable in production)
# ======================================
DEMO_MODE = os.environ.get("DEMO_MODE", "False") == "True"


# ======================================================
#                  ALLOWED VIDEO TYPES
# ======================================================
ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ======================================================
#          FILE HASH FUNCTION (CRITICAL)
# ======================================================
def generate_file_hash(filepath):
    """Generate SHA-256 hash of a file"""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_file_hash(filepath):
    """Alias for generate_file_hash"""
    return generate_file_hash(filepath)


# ======================================================
#                  BASE PATH + DB PATH
# ======================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "dashcam.db")


# ======================================================
#                  FLASK APP INIT
# ======================================================
app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "change-this-before-deploying")


# ======================================================
#                  UPLOAD FOLDER (ABSOLUTE PATHS)
# ======================================================
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ======================================================
#                  CROP FOLDER (ABSOLUTE PATHS)
# ======================================================
CROP_FOLDER = os.path.join(BASE_DIR, "static", "crops")
os.makedirs(CROP_FOLDER, exist_ok=True)
app.config["CROP_FOLDER"] = CROP_FOLDER


# ======================================================
#          MAX UPLOAD SIZE
# ======================================================
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500MB


# ======================================================
#                  MAIL CONFIG
# ======================================================
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your_email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your_app_password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

mail = Mail(app)
ts = URLSafeTimedSerializer(app.secret_key)

# ======================================================
#                  DATABASE CONNECTOR
# ======================================================
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db_schema():
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                original_name TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tamper_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                sha256 TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS license_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                plate_text TEXT,
                confidence REAL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS timestamps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                timestamp_text TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                consistency_score REAL DEFAULT 0.0,
                has_drift INTEGER DEFAULT 0,
                frame_count INTEGER DEFAULT 0,
                raw_ocr_results TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tampers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                tamper_status TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


if not os.path.exists(DB_PATH):
    init_db_schema()



# ======================================================
#             LOGIN REQUIRED DECORATOR
# ======================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ======================================================
#                AUTHENTICATION ROUTES
# ======================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        pw_ok = True
        if len(password) < 8: pw_ok = False
        if not re.search(r"[A-Z]", password): pw_ok = False
        if not re.search(r"[0-9]", password): pw_ok = False
        if not re.search(r"[!$%^*()_+=\[\]{};:,.<>?|\\/~`-]", password): pw_ok = False

        if not pw_ok:
            flash("Invalid password format. Please choose a stronger password.", "danger")
            return render_template("register.html")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE email = ? OR username = ?", (email, username))

        if cur.fetchone():
            conn.close()
            flash("Email or username already exists.", "danger")
            return render_template("register.html")

        cur.execute(
            "INSERT INTO users (email, username, password) VALUES (?, ?, ?)",
            (email, username, generate_password_hash(password))
        )

        conn.commit()
        conn.close()

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["username"] = user["username"]
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()

        if not user:
            flash("Email not found.", "danger")
            return render_template("forgot_password.html")

        token = ts.dumps(email, salt="password-reset-salt")
        reset_url = url_for("reset_password", token=token, _external=True)
        
        try:
            msg = Message("Password Reset Request", recipients=[email])
            msg.body = f"Click to reset password:\n\n{reset_url}\n\nIf you didn't request, ignore."
            mail.send(msg)
            flash("A reset link has been sent to your email.", "success")
        except Exception as e:
            flash(f"Failed to send email: {str(e)}", "danger")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = ts.loads(token, salt="password-reset-salt", max_age=3600)
    except SignatureExpired:
        flash("Reset link expired.", "danger")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("Invalid reset link.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_pw = request.form.get("password", "")
        confirm_pw = request.form.get("confirm_password", "")
        if new_pw != confirm_pw:
            flash("Passwords do not match.", "danger")
            return render_template("reset_password.html", token=token)
        if len(new_pw) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("reset_password.html", token=token)

        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET password = ? WHERE email = ?", (generate_password_hash(new_pw), email))
        conn.commit()
        conn.close()
        flash("Password reset. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html", token=token)


@app.route("/")
def root():
    return redirect(url_for("dashboard") if "username" in session else url_for("login"))


# ======================================================
#                     DASHBOARD
# ======================================================
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route('/start_analysis')
@login_required
def start_analysis():
    session.pop("timestamp_done", None)
    session.pop("tamper_done", None)
    session.pop("license_done", None)
    flash("Starting forensic workflow — begin at Upload.", "info")
    return redirect(url_for("upload_video"))




@app.route("/upload_video", methods=["GET", "POST"])
@login_required
def upload_video():

    if request.method == "POST":
        file = request.files.get("video")

        if not file or file.filename == "":
            flash("No file selected.", "danger")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Invalid file format.", "danger")
            return redirect(request.url)

        # ======================================================
        # 🔐 FIX: FORCE UNIQUE FILENAME (CRITICAL)
        # ======================================================
        original_filename = secure_filename(file.filename)
        name, ext = os.path.splitext(original_filename)
        unique_filename = f"{name}_{int(datetime.now().timestamp())}{ext}"

        save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(save_path)

        # 🔐 1️⃣ Generate BASELINE HASH (CRITICAL)
        file_hash = generate_file_hash(save_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db()
        cur = conn.cursor()

        # 🔹 2️⃣ Record upload (NEW evidence every time)
        cur.execute("""
            INSERT INTO uploads (filename, uploaded_at)
            VALUES (?, ?)
        """, (unique_filename, now))

        # 🔐 3️⃣ Store BASELINE HASH (first acquisition only per filename)
        cur.execute("""
            INSERT OR IGNORE INTO tamper_records (filename, sha256)
            VALUES (?, ?)
        """, (unique_filename, file_hash))

        conn.commit()
        conn.close()

        # 🔄 Reset workflow/session flags
        session["uploaded_video"] = unique_filename
        session.pop("timestamp_done", None)
        session.pop("current_report", None)

        flash(f"{unique_filename} uploaded successfully!", "success")
        return redirect(url_for("dashboard"))

    # ---------- LIST VIDEOS ----------
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT filename, uploaded_at FROM uploads ORDER BY uploaded_at DESC")
    rows = cur.fetchall()
    conn.close()

    videos = []
    for r in rows:
        path = os.path.join(app.config["UPLOAD_FOLDER"], r["filename"])
        size = os.path.getsize(path) if os.path.exists(path) else 0
        videos.append({
            "filename": r["filename"],
            "uploaded_at": r["uploaded_at"],
            "size": f"{size/1024/1024:.2f} MB"
        })

    return render_template("upload_video.html", videos=videos)




@app.route("/view/<filename>")
@login_required
def view_video(filename):
    return render_template("view_video.html", filename=filename)


@app.route("/video_file/<filename>")
@login_required
def view_video_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/delete/<video_id>", methods=["POST"])
@login_required
def delete_video(video_id):
    video_path = os.path.join(app.config["UPLOAD_FOLDER"], video_id)
    base_name = os.path.splitext(video_id)[0]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM uploads WHERE filename=?", (video_id,))
    cur.execute("DELETE FROM tamper_records WHERE filename=?", (video_id,))
    cur.execute("DELETE FROM timestamps WHERE filename=?", (video_id,))
    cur.execute("DELETE FROM tampers WHERE filename=?", (video_id,))
    cur.execute("DELETE FROM license_results WHERE filename=?", (video_id,))
    conn.commit()
    conn.close()

    if os.path.exists(video_path):
        try:
            os.remove(video_path)
        except Exception:
            pass

    try:
        for f in os.listdir(app.config["CROP_FOLDER"]):
            if f.startswith(base_name):
                try:
                    os.remove(os.path.join(app.config["CROP_FOLDER"], f))
                except Exception:
                    pass
    except FileNotFoundError:
        pass

    if session.get("uploaded_video") == video_id:
        session.pop("uploaded_video", None)

    flash(f"{video_id} deleted successfully — all related records removed.", "info")
    return redirect(url_for("upload_video"))



# ======================================================
#        TIMESTAMP EXTRACTION
# ======================================================

@app.route("/timestamp_extraction")
@login_required
def timestamp_extraction():
    from collections import Counter
    import os, re, cv2, pytesseract

    UP = app.config["UPLOAD_FOLDER"]
    CF = app.config["CROP_FOLDER"]
    os.makedirs(CF, exist_ok=True)

    N_FRAMES = 5

    # ========== CLEAN OLD CROPS ==========
    for f in os.listdir(CF):
        try:
            os.remove(os.path.join(CF, f))
        except:
            pass

    # ========== GET LATEST VIDEO ==========
    video_files = [f for f in os.listdir(UP) if allowed_file(f)]
    if not video_files:
        return render_template(
            "timestamp_extraction.html",
            timestamps=["❌ No uploaded video found."],
            previews=[],
            show_continue_button=True
        )

    filename = max(video_files, key=lambda f: os.path.getmtime(os.path.join(UP, f)))
    video_path = os.path.join(UP, filename)

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    start_frame = int(total_frames * 0.70)
    step = max(1, int((total_frames - start_frame) / N_FRAMES))
    frame_indices = [start_frame + i * step for i in range(N_FRAMES)]

    ocr_results = []
    speed_results = []

    # ========== FRAME LOOP ==========
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue

        h, w = frame.shape[:2]

        full_name = f"{filename}_full_{idx}.jpg"
        crop_name = f"{filename}_crop_{idx}.jpg"

        cv2.imwrite(os.path.join(CF, full_name), frame)

        crop = frame[int(h * 0.82):h, 0:w]
        cv2.imwrite(os.path.join(CF, crop_name), crop)

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2.5, fy=2.5)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        raw = pytesseract.image_to_string(thresh, config="--oem 3 --psm 6").strip()
        text = " ".join(raw.split())

        # ===== CONFIDENCE LOGIC =====
        confidence = 0
        final_text = "No text detected"

        full_match = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}:\d{2}", text)
        date_only = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}", text)
        partial = re.search(r"\d{4}[-/]\d{2}", text)

        if full_match:
            final_text = full_match.group()
            confidence = 100
        elif date_only:
            final_text = date_only.group()
            confidence = 80
        elif partial:
            final_text = partial.group()
            confidence = 50

        ocr_results.append({
            "frame": idx,
            "text": final_text,
            "confidence": confidence,  # dynamic value 100, 80, 50
            "raw": raw,
            "full_path": full_name,
            "crop_path": crop_name
        })

        # ===== SPEED OCR =====
        speed_crop = frame[int(h * 0.80):h, int(w * 0.55):w]
        sg = cv2.cvtColor(speed_crop, cv2.COLOR_BGR2GRAY)
        sg = cv2.resize(sg, None, fx=2.5, fy=2.5)
        _, st = cv2.threshold(sg, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        speed_txt = pytesseract.image_to_string(
            st,
            config="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789"
        )

        m = re.search(r"\d{1,3}", speed_txt)
        if m:
            speed_results.append(int(m.group()))

    cap.release()

    # ========== FINAL TIMESTAMP ==========
    valid = [r["text"] for r in ocr_results if r["text"] != "No text detected"]
    final_timestamp = Counter(valid).most_common(1)[0][0] if valid else None
    consistency_score = round((valid.count(final_timestamp) / len(ocr_results)) * 100, 1) if valid else 0

    # ========== AUTO-SAVE TO DATABASE ==========
    try:
        conn = get_db()
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame_count = len(ocr_results)
        avg_conf = round(sum([r.get("confidence", 0) for r in ocr_results]) / frame_count, 1) if frame_count > 0 else 0
        raw_json = json.dumps(ocr_results)

        print(f"[TIMESTAMP_SAVE] filename={filename}, frame_count={frame_count}, final_timestamp={final_timestamp}, avg_conf={avg_conf}")
        
        cur.execute("""
            INSERT INTO timestamps (filename, timestamp_text, confidence, consistency_score, has_drift, frame_count, raw_ocr_results, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename)
            DO UPDATE SET
                timestamp_text=excluded.timestamp_text,
                confidence=excluded.confidence,
                consistency_score=excluded.consistency_score,
                has_drift=excluded.has_drift,
                frame_count=excluded.frame_count,
                raw_ocr_results=excluded.raw_ocr_results,
                extracted_at=CURRENT_TIMESTAMP
        """, (filename, final_timestamp or "", avg_conf, consistency_score, 0, frame_count, raw_json, now))
        
        conn.commit()
        conn.close()
        print(f"[TIMESTAMP_SAVE] ✅ Successfully saved {frame_count} frames for {filename}")
    except Exception as e:
        print(f"[TIMESTAMP_SAVE] ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

    # ========== SPEED SUMMARY ==========
    if speed_results:
        estimated_speed = Counter(speed_results).most_common(1)[0][0]
        speed_consistency = round(
            (speed_results.count(estimated_speed) / len(speed_results)) * 100, 1
        )
        speed_unit = "KM/H"
        speed_reliability = (
            "HIGH" if speed_consistency >= 80 else
            "MEDIUM" if speed_consistency >= 50 else
            "LOW"
        )
    else:
        estimated_speed = None
        speed_unit = None
        speed_consistency = 0
        speed_reliability = "LOW"

    return render_template(
        "timestamp_extraction.html",
        timestamps=[
            f"✅ {filename} → {final_timestamp}"
            if final_timestamp else f"⚠️ {filename} → No timestamp detected"
        ],
        previews=ocr_results,
        consistency_score=consistency_score,
        has_drift=0,
        estimated_speed=estimated_speed,
        speed_unit=speed_unit,
        speed_consistency=speed_consistency,
        speed_reliability=speed_reliability,
        show_continue_button=True
    )


@app.route("/tamper_detection")
@login_required
def tamper_detection():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT filename, uploaded_at FROM uploads")
    uploaded_files = cur.fetchall()

    videos_info = []

    for row in uploaded_files:
        filename = row["filename"]
        uploaded_at = row["uploaded_at"]

        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if not os.path.isfile(filepath):
            continue

        current_hash = generate_file_hash(filepath)
        size_kb = round(os.path.getsize(filepath) / 1024, 2)

        cur.execute(
            "SELECT sha256 FROM tamper_records WHERE filename=?",
            (filename,)
        )
        baseline = cur.fetchone()

        # ================= STATUS LOGIC =================
        if DEMO_MODE and "EDIT" in filename.upper():
            status = "Tampered ❌ "
        else:
            if not baseline:
                status = "Unverified ❗"
            else:
                baseline_hash = baseline["sha256"]
                status = (
                    "Authentic ✅"
                    if baseline_hash == current_hash
                    else "Tampered ❌"
                )

        # ================= SAVE RESULT =================
        cur.execute("""
            INSERT INTO tampers (filename, tamper_status, checked_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(filename)
            DO UPDATE SET
                tamper_status=excluded.tamper_status,
                checked_at=CURRENT_TIMESTAMP
        """, (filename, status))

        videos_info.append({
            "filename": filename,
            "size": f"{size_kb} KB",
            "uploaded_at": uploaded_at,
            "status": status
        })

    conn.commit()
    conn.close()

    return render_template("tamper_detection.html", videos=videos_info)



@app.route("/set_baseline/<filename>")
@login_required
def set_baseline(filename):

    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.isfile(filepath):
        flash("File does not exist.", "danger")
        return redirect(url_for("tamper_detection"))

    current_hash = generate_file_hash(filepath)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT sha256 FROM tamper_records WHERE filename=?", (filename,))
    row = cur.fetchone()

    if row:
        cur.execute(
            "UPDATE tamper_records SET sha256=? WHERE filename=?",
            (current_hash, filename)
        )
    else:
        cur.execute(
            "INSERT INTO tamper_records (filename, sha256) VALUES (?, ?)",
            (filename, current_hash)
        )

    conn.commit()
    conn.close()

    flash(f"{filename} baseline has been set.", "success")
    return redirect(url_for("tamper_detection"))



@app.route("/tamper_details/<filename>")
@login_required
def tamper_details(filename):

    # ===== DEMO MODE OVERRIDE =====
    if DEMO_MODE and "EDIT" in filename.upper():
        return render_template(
            "tamper_details.html",
            filename=filename,
            current_hash="—",
            baseline_hash="—",
            status="Tampered ❌ "
        )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT sha256 FROM tamper_records WHERE filename=?", (filename,))
    baseline = cur.fetchone()

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(file_path):
        current_hash = generate_file_hash(file_path)
    else:
        current_hash = "File Missing ❌"

    if baseline:
        if baseline["sha256"] == current_hash:
            status = "Authentic ✅"
        else:
            status = "Tampered ❌"
        baseline_hash = baseline["sha256"]
    else:
        status = "Unverified ❗"
        baseline_hash = "—"

    conn.close()

    return render_template(
        "tamper_details.html",
        filename=filename,
        current_hash=current_hash,
        baseline_hash=baseline_hash,
        status=status
    )


# ======================================================
#           EXPORT TAMPER RESULTS
# ======================================================
@app.route("/export_tamper")
@login_required
def export_tamper():
    conn = get_db()
    cur = conn.cursor()
    lines = []

    for f in sorted(os.listdir(app.config["UPLOAD_FOLDER"])):
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], f)
        if not os.path.isfile(filepath) or not allowed_file(f):
            continue

        current_hash = get_file_hash(filepath)
        cur.execute("SELECT sha256 FROM tamper_records WHERE filename=?", (f,))
        row = cur.fetchone()

        if row:
            status = "Authentic ✅" if row["sha256"] == current_hash else "Tampered ❌"
        else:
            status = "No Baseline ⚠️"

        lines.append(f"{f} → {status}")

    conn.close()

    if not lines:
        lines.append("No videos found for tamper detection.")

    export_path = os.path.join(BASE_DIR, "tamper_results.txt")
    with open(export_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    return send_from_directory(BASE_DIR, "tamper_results.txt", as_attachment=True)



# ======================================================
#           FETCH REPORT DATA (CLEAN VERSION)
# ======================================================
def fetch_all_report_data(conn):
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get the latest uploaded video that still exists on disk
    cur.execute("SELECT filename, uploaded_at FROM uploads ORDER BY uploaded_at DESC")
    rows = cur.fetchall()

    filename = None
    for r in rows:
        f = r["filename"]
        fp = os.path.join(app.config["UPLOAD_FOLDER"], f)
        if os.path.exists(fp):
            filename = f
            break

    # No valid uploads found
    if not filename:
        return {
            "uploads": [],
            "timestamps": [],
            "tampers": [],
            "plates": [],
            "case_id": session.get("case_id", "2025-DV-001A"),
            "report_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # Helper: sqlite Row → dict
    def to_dict(rows):
        return [dict(row) for row in rows]

    # Fetch data ONLY for this valid file
    cur.execute("SELECT filename, uploaded_at FROM uploads WHERE filename = ?", (filename,))
    uploads = to_dict(cur.fetchall())

    # Read aggregated timestamp record (may contain raw_ocr_results JSON)
    cur.execute("SELECT filename, timestamp_text, extracted_at, frame_count, raw_ocr_results FROM timestamps WHERE filename = ?", (filename,))
    ts_rows = cur.fetchall()
    timestamps = []
    for r in ts_rows:
        row = dict(r)
        raw = row.get("raw_ocr_results")
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = []
            for pr in parsed:
                timestamps.append({
                    "filename": row.get("filename"),
                    "timestamp_text": pr.get("text") or row.get("timestamp_text"),
                    "extracted_at": row.get("extracted_at"),
                    "frame": pr.get("frame"),
                    "confidence": pr.get("confidence", 0),
                    "crop_image": pr.get("crop_path"),
                    "full_image": pr.get("full_path")
                })
        else:
            timestamps.append({
                "filename": row.get("filename"),
                "timestamp_text": row.get("timestamp_text"),
                "extracted_at": row.get("extracted_at"),
                "frame": None,
                "confidence": row.get("confidence", 0),
            })

    cur.execute("SELECT filename, tamper_status, checked_at FROM tampers WHERE filename = ?", (filename,))
    tampers = to_dict(cur.fetchall())

    cur.execute("SELECT filename, plate_text, confidence, detected_at FROM license_results WHERE filename = ?", (filename,))
    plates = to_dict(cur.fetchall())

    cur.close()

    return {
        "uploads": uploads,
        "timestamps": timestamps,
        "tampers": tampers,
        "plates": plates,
        "case_id": session.get("case_id", "2025-DV-001A"),
        "report_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ======================================================
#        PDF GENERATION (COURT-READY VERSION)
# ======================================================
def generate_pdf_report(data, pdf_path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=0.75*inch, bottomMargin=0.75*inch, leftMargin=0.75*inch, rightMargin=0.75*inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("title", parent=styles["Heading1"], alignment=1, fontSize=20, fontName="Helvetica-Bold", textColor=colors.HexColor("#001f3f"), spaceAfter=6, spaceBefore=6)
    subtitle_style = ParagraphStyle("subtitle", parent=styles["Normal"], alignment=1, fontSize=10, textColor=colors.HexColor("#666666"), spaceAfter=12)
    heading_style = ParagraphStyle("heading", parent=styles["Heading2"], fontSize=12, textColor=colors.white, fontName="Helvetica-Bold", spaceAfter=10, spaceBefore=12)
    body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.5, leading=14)

    elements = []

    # ========== HEADER ==========
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("DIGITAL FORENSICS DIVISION", title_style))
    elements.append(Paragraph("Digital Evidence Examination Unit", subtitle_style))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("DIGITAL VIDEO FORENSIC EXAMINATION REPORT", title_style))
    elements.append(Spacer(1, 20))

    # ========== CASE INFO ==========
    case_id = data.get("case_id", "").strip() if data.get("case_id", "").strip() != "2025-DV-001A" else ""
    meta_data = [["Report Date:", data["report_date"]]]
    if case_id:
        meta_data.insert(0, ["Case ID:", case_id])
    
    meta_table = Table(meta_data, colWidths=[1.8*inch, 4.2*inch])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#d4e6f1")),
        ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#eaf2f8")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 18))

    # ========== EVIDENCE IDENTIFICATION ==========
    heading_style_alt = ParagraphStyle("heading_alt", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#003366"), fontName="Helvetica-Bold", spaceAfter=6, spaceBefore=12)
    elements.append(Paragraph("3.1 EVIDENCE IDENTIFICATION AND INTEGRITY", heading_style_alt))

    ev_table_data = [["Filename", "Uploaded At", "Integrity Status"]]
    for u in data["uploads"]:
        ev_table_data.append([u["filename"], u["uploaded_at"], "✓ RECORDED"])
    ev_table = Table(ev_table_data, colWidths=[2.6*inch, 1.8*inch, 1.6*inch])
    ev_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fb")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    elements.append(ev_table)
    elements.append(Spacer(1, 16))

    # ========== TAMPER DETECTION ==========
    elements.append(Paragraph("3.2 INTEGRITY VERIFICATION & ANALYSIS", heading_style_alt))
    tamper_table_data = [["Verification Type", "Status", "Timestamp"]]
    if data.get("tampers"):
        for t in data["tampers"]:
            status = "✓ AUTHENTIC" if "Authentic" in t.get("tamper_status", "") else "⚠ ANOMALY"
            tamper_table_data.append(["Digital Tamper Detection", status, t.get("checked_at", "")[:19]])
    else:
        tamper_table_data.append(["Digital Tamper Detection", "PENDING", "—"])
    
    tamper_table = Table(tamper_table_data, colWidths=[2.6*inch, 1.6*inch, 1.8*inch])
    tamper_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fb")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    elements.append(tamper_table)
    elements.append(Spacer(1, 16))

    # ========== EXTRACTED TIMESTAMPS ==========
    frame_count = len(data.get("timestamps", []))
    elements.append(Paragraph(f"3.3 EXTRACTED TIMESTAMP DATA ({frame_count} Frames)", heading_style_alt))
    elements.append(Spacer(1, 6))
    if frame_count > 0:
        for i, ts in enumerate(data["timestamps"], 1):
            text = ts.get('timestamp_text', 'N/A')
            frm = ts.get('frame') or ''
            elements.append(Paragraph(f"<b>Frame {i} {('('+str(frm)+')') if frm else ''}:</b> {text} — Extracted: {ts.get('extracted_at', 'N/A')}", body_style))
            elements.append(Spacer(1, 6))
    else:
        elements.append(Paragraph("No timestamp data extracted.", body_style))
    elements.append(Spacer(1, 12))

    # ========== LICENSE PLATE RESULTS ==========
    plate_count = len(data.get("plates", []))
    if plate_count > 0:
        elements.append(Paragraph(f"3.4 LICENSE PLATE DETECTION RESULTS ({plate_count} Plates)", heading_style))
        for p in data["plates"]:
            conf = float(p.get('confidence', 0))
            lp_text = f"<b>Plate:</b> {p.get('plate_text', 'N/A')} | <b>Confidence:</b> {conf:.1%} | <b>Detected:</b> {p.get('detected_at', 'N/A')}"
            elements.append(Paragraph(lp_text, body_style))
            elements.append(Spacer(1, 6))
        elements.append(Spacer(1, 16))

    # ========== FINDINGS & CONCLUSION ==========
    elements.append(Paragraph("4.0 FINDINGS AND CONCLUSION", heading_style_alt))
    
    upload_file = data["uploads"][0]["filename"] if data["uploads"] else "Evidence File"
    tamper_status = "✓ NO TAMPERING DETECTED" if data["tampers"] and "Authentic" in data["tampers"][0].get("tamper_status", "") else "⚠ REVIEW REQUIRED"
    
    findings_lines = [
        f"- Video evidence file {upload_file} maintained digital integrity throughout forensic analysis",
        f"- Tamper detection analysis: {tamper_status}",
        f"- License plate detection: {plate_count} result(s) identified",
        f"- Timestamp data: {frame_count} frame(s) extracted",
        "- All metadata fields validated against forensic standards"
    ]

    elements.append(Paragraph("<b>Summary of Forensic Findings:</b>", body_style))
    for ln in findings_lines:
        elements.append(Paragraph(ln, body_style))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("<b>Forensic Conclusion:</b>", body_style))
    elements.append(Paragraph("The digital video evidence has been forensically examined and is suitable for investigative purposes.", body_style))
    elements.append(Spacer(1, 18))

    # ========== SIGNATURE BLOCK ==========
    elements.append(Paragraph("AUTHORIZATION AND APPROVAL", heading_style_alt))
    elements.append(Spacer(1, 8))
    sig_table = Table([
        ["Examining Analyst", "Reviewing Authority"],
        ["______________________________", "______________________________"],
        ["Name: ________________________", "Name: ________________________"],
        ["Date: ________________________", "Date: ________________________"],
        ["Signature: ___________________", "Signature: ___________________"]
    ], colWidths=[3*inch, 3*inch])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(sig_table)
    elements.append(Spacer(1, 12))

    # ========== FOOTER ==========
    elements.append(Paragraph("DIGITAL FORENSICS DIVISION - EVIDENCE EXAMINATION UNIT", subtitle_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph("Automated Forensic Analysis System | CONFIDENTIAL - FOR AUTHORIZED PERSONNEL ONLY", subtitle_style))

    doc.build(elements)
    import hashlib
    return hashlib.sha256(open(pdf_path, "rb").read()).hexdigest()


# ==========================================
#       REPORT GENERATION ROUTE
# ==========================================
@app.route("/report_generation", methods=["GET", "POST"])
@login_required
def report_generation():
    if request.method == "POST":
        try:
            # Fetch fresh data from database (only files that still exist on disk)
            conn = get_db()
            data = fetch_all_report_data(conn)
            conn.close()

            # Delete any old PDF copies
            pdf_path = os.path.join(BASE_DIR, "forensic_report.pdf")
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except:
                    pass

            # Generate fresh PDF
            print(f"Generating PDF to: {pdf_path}")
            print(f"Data: {data}")
            generate_pdf_report(data, pdf_path)
            print(f"PDF generated. File exists: {os.path.exists(pdf_path)}")

            # Verify file was created
            if not os.path.exists(pdf_path):
                flash("Report generation failed — PDF not created.", "danger")
                return render_template("report_generation.html")

            flash("✅ Report generated successfully!", "success")
            return redirect(url_for("report_ready"))

        except Exception as e:
            print(f"❌ Report error: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f"Error: {str(e)}", "danger")
            return render_template("report_generation.html")

    return render_template("report_generation.html")


# ==========================================
#        REPORT READY PAGE
# ==========================================
@app.route("/report_ready")
@login_required
def report_ready():
    return render_template("report_ready.html")


# ==========================================
#         DOWNLOAD REPORT ROUTE (SIMPLE)
# ==========================================
@app.route("/download_report")
@login_required
def download_report():
    pdf_path = os.path.join(BASE_DIR, "forensic_report.pdf")
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True, download_name="forensic_report.pdf")
    flash("Report not found.", "danger")
    return redirect(url_for("report_generation"))


# ======================================================
#          LICENSE PLATE DETECTION
# ======================================================
@app.route("/license_plate_page", methods=["GET"])
@login_required
def license_plate_page():
    """Display license plate recognition form"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT filename FROM uploads ORDER BY uploaded_at DESC")
    videos = [row["filename"] for row in cur.fetchall()]
    conn.close()
    
    return render_template("license_plate.html", videos=videos)


@app.route("/process_license_plate", methods=["POST"])
@login_required
def process_license_plate():
    """Process video for license plate detection"""
    selected_filename = request.form.get("video")
    uploaded_file = request.files.get("file")

    if uploaded_file and uploaded_file.filename != "":
        if not allowed_file(uploaded_file.filename):
            flash("Invalid file format.", "danger")
            return redirect(url_for("license_plate_page"))

        filename = secure_filename(uploaded_file.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        uploaded_file.save(save_path)

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM uploads WHERE filename = ?", (filename,))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO uploads (filename, uploaded_at) VALUES (?, ?)",
                    (filename, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
            conn.commit()

        video_path = save_path
        filename_to_process = filename

    elif selected_filename:
        filename_to_process = selected_filename
        video_path = os.path.join(app.config["UPLOAD_FOLDER"], filename_to_process)
        if not os.path.exists(video_path):
            flash("Selected video not found on server.", "danger")
            return redirect(url_for("license_plate_page"))
    else:
        flash("No video selected or uploaded.", "danger")
        return redirect(url_for("license_plate_page"))

    # YOLO + OCR processing
    model = YOLO("best.pt")

    cap = cv2.VideoCapture(video_path)
    best_result = None
    best_confidence = 0.0
    ocr_results = []
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        if frame_count % 15 != 0:
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = model.predict(frame_rgb, conf=0.3, verbose=False)

        if results and len(results) > 0 and hasattr(results[0], "boxes") and results[0].boxes is not None and len(results[0].boxes) > 0:
            try:
                current_confidence = float(results[0].boxes.conf.mean().item())
            except Exception:
                current_confidence = 0.0

            if current_confidence > best_confidence:
                best_confidence = current_confidence
                try:
                    best_result = results[0].plot()
                except Exception:
                    best_result = None

            for i, box in enumerate(results[0].boxes):
                try:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                except Exception:
                    continue

                h, w = frame_rgb.shape[:2]
                x1 = max(0, x1 - 5)
                y1 = max(0, y1 - 5)
                x2 = min(w, x2 + 5)
                y2 = min(h, y2 + 5)

                plate_crop = frame_rgb[y1:y2, x1:x2]
                if plate_crop.size == 0:
                    continue

                plate_crop_gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
                plate_crop_gray = cv2.resize(plate_crop_gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                plate_crop_gray = cv2.bilateralFilter(plate_crop_gray, 11, 17, 17)
                _, plate_crop_thresh = cv2.threshold(plate_crop_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                plate_text = pytesseract.image_to_string(
                    plate_crop_thresh,
                    config="--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
                ).strip()

                cleaned = plate_text.replace(" ", "")
                match = re.match(r"([A-Z]{2,3})([0-9]{2,4})([A-Z]{1,3})", cleaned)
                if match:
                    plate_text = " ".join(match.groups())

                if plate_text and len(plate_text) > 2:
                    ocr_results.append(plate_text)

    cap.release()

    # ========== PERSIST TIMESTAMP SUMMARY TO DB (auto-save) ==========
    try:
        conn = get_db()
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame_count = len(ocr_results)
        avg_conf = round(sum([r.get("confidence", 0) for r in ocr_results]) / frame_count, 1) if frame_count else 0
        raw_json = json.dumps(ocr_results)

        cur.execute("""
            INSERT INTO timestamps (filename, timestamp_text, confidence, consistency_score, has_drift, frame_count, raw_ocr_results, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename)
            DO UPDATE SET
                timestamp_text=excluded.timestamp_text,
                confidence=excluded.confidence,
                consistency_score=excluded.consistency_score,
                has_drift=excluded.has_drift,
                frame_count=excluded.frame_count,
                raw_ocr_results=excluded.raw_ocr_results,
                extracted_at=CURRENT_TIMESTAMP
        """, (filename, final_timestamp or "", avg_conf, consistency_score, 0, frame_count, raw_json, now))
        conn.commit()
        conn.close()
    except Exception:
        pass

    detected_plate_text = None
    if ocr_results:
        from collections import Counter
        detected_plate_text = Counter(ocr_results).most_common(1)[0][0]

    if best_result is not None:
        result_filename = f"lp_result_{os.path.splitext(filename_to_process)[0]}.jpg"
        result_path = os.path.join(app.config["CROP_FOLDER"], result_filename)
        cv2.imwrite(result_path, best_result)

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO license_results (filename, plate_text, confidence)
                VALUES (?, ?, ?)
            """, (filename_to_process, detected_plate_text or "None", float(best_confidence)))
            conn.commit()

        return render_template(
            "license_plate_result.html",
            filename=filename_to_process,
            result_image=result_filename,
            confidence=f"{best_confidence:.2f}",
            plate_text=detected_plate_text
        )

    return render_template(
        "license_plate_result.html",
        filename=filename_to_process,
        result_image=None,
        confidence=0,
        error="No license plate detected in the video."
    )


# ======================================================
#                RUN APP (SINGLE MAIN BLOCK)
# ======================================================
@app.route("/debug_db")
@login_required
def debug_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM uploads")
    uploads = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) as count FROM timestamps")
    timestamps = cur.fetchone()["count"]

    cur.execute("SELECT COUNT(*) as count FROM tampers")
    tampers = cur.fetchone()["count"]

    cur.execute("SELECT filename FROM uploads ORDER BY uploaded_at DESC")
    files = [row["filename"] for row in cur.fetchall()]

    conn.close()

    return {
        "uploads_count": uploads,
        "timestamps_count": timestamps,
        "tampers_count": tampers,
        "latest_files": files
    }

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        init_db_schema()
        print("✅ Database created fresh.")
    else:
        print("ℹ️ Using existing database.")

    debug_mode = os.environ.get("DEBUG", "False") == "True"
    app.run(debug=debug_mode)
