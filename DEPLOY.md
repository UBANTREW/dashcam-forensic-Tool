DigitalOcean deployment notes

- Ensure environment variables are set on the Droplet/App Platform:
  - `APP_SECRET` — Flask secret key
  - `MYSQL_HOST`, `MYSQL_PORT` (default 3306), `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`
  - `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`
  - Any other keys in `.env`

- Use a managed MySQL or run MySQL and open port 3306.
- Set `MYSQL_PORT=3306` in production (DigitalOcean uses 3306).
- Place `best.pt` and any model files in the repo or accessible path.
- Ensure `forensic_report.pdf` is served from the project root (current code expects `BASE_DIR/forensic_report.pdf`).

Quick deploy steps:
1. Push code to GitHub.
2. Create a Droplet or use App Platform; set environment variables in the dashboard.
3. Install dependencies and run the app with a WSGI server (gunicorn) behind nginx.

Estimated time: 20–60 minutes (depends on DB provisioning and DNS).