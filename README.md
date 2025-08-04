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


Todo:
finish samp and complete ai analysis
fix downsample probably just run a for loop through station ids should work as the others are just 1
change google maps api to new long term one
make start with everything clicked, and clicking an active group also starts with everything clicked
make download also have longtitude and latitude 
borealis api pull weekly sample data
Borealis and Sharepoint uploads
make everything use config/filters.py 
documentation
dew point, relative humidty, solar radition arent being shown on wetaher graph anymore
change hover:text-black to accent on download button
make legend show regardless on modal open
convert everything to est

UNIT TEST EVERYTHING

if active group not open, and you press dropdown arrow, then press subfilter should turn on active group. In short if active group is clicked on, then chevron should always be down (whether its alreayd down or not), if its off then chevron shuld always be right (wheterh its already right or not) but pressing the checvron individually doesnt change it (and make hover effect on chevron)

Home page

Additional:
email notifications for errors in logs
rate limiting api, bugs, caching fixes.
multi sensor ai analysis that only compares sensor to sensor data
*CHECK BEST PRACTISES AND SECURITY FOR ALL COMPONENTS*
make sure calling api/analysis or whatever on website itself doesnt call and only valid calls to the api are sent

