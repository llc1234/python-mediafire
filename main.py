import os
import json
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

# File to store metadata
METADATA_FILE = 'file_metadata.json'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_metadata(metadata):
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f)

def generate_file_id(filename):
    # Generate a unique ID based on filename and timestamp
    timestamp = str(datetime.now().timestamp())
    unique_string = filename + timestamp
    return hashlib.md5(unique_string.encode()).hexdigest()

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
    
    metadata = load_metadata()
    files = []
    
    for file_id, file_data in metadata.items():
        files.append({
            'id': file_id,
            'name': file_data['name'],
            'upload_date': file_data['upload_date'],
            'size': file_data['size'],
            'downloads': file_data.get('downloads', 0)
        })
    
    # Sort files by upload date (newest first)
    files.sort(key=lambda x: x['upload_date'], reverse=True)
    
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
        
        # Format file size for display
        size_units = ['B', 'KB', 'MB', 'GB']
        size_index = 0
        while file_size >= 1024 and size_index < len(size_units) - 1:
            file_size /= 1024.0
            size_index += 1
        formatted_size = f"{file_size:.2f} {size_units[size_index]}"
        
        # Update metadata
        metadata = load_metadata()
        metadata[file_id] = {
            'name': filename,
            'upload_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'size': formatted_size,
            'size_bytes': os.path.getsize(file_path),
            'downloads': 0
        }
        save_metadata(metadata)
        
        flash(f'File "{filename}" uploaded successfully', 'success')
    
    return redirect(url_for('dashboard'))

@app.route('/delete/<file_id>')
def delete_file(file_id):
    if 'username' not in session or session['username'] != DEFAULT_USERNAME:
        return redirect(url_for('login'))
    
    metadata = load_metadata()
    
    if file_id in metadata:
        # Delete file from filesystem
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Remove from metadata
        filename = metadata[file_id]['name']
        del metadata[file_id]
        save_metadata(metadata)
        
        flash(f'File "{filename}" deleted successfully', 'success')
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
    
    metadata = load_metadata()
    
    if file_id in metadata:
        old_name = metadata[file_id]['name']
        metadata[file_id]['name'] = new_name
        save_metadata(metadata)
        
        flash(f'File renamed from "{old_name}" to "{new_name}"', 'success')
    else:
        flash('File not found', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/download/<file_id>')
def download_page(file_id):
    metadata = load_metadata()
    
    if file_id not in metadata:
        flash('File not found', 'error')
        return redirect(url_for('index'))
    
    file_data = metadata[file_id]
    return render_template('download.html', file=file_data, file_id=file_id)

@app.route('/download_file/<file_id>')
def download_file(file_id):
    metadata = load_metadata()
    
    if file_id not in metadata:
        flash('File not found', 'error')
        return redirect(url_for('index'))
    
    # Update download count
    metadata[file_id]['downloads'] = metadata[file_id].get('downloads', 0) + 1
    save_metadata(metadata)
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    filename = metadata[file_id]['name']
    
    return send_file(file_path, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True)