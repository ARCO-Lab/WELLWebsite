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