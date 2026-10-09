@echo off
chcp 65001 >nul
title 弹窗式文字人生模拟器
cd /d "%~dp0"

echo ============================================================
echo            弹窗式文字人生模拟器  Life Simulator
echo ============================================================
echo.

rem ---- 1) 依次尝试 python / py 启动 ----
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY ( where py >nul 2>nul && set "PY=py" )

if not defined PY (
    echo [错误] 没有找到 Python。
    echo.
    echo 请先安装 Python 3.8 或更高版本：
    echo     https://www.python.org/downloads/
    echo.
    echo 安装时请务必勾选：
    echo     [x] Add Python to PATH          ^(把 Python 加入 PATH^)
    echo     [x] tcl/tk and IDLE              ^(游戏界面需要 tkinter^)
    echo.
    echo 安装完成后重新双击本文件即可。
    echo.
    pause
    exit /b 1
)

rem ---- 2) 便携模式：存档与游戏放在同一个文件夹 ----
if not exist "save" mkdir "save"

echo 正在启动游戏……（关闭游戏窗口即退出）
echo.
%PY% "%~dp0LifeSimulator.py" --portable %*

if errorlevel 1 (
    echo.
    echo [提示] 游戏异常退出，错误码 %errorlevel%。
    echo        如果窗口一闪而过，请把上面的报错信息截图反馈。
    echo.
    pause
)
