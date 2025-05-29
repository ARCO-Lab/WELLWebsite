# WELL Environmental Data Platform

This project is part of the McMaster Watershed Ecosystems Living Lab (WELL). It fetches environmental sensor data (starting with weather station data via HOBOlink Licor Cloud API) for analysis and visualization in a future web dashboard.

---

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


TODO: 
start with everything checked when page loads, then allow user to change (default date range being the last week)
graphs mimic wqlive graph template

have latest dat take full part when only 1 half when 2, third when 3 with scroll if needed:

have pop up close on click off, take bigger part of page normally, and not recall api but open the existing metric or graph

ensure calendar date start cant be higher than end, and default hours minutes seconds is 00:00:00 for the request

fix download have header have units
database in est while frontend in utc