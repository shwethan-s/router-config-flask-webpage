# app.py
# -------------------- Imports & Setup --------------------
from flask import (
    Flask, render_template, request, redirect,
    url_for, send_file, flash, get_flashed_messages
)
import sqlite3, datetime, os, zipfile

# Base directory and file paths
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DB_PATH       = os.path.join(BASE_DIR, 'buildings.db')
EXPORT_FOLDER = os.path.join(BASE_DIR, 'export')
INI_FILE      = 'TSIRouters.ini'

# Create Flask app and set a secret key for flash messages
app = Flask(__name__)
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
        flash('Invalid building number or IP.')
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
        flash(f'Added building {num} ({ip}).')
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
                       status       = 'active',
                       last_updated = ?
                 WHERE building_number = ?
            ''', (ip, now, num))
            conn.commit()
            flash(f'Re-activated building {num} ({ip}).')
            log_action(num, 'reactivated')
        else:
            flash(f'Building {num} already exists.')
    finally:
        conn.close()

def remove_building(num):
    """Mark a building as removed (soft delete) and log it."""
    if num <= 0:
        flash('Invalid building number.')
        return
    
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor() # get a cursor object
    # Update the status to 'removed' and set last_updated timestamp
    c.execute(
        "UPDATE buildings SET status='removed', last_updated =? WHERE building_number=?",
        (datetime.datetime.now().isoformat(), num)
    )
    conn.commit()
    conn.close()
    flash(f'Removed building {num}.') # fstring that controls the message
    log_action(num, 'removed')


# -------------------- INI Generation --------------------
def generate_tsirouters_ini():
    """
    Make the master TSIRouters.ini listing every active building.
    Returns the path to the file.
    """
    lines = [
        "[OPTIONS]",
        "IP_ROUTER_AUTODETECT=FALSE",
        "",
        "[ROUTERS]",
        "Format= Segment Number = IP Address of the Router, Monitor for Alarms"
    ]
    for b in get_buildings():
     
    
        lines.append(f"{b[1]}={b[2]},FALSE") 
       # clear the list after each iteration

    os.makedirs(EXPORT_FOLDER, exist_ok=True)
    path = os.path.join(EXPORT_FOLDER, INI_FILE)
    with open(path, 'w') as f:
        f.write("\n".join(lines))
    return path

def generate_single_ini(building_number):
    """
    Generate TSIRouters_<num>.ini for one building,
    excluding itself from the list. Returns path or None.
    """
    buildings = get_buildings()
    nums = [b[1] for b in buildings]
    if building_number not in nums:
        return None

    lines = [
        "[OPTIONS]",
        "IP_ROUTER_AUTODETECT=FALSE",
        "",
        "[ROUTERS]",
        "Format= Segment Number = IP Address of the Router, Monitor for Alarms"
    ]
    for num, ip in [(b[1], b[2]) for b in buildings if b[1] != building_number]:
        lines.append(f"{num}={ip},FALSE")

    os.makedirs(EXPORT_FOLDER, exist_ok=True)
    fname = f"TSIRouters_{building_number}.ini"
    path = os.path.join(EXPORT_FOLDER, fname)
    with open(path, 'w') as f:
        f.write("\n".join(lines))
    return path

def generate_all_inis():
    """
    Generate one per-controller INI and bundle into all_configs.zip.
    Returns the zip path.
    """
    buildings = get_buildings()
    os.makedirs(EXPORT_FOLDER, exist_ok=True)

    paths = []
    for b in buildings:
        p = generate_single_ini(b[1])
        if p:
            paths.append(p)

    zip_path = os.path.join(EXPORT_FOLDER, 'all_configs.zip')
    with zipfile.ZipFile(zip_path, 'w') as z:
        for p in paths:
            z.write(p, arcname=os.path.basename(p))
    return zip_path


# -------------------- Flask Routes --------------------
@app.route('/')
def index():
    """Dashboard: list, flash messages, last-updated."""
    return render_template(
        'index.html',
        buildings=get_buildings(),
        last_update=get_last_update(),
        messages=get_flashed_messages()
    )

@app.route('/add', methods=['POST'])
def add():
    """Handle the Add form."""
    try:
        num = int(request.form.get('building_number', 0))
        ip  = request.form.get('ip', '').strip()
        add_building(num, ip)
    except ValueError:
        flash('Building number must be an integer.')
    return redirect(url_for('index'))

@app.route('/remove/<building_number>')
def remove(building_number):
    """Handle the Remove link."""
    try:
        num = int(building_number)
        remove_building(num)
    except ValueError:
        flash('Invalid removal request.')
    return redirect(url_for('index'))

@app.route('/export', methods=['GET'])
def export():
    """
    Download configs based on `?type=`:
      - master → master TSIRouters.ini
      - all    → all_configs.zip
      - single → TSIRouters_<num>.ini (requires building_number=X)
    """
    mode = request.args.get('type', 'master')

    if mode == 'master':
        path = generate_tsirouters_ini()
        return send_file(path, as_attachment=True)

    elif mode == 'all':
        zip_path = generate_all_inis()
        return send_file(zip_path, as_attachment=True)

    elif mode == 'single':
        try:
            num = int(request.args.get('building_number', 0))
        except ValueError:
            flash("Specify a valid building number for single export.")
            return redirect(url_for('index'))

        path = generate_single_ini(num)
        if not path:
            flash(f"Building {num} not found in master list.")
            return redirect(url_for('index'))

        return send_file(path, as_attachment=True)

    else:
        flash("Unknown export type.")
        return redirect(url_for('index'))


# -------------------- Launch App --------------------
if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0')
