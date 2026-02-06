# GitHub Actions 自动构建

## 🚀 快速开始

### 1. 推送代码到 GitHub

```bash
git add .
git commit -m "添加 Tauri 前端和 GitHub Actions"
git push origin main
```

### 2. 查看构建状态

- 进入 GitHub 仓库页面
- 点击 "Actions" 标签
- 查看构建进度

### 3. 下载构建产物

构建完成后，可以在以下位置下载：

**方式一：Actions 页面下载**
- 进入 Actions → 选择最新工作流运行
- 在 "Artifacts" 部分下载 EXE 或 MSI

**方式二：Release 页面下载（推荐）**

创建标签触发 Release：

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions 会自动：
1. 构建 Windows EXE 和 MSI 安装包
2. 构建 Linux AppImage 和 DEB 包
3. 构建 macOS DMG 包
4. 创建 GitHub Release 并上传所有文件

## 📦 构建输出

| 平台 | 文件类型 | 输出路径 |
|------|----------|----------|
| Windows | EXE | `iFlow2API.exe` |
| Windows | MSI 安装包 | `iFlow2API_1.0.0_x64_en-US.msi` |
| Linux | AppImage | `iFlow2API_1.0.0_amd64.AppImage` |
| Linux | DEB 包 | `iFlow2API_1.0.0_amd64.deb` |
| macOS | DMG | `iFlow2API_1.0.0_universal.dmg` |

## ⚙️ 工作流配置

### 触发条件

工作流会在以下情况自动运行：

1. **推送代码到 main/master 分支**
2. **创建 v 开头的标签**（如 v1.0.0）- 会触发 Release
3. **手动触发** - 在 Actions 页面点击 "Run workflow"

### 手动触发构建

如果不想推送代码，可以手动触发：

1. 进入 GitHub 仓库 → Actions
2. 选择 "Build and Release" 工作流
3. 点击 "Run workflow" → "Run workflow"

## 🔧 构建说明

### Windows 构建
- 使用 `windows-latest` 运行器
- 安装 Node.js 20
- 安装 Rust stable
- 输出 EXE 和 MSI

### Linux 构建
- 使用 `ubuntu-latest` 运行器
- 安装系统依赖（GTK、WebKit 等）
- 输出 AppImage 和 DEB

### macOS 构建
- 使用 `macos-latest` 运行器
- 构建 Universal 二进制（支持 Intel 和 Apple Silicon）
- 输出 DMG

## 📝 使用步骤

### 第一次使用

1. 确保代码已推送到 GitHub
2. 等待 Actions 完成构建（约 10-15 分钟）
3. 下载构建产物测试

### 发布新版本

```bash
# 1. 更新版本号（修改 package.json 和 tauri.conf.json）

# 2. 提交更改
git add .
git commit -m "Release v1.1.0"

# 3. 创建标签
git tag v1.1.0

# 4. 推送标签（触发 Release 构建）
git push origin main
git push origin v1.1.0

# 5. 等待 GitHub Actions 完成
# 6. 在 GitHub Release 页面查看自动创建的 Release
```

## ⚠️ 注意事项

1. **第一次构建较慢**（约 15-20 分钟），因为需要安装依赖
2. **缓存机制**：Node.js 和 Rust 依赖会被缓存，后续构建会更快
3. **构建失败**：检查 Actions 日志，通常是依赖问题

## 🔗 相关链接

- [GitHub Actions 文档](https://docs.github.com/cn/actions)
- [Tauri 构建指南](https://tauri.app/v1/guides/building/)
- [DaisyUI 文档](https://daisyui.com/)
