# iFlow2API

将 iFlow API 转换为 OpenAI/Anthropic 兼容格式的代理服务。

## 功能特性

### 核心功能
- 兼容 OpenAI `/v1/chat/completions` 接口
- 兼容 Anthropic `/v1/messages` 接口
- 支持流式和非流式输出
- 内置管理面板 (`/admin`)
- OAuth 2.0 认证支持
- 自动 Token 刷新机制
- 思考模式支持（GLM-4.x, DeepSeek R1, Qwen thinking）

### 稳定性增强
- **智能重试机制**：上游 API 失败时自动重试 3 次，采用指数退避策略
- **错误类型区分**：区分上游错误（502）和本地错误（500），便于快速定位问题
- **上下文压缩**：自动压缩历史对话，优化 token 使用
- **消息验证**：请求前验证消息数组格式，避免无效请求
- **自动续写**：当输出因 `max_tokens` 截断时，自动继续生成直到完成
- **类型安全**：增强类型检查，防止运行时类型错误

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

### 自动续写

当模型输出因 `max_tokens` 限制被截断时（`finish_reason: "length"`），服务会自动继续生成，最多续写 5 次，确保完整输出。

### 上下文压缩

使用滑动窗口算法自动压缩历史对话：
- 保留最近 10 轮对话
- 自动移除过早的消息
- 优化 token 使用，降低成本

### 智能重试

上游 API 调用失败时：
- 自动重试 3 次
- 采用指数退避策略（1s, 2s, 3s）
- 详细记录每次重试日志

### 错误处理

- **502 Bad Gateway**：上游 iFlow API 返回错误
- **500 Internal Server Error**：本地服务处理错误
- **400 Bad Request**：请求参数验证失败

## 故障排除

### OAuth 认证失败
- 确保端口 8087 未被占用
- 检查网络连接是否正常
- 查看 `~/.iflow/oauth_creds.json` 是否存在

### API 调用失败
- 检查配置文件是否正确
- 确认 API Key 或 OAuth Token 有效
- 查看服务日志获取详细错误信息

### 上游 API 错误（502）
- 检查 iFlow API 服务状态
- 查看日志中的重试记录
- 确认网络连接稳定

### 输出被截断
- 服务会自动续写，无需手动干预
- 检查日志中的续写次数
- 如需调整，修改 `MAX_CONTINUATIONS` 参数

## 技术栈

- **FastAPI**：高性能异步 Web 框架
- **httpx**：异步 HTTP 客户端
- **Python 3.8+**：类型提示和异步支持

## 许可证

MIT License
