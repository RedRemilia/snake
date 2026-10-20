@echo off
chcp 65001 >nul
cd /d "%~dp0"

call conda activate py313 >nul 2>&1
if errorlevel 1 (
    where conda >nul 2>&1
    if errorlevel 1 (
        echo [错误] 未找到 conda，请先安装 Anaconda 或 Miniconda。
        pause
        exit /b 1
    )
    echo 未能直接激活环境，改用 conda run 启动 py313...
    conda run --no-capture-output -n py313 python main.py
) else (
    python main.py
)

if errorlevel 1 pause
