# iFlow2API

Python 版 iFlow 反向代理，提供 OpenAI/Anthropic 兼容接口，并带本地 GUI 控制台。

## 1. 主要能力
- OpenAI 兼容接口：`/v1/chat/completions`
- Anthropic 兼容接口：`/v1/messages`
- 模型列表转发：`/v1/models`
- 健康检查：`/health`、`/v1/health`
- GUI 一键启动服务、查看日志、打开管理页
- 图片输入自动识别并切换视觉模型（主模型不支持视觉时生效）

## 2. 运行要求
- Python 3.10 及以上
- Windows（GUI 基于 PyQt5）

## 3. 安装与启动
### 3.1 安装依赖
```bash
pip install -r requirements.txt
```

### 3.2 配置认证
推荐先走 OAuth：
```bash
python iflow_auth_cli.py
```

### 3.3 启动方式
命令行启动服务：
```bash
python main.py
```

启动 GUI：
```bash
python gui_pyqt.py
```

默认端口：`8000`  
管理页：`http://127.0.0.1:8000/admin`

## 4. GUI 使用说明
- `启动服务`：启动/停止本地代理
- `管理面板`：打开 Web 管理页（模型、日志、系统信息）
- `OAuth认证`：执行 OAuth 认证流程
- `API示例`：查看请求示例
- `健康检查`：检查服务是否可用

窗口行为：
- 点击最小化：普通最小化到任务栏
- 点击关闭：隐藏到系统托盘，不退出进程
- 托盘菜单 `退出`：真正退出程序

## 5. 配置文件
程序会自动读取以下文件：
- `~/.iflow/oauth_creds.json`（OAuth）
- `~/.iflow/settings.json`（API Key）

常用字段：
- `apiKey`：上游访问密钥
- `baseUrl`：上游地址，默认 `https://apis.iflow.cn/v1`
- `visionModel`：视觉模型，默认 `qwen3-vl-plus`
- `autoVisionModel`：是否允许图片输入时自动切视觉模型，默认 `true`
- `allowLocalFileImages`：是否允许读取本地图片路径并转 base64，默认 `false`

## 6. 接口调用示例
### 6.1 OpenAI 文本请求
```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"glm-4.7\",\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}]}"
```

### 6.2 OpenAI 图片请求
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

### 6.3 Anthropic 请求
```bash
curl http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d "{
    \"model\":\"glm-4.7\",
    \"max_tokens\":1024,
    \"messages\":[{\"role\":\"user\",\"content\":\"hello\"}]
  }"
```

## 7. 模型列表说明
`/v1/models` 默认来自上游 `/models`。  
此外，服务会额外补充以下可用模型（即使上游列表未返回）：
- `glm-4.7`
- `minimax-m2.1`
- `kimi-k2.5`


## 8. 常见问题
### 8.1 上传图片但模型不识图
- 确认请求里 `messages[].content` 包含图片块
- 主模型不支持视觉时，服务会自动切换到视觉模型
- 若使用本地路径图片，需要启用 `allowLocalFileImages`

### 8.2 出现 429
- 这是上游限流，通常等待后重试
- 可降低并发或在客户端做退避重试

### 8.3 关闭窗口后程序还在
- 这是预期行为，程序被隐藏到托盘
- 需要彻底退出请在托盘菜单点 `退出`

## 9. 构建 EXE
```bash
python build_gui.py
python build_agent.py
```
输出文件：
- `dist/iflow2api-gui.exe`
- `dist/iflow2api-agent.exe`

## 10. Agent 使用（无 GUI 后台模式）
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

安装开机自启（Windows 登录后启动）：
```bash
python iflow_agent.py install-autostart --port 8000
```

移除开机自启：
```bash
python iflow_agent.py uninstall-autostart
```

给终端用户的一键停止脚本：
- `stop_iflow2api.bat`

## 11. GitHub Actions 自动发布
仓库已配置 Windows 构建工作流：
- `push main`：自动构建并上传 artifact
- `push tag v*`：自动创建 Release 并上传：
- `dist/iflow2api-gui.exe`
- `dist/iflow2api-agent.exe`
- `stop_iflow2api.bat`

发布命令示例：
```bash
git tag v1.11.1
git push origin v1.11.1
```
