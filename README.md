# iFlow2API

将 iFlow API 转换为 OpenAI/Anthropic 兼容格式的代理服务。

## 功能

- 兼容 OpenAI `/v1/chat/completions` 接口
- 兼容 Anthropic `/v1/messages` 接口
- 支持流式输出
- 内置管理面板 (`/admin`)
- 自动启用思考模式

## 配置

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
