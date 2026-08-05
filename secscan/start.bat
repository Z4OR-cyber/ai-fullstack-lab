@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================
REM SecScan 一键启动脚本 (Windows)
REM 功能：检查 Python → 安装依赖 → 启动服务 → 提示访问地址
REM ============================================================

REM ---- 配置 ----
set APP_NAME=SecScan
set APP_PORT=8000
if defined APP_PORT_OVERRIDE set APP_PORT=%APP_PORT_OVERRIDE%
set APP_URL=http://localhost:%APP_PORT%
set PYTHON_MIN_MAJOR=3
set PYTHON_MIN_MINOR=10

REM ---- 获取脚本所在目录（项目根目录）----
cd /d "%~dp0"

REM ---- 横幅 ----
echo.
echo   ╔══════════════════════════════════════════════╗
echo   ║          🛡️  SecScan  v2.0.0                 ║
echo   ║     AI 驱动的代码安全审计平台  一键启动       ║
echo   ╚══════════════════════════════════════════════╝
echo.

REM ============================================================
REM 步骤 1：检查 Python 环境
REM ============================================================
echo.
echo   ━━━ 步骤 1/4：检查 Python 环境 ━━━
echo.

REM 尝试查找 Python 命令
set PYTHON_CMD=
where python >nul 2>&1 && set PYTHON_CMD=python
if not defined PYTHON_CMD (
    where python3 >nul 2>&1 && set PYTHON_CMD=python3
)
if not defined PYTHON_CMD (
    where py >nul 2>&1 && set PYTHON_CMD=py
)

if not defined PYTHON_CMD (
    echo   [ERROR] 未检测到 Python 环境！
    echo.
    echo   请安装 Python %PYTHON_MIN_MAJOR%.%PYTHON_MIN_MINOR% 或更高版本：
    echo   官网下载： https://www.python.org/downloads/
    echo   安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM 获取 Python 版本
for /f "tokens=*" %%i in ('%PYTHON_CMD% -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PYTHON_VERSION=%%i
for /f "tokens=1 delims=." %%i in ("%PYTHON_VERSION%") do set PYTHON_MAJOR=%%i
for /f "tokens=2 delims=." %%i in ("%PYTHON_VERSION%") do set PYTHON_MINOR=%%i

echo   [INFO]  检测到 Python：%PYTHON_CMD% ^(v%PYTHON_VERSION%^)

REM 检查版本是否满足要求
set /a VERSION_OK=0
if %PYTHON_MAJOR% gtr %PYTHON_MIN_MAJOR% set /a VERSION_OK=1
if %PYTHON_MAJOR% equ %PYTHON_MIN_MAJOR% if %PYTHON_MINOR% geq %PYTHON_MIN_MINOR% set /a VERSION_OK=1

if !VERSION_OK! equ 0 (
    echo   [ERROR] Python 版本过低！当前 v%PYTHON_VERSION%，需要 v%PYTHON_MIN_MAJOR%.%PYTHON_MIN_MINOR%+
    echo.
    echo   请升级 Python 版本后重试。
    echo.
    pause
    exit /b 1
)

echo   [OK]    Python 版本满足要求 ^(%PYTHON_MAJOR%.%PYTHON_MINOR%+^)

REM ============================================================
REM 步骤 2：创建虚拟环境并安装依赖
REM ============================================================
echo.
echo   ━━━ 步骤 2/4：安装依赖 ━━━
echo.

set VENV_DIR=.venv

REM 创建虚拟环境（如果不存在）
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo   [INFO]  创建虚拟环境 ^(%VENV_DIR%^) ...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    echo   [OK]    虚拟环境已创建
) else (
    echo   [INFO]  虚拟环境已存在，跳过创建
)

REM 激活虚拟环境
if exist "%VENV_DIR%\Scripts\activate.bat" (
    call "%VENV_DIR%\Scripts\activate.bat"
    echo   [OK]    已激活虚拟环境
) else (
    echo   [WARN]  虚拟环境激活文件不存在，使用系统 Python 继续
)

REM 检查是否需要安装依赖
pip show fastapi >nul 2>&1
if %errorlevel% equ 0 (
    echo   [INFO]  依赖已安装，跳过安装步骤
) else (
    echo   [INFO]  安装依赖 ^(requirements.txt^) ...
    echo.
    python -m pip install --upgrade pip -q
    pip install -r requirements.txt -q
    echo   [OK]    依赖安装完成
)

REM ============================================================
REM 步骤 3：检查端口占用
REM ============================================================
echo.
echo   ━━━ 步骤 3/4：检查端口 %APP_PORT% ━━━
echo.

REM 检查端口是否被占用
netstat -ano | findstr ":%APP_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [WARN]  端口 %APP_PORT% 已被占用！
    echo.
    echo   解决方法：
    echo   1. 终止占用进程：netstat -ano | findstr :%APP_PORT% 查看后 taskkill /PID ^<PID^> /F
    echo   2. 换端口启动：set APP_PORT_OVERRIDE=8080 ^&^& start.bat
    echo.
    set /a NEW_PORT=%APP_PORT%+1
    echo   [INFO]  尝试自动切换到端口 !NEW_PORT! ...
    netstat -ano | findstr ":!NEW_PORT! " | findstr "LISTENING" >nul 2>&1
    if !errorlevel! neq 0 (
        set APP_PORT=!NEW_PORT!
        set APP_URL=http://localhost:!APP_PORT!
        echo   [OK]    已切换到端口 !APP_PORT!
    ) else (
        echo   [ERROR] 端口 !NEW_PORT! 也被占用，请手动指定端口
        echo   set APP_PORT_OVERRIDE=9000 ^&^& start.bat
        pause
        exit /b 1
    )
) else (
    echo   [OK]    端口 %APP_PORT% 可用
)

REM ============================================================
REM 步骤 4：启动服务
REM ============================================================
echo.
echo   ━━━ 步骤 4/4：启动 SecScan 服务 ━━━
echo.
echo.
echo   SecScan 正在启动...
echo.
echo   Web 界面：  %APP_URL%
echo   API 文档：  %APP_URL%/docs
echo   健康检查：  %APP_URL%/
echo.
echo   按 Ctrl+C 停止服务
echo.
echo   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

REM 尝试打开浏览器（后台执行，不阻塞）
start "" /b cmd /c "timeout /t 3 /nobreak >nul 2>&1 && start %APP_URL%"

REM 启动 uvicorn
python -m uvicorn app.main:app --host 0.0.0.0 --port %APP_PORT%

REM 如果 uvicorn 异常退出，暂停以便查看错误
if %errorlevel% neq 0 (
    echo.
    echo   [ERROR] 服务启动失败，请检查上方错误信息
    echo.
    pause
)

endlocal
