import os
import sqlite3
import hashlib
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, session, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 * 1024  # 50 GB

# Default login credentials
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin'

# SQLite database file
DB_FILE = 'files.db'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ---------------------- Database Setup ----------------------
def init_db():
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

# ---------------------- Sync DB with Uploads Folder ----------------------
def sync_filesystem_and_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Get all file IDs from DB
    c.execute("SELECT id FROM files")
    db_files = set(row[0] for row in c.fetchall())

    # Get all file IDs from filesystem
    fs_files = set(os.listdir(app.config['UPLOAD_FOLDER']))

    # Files in folder but not in DB -> delete from folder
    for file_id in fs_files - db_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if os.path.isfile(file_path):
            os.remove(file_path)

    # Files in DB but not in folder -> delete from DB
    for file_id in db_files - fs_files:
        c.execute("DELETE FROM files WHERE id=?", (file_id,))

    conn.commit()
    conn.close()


init_db()
sync_filesystem_and_db()

# ---------------------- Helpers ----------------------
def generate_file_id(filename):
    timestamp = str(datetime.now().timestamp())
    unique_string = filename + timestamp
    return hashlib.md5(unique_string.encode()).hexdigest()

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
    if 'username' in session and session['username'] == DEFAULT_USERNAME:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == DEFAULT_USERNAME and password == DEFAULT_PASSWORD:
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'username' not in session or session['username'] != DEFAULT_USERNAME:
        return redirect(url_for('login'))

    files = get_all_files()
    return render_template('dashboard.html', files=files)


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'username' not in session or session['username'] != DEFAULT_USERNAME:
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('dashboard'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('dashboard'))

    if file:
        filename = secure_filename(file.filename)
        file_id = generate_file_id(filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)

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

        flash(f'File "{filename}" uploaded successfully', 'success')

    return redirect(url_for('dashboard'))


@app.route('/delete/<file_id>')
def delete_file(file_id):
    if 'username' not in session or session['username'] != DEFAULT_USERNAME:
        return redirect(url_for('login'))

    file = get_file(file_id)
    if file:
        # Delete file from filesystem
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if os.path.exists(file_path):
            os.remove(file_path)

        # Remove from DB
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM files WHERE id=?", (file_id,))
        conn.commit()
        conn.close()

        flash(f'File "{file["name"]}" deleted successfully', 'success')
    else:
        flash('File not found', 'error')

    return redirect(url_for('dashboard'))


@app.route('/rename/<file_id>', methods=['POST'])
def rename_file(file_id):
    if 'username' not in session or session['username'] != DEFAULT_USERNAME:
        return redirect(url_for('login'))

    new_name = request.form.get('new_name')
    if not new_name:
        flash('Please provide a new name', 'error')
        return redirect(url_for('dashboard'))

    file = get_file(file_id)
    if file:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE files SET name=? WHERE id=?", (new_name, file_id))
        conn.commit()
        conn.close()

        flash(f'File renamed from "{file["name"]}" to "{new_name}"', 'success')
    else:
        flash('File not found', 'error')

    return redirect(url_for('dashboard'))


@app.route('/download/<file_id>')
def download_page(file_id):
    file = get_file(file_id)
    if not file:
        flash('File not found', 'error')
        return redirect(url_for('index'))

    return render_template('download.html', file=file, file_id=file_id)


@app.route('/download_file/<file_id>')
def download_file(file_id):
    file = get_file(file_id)
    if not file:
        flash('File not found', 'error')
        return redirect(url_for('index'))

    # Update download count
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE files SET downloads = downloads + 1 WHERE id=?", (file_id,))
    conn.commit()
    conn.close()

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    return send_file(file_path, as_attachment=True, download_name=file["name"])


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000, debug=False)