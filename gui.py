import flet as ft
import threading
import asyncio
import uvicorn
from datetime import datetime
from main import app, request_logs, stats, CONFIG

class Server:
    def __init__(self):
        self.server = None
        self.thread = None
        self.running = False

    def start(self, port):
        if self.running:
            return False
        self.running = True
        self.thread = threading.Thread(target=self._run, args=(port,), daemon=True)
        self.thread.start()
        return True

    def _run(self, port):
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
        self.server = uvicorn.Server(config)
        asyncio.run(self.server.serve())

    def stop(self):
        if self.server:
            self.server.should_exit = True
        self.running = False

server = Server()

def card(content, **kwargs):
    return ft.Container(
        content=content,
        bgcolor="#1e1e2e",
        border_radius=12,
        padding=16,
        **kwargs
    )

def main(page: ft.Page):
    page.title = "iFlow2API"
    page.window.width = 520
    page.window.height = 780
    page.bgcolor = "#11111b"
    page.padding = 24

    status_icon = ft.Icon(ft.Icons.CIRCLE, color="#6c7086", size=14)
    status_text = ft.Text("服务未运行", color="#6c7086", size=14)
    port_field = ft.TextField(
        value="8000", width=80, height=40, text_size=14,
        border_color="#45475a", focused_border_color="#89b4fa",
        bgcolor="#181825", color="#cdd6f4"
    )
    log_list = ft.ListView(expand=True, spacing=4, auto_scroll=True)

    def add_log(msg, color="#a6adc8"):
        log_list.controls.append(ft.Text(
            f"[{datetime.now().strftime('%H:%M:%S')}] {msg}",
            size=12, color=color
        ))
        if len(log_list.controls) > 100:
            log_list.controls.pop(0)
        page.update()

    def start_server(e):
        port = int(port_field.value or 8000)
        if server.start(port):
            status_text.value = f"运行中 · localhost:{port}"
            status_text.color = "#a6e3a1"
            status_icon.color = "#a6e3a1"
            start_btn.disabled = True
            stop_btn.disabled = False
            add_log(f"服务已启动，端口 {port}", "#a6e3a1")
            page.update()

    def stop_server(e):
        server.stop()
        status_text.value = "已停止"
        status_text.color = "#f38ba8"
        status_icon.color = "#f38ba8"
        start_btn.disabled = False
        stop_btn.disabled = True
        add_log("服务已停止", "#f38ba8")
        page.update()

    def refresh_logs(e=None):
        log_list.controls.clear()
        for log in list(request_logs)[:50]:
            color = "#a6e3a1" if log['status'] < 400 else "#f38ba8"
            log_list.controls.append(ft.Text(
                f"{log['time']}  {log['method']:4} {log['path']} → {log['status']}",
                size=11, color=color, font_family="Consolas"
            ))
        page.update()

    start_btn = ft.ElevatedButton(
        "启动", on_click=start_server,
        bgcolor="#a6e3a1", color="#1e1e2e",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )
    stop_btn = ft.ElevatedButton(
        "停止", on_click=stop_server, disabled=True,
        bgcolor="#f38ba8", color="#1e1e2e",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
    )

    page.add(
        ft.Row([
            ft.Icon(ft.Icons.API, color="#89b4fa", size=28),
            ft.Text("iFlow2API", size=22, weight=ft.FontWeight.BOLD, color="#cdd6f4"),
        ], spacing=10),
        ft.Container(height=16),
        card(ft.Column([
            ft.Row([status_icon, status_text], spacing=8),
            ft.Container(height=8),
            ft.Row([
                ft.Text("端口", color="#a6adc8", size=13),
                port_field, start_btn, stop_btn
            ], spacing=12),
        ])),
        ft.Container(height=12),
        card(ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.SETTINGS, color="#89b4fa", size=16),
                ft.Text("配置", color="#cdd6f4", weight=ft.FontWeight.W_500),
            ], spacing=8),
            ft.Container(height=8),
            ft.Text(f"Key: {CONFIG['api_key'][:20]}...", size=12, color="#6c7086"),
            ft.Text(f"URL: {CONFIG['base_url']}", size=12, color="#6c7086"),
        ])),
        ft.Container(height=12),
        card(ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.SMART_TOY, color="#89b4fa", size=16),
                ft.Text("模型列表", color="#cdd6f4", weight=ft.FontWeight.W_500),
            ], spacing=8),
            ft.Container(height=8),
            ft.Row(
                [ft.Container(
                    content=ft.Text(m, size=11, color="#cdd6f4"),
                    bgcolor="#313244", border_radius=6, padding=ft.padding.symmetric(6, 10)
                ) for m in ["glm-4.7", "deepseek-v3", "deepseek-r1", "qwen3-max", "kimi-k2", "minimax-m2.1"]],
                wrap=True, spacing=6, run_spacing=6
            ),
        ])),
        ft.Container(height=12),
        card(ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.LIST_ALT, color="#89b4fa", size=16),
                ft.Text("请求日志", color="#cdd6f4", weight=ft.FontWeight.W_500),
                ft.Container(expand=True),
                ft.IconButton(ft.Icons.REFRESH, icon_color="#6c7086", icon_size=18, on_click=refresh_logs),
            ], spacing=8),
            ft.Container(
                content=log_list, height=280,
                bgcolor="#181825", border_radius=8, padding=10
            ),
        ]), expand=True),
    )

if __name__ == "__main__":
    ft.app(target=main)
