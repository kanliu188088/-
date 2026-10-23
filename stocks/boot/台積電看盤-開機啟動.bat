@echo off
rem 開機後全螢幕打開「台積電 AI 鏈看盤」儀表板。按 Alt+F4 關閉。
set URL=https://claude.ai/artifact/26V5pEmZoJMCHDeNWGMHSW
timeout /t 15 /nobreak >nul
where msedge >nul 2>nul && (start "" msedge --app=%URL% --start-fullscreen & exit /b)
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app=%URL% --start-fullscreen & exit /b)
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app=%URL% --start-fullscreen & exit /b)
start "" %URL%
