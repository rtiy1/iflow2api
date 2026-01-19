# iFlow2API

将 iFlow API 转换为 OpenAI/Anthropic 兼容格式的代理服务。

## 功能

- 兼容 OpenAI `/v1/chat/completions` 接口
- 兼容 Anthropic `/v1/messages` 接口
- 支持流式输出
- 内置管理面板 (`/admin`)
- OAuth 2.0 认证支持
- 自动 Token 刷新机制
- 思考模式支持（GLM-4.x, DeepSeek R1, Qwen thinking）

## 配置

### 方式一：OAuth 认证（推荐）

运行 OAuth 认证工具：

```bash
python iflow_auth_cli.py
```

按提示在浏览器中完成授权，凭证将自动保存到 `~/.iflow/oauth_creds.json`。

OAuth 认证支持：
- 自动 Token 刷新（45 小时阈值）
- 更安全的授权流程
- 无需手动管理 API Key

### 方式二：传统 API Key

在 `~/.iflow/settings.json` 中配置：

```json
{
  "apiKey": "your-api-key",
  "baseUrl": "https://apis.iflow.cn/v1"
}
```

## 使用

### 方式一：直接运行 exe

下载 [Release](https://github.com/rtiy1/ifow2api/releases) 中的 `iFlow2API.exe`，双击运行。

### 方式二：源码运行

```bash
pip install -r requirements.txt
python main.py
```

服务启动后访问：
- API: `http://localhost:8000`
- 管理面板: `http://localhost:8000/admin`

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /v1/models` | 获取模型列表 |
| `POST /v1/chat/completions` | OpenAI 格式对话 |
| `POST /v1/messages` | Anthropic 格式对话 |
| `GET /admin` | 管理面板 |

## 高级特性

### 思考模式

支持的思考模型：
- `glm-4.x` 系列：通过 `reasoning_effort` 参数控制
- `deepseek-r1`：原生思考模型
- `qwen3-235b-a22b-thinking`：Qwen 思考模型

使用示例：

```python
{
  "model": "glm-4.7",
  "messages": [...],
  "reasoning_effort": "high"  # 启用思考模式
}
```

### Token 自动刷新

使用 OAuth 认证时，系统会在 Token 过期前 45 小时自动刷新，无需手动干预。

## 故障排除

**OAuth 认证失败**
- 确保端口 8087 未被占用
- 检查网络连接是否正常
- 查看 `~/.iflow/oauth_creds.json` 是否存在

**API 调用失败**
- 检查配置文件是否正确
- 确认 API Key 或 OAuth Token 有效
- 查看服务日志获取详细错误信息
