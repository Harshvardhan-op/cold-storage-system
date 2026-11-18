# FrostGuard — Smart Cold Storage Monitoring System

A Streamlit academic prototype for simulated cold-storage monitoring.

## Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Create and activate a virtual environment (recommended).
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Start the app:

   ```bash
   streamlit run app.py
   ```

The app opens in your browser, usually at `http://localhost:8501`.

## Demo login

- Admin: `admin` / `admin123`
- User: `user` / `user123`

These are demonstration credentials only. Do not use them for a public deployment.

## Included

- Navy-blue and ice-blue dashboard design inspired by the supplied UI references.
- Login screen with Admin and User demo roles.
- Overview dashboard with latest temperature, humidity, storage status and alert count.
- Live simulator with automatic 3-second readings and manual reading generation.
- Configurable temperature and humidity limits (Admin).
- Automatic warning and critical alert logging.
- Historical analytics and interactive Plotly charts.
- CSV exports for readings and alerts, plus a PDF monitoring report.
- Local SQLite persistence in `cold_storage.db`.

## Notes

- This is a software simulation. No physical sensors are connected.
- The default safe limits are 8.0 °C and 80.0% humidity, matching the initial prototype description.
- The simulator generates plausible changing values around the previous reading. Values can exceed limits to demonstrate alert handling.
- The SQLite database is created automatically beside `app.py`.
- The demo login is not production authentication. Add proper password hashing, user management, HTTPS and deployment secrets before any real deployment.
