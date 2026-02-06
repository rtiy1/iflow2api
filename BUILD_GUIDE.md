# iFlow2API 构建指南

## ⚠️ 前置条件

构建 Tauri 应用需要以下软件：

1. **Node.js** (v18+) - https://nodejs.org/
2. **Rust** (最新版) - https://rustup.rs/
3. **Python** - 你的 main.py 依赖

## 🚀 快速构建步骤

### 方法一：自动脚本（推荐）

双击运行 `setup_and_build.bat`，它会自动：
1. 检查并安装 Rust
2. 安装 Tauri CLI
3. 构建前端
4. 构建 EXE

### 方法二：手动步骤

#### 1. 安装 Rust

访问 https://rustup.rs/ 下载安装，或在 PowerShell 运行：

```powershell
Invoke-WebRequest -Uri https://win.rustup.rs/x86_64 -OutFile rustup-init.exe
.\rustup-init.exe -y
```

安装完成后重启终端，验证：
```bash
rustc --version
cargo --version
```

#### 2. 安装依赖

```bash
# Node.js 依赖
npm install

# Tauri CLI
cargo install tauri-cli
```

#### 3. 构建

```bash
# 构建发布版本
cargo tauri build
```

构建完成后，输出文件在：
- **EXE**: `src-tauri/target/release/iFlow2API.exe`
- **MSI 安装包**: `src-tauri/target/release/bundle/msi/iFlow2API_1.0.0_x64_en-US.msi`

## 📦 打包注意事项

### 包含的文件

构建后的 EXE 需要以下文件在同一目录：

```
iFlow2API.exe
main.py              # 你的 API 服务
iflow_oauth.py       # OAuth 模块
iflow_token.py       # Token 管理（如果有）
requirements.txt     # Python 依赖
```

### 分发方式

1. **绿色版**: 直接复制 `iFlow2API.exe` + Python 文件给用户
2. **安装包**: 使用构建的 MSI 安装包

## 🔧 常见问题

### 1. 构建失败：找不到 cargo

确保 Rust 已正确安装并重启终端：
```bash
# 添加 cargo 到 PATH
$env:PATH += ";$env:USERPROFILE\.cargo\bin"
```

### 2. 构建失败：前端构建错误

```bash
# 单独构建前端测试
npm run build
```

### 3. 运行时提示缺少 Python

确保用户系统已安装 Python，或在打包时考虑使用 PyInstaller 将 Python 服务也打包。

### 4. 图标不显示

确保 `src-tauri/icons/` 目录包含：
- icon.ico (Windows)
- 128x128.png

## 📝 当前状态

Node.js 依赖已安装完成 ✅

等待 Rust 安装后执行 `cargo tauri build`
