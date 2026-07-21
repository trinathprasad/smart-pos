@echo off
pyinstaller --onefile --name device-monitor-server run.py
pyinstaller --onefile --name device-monitor-client collect_client.py
pyinstaller --onefile --name device-monitor-export export_excel.py
echo Build completed. Check the dist folder.
