# 🚀 DIGITAL OCEAN DEPLOYMENT GUIDE

## Pre-Deployment Checklist ✅

- [x] All hardcoded secrets removed
- [x] Flask app initialized only once
- [x] Paths use absolute BASE_DIR
- [x] DEMO_MODE set via environment variable
- [x] requirements.txt created
- [x] .env.example provided
- [x] Debug mode controlled by env variable

---

## Step 1: Create DigitalOcean Droplet

1. Create Ubuntu 22.04 LTS Droplet (minimum 2GB RAM recommended)
2. SSH into droplet: `ssh root@your_droplet_ip`

---

## Step 2: Install System Dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install Python & pip
apt install -y python3.11 python3.11-venv python3-pip

# Install Tesseract OCR (required for timestamp extraction)
apt install -y tesseract-ocr

# Install OpenCV dependencies
apt install -y libsm6 libxext6 libxrender-dev

# Install git
apt install -y git

# Install supervisor (for process management - optional but recommended)
apt install -y supervisor
```

---

## Step 3: Clone Repository & Setup

```bash
# Clone your GitHub repository
cd /home
git clone https://github.com/YOUR_USERNAME/Dashcam_Auth_MySQL.git
cd Dashcam_Auth_MySQL

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Download YOLO model (best.pt) - THIS IS LARGE (~20MB)
# Copy best.pt to the project root if not in git
# Or download with: wget https://github.com/ultralytics/yolov8/releases/download/v8.0.181/yolov8n.pt -O best.pt
```

---

## Step 4: Configure Environment Variables

```bash
# Copy .env.example to .env
cp .env.example .env

# Edit .env with your values
nano .env
```

**CRITICAL: Set these in .env:**
```
APP_SECRET=generate-a-strong-random-string-here
MAIL_USERNAME=your-gmail@gmail.com
MAIL_PASSWORD=your-gmail-app-password
DEBUG=False
DEMO_MODE=False
```

---

## Step 5: Create Database & Test App

```bash
# Still inside venv
python -c "from app import init_db_schema; init_db_schema(); print('Database initialized!')"

# Run app once to test (should not error)
python app.py &

# Give it 5 seconds then Ctrl+C to stop
# Check if http://your_droplet_ip:5000 is accessible
```

---

## Step 6: Setup Gunicorn & Supervisor (Production)

```bash
# Install Gunicorn
pip install gunicorn

# Create supervisor config
cat > /etc/supervisor/conf.d/dashcam.conf << 'EOF'
[program:dashcam]
directory=/home/Dashcam_Auth_MySQL
command=/home/Dashcam_Auth_MySQL/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
autostart=true
autorestart=true
stderr_logfile=/var/log/dashcam.err.log
stdout_logfile=/var/log/dashcam.out.log
environment=PATH=/home/Dashcam_Auth_MySQL/venv/bin
EOF

# Start supervisor
supervisorctl reread
supervisorctl update
supervisorctl start dashcam

# Check status
supervisorctl status dashcam
```

---

## Step 7: Setup Nginx Reverse Proxy (Optional but Recommended)

```bash
# Install Nginx
apt install -y nginx

# Create Nginx config
cat > /etc/nginx/sites-available/dashcam << 'EOF'
server {
    listen 80;
    server_name your_droplet_ip;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Enable site
ln -s /etc/nginx/sites-available/dashcam /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

---

## Step 8: Verify Deployment

```bash
# Check app is running
ps aux | grep gunicorn

# Check logs
tail -f /var/log/dashcam.out.log
tail -f /var/log/dashcam.err.log

# Test endpoint
curl http://localhost:5000/debug_db
```

---

## Troubleshooting

### Problem: "No module named 'cv2'"
```bash
# Inside venv:
pip install --upgrade opencv-python
```

### Problem: "Tesseract is not installed"
```bash
apt install -y tesseract-ocr
```

### Problem: "YOLO model not found (best.pt)"
```bash
# Upload best.pt to /home/Dashcam_Auth_MySQL/ via SCP
scp best.pt root@your_droplet_ip:/home/Dashcam_Auth_MySQL/
```

### Problem: App starts but crashes on timestamp extraction
```bash
# Check if pytesseract can find tesseract binary
python -c "import pytesseract; print(pytesseract.pytesseract.find_tesseract())"
```

---

## Monitoring & Maintenance

### View Real-time Logs
```bash
tail -f /var/log/dashcam.out.log
```

### Restart Application
```bash
supervisorctl restart dashcam
```

### Backup Database
```bash
cp /home/Dashcam_Auth_MySQL/dashcam.db /home/Dashcam_Auth_MySQL/dashcam.db.backup
```

### Update Code from GitHub
```bash
cd /home/Dashcam_Auth_MySQL
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
supervisorctl restart dashcam
```

---

## Security Recommendations

1. ✅ Never commit .env to git
2. ✅ Use strong APP_SECRET (64+ characters)
3. ✅ Enable HTTPS with Let's Encrypt:
   ```bash
   apt install certbot python3-certbot-nginx
   certbot --nginx -d your_domain.com
   ```
4. ✅ Setup firewall:
   ```bash
   ufw allow 22/tcp
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw enable
   ```
5. ✅ Enable auto-updates:
   ```bash
   apt install unattended-upgrades
   dpkg-reconfigure -plow unattended-upgrades
   ```

---

## Estimated Deployment Time

- System setup: 5-10 minutes
- Dependencies: 15-20 minutes
- Database init: 2 minutes
- Testing: 5-10 minutes
- **Total: ~30-50 minutes**

