import os
import time
import psutil
import sqlite3
import hashlib
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Change this in production
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 * 1024  # 50 GB

# Default login credentials
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin'

# SQLite database file
DB_FILE = 'files.db'

# Logger for all data
DB_LOGGER = True
DB_LOGGER_DIR = "logs"
DB_LOGGER_PRINT = True
DB_LOGGER_FILENAME = "logg.txt"

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(DB_LOGGER_DIR, exist_ok=True)  # Ensure log folder exists


# ---------------------- DataLogger -------------------------

def get_log_filename():
    """Generate log file path based on current date"""
    return os.path.join(DB_LOGGER_DIR, datetime.now().strftime("%Y-%m-%d") + ".log")

_current_log_date = None
_log_file_handle = None

def DataLogger(text):
    global _current_log_date, _log_file_handle

    if DB_LOGGER:
        log_date = datetime.now().strftime("%Y-%m-%d")
        if _current_log_date != log_date:
            # Close old log file if open
            if _log_file_handle:
                _log_file_handle.close()
            # Open new log file
            log_filename = get_log_filename()
            _log_file_handle = open(log_filename, "a", encoding="utf-8")
            _current_log_date = log_date

        log_line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - {text}"
        if DB_LOGGER_PRINT:
            print(log_line)  # Console
        _log_file_handle.write(log_line + "\n")
        _log_file_handle.flush()

"""
def DataLogger(text):
    if DB_LOGGER:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {text}")

"""

# ---------------------- System Monitoring --------------------

network_stats = {
    'bytes_sent': 0,
    'bytes_recv': 0,
    'last_check': time.time()
}

def get_system_stats():
    """Get current system statistics"""
    # Disk usage
    disk_usage = psutil.disk_usage('/')
    storage_used = disk_usage.used
    storage_left = disk_usage.free
    storage_total = disk_usage.total
    
    # RAM usage
    ram = psutil.virtual_memory()
    ram_used = ram.used
    ram_total = ram.total
    ram_percent = ram.percent
    
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.1)
    
    # Network usage (calculate difference from last check)
    net_io = psutil.net_io_counters()
    current_time = time.time()
    time_diff = current_time - network_stats['last_check']
    
    if time_diff > 0:
        sent_speed = (net_io.bytes_sent - network_stats['bytes_sent']) / time_diff
        recv_speed = (net_io.bytes_recv - network_stats['bytes_recv']) / time_diff
    else:
        sent_speed = 0
        recv_speed = 0
    
    # Update network stats for next calculation
    network_stats['bytes_sent'] = net_io.bytes_sent
    network_stats['bytes_recv'] = net_io.bytes_recv
    network_stats['last_check'] = current_time
    
    # Files count and DB size
    files_count = len(get_all_files())
    db_size = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
    
    # System uptime
    uptime_seconds = time.time() - psutil.boot_time()
    uptime_str = str(timedelta(seconds=int(uptime_seconds)))
    
    return {
        'storage_used': format_bytes(storage_used),
        'storage_left': format_bytes(storage_left),
        'storage_total': format_bytes(storage_total),
        'ram_used': format_bytes(ram_used),
        'ram_total': format_bytes(ram_total),
        'ram_percent': f"{ram_percent}%",
        'cpu_percent': f"{cpu_percent}%",
        'network_sent': format_speed(sent_speed),
        'network_recv': format_speed(recv_speed),
        'files_count': files_count,
        'db_size': format_bytes(db_size),
        'uptime': uptime_str
    }


# ---------------------- Password Warning --------------------


def SeeIfPasswordIsDefalt():
    if DEFAULT_USERNAME == "admin" and DEFAULT_PASSWORD == "admin":
        DataLogger("[WARNING] - username and password is 'admin'")
    elif DEFAULT_PASSWORD == "admin":
        DataLogger("[WARNING] - password is 'admin'")

    if app.secret_key == 'your-secret-key':
        DataLogger("[WARNING] - app.secret_key is 'your-secret-key'")

# ---------------------- Database Setup ----------------------
def init_db():
    db_exists = os.path.exists(DB_FILE)
    if db_exists:
        DataLogger(f"[Database] - file exists: {db_exists}, Name: {DB_FILE}")
    else:
        DataLogger(f"[Database] - file exists: {db_exists}, Making Database... {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            upload_date TEXT NOT NULL,
            size TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            downloads INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    DataLogger("[Database] - initialized")

# ---------------------- Sync DB with Uploads Folder ----------------------
def sync_filesystem_and_db():
    DataLogger("[Sync] - syncing filesystem and database...")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Get all file IDs from DB
    c.execute("SELECT id FROM files")
    db_files = set(row[0] for row in c.fetchall())

    # Get all file IDs from filesystem
    fs_files = set(os.listdir(app.config['UPLOAD_FOLDER']))

    DataLogger(f"[Sync] - DB count: {len(db_files)}, FS count: {len(fs_files)}")

    # Files in folder but not in DB -> delete from folder
    for file_id in fs_files - db_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if os.path.isfile(file_path):
            os.remove(file_path)
            DataLogger(f"[Database] Removed file from filesystem (not in DB): {file_id}")

    # Files in DB but not in folder -> delete from DB
    for file_id in db_files - fs_files:
        c.execute("DELETE FROM files WHERE id=?", (file_id,))
        DataLogger(f"[Database] Removed entry from database (missing on filesystem): {file_id}")

    conn.commit()
    conn.close()
    DataLogger("[Sync] - complete")


# init_db()
# SeeIfPasswordIsAdmin()
# sync_filesystem_and_db()

# ---------------------- Format Helpers ----------------------
def format_bytes(size_bytes):
    """Convert bytes to human-readable format"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.2f} {size_names[i]}"

def format_speed(speed_bytes):
    """Convert bytes per second to human-readable format"""
    return format_bytes(speed_bytes) + "/s"

# ---------------------- Helpers ----------------------
def generate_file_id(filename):
    timestamp = str(datetime.now().timestamp())
    unique_string = filename + timestamp
    h = hashlib.md5(unique_string.encode()).hexdigest()
    DataLogger(f"[Helper] - generated file_id {h} for {filename}")
    return h

def get_all_files():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM files ORDER BY upload_date DESC")
    files = c.fetchall()
    conn.close()
    return files

def get_file(file_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM files WHERE id=?", (file_id,))
    file = c.fetchone()
    conn.close()
    return file


# ---------------------- Routes ----------------------
@app.route('/')
def index():
    DataLogger("[Route] - / (index)")
    if 'username' in session and session['username'] == DEFAULT_USERNAME:
        DataLogger("[Auth] - already logged in, redirecting to dashboard")
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        DataLogger(f"[Auth] - login attempt user={username}")

        if username == DEFAULT_USERNAME and password == DEFAULT_PASSWORD:
            session['username'] = username
            DataLogger("[Auth] - login success")
            return redirect(url_for('dashboard'))
        else:
            DataLogger("[Auth] - login failed")
            flash('Invalid credentials', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    DataLogger("[Route] - /logout")
    session.pop('username', None)
    DataLogger("[Auth] - logged out")
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    DataLogger("[Route] - /dashboard")
    if 'username' not in session or session['username'] != DEFAULT_USERNAME:
        DataLogger("[Auth] - access denied, redirect to login")
        return redirect(url_for('login'))

    files = get_all_files()
    DataLogger(f"[Dashboard] - showing {len(files)} files")

    system_stats = get_system_stats()

    return render_template('dashboard.html', files=files, system_stats=system_stats)


@app.route('/upload', methods=['POST'])
def upload_file():
    DataLogger("[Route] - /upload")
    if 'username' not in session or session['username'] != DEFAULT_USERNAME:
        DataLogger("[Auth] - upload denied (not logged in)")
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('No file selected', 'error')
        DataLogger("[Upload] - no file in request")
        return redirect(url_for('dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        DataLogger("[Upload] - empty filename")
        return redirect(url_for('dashboard'))

    if file:
        filename = secure_filename(file.filename)
        file_id = generate_file_id(filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        DataLogger(f"[Upload] - saving {filename} as {file_id}")

        # Save file
        file.save(file_path)

        # Get file size
        file_size = os.path.getsize(file_path)

        # Format file size
        size_units = ['B', 'KB', 'MB', 'GB']
        size_index = 0
        size_val = file_size
        while size_val >= 1024 and size_index < len(size_units) - 1:
            size_val /= 1024.0
            size_index += 1
        formatted_size = f"{size_val:.2f} {size_units[size_index]}"

        # Insert into DB
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO files (id, name, upload_date, size, size_bytes, downloads)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (file_id, filename, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              formatted_size, file_size))
        conn.commit()
        conn.close()
        DataLogger(f"[Upload] - inserted into DB {file_id} ({filename}, {formatted_size})")

        flash(f'File "{filename}" uploaded successfully', 'success')

    return redirect(url_for('dashboard'))


@app.route('/delete/<file_id>')
def delete_file(file_id):
    DataLogger(f"[Route] - /delete/{file_id}")
    if 'username' not in session or session['username'] != DEFAULT_USERNAME:
        DataLogger("[Auth] - delete denied (not logged in)")
        return redirect(url_for('login'))

    file = get_file(file_id)
    if file:
        # Delete file from filesystem
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if os.path.exists(file_path):
            os.remove(file_path)
            DataLogger(f"[Delete] - removed from filesystem {file_id}")

        # Remove from DB
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM files WHERE id=?", (file_id,))
        conn.commit()
        conn.close()
        DataLogger(f"[Delete] - removed from DB {file_id} ({file['name']})")

        flash(f'File "{file["name"]}" deleted successfully', 'success')
    else:
        DataLogger(f"[Delete] - file not found {file_id}")
        flash('File not found', 'error')

    return redirect(url_for('dashboard'))


@app.route('/rename/<file_id>', methods=['POST'])
def rename_file(file_id):
    DataLogger(f"[Route] - /rename/{file_id}")
    if 'username' not in session or session['username'] != DEFAULT_USERNAME:
        DataLogger("[Auth] - rename denied (not logged in)")
        return redirect(url_for('login'))

    new_name = request.form.get('new_name')
    if not new_name:
        flash('Please provide a new name', 'error')
        DataLogger("[Rename] - new name missing")
        return redirect(url_for('dashboard'))

    file = get_file(file_id)
    if file:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE files SET name=? WHERE id=?", (new_name, file_id))
        conn.commit()
        conn.close()
        DataLogger(f"[Rename] - {file['name']} -> {new_name}")

        flash(f'File renamed from "{file["name"]}" to "{new_name}"', 'success')
    else:
        DataLogger(f"[Rename] - file not found {file_id}")
        flash('File not found', 'error')

    return redirect(url_for('dashboard'))


@app.route('/download/<file_id>')
def download_page(file_id):
    DataLogger(f"[Route] - /download/{file_id}")
    file = get_file(file_id)
    if not file:
        DataLogger("[Download] - file not found")
        flash('File not found', 'error')
        return redirect(url_for('index'))

    return render_template('download.html', file=file, file_id=file_id)


@app.route('/download_file/<file_id>')
def download_file(file_id):
    DataLogger(f"[Route] - /download_file/{file_id}")
    file = get_file(file_id)
    if not file:
        DataLogger("[Download] - file not found")
        flash('File not found', 'error')
        return redirect(url_for('index'))

    # Update download count
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE files SET downloads = downloads + 1 WHERE id=?", (file_id,))
    conn.commit()
    conn.close()
    DataLogger(f"[Download] - incremented download count for {file_id}")

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    return send_file(file_path, as_attachment=True, download_name=file["name"])


@app.route('/system_stats')
def system_stats():
    if 'username' not in session or session['username'] != DEFAULT_USERNAME:
        return jsonify({'error': 'Unauthorized'}), 401
    
    stats = get_system_stats()
    
    # Format the data for display
    
    # DataLogger(f"[Route] - /system_stats - {stats}")
    
    return jsonify(stats)


if __name__ == '__main__':
    DataLogger("[Server] - ########################## starting Flask Server ##########################")

    init_db()
    SeeIfPasswordIsDefalt()
    sync_filesystem_and_db()


    app.run(host="0.0.0.0", port=8000, debug=False)
