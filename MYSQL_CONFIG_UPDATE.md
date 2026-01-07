# ✅ MySQL Configuration Updated for DigitalOcean

## Changes Made

### config.py
- ✅ Changed port from **3307** to **3306** (DigitalOcean standard)
- ✅ Changed all hardcoded values to **environment variables**
- ✅ Removed hardcoded password `'your_root_password'`
- ✅ Added import for `dotenv` and `os`

**Before:**
```python
app.config['MYSQL_PORT'] = 3307
app.config['MYSQL_PASSWORD'] = 'your_root_password'
```

**After:**
```python
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', '')
```

### .env.example
- ✅ Updated to reflect port **3306** instead of 3307
- ✅ Updated database name to `dashcam_forensics` (standard)
- ✅ All values are placeholders (never hardcoded)

---

## Environment Variables to Set on DigitalOcean

When you deploy, set these in your `.env` file:

```bash
# MySQL (DigitalOcean Default)
MYSQL_HOST=your-db-host.db.ondigitalocean.com
MYSQL_PORT=3306
MYSQL_USER=doadmin
MYSQL_PASSWORD=your_strong_password_here
MYSQL_DB=dashcam_forensics
```

---

## Current Setup Status

| Item | Status |
|------|--------|
| Local Database | SQLite (dashcam.db) ✅ |
| DigitalOcean MySQL | Configured via env vars ✅ |
| Port | 3306 ✅ |
| Credentials | Environment variables ✅ |
| Hardcoded Values | ✅ REMOVED |

---

## Ready for Deployment ✅

All database credentials now use environment variables.
Port is set to 3306 (DigitalOcean standard).
No hardcoded passwords anywhere.

