@echo off
echo GitHub'da yeni repo olusturun ve URL'yi girin
echo Ornek: https://github.com/Bahadir67/WhatsApp-B2B-Swarm.git
echo.
set /p REPO_URL="GitHub Repo URL: "

git remote add origin %REPO_URL%
git branch -M main
git push -u origin main

echo.
echo ✅ Temiz proje GitHub'a yuklendi!
echo Repo: %REPO_URL%
pause