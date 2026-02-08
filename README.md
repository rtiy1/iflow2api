# iFlow2API

iFlow 的 Python 反向代理，提供 OpenAI/Anthropic 兼容接口，包含 GUI 控制台与无 GUI Agent（适合常驻后台）。

## 1. 功能概览

- OpenAI 兼容接口：`/v1/chat/completions`
- Anthropic 兼容接口：`/v1/messages`
- 模型列表接口：`/v1/models`
- 健康检查：`/health`、`/v1/health`
- GUI 一键启动/停止、日志查看、模型列表查看
- Agent 后台运行、开机自启、状态查询与停止
- 图片请求智能处理（仅对指定模型系列启用两段式）

## 2. 当前图片识别策略（重要）

当前不是“全模型强制视觉模型”，而是按模型系列分流：

- `glm*`、`minimax*`：走两段式
1. 先使用 `qwen3-vl-plus` 读取图片并生成结构化摘要
2. 去除原消息中的图片块
3. 将视觉摘要作为桥接系统消息
4. 再交回原主模型继续回答

- 其他模型：不自动切换，按原模型直接请求

说明：

- 视觉阶段失败时，会降级为直接由视觉模型返回结果（避免完全失败）
- 语义错误回退机制已移除，当前主路径是显式两段式

## 3. `/v1/models` 模型列表策略

`/v1/models` 会先返回上游结果，并补充本地可用但上游列表可能不返回的模型：

- `glm-4.7`
- `minimax-m2.1`
- `kimi-k2.5`

GUI 的“模型列表”按钮读取的是这个接口，因此会看到上述补充模型。

## 4. 项目结构（模块化）

- `app/`：FastAPI 服务与路由
- `proxy/`：上游请求代理、模型转换、两段式视觉逻辑
- `auth/`：OAuth 与 token 管理
- `converters/`：消息格式转换相关能力
- `core/`：配置、通用逻辑（如 thinking）
- `gui/`：PyQt GUI
- `agent/`：后台 Agent 入口与管理
- 兼容入口：
- `main.py`
- `gui_pyqt.py`
- `iflow_agent.py`
- `iflow_auth_cli.py`

## 5. 运行环境

- Python 3.10+
- Windows（GUI 使用 PyQt5）

## 6. 安装与启动

### 6.1 安装依赖

```bash
pip install -r requirements.txt
```

### 6.2 认证配置（推荐 OAuth）

```bash
python iflow_auth_cli.py
```

默认读取：

- `~/.iflow/oauth_creds.json`
- `~/.iflow/settings.json`

### 6.3 启动服务（命令行）

```bash
python main.py
```

默认端口：`8000`  
管理页：`http://127.0.0.1:8000/admin`

### 6.4 启动 GUI

```bash
python gui_pyqt.py
```

GUI 行为：

- 支持单实例（重复启动会提示并退出）
- 点击关闭为托盘驻留，不是立刻退出
- 通过托盘菜单可彻底退出

### 6.5 启动 Agent（无 GUI）

前台运行：

```bash
python iflow_agent.py run --port 8000
```

后台启动：

```bash
python iflow_agent.py start --port 8000
```

查看状态：

```bash
python iflow_agent.py status
```

停止：

```bash
python iflow_agent.py stop
```

安装开机自启：

```bash
python iflow_agent.py install-autostart --port 8000
```

移除开机自启：

```bash
python iflow_agent.py uninstall-autostart
```

用户可用一键停止脚本：

- `stop_iflow2api.bat`

## 7. 关键配置项

配置来源：`~/.iflow/oauth_creds.json` 或 `~/.iflow/settings.json`

- `apiKey` / `api_key`
- `baseUrl` / `base_url`
- `visionModel` / `vision_model`（默认 `qwen3-vl-plus`）
- `autoVisionModel` / `auto_vision_model`（默认 `true`）
- `allowLocalFileImages` / `allow_local_file_images`（默认 `false`）

说明：

- 当前两段式逻辑仅对 `glm*` 与 `minimax*` 生效
- 已移除自动上下文压缩逻辑（不再按固定阈值压缩）

## 8. 接口示例

### 8.1 OpenAI 文本请求

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"glm-4.7\",\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}]}"
```

### 8.2 OpenAI 图片请求

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{
    \"model\":\"glm-4.7\",
    \"messages\":[
      {
        \"role\":\"user\",
        \"content\":[
          {\"type\":\"text\",\"text\":\"图里写了什么？\"},
          {\"type\":\"image_url\",\"image_url\":{\"url\":\"https://example.com/a.png\"}}
        ]
      }
    ]
  }"
```

### 8.3 Anthropic 请求

```bash
curl http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d "{
    \"model\":\"glm-4.7\",
    \"max_tokens\":1024,
    \"messages\":[{\"role\":\"user\",\"content\":\"hello\"}]
  }"
```

### 8.4 模型列表

```bash
curl http://127.0.0.1:8000/v1/models
```

## 9. 本地构建 EXE

```bash
python build_gui.py
python build_agent.py
```

输出：

- `dist/iflow2api-gui.exe`
- `dist/iflow2api-agent.exe`

## 10. GitHub Actions 自动构建与 Release

工作流文件：`.github/workflows/build-exe.yml`

- `push main`：自动构建并上传 artifact
- `push tag v*`：自动创建/更新 Release 并上传产物

Release 上传文件：

- `dist/iflow2api-gui.exe`
- `dist/iflow2api-agent.exe`
- `stop_iflow2api.bat`

发布示例：

```bash
git tag v1.11.2
git push origin v1.11.2
```

## 11. 常见问题

### 11.1 构建成功但 Release 没有文件

- 确认触发的是 `v*` tag 推送，不是普通分支推送
- 确认工作流中 `Create GitHub Release` 步骤执行成功
- 确认上传路径与实际构建产物路径一致

### 11.2 图片请求没有识别

- 确认请求体中图片块格式正确（`image_url` 或兼容格式）
- 确认模型是否属于 `glm*`/`minimax*`（两段式目前仅对这两类启用）
- 查看日志中是否出现两段式链路日志：`原模型 -> qwen3-vl-plus -> 原模型`

### 11.3 本地文件图片无法读取

- 启用 `allowLocalFileImages`
- 路径需可访问且文件大小不超过限制
