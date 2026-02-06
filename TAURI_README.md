# iFlow2API Tauri + React 前端

现代化的 Tauri + React + TypeScript + TailwindCSS + DaisyUI 桌面应用。

## 技术栈

- **Tauri** - Rust 后端框架，打包为原生桌面应用
- **React 18** - 前端框架
- **TypeScript** - 类型安全
- **TailwindCSS** - 原子化 CSS
- **DaisyUI** - Tailwind 组件库
- **Zustand** - 状态管理
- **React Router** - 路由管理
- **Lucide React** - 图标库

## 功能页面

1. **仪表盘** - 服务状态、系统监控、快捷操作
2. **账号管理** - OAuth 认证、API Key 配置
3. **API 反代** - 代理配置、高级设置
4. **流量日志** - 请求日志查看和筛选
5. **设置** - 主题、语言、缓存管理

## 安装依赖

### 1. 安装 Node.js
https://nodejs.org/ (推荐 v20+)

### 2. 安装 Rust
https://rustup.rs/

### 3. 安装 Tauri CLI
```bash
cargo install tauri-cli
```

### 4. 安装项目依赖
```bash
npm install
```

## 开发运行

```bash
# 启动 Tauri 开发服务器
cargo tauri dev

# 或使用 npm 脚本
npm run tauri:dev
```

## 构建发布版本

```bash
# 构建 Windows EXE
cargo tauri build

# 或使用 npm 脚本
npm run tauri:build
```

构建后的 EXE 位于 `src-tauri/target/release/iFlow2API.exe`

## 项目结构

```
iflow2api/
├── src/                      # React 前端代码
│   ├── components/           # UI 组件
│   │   ├── layout/           # 布局组件
│   │   └── navbar/           # 导航栏组件
│   ├── pages/                # 页面组件
│   │   ├── Dashboard.tsx     # 仪表盘
│   │   ├── Accounts.tsx      # 账号管理
│   │   ├── ApiProxy.tsx      # API 反代
│   │   ├── Monitor.tsx       # 流量日志
│   │   └── Settings.tsx      # 设置
│   ├── stores/               # Zustand 状态管理
│   ├── types/                # TypeScript 类型定义
│   ├── utils/                # 工具函数
│   ├── App.tsx               # 应用入口
│   ├── main.tsx              # React 入口
│   └── index.css             # 全局样式
├── src-tauri/                # Rust 后端代码
│   └── src/main.rs           # Tauri 主程序
├── package.json              # NPM 配置
├── tailwind.config.js        # Tailwind 配置
├── tsconfig.json             # TypeScript 配置
└── vite.config.ts            # Vite 配置
```

## 配色方案

使用 DaisyUI dark 主题：
- `base-100`: #0f172a (Slate-900) - 主背景
- `base-200`: #1e293b (Slate-800) - 卡片背景
- `base-300`: #334155 (Slate-700) - 边框/分隔线
- `primary`: #3b82f6 (Blue-500) - 主色
- `accent`: #10b981 (Emerald-500) - 强调色

## 与 Python 后端集成

Tauri Rust 后端通过 `std::process::Command` 启动 Python 服务：

```rust
Command::new("python")
    .arg("-m")
    .arg("uvicorn")
    .arg("main:app")
    .arg("--host")
    .arg("0.0.0.0")
    .arg("--port")
    .arg(port.to_string())
    .spawn()
```

打包时需要将 `main.py` 和所有依赖放在 EXE 同级目录。

## 注意事项

1. 确保 Python 已安装并在 PATH 中
2. 确保 `main.py` 所在目录有 `requirements.txt` 中的依赖
3. 开发模式下 Python 服务输出会显示在终端中
4. 首次启动可能需要几秒钟初始化
