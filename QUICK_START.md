# 快速开始 - GitHub Actions 自动构建

## 🚀 一步触发构建

双击运行 `push_and_build.bat`，它会自动：
1. 添加所有更改
2. 提交代码
3. 推送到 GitHub
4. 触发 GitHub Actions 构建

## 📋 或者手动操作

### 1. 添加并提交代码

```bash
git add .
git commit -m "添加 Tauri 前端"
git push origin main
```

### 2. 查看构建状态

打开浏览器访问：
```
https://github.com/你的用户名/iflow2api/actions
```

### 3. 下载 EXE

构建完成后（约 10-15 分钟）：
- 进入 Actions 页面
- 点击最新的工作流运行
- 在 Artifacts 部分下载 `iFlow2API-Windows-EXE`

## 🏷️ 发布正式版本

创建标签触发自动 Release：

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions 会自动：
- 构建所有平台的安装包
- 创建 GitHub Release
- 上传所有构建产物

## 📦 构建产物

| 文件 | 说明 |
|------|------|
| `iFlow2API.exe` | 绿色版，可直接运行 |
| `iFlow2API_1.0.0_x64_en-US.msi` | Windows 安装包 |
| `iFlow2API_1.0.0_amd64.AppImage` | Linux 绿色版 |
| `iFlow2API_1.0.0_amd64.deb` | Linux 安装包 |
| `iFlow2API_1.0.0_universal.dmg` | macOS 安装包 |

## ⚠️ 首次使用注意

1. **EXE 需要 Python**：确保目标机器已安装 Python，或者将 Python 一起打包
2. **防火墙提示**：首次启动服务可能会有防火墙提示，允许即可
3. **端口占用**：默认使用 8000 端口，如果被占用请修改配置

## 🔧 本地测试（可选）

如果不想等 GitHub Actions，可以在本地构建：

```bash
# 安装依赖
npm install

# 本地开发运行
npm run dev

# 构建 EXE（需要 Rust）
cargo tauri build
```
