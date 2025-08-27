# python-mediafire

A **self-hosted MediaFire-style file hosting service** built with Python and Flask.  
This project allows you to upload, download, manage, and share files from your own server with a web dashboard.  

---

## ✨ Features
- 📂 Upload, rename, and delete files via the web interface  
- 📥 Direct file download pages with download counter  
- 📊 System monitoring (CPU, RAM, Disk, Network, Uptime)  
- 🔐 Basic authentication with session login  
- 💾 SQLite database for file management  
- 📝 Daily logging system with optional console output  
- ⚡ Sync mechanism to keep filesystem and database consistent  

---

## 🚀 Installation

Clone the repository:
    git clone https://github.com/llc1234/python-mediafire.git
    cd python-mediafire

(Optional) Create a virtual environment:
    python -m venv venv
    source venv/bin/activate   # Linux/Mac
    venv\\Scripts\\activate    # Windows

Install dependencies:
    pip install -r requirements.txt

---

## ▶️ Usage

Run the app:
    python app.py

- The server runs by default on http://0.0.0.0:8000  
- Login with the default credentials:
  - Username: admin
  - Password: admin

⚠️ Important: Change the default credentials and app.secret_key before running in production.

---

## 📂 Project Structure

python-mediafire/
├── app.py              # Main Flask application
├── templates/          # HTML templates (dashboard, login, download pages)
├── uploads/            # Uploaded files
├── logs/               # Daily log files
├── files.db            # SQLite database
└── requirements.txt    # Dependencies

---

## 🛠️ Dependencies
- Flask
- psutil
- sqlite3 (built-in)
- werkzeug
- hashlib

(Install automatically via: pip install -r requirements.txt)

---

## 🔒 Security Notes
- Default login is admin:admin — must be changed!  
- Default app.secret_key is insecure — must be changed!  
- HTTPS is recommended if exposed to the internet.  

---

## 📜 License
This project is licensed under the MIT License.  
See the LICENSE file for details.  

---

## 🤝 Contributing
Pull requests are welcome!  
For major changes, please open an issue first to discuss what you would like to change.

---
