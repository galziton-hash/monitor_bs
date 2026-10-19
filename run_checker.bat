@echo off
:: HBS Ticket Checker - runs the Python script
:: Called by Windows Task Scheduler every 3 minutes

cd /d "C:\Users\galz\source\HBS_Shefa"

set PYTHONIOENCODING=utf-8
set LOGIN_EMAIL=eladb8@gmail.com
set LOGIN_PASSWORD=Imri1212
set NTFY_TOPIC=hbs-shefa
set NTFY_SERVER=https://ntfy.sh
set CHROME_PROFILE_PATH=C:\Users\galz\AppData\Local\Google\Chrome\User Data\Default

if not exist logs mkdir logs
python check_tickets.py >> logs\checker.log 2>&1
