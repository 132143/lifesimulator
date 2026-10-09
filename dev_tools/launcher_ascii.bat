@echo off
title Life Simulator
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ============================================================
echo            Life Simulator
echo ============================================================
echo.

rem ---- 逐个候选，真实执行 --version 来验证是不是可用的 Python ----
set "PY="
call :TRYPY python
if not defined PY call :TRYPY py
if not defined PY call :TRYPY python3

if not defined PY goto SEARCH_COMMON
goto HAVE_PY

rem ==============================================================
rem :TRYPY  参数1 = 命令名。能真正打印版本号才算可用
rem         （Microsoft Store 的 python.exe 占位程序会失败，必须排除）
rem ==============================================================
:TRYPY
"%~1" --version >nul 2>nul
if %errorlevel%==0 set "PY=%~1"
goto :eof

rem ---- PATH 里找不到，就去找常见安装位置 ----
:SEARCH_COMMON
for %%D in (
    "%LOCALAPPDATA%\Programs\Python"
    "%ProgramFiles%"
    "%ProgramFiles(x86)%"
    "C:\"
) do (
    if not defined PY (
        for /d %%P in ("%%~D\Python*") do (
            if not defined PY (
                if exist "%%~P\python.exe" set "PY=%%~P\python.exe"
            )
        )
    )
)

if not defined PY goto NOPYTHON

:HAVE_PY
if not exist "save" mkdir "save"

echo 使用解释器：!PY!
echo 正在启动游戏，请稍候……
echo.
"!PY!" "LifeSimulator.py" --portable %*

if %errorlevel%==0 goto DONE
echo.
echo [警告] 游戏异常退出，错误码 %errorlevel%
pause
goto DONE

:NOPYTHON
echo [错误] 没有检测到可用的 Python
echo.
echo 说明：如果您只装了微软商店的 python 占位程序，它无法运行本游戏。
echo.
echo 请安装官方 Python 3.8 或更高版本：
echo     1. 打开  https://www.python.org/downloads/
echo     2. 点击黄色大按钮下载安装包并运行
echo     3. 安装界面务必勾选：
echo          [x] Add Python to PATH
echo          [x] tcl/tk and IDLE
echo     4. 装好后重新双击本文件
echo.
echo 提示：也可以在微软商店搜索 Python 3.12 安装（同样可以运行）。
pause

:DONE
endlocal
