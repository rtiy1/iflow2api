import requests
import json

# 测试 models 端点
print("测试 /v1/models 端点...")
response = requests.get("http://localhost:8001/v1/models")
print(f"状态码: {response.status_code}")
print(f"模型数量: {len(response.json()['data'])}")
print()

# 测试 chat completions 端点
print("测试 /v1/chat/completions 端点...")
payload = {
    "model": "glm-4.7",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 50,
    "stream": False
}

response = requests.post(
    "http://localhost:8001/v1/chat/completions",
    json=payload,
    headers={"Content-Type": "application/json"}
)

print(f"状态码: {response.status_code}")
print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
