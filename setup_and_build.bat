@echo off
chcp 65001 >nul
echo ==========================================
echo iFlow2API 构建脚本
echo ==========================================
echo.

:: 检查是否已安装 Rust
where cargo >nul 2>nul
if %ERRORLEVEL% == 0 (
    echo [✓] Rust 已安装
    goto :BUILD
) else (
    echo [!] Rust 未安装，开始安装...
    goto :INSTALL_RUST
)

:INSTALL_RUST
:: 下载并安装 Rust
echo 正在下载 Rust 安装器...
powershell -Command "& {$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://win.rustup.rs/x86_64' -OutFile 'rustup-init.exe'}"
if not exist rustup-init.exe (
    echo [✗] 下载失败，请手动安装 Rust: https://rustup.rs/
    pause
    exit /b 1
)

echo 正在安装 Rust（可能需要几分钟）...
rustup-init.exe -y --default-toolchain stable
if %ERRORLEVEL% neq 0 (
    echo [✗] Rust 安装失败
    pause
    exit /b 1
)

:: 设置环境变量
call "%USERPROFILE%\.cargo\env"

:BUILD
echo.
echo ==========================================
echo 开始构建 iFlow2API
echo ==========================================
echo.

:: 安装 Tauri CLI
echo [1/4] 检查 Tauri CLI...
cargo install tauri-cli 2>nul

:: 构建前端
echo [2/4] 构建前端...
call npm install
call npm run build
if %ERRORLEVEL% neq 0 (
    echo [✗] 前端构建失败
    pause
    exit /b 1
)

:: 构建 Tauri
echo [3/4] 构建 Tauri 应用（这可能需要几分钟）...
cargo tauri build
if %ERRORLEVEL% neq 0 (
    echo [✗] 构建失败
    pause
    exit /b 1
)

echo.
echo ==========================================
echo [✓] 构建成功！
echo ==========================================
echo.
echo 输出文件:
echo   - EXE: src-tauri\target\release\iFlow2API.exe
echo   - 安装包: src-tauri\target\release\bundle\msi\
echo.
pause
