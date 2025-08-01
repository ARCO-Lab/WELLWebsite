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


Before August 4:
Finish UI upgrade for dashboard
Add other page for sample points
Borealis and Sharepoint uploads
Make consistent formatting from ai analysis api to avoid issues
fix readme todo
when logger added, get name for Logger(last digit in alphabet (L = 2)) and then number of logger for station id db wise (parse in the loggerservice itself)
create new table for sample data using same encoding for each creek 

After august 4:




AFTER:
Fix reset key on checkboxes as fades in properly when loading in, but doesnt after, and fix sublogger animation
LatestMetrics and Graphs should use Collapsible and fade in new components, and opposite, modal should fade in, 
Apply Metrics Gallery Code to latest metrics to view each metric add images and pictures related to it
windrose tab
make sure marker info pop up doesn't disspear when hover on it
make latestmetrics be a bit shorter so that ai analysis has some space at the bottom
spinning animation while graphs load
Icons for download, X on modal, animation on home page icon like shadow, 
fix header

CHANGE API LINK IT IS NEW
CHEK IF BEST PRACTISE TO HAVE AI IN ENDPOINT


After: 
email notifications for errors in logs
start with everything checked when page loads, then allow user to change (default date range being the last week)
rate limiting api, bugs, caching fixes.
have hooks already ready to go on index page.
add pictures of each station on info pop up
multi sensor ai analysis that only compares sensor to sensor data
*CHECK BEST PRACTISES AND SECURITY FOR ALL COMPONENTS*


logger graph:
similar to metric resizing, have y axis cuts that go from same range to same range essentially 5 different graphs(or less depending on how mnay loggers clicked) but hovering shows all metrics for all loggers, water level blue, temp red, same for all loggers, same legend, just resizing similar to latestmetrics with cuts so that y axis has the same stuff

make sure calling api/analysis or whatever on website itself doesnt call and only valid calls to the api are sent

when other tab for other smaple data is ready make all filters and stuff flip to show other options
borealis api pull
monthly sharepoint and borealis push database


