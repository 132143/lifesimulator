@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   弹窗式文字人生模拟器  Life Simulator
echo ============================================
echo.
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没有找到 python 命令。
    echo        请先安装 Python 3.8 以上版本，并勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)
python "%~dp0LifeSimulator.py" %*
if errorlevel 1 (
    echo.
    echo 程序异常退出，错误码 %errorlevel%。
    pause
)
