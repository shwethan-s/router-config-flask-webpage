# app.py
# -------------------- Imports & Setup --------------------
import os
import sys
import sqlite3
import datetime
import zipfile
import threading
import webbrowser

from flask import (
    Flask, render_template, request, redirect,
    url_for, send_file, flash, get_flashed_messages
)

# ————— Determine base dir (for PyInstaller compatibility) —————
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH       = os.path.join(BASE_DIR,   'buildings.db')
EXPORT_FOLDER = os.path.join(BASE_DIR,   'export')

# **Strict filenames per spec — no ".ini" extension**
MASTER_LIST_FN = 'Master List'
SINGLE_FN_BASE = 'HOSTS'
ALL_ZIP_FN     = 'all_configs.zip'

# Create Flask app, pointing at the bundled templates
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates')
)
app.secret_key = 'supersecretchangeme'


# -------------------- Database Initialization --------------------
def init_db():
    """
    Ensure the tables exist, then seed the six default routers
    only if the table is brand-new (empty).
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1) Create tables if missing
    c.execute('''
        CREATE TABLE IF NOT EXISTS buildings (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            building_number  INTEGER UNIQUE,
            ip_address       TEXT,
            status           TEXT    DEFAULT 'active',
            last_updated     TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            building_number  INTEGER,
            action           TEXT,
            timestamp        TEXT
        )
    ''')
    conn.commit()

    # 2) Seed defaults only on first run
    c.execute("SELECT COUNT(*) FROM buildings")
    if c.fetchone()[0] == 0:
        now = datetime.datetime.now().isoformat()
        defaults = [
            (1, "130.113.195.52"),
            (2, "130.113.171.68"),
            (3, "130.113.171.96"),
            (4, "130.113.171.99"),
            (5, "130.113.40.190"),
            (6, "130.113.171.98"),
        ]
        for num, ip in defaults:
            c.execute('''
                INSERT INTO buildings
                  (building_number, ip_address, status, last_updated)
                VALUES (?, ?, 'active', ?)
            ''', (num, ip, now))
        conn.commit()

    conn.close()


# -------------------- Helper Functions --------------------
def get_buildings():
    """Return all active controllers as a list of rows."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT * FROM buildings
         WHERE status='active' AND building_number>0
      ORDER BY building_number
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def get_last_update():
    """Get the latest action timestamp from logs."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MAX(timestamp) FROM logs")
    ts = c.fetchone()[0]
    conn.close()
    return ts


def log_action(num, action):
    """Append an add/remove/reactivate entry to logs."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO logs (building_number, action, timestamp) VALUES (?, ?, ?)",
        (num, action, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def add_building(num, ip):
    """
    Insert a new building, or if it already existed but was removed,
    flip it back to active (and update the IP+timestamp).
    """
    if num <= 0 or not ip:
        flash('Invalid building number or IP.', 'error')
        return

    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Try to insert fresh
        c.execute(
            "INSERT INTO buildings (building_number, ip_address, last_updated) VALUES (?, ?, ?)",
            (num, ip, now)
        )
        conn.commit()
        flash(f'Added Network {num} ({ip})', 'success')
        log_action(num, 'added')

    except sqlite3.IntegrityError:
        # Already exists: check if it was 'removed'
        c.execute(
            "SELECT status FROM buildings WHERE building_number=?",
            (num,)
        )
        row = c.fetchone()
        if row and row[0] == 'removed':
            # Reactivate
            c.execute('''
                UPDATE buildings
                   SET ip_address   = ?,
                       last_updated = ?,
                       status       = 'active'
                 WHERE building_number = ?
            ''', (ip, now, num))
            conn.commit()
            flash(f'Re-activated Network {num} ({ip})', 'success')
            log_action(num, 'reactivated')
        else:
            flash(f'Network {num} already exists.', 'error')
    finally:
        conn.close()


def remove_building(num):
    """Mark a building as removed (soft delete) and log it."""
    if num <= 0:
        flash('Invalid Network Number', 'error')
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE buildings SET status='removed', last_updated =? WHERE building_number=?",
        (datetime.datetime.now().isoformat(), num)
    )
    conn.commit()
    conn.close()

    flash(f'Removed Network {num}', 'error')
    log_action(num, 'removed')


# -------------------- INI Generation --------------------
def generate_master_list():
    """
    Write Master List (no extension) with all active buildings,
    using the strict "<IP> TNR_<number>" format.
    """
    lines = []
    for b in get_buildings():
        ip  = b[2]
        num = b[1]
        lines.append(f"{ip} TNR_{num}")

    os.makedirs(EXPORT_FOLDER, exist_ok=True)
    path = os.path.join(EXPORT_FOLDER, MASTER_LIST_FN)
    with open(path, 'w') as f:
        f.write("\n".join(lines))
    return path


def generate_single_ini(building_number):
    """
    Write HOSTS-<number> (no extension) listing every other active building
    in the "<IP> TNR_<number>" format.
    """
    buildings = get_buildings()
    nums = [b[1] for b in buildings]
    if building_number not in nums:
        return None

    lines = []
    for b in buildings:
        if b[1] != building_number:
            lines.append(f"{b[2]} TNR_{b[1]}")

    os.makedirs(EXPORT_FOLDER, exist_ok=True)
    filename = f"{SINGLE_FN_BASE}-{building_number}"
    path = os.path.join(EXPORT_FOLDER, filename)
    with open(path, 'w') as f:
        f.write("\n".join(lines))
    return path


def generate_all_inis():
    """
    Generate one HOSTS-<number> per building and bundle them
    all into all_configs.zip with each entry named "HOSTS-<number>".
    """
    buildings = get_buildings()
    os.makedirs(EXPORT_FOLDER, exist_ok=True)

    single_paths = [generate_single_ini(b[1]) for b in buildings]

    zip_path = os.path.join(EXPORT_FOLDER, ALL_ZIP_FN)
    with zipfile.ZipFile(zip_path, 'w') as z:
        for sp in single_paths:
            arcname = os.path.basename(sp)
            z.write(sp, arcname=arcname)
    return zip_path


# -------------------- Flask Routes --------------------
@app.route('/')
def index():
    """Dashboard home, with formatted last-update timestamp."""
    raw_ts = get_last_update()
    if raw_ts:
        try:
            dt = datetime.datetime.fromisoformat(raw_ts)
            last_update = dt.strftime("%b %d, %Y %H:%M:%S")
        except Exception:
            last_update = raw_ts
    else:
        last_update = '—'

    return render_template(
        'index.html',
        buildings   = get_buildings(),
        last_update = last_update,
        messages    = get_flashed_messages(with_categories=True)
    )


@app.route('/add', methods=['POST'])
def add():
    """Handle the Add form."""
    try:
        num = int(request.form.get('building_number', 0))
        ip  = request.form.get('ip', '').strip()
        add_building(num, ip)
    except ValueError:
        flash('Network number must be an integer', 'error')
    return redirect(url_for('index'))


@app.route('/remove/<building_number>')
def remove(building_number):
    """Handle the Remove link."""
    try:
        num = int(building_number)
        remove_building(num)
    except ValueError:
        flash('Invalid removal request.', 'error')
    return redirect(url_for('index'))


@app.route('/export', methods=['GET'])
def export():
    """
    ?type=master  → download "Master List" (no extension)
    ?type=all     → download "all_configs.zip"
    ?type=single  → download "HOSTS-<number>"
    """
    mode = request.args.get('type', 'master')
    

    if mode == 'master':
        path = generate_master_list()
        return send_file(path, as_attachment=True, download_name=MASTER_LIST_FN)

    elif mode == 'all':
        path = generate_all_inis()
        return send_file(path, as_attachment=True, download_name=ALL_ZIP_FN)

    elif mode == 'single':
        try:
            num = int(request.args.get('building_number', 0))
        except ValueError:
            flash("Specify a valid Network number for single export", 'error')
            return redirect(url_for('index'))

        path = generate_single_ini(num)
        if not path:
            flash(f"Network {num} not found in master list", 'error')
            return redirect(url_for('index'))

        download_name = os.path.basename(path)
        return send_file(path, as_attachment=True, download_name=download_name)

    else:
        flash("Unknown export type", 'error')
        return redirect(url_for('index'))


# -------------------- Launch App --------------------
if __name__ == '__main__':
    init_db()
    # auto-open browser, then start Flask
    threading.Timer(1, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host='127.0.0.1', port=5000)
