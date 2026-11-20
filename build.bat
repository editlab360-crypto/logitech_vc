@echo off
pip install -r requirements.txt
pyinstaller logitech_vc.spec --clean --noconfirm
echo.
echo Done: dist\LogitechVC\LogitechVC.exe
pause
