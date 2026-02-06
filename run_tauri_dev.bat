@echo off
chcp 65001 >nul
echo Starting iFlow2API Tauri Development Server...
echo.
echo Make sure you have installed:
echo   1. Node.js (https://nodejs.org/)
echo   2. Rust (https://rustup.rs/)
echo   3. Tauri CLI: cargo install tauri-cli
echo.
echo Installing dependencies...
call npm install
echo.
echo Starting Tauri development server...
cargo tauri dev
pause
