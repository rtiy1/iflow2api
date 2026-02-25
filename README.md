<h1 align="center">🚀 iFlow2API</h1>

<p align="center">
  <strong>Advanced Python Reverse Proxy for iFlow.</strong><br>
  <em>OpenAI & Anthropic Compatible APIs • Stunning GUI Console • Headless Agent</em>
</p>

<p align="center">
  <strong>English</strong> | <a href="https://github.com/rtiy1/iflow2api/blob/main/README_zh.md">简体中文</a>
</p>

<p align="center">
  <a href="https://github.com/rtiy1/iflow2api"><img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python Version"/></a>
  <a href="https://github.com/rtiy1/iflow2api"><img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform"/></a>
  <a href="https://github.com/rtiy1/iflow2api/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License"/></a>
  <img src="https://img.shields.io/badge/Build-Success-success?style=for-the-badge&logo=github-actions&logoColor=white" alt="Build Status"/>
</p>

---

## 🌟 Overview

**iFlow2API** is a robust Python reverse proxy designed to bridge the gap between iFlow and standard AI software. It transforms non-standard interfaces into fully compliant **OpenAI** and **Anthropic** endpoints, featuring a modern PyQt5 dashboard for effortless management.

### ✨ Key Features

| Category | Highlights |
| :--- | :--- |
| **🔌 Universal API** | Full compatibility with `/v1/chat/completions` and `/v1/messages`. |
| **👁️ Smart Vision** | Intelligent two-stage vision routing for `glm*` and `minimax*` series. |
| **🖥️ GUI Control** | Real-time monitoring, log viewer, and model lists in a sleek console. |
| **🤖 Background Agent** | Headless mode with auto-start and system tray integration. |
| **📦 Smart Discovery** | Automatic model list augmentation and health tracking. |

---

## 🏗️ Architecture

```mermaid
graph TD
    User([User App]) --> API[API Gateway - FastAPI]
    API --> Controller{Logic Controller}
    
    subgraph Core Engine
        Controller --> Proxy[Reverse Proxy]
        Proxy --> Vision[Two-Stage Vision Phase]
        Vision --> Upstream[iFlow Upstream]
        Upstream --> Proxy
    end
    
    subgraph Management Layer
        Auth[OAuth & Token Mgmt]
        Pool[Account Pool Manager]
        Config[Dynamic Config]
    end
    
    API --- Management Layer
    
    subgraph Frontend
        GUI[PyQt5 Dashboard]
        Agent[Headless Daemon]
    end
    
    Frontend <--> API
```

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone and enter the project
git clone https://github.com/rtiy1/iflow2api.git
cd iflow2api

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (OAuth)

Initialize your credentials conveniently through the CLI:
```bash
python iflow_auth_cli.py
```

### 3. Execution

| Mode | Command | Best For |
| :--- | :--- | :--- |
| **GUI** | `python gui_pyqt.py` | Desktop desktop users, visual monitoring. |
| **Server** | `python main.py` | Production-like server environments. |
| **Agent** | `python iflow_agent.py start` | Persistent background services. |

---

## ⚙️ Configuration

Settings reside in `~/.iflow/settings.json` or `oauth_creds.json`.

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `base_url` | - | Upstream endpoint address. |
| `api_key` | - | Authentication token or key. |
| `vision_model` | `qwen3-vl-plus` | Model used for image reasoning stage. |
| `auto_vision_model` | `true` | Toggle automatic two-stage vision logic. |
| `allow_local_images`| `false` | Enable/Disable local file path parsing. |

---

## 🧪 API Showcase

### OpenAI Format (Chat)
```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-4.7",
    "messages": [{"role": "user", "content": "Explain quantum computing."}]
  }'
```

### Anthropic Format (Messages)
```bash
curl http://127.0.0.1:8000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-4.7",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## 🛠️ Build & Release

We use **GitHub Actions** for automated builds. For local builds:

```bash
python build_gui.py     # Builds the PyQt5 Console
python build_agent.py   # Builds the Headless Agent
```
*Artifacts will be available in the `dist/` directory.*

---

## 📄 License & Credits

- Licensed under the **MIT License**.
- Primary Developer: [rtiy1](https://github.com/rtiy1)
- Built with **FastAPI**, **PyQt5**, and 🧡.

<p align="center">
  <a href="https://github.com/rtiy1/iflow2api/stargazers"><img src="https://img.shields.io/github/stars/rtiy1/iflow2api?style=social" alt="Stars"/></a>
  <a href="https://github.com/rtiy1/iflow2api/network/members"><img src="https://img.shields.io/github/forks/rtiy1/iflow2api?style=social" alt="Forks"/></a>
</p>
