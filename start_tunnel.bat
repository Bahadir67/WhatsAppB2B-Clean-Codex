@echo off
REM CloudFlare Tunnel Starter Script
REM Bu script .env dosyasından TUNNEL_PORT değerini okur ve CloudFlare tunnel başlatır

echo ==========================================
echo CloudFlare Tunnel Baslatiliyor...
echo ==========================================

REM .env dosyasından TUNNEL_PORT değerini oku
for /f "tokens=2 delims==" %%a in ('findstr "TUNNEL_PORT" .env') do set TUNNEL_PORT=%%a

REM Eğer TUNNEL_PORT tanımlı değilse varsayılan olarak 3005 kullan
if "%TUNNEL_PORT%"=="" (
    set TUNNEL_PORT=3005
    echo [UYARI] TUNNEL_PORT .env dosyasinda bulunamadi. Varsayilan port: 3005
)

echo [INFO] Tunnel Port: %TUNNEL_PORT%
echo [INFO] Tunnel URL'i CloudFlare tarafindan otomatik olusturulacak
echo [INFO] Yeni URL'i .env dosyasindaki TUNNEL_URL'e kaydetmeyi unutmayin!
echo.
echo Baslatiliyor: http://localhost:%TUNNEL_PORT%
echo.

REM CloudFlare tunnel'ı başlat
cloudflared.exe tunnel --url http://localhost:%TUNNEL_PORT%

pause