from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8000/v1",
    api_key="sk-65ccd5e4cb8ae1e7923178e1804e582e",
    model="glm-4.7"
)

response = llm.invoke("你好")
print(response.content)
