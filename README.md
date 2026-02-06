# WELL Environmental Data Platform

This project is part of the McMaster Watershed Ecosystems Living Lab (WELL). It fetches environmental sensor data (starting with weather station data via HOBOlink Licor Cloud API) for analysis and visualization in a future web dashboard.

---

WP username: mcmasterwell
WP Password: Monitoring@AncasterCr33k

## Python Environment Setup

```bash
python -m venv venv
.\venv\Scripts\activate on Windows
pip install -r requirements.txt
```
If you have already setup the virtual enviroment, to reactivate it do:
```bash
.\venv\Scripts\Activate.ps1
```

## Environment Variables
Create ```bash .env``` file in ```bash backend/``` directory:

```bash
HOBOLINK_API_URL=https://api.hobolink.licor.cloud/v1/data
HOBOLINK_API_TOKEN=your-api-token-here
HOBOLINK_LOGGERS=weatherlogger,waterlogger1,waterlogger2,...,waterlogger5

WQDATA_API_URL=https://www.wqdatalive.com/api/v1
WQDATA_API_KEY=your-api-key-here
WQDATA_DEVICE_ID=your-device-id-here
```
```bash HOBOLINK_LOGGERS``` should be the serial number of each logger

README checklist:
Linux VM hosting stuff
Backend Flask/WSGI and config, Routes, Services, DB, logs, all SCRIPTS, .env

CRON
frontend components, animations, config, filters metrics just an idea of the directory, hooks, api routes, index and styles, Dockerfile and CONFIG IGNORING ERRORS

wordpress self explanatory
nginx
redeploy script
docker compose


python upload_data.py --year 2023 --month 7

Large:
update config.py to use os.get env for all borealis and sharepoint stuff instead of calling it there
Sharepoint Uploads
take out whatever files (css, js, etc ) from wordpress, remove unused classes, and chagne so it doesnt look like macsites theme

Small:
change google maps api to new long term one without dev purposes
openai api too under matt
use webhooks with flask to automate redployments on push to repo
check if sees/macsites/lovable is present anywhere
cron job for inputting to database (add once a month retrieval of borealis as well in same script)
cron job for updating to borealis and sharepoint (use download feature from frontend)
make sure calling api/analysis or whatever on website itself doesnt call and only valid calls to the api are sent
fix all type errors, eslint, typescript etc. by removing the pass in config
CHECK IF MUTLIPLE PEOPLE ON WEBSITE CAN HANDLE
HOST ON VM (DASHBOARD ON dashboard.well.mcmaster.ca) WP on well.mcmaster.ca

https://www.youtube.com/watch?v=-yIsQPp31L0&ab_channel=ByteGrad


Great questions! Here’s a concise breakdown:

---

### 1. How does this config code work?

```python
BOREALIS_URL = Config.DEMO_BOREALIS_URL
BOREALIS_API_TOKEN = Config.BOREALIS_API_TOKEN
# etc.
```
- These lines **read environment variables** via your `Config` class.
- On your Linux VM, you must set these environment variables (e.g., in your shell, .env file, or systemd service).
- When your app starts, `Config` reads them and makes them available everywhere you use `Config`.

---

### 2. What is a WSGI server?

- **WSGI** stands for **Web Server Gateway Interface**.
- It’s a Python standard for running web apps in production.
- **Flask’s built-in server** (`app.run(...)`) is for development only—**not safe or performant for production**.
- **WSGI servers** (like **gunicorn**, **uWSGI**, or **mod_wsgi**) run your Flask app in a robust, multi-process, production-ready way.

---

### 3. What changes for production?

- **You do NOT run `python server.py` directly in production.**
- Instead, you run a WSGI server and point it at your Flask app’s entry point (the `create_app` function in server.py).
- **No code changes are needed** if you use the `create_app` pattern (which you do).

**Example with gunicorn:**
```bash
export DEMO_BOREALIS_URL=...
export BOREALIS_API_TOKEN=...
# etc.
gunicorn --bind 0.0.0.0:5000 server:create_app
```
- This tells gunicorn to use the `create_app` function in server.py.

---

### 4. Can I run multiple processes and load-balance?

- **Yes!** WSGI servers like gunicorn can run multiple worker processes:
    ```bash
    gunicorn --workers 4 --bind 0.0.0.0:5000 server:create_app
    ```
- Gunicorn will **split incoming requests among the workers** automatically.
- For even more scalability, you can run multiple gunicorn instances behind a load balancer (like nginx).

---

### **Summary Table**

| Environment | How to Run                | Handles Concurrency? | Production Ready? |
|-------------|---------------------------|----------------------|-------------------|
| Dev         | `python server.py`        | No                   | No                |
| Prod        | `gunicorn server:create_app` | Yes (multi-worker)   | Yes               |

---

**TL;DR:**  
- Set your environment variables on the VM.
- Use a WSGI server like gunicorn for production.
- No code changes needed for WSGI.
- WSGI servers handle concurrency and load balancing for you.

TODO:
add shared-secret header between dashboard and backend (dashboard sends X-Internal-Auth; Flask validates) for extra protection
Check all backend injection script (historical and scheduled), 
Check CORS for backend API
Setup Template for CSV Sampling uploads
Check if loggers is being inputted
Add indexes on DB for speed
Highcharts Boost Module for faster rendering
Upgrade backend API calls Data chunking, load balancing for multiple concurrent users
Upgrade Frontend to not lag on 
Add script to remove logs from C:\Program Files\PostgreSQL\17\data\log that are a couple months old as storage builds up fast
Add sampling template for researchers to follow
Get proper google maps api 