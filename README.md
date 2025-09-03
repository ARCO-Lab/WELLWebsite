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


python upload_data.py --year 2023 --month 7

Large:
Change hero section
- responsiveness in mobile
borealis api pull weekly sample data
Borealis and Sharepoint uploads
take out whatever files (css, js, etc ) from wordpress, remove unused classes, and chagne so it doesnt look like macsites theme

Small:
change google maps api to new long term one without dev purposes
openai api too under matt
use webhooks with flask to automate redployments on push to repo
documentation
check if sees/macsites/lovable is present anywhere
cron job for inputting to database (add once a month retrieval of borealis as well in same script)
cron job for updating to borealis and sharepoint (use download feature from frontend)
make sure calling api/analysis or whatever on website itself doesnt call and only valid calls to the api are sent
fix all type errors, eslint, typescript etc. by removing the pass in config
CHECK IF MUTLIPLE PEOPLE ON WEBSITE CAN HANDLE
HOST ON VM (DASHBOARD ON dashboard.well.mcmaster.ca) WP on well.mcmaster.ca


UNIT TEST EVERYTHING



Additional:
email notifications for errors in logs
rate limiting api, bugs, caching fixes.
*CHECK BEST PRACTISES AND SECURITY FOR ALL COMPONENTS*
make sure calling api/analysis or whatever on website itself doesnt call and only valid calls to the api are sent

https://www.youtube.com/watch?v=-yIsQPp31L0&ab_channel=ByteGrad