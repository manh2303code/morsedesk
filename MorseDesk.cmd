@echo off
rem Bấm đúp file này để mở MorseDesk trên Windows.
rem
rem Không cần mở terminal, không cần nhớ lệnh. Script tự tìm uv, tự cài phụ thuộc nếu thiếu,
rem rồi mở giao diện. Cửa sổ đen này đóng lại ngay sau khi ứng dụng hiện lên.
setlocal
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
    echo Khong tim thay "uv". Cai bang lenh sau roi chay lai:
    echo     powershell -c "irm https://astral.sh/uv/install.ps1 ^| iex"
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Lan dau chay: dang cai phu thuoc, mat vai phut...
    uv sync --extra runtime --extra gui
    if errorlevel 1 (
        echo Cai phu thuoc that bai. Xem thong bao loi phia tren.
        pause
        exit /b 1
    )
)

start "" /b uv run morsedesk-gui %*
endlocal
