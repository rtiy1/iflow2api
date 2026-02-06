# iFlow2API (Python + GUI)

轻量的 iFlow 反代服务，提供 OpenAI/Anthropic 风格接口与本地 GUI 管理。

## 功能
- FastAPI 反代服务（OpenAI / Anthropic 兼容）
- GUI 一键启动、端口管理、请求日志与状态页
- OAuth 登录与本地配置读取
- 多模态图片输入自动切换视觉模型（默认 `qwen3-vl-plus`）

## 运行环境
- Python 3.10+
- Windows（GUI 依赖 PyQt5）

## 快速开始
1. 安装依赖
```bash
pip install -r requirements.txt
```

2. OAuth 登录（可选但推荐）
```bash
python iflow_auth_cli.py
```

3. 启动服务（命令行）
```bash
python main.py
```

4. 启动 GUI
```bash
python gui_pyqt.py
```

默认端口：`8000`  
管理页：`http://127.0.0.1:8000/admin`

## 主要接口
- `POST /v1/chat/completions`
- `POST /v1/messages`
- `GET /health`

## 配置文件
自动读取：
- `~/.iflow/oauth_creds.json`（OAuth）
- `~/.iflow/settings.json`（API Key）

支持的关键字段：
- `apiKey`
- `baseUrl`
- `visionModel`（默认 `qwen3-vl-plus`）
- `autoVisionModel`（默认 `true`）
- `allowLocalFileImages`（默认 `false`）

## 构建 EXE
```bash
python build_gui.py
```
输出：`dist/iflow2api-gui.exe`
