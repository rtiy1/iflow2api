# OAuth 集成完成

## ✅ 已完成的功能

### 1. Python OAuth CLI 脚本
- **文件**: `iflow_oauth_cli.py`
- **功能**: 启动 OAuth 流程，自动打开浏览器，处理回调，保存凭据
- **输出**: JSON 格式结果供 Tauri 解析

### 2. Rust 后端命令
- **get_oauth_creds**: 读取已保存的 OAuth 凭据
- **start_oauth**: 启动 OAuth 流程，调用 Python 脚本
- **delete_oauth_creds**: 删除凭据文件

### 3. 前端 API 封装
- `api.getOAuthCreds()` - 获取凭据
- `api.startOAuth()` - 启动 OAuth
- `api.deleteOAuth()` - 删除凭据

### 4. 账号管理页面
- 自动加载已保存的凭据
- 显示认证状态和过期时间
- 启动 OAuth 登录流程
- 退出登录删除凭据

## 📋 OAuth 流程

```
用户点击「OAuth 登录」
    ↓
Rust 调用 python iflow_oauth_cli.py
    ↓
Python 生成授权 URL
    ↓
自动打开系统浏览器
    ↓
用户在浏览器完成授权
    ↓
iFlow 重定向到 localhost:8087/oauth2callback
    ↓
Python HTTP 服务器接收回调
    ↓
Python 交换 code 获取 token
    ↓
Python 获取用户信息和 API Key
    ↓
保存到 ~/.iflow/oauth_creds.json
    ↓
返回 JSON 结果给 Rust
    ↓
前端更新认证状态
```

## 🔧 文件改动

### 新增文件
- `iflow_oauth_cli.py` - OAuth CLI 脚本

### 修改文件
- `src-tauri/src/main.rs` - 添加 OAuth 命令
- `src/utils/request.ts` - 添加 OAuth API
- `src/pages/Accounts.tsx` - 集成真实 OAuth 功能

## ⚠️ 注意事项

1. **端口 8087**: OAuth 回调使用固定端口 8087，确保未被占用
2. **浏览器**: 需要系统默认浏览器可用
3. **网络**: 需要访问 iflow.cn 进行授权
4. **httpx**: Python 环境需要安装 httpx: `pip install httpx`

## 🧪 测试步骤

```bash
# 1. 启动开发服务器
cargo tauri dev

# 2. 进入账号管理页面
# 3. 点击「OAuth 登录」
# 4. 浏览器应该自动打开授权页面
# 5. 完成授权后，页面会显示已认证状态
# 6. 检查 ~/.iflow/oauth_creds.json 是否存在
```
