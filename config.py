import os
from dotenv import load_dotenv

load_dotenv()

# ===============================================
# DATABASE CONFIGURATION
# ===============================================
# Currently using SQLite locally, but these are
# environment variables ready for MySQL migration
# on DigitalOcean

app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB', 'dashcam_forensics')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# ===============================================
# NOTE: Flask app is initialized in app.py
# This file is for reference/future MySQL migration
# ===============================================

