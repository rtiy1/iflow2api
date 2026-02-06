@echo off
chcp 65001 >nul
echo ==========================================
echo iFlow2API GitHub Actions 触发脚本
echo ==========================================
echo.

:: 检查 git 是否安装
where git >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [✗] 未找到 git，请先安装 Git
    pause
    exit /b 1
)

:: 检查是否在 git 仓库中
git rev-parse --git-dir >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [✗] 当前目录不是 git 仓库
    pause
    exit /b 1
)

:: 显示当前状态
echo [1/4] 检查 git 状态...
git status --short
echo.

:: 添加所有更改
echo [2/4] 添加更改到暂存区...
git add .

:: 提交
echo [3/4] 创建提交...
git commit -m "feat: 添加 Tauri 前端和 GitHub Actions 自动构建

- 添加 React + TypeScript + TailwindCSS + DaisyUI 前端
- 集成 OAuth 认证功能
- 添加 GitHub Actions 自动构建工作流
- 支持 Windows、Linux、macOS 多平台构建"

if %ERRORLEVEL% neq 0 (
    echo [!] 没有可提交的更改，或提交失败
    echo.
    echo 是否强制推送现有代码？(y/n)
    set /p force_push=
    if /I "%force_push%"=="y" goto :PUSH
    pause
    exit /b 1
)

:PUSH
echo.
echo [4/4] 推送到 GitHub...
git push origin main

if %ERRORLEVEL% neq 0 (
    echo [✗] 推送失败
    pause
    exit /b 1
)

echo.
echo ==========================================
echo [✓] 推送成功！
echo ==========================================
echo.
echo GitHub Actions 已触发构建，请访问：
echo   https://github.com/%GITHUB_REPOSITORY%/actions
echo.
echo 或手动查看：
echo   1. 打开 GitHub 仓库页面
echo   2. 点击 Actions 标签
echo   3. 查看 Build and Release 工作流
echo.
pause
