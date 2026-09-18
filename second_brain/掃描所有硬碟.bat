@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 開始掃描所有硬碟（第一次會比較久，可隨時按 Ctrl+C 中斷，進度會保留）
python second_brain.py scan %*
echo.
echo 完成。搜尋範例：python second_brain.py search 關鍵字
pause
