from typing import Optional, Dict, List, Callable, Awaitable, Any
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QGridLayout,
    QProgressBar, QSizePolicy, QScrollArea, QTextEdit,
    QGraphicsDropShadowEffect, QDialog, QCheckBox, QMessageBox,
    QSystemTrayIcon, QMenu, QAction, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, pyqtSignal, pyqtSlot, QThread, QPoint, QSettings, QLockFile
)
from PyQt5.QtGui import QFont, QColor, QPainter, QIntValidator, QCursor, QIcon
import sys
import threading
import asyncio
import json
import hashlib
import uvicorn
import webbrowser
import platform
import psutil
import os
import time
from pathlib import Path
from datetime import datetime
from collections import deque
import html
from app.server import app, request_logs, stats, CONFIG
from proxy.proxy import get_proxy

start_time = time.time()

# ==============================
# 常量定义（统一管理，便于维护）
# ==============================
APP_TITLE = "iFlow2API Console"
WINDOW_SIZE = (540, 470)  # 大号窗口，提升可读性
REFRESH_INTERVAL = 500  # 定时器刷新间隔(ms)
PORT_MIN = 1024
PORT_MAX = 65535
DEFAULT_PORT = 8000
LOGO_TEXT = "IFLOW\nTO API"
APP_ID = "iFlow2API"
SETTINGS_AUTOSTART = "autostart_enabled"
STARTUP_BAT_NAME = "iFlow2API_Autostart.bat"
GUI_LOCK_FILE = Path.home() / ".iflow2api" / "iflow2api-gui.lock"


def resource_path(*parts: str) -> str:
    """Resolve resource paths for dev and PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).resolve().parent.parent
    return str(base_dir.joinpath(*parts))


ICON_PATH = resource_path("icon.ico")

# ==============================
# 样式表（结构化管理）
# ==============================
class Styles:
    """样式表管理类"""
    BASE = """
    QMainWindow {
        background-color: #050505;
    }

    QWidget {
        font-family: 'Consolas', 'Microsoft YaHei', monospace;
        color: #ff9966;
    }

    /* Frame Borders */
    QFrame.MainContainer {
        border: 1px solid #ff5500;
        border-radius: 8px;
        background-color: #0a0a0a;
    }

    /* Pixel Logo Text */
    QLabel.PixelLogo {
        font-family: 'Impact', 'Arial Black', sans-serif;
        font-size: 56px;
        color: #ff7733;
        font-weight: bold;
    }

    QLabel.PixelLogoSmall {
        font-family: 'Impact', 'Arial Black', sans-serif;
        font-size: 42px;
        color: #ff7733;
        font-weight: bold;
    }

    /* Stats Labels */
    QLabel.StatLabel {
        color: #888888;
        font-size: 12px;
        font-weight: normal;
    }

    QLabel.StatValue {
        color: #ff9966;
        font-size: 13px;
        font-weight: bold;
    }

    /* Progress Bar */
    QProgressBar {
        border: 1px solid #333;
        background-color: #1a1a1a;
        border-radius: 2px;
        text-align: center;
        color: transparent;
    }

    QProgressBar::chunk {
        background-color: #ff7733;
        border-radius: 1px;
    }

    /* Buttons */
    QPushButton {
        background-color: #120802;
        color: #e08050;
        border: 1px solid #2d1808;
        border-radius: 3px;
        padding: 2px 8px;
        font-family: 'Microsoft YaHei', sans-serif;
        font-weight: bold;
        font-size: 12px;
    }

    QPushButton:hover {
        background-color: #1a0d05;
        border-color: #ff7733;
        color: #ff9966;
    }

    QPushButton:pressed {
        background-color: #0f0500;
        border-color: #aa3300;
    }

    QPushButton.ActionBtn {
        height: 24px;
    }

    QPushButton:disabled {
        background: #1a1a1a;
        border-color: #555555;
        color: #888888;
    }

    /* Checkbox */
    QCheckBox {
        color: #bbbbbb;
        font-size: 12px;
    }
    QCheckBox::indicator {
        width: 10px;
        height: 10px;
    }
    QCheckBox::indicator:unchecked {
        border: 1px solid #444444;
        background: #1a1a1a;
    }
    QCheckBox::indicator:checked {
        border: 1px solid #ff7733;
        background: #ff7733;
    }

    /* Input */
    QLineEdit {
        background: #1a0d05;
        color: #ff9966;
        border: 1px solid #ff5500;
        border-radius: 3px;
        padding: 1px 3px;
        font-size: 12px;
    }

    QLineEdit:disabled {
        background: #222222;
        border-color: #663300;
        color: #999999;
    }

    /* Dialog */
    QDialog {
        background-color: #050505;
        color: #ff9966;
        border: 1px solid #ff5500;
        border-radius: 10px;
    }

    QTextEdit#DialogText {
        background-color: #0a0a0a;
        color: #ff9966;
        border: 1px solid #ff5500;
        border-radius: 6px;
        padding: 12px;
        font-family: 'Consolas', 'Microsoft YaHei', monospace;
        font-size: 14px;
        selection-background-color: #ff7733;
        selection-color: #111111;
    }

    QTableWidget {
        background-color: #0a0a0a;
        alternate-background-color: #120a06;
        color: #ff9966;
        border: 1px solid #ff5500;
        border-radius: 6px;
        gridline-color: #2d1808;
        selection-background-color: #2a1408;
        selection-color: #ffbb88;
        font-size: 12px;
    }

    QHeaderView::section {
        background-color: #130903;
        color: #ffbb88;
        border: 1px solid #2d1808;
        padding: 4px 6px;
        font-weight: bold;
    }

    QTableCornerButton::section {
        background-color: #130903;
        border: 1px solid #2d1808;
    }

    /* Log Area */
    QFrame.LogArea {
        background-color: #000000;
        border-top: 1px solid #331100;
    }

    QTextEdit.LogText {
        background-color: #000000;
        color: #ff9966;
        font-size: 12px;
        border: none;
        padding: 2px;
        font-family: 'Consolas', monospace;
    }
    """

    @classmethod
    def get_style(cls) -> str:
        """获取完整样式表"""
        return cls.BASE

# ==============================
# 像素LOGO生成（可选保留）
# ==============================
PIXEL_MAP = {
    'I': ["111", "010", "010", "010", "111"],
    'F': ["1111", "1000", "1110", "1000", "1000"],
    'L': ["1000", "1000", "1000", "1000", "1111"],
    'O': ["0110", "1001", "1001", "1001", "0110"],
    'W': ["10001", "10001", "10101", "11011", "10001"],
    'T': ["11111", "00100", "00100", "00100", "00100"],
    'A': ["0110", "1001", "1111", "1001", "1001"],
    'P': ["1110", "1001", "1110", "1000", "1000"],
    ' ': ["00", "00", "00", "00", "00"]
}

def generate_pixel_html(text: str, pixel_size: int = 6, color: str = "#ff7733") -> str:
    """生成像素风格的HTML文本（备用）"""
    html = f'<table cellspacing="1" cellpadding="0" style="border-collapse: collapse; line-height: 0;">'
    rows_html = [""] * 5

    for char in text:
        bitmap = PIXEL_MAP.get(char.upper(), PIXEL_MAP[' '])
        width = len(bitmap[0])

        for r in range(5):
            row_bits = bitmap[r]
            for bit in row_bits:
                bg = color if bit == '1' else "transparent"
                rows_html[r] += f'<td style="background-color: {bg}; width: {pixel_size}px; height: {pixel_size}px;"></td>'
            rows_html[r] += f'<td style="width: {pixel_size}px; height: {pixel_size}px;"></td>'

    for row_content in rows_html:
        html += f'<tr>{row_content}</tr>'
    html += '</table>'
    return html

# ==============================
# 自定义LOGO控件（优化资源）
# ==============================
class DoubleStrokeLabel(QWidget):
    """双描边LOGO标签"""
    def __init__(self, text: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.text = text
        self.setFixedSize(230, 96) # 放大 LOGO 区域
        
        # 缓存字体和颜色，避免重复创建
        self.font = QFont("Courier New", 32, QFont.Bold) # 放大 LOGO 字号
        self.stroke_color = QColor(0x70, 0x30, 0x20)  # 深棕色描边
        self.fill_color = QColor(0xE0, 0x80, 0x50)    # 浅橙色填充

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(self.font)
        
        # 绘制底层描边（偏移 +2,+2）
        painter.setPen(self.stroke_color)
        painter.drawText(2, 2, self.width(), self.height(), 
                         Qt.AlignLeft | Qt.AlignVCenter, self.text)
        
        # 绘制上层主文字（无偏移）
        painter.setPen(self.fill_color)
        painter.drawText(0, 0, self.width(), self.height(), 
                         Qt.AlignLeft | Qt.AlignVCenter, self.text)

# ==============================
# 服务器管理（线程安全优化）
# ==============================
class ServerWorker(QThread):
    """服务器运行线程（基于QThread，支持信号槽）"""
    server_error = pyqtSignal(str)
    server_started = pyqtSignal()
    server_stopped = pyqtSignal()

    def __init__(self, port: int):
        super().__init__()
        self.port = port
        self.server: Optional[uvicorn.Server] = None
        self._is_running = False

    def run(self):
        """线程运行入口"""
        # 先检查端口是否可用
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', self.port))
        except OSError:
            self.server_error.emit(f"端口 {self.port} 已被占用，请更换端口或关闭占用该端口的程序")
            return

        self._is_running = True
        try:
            config = uvicorn.Config(app, host="0.0.0.0", port=self.port, log_config=None)
            self.server = uvicorn.Server(config)

            # 标记服务器已启动
            self.server_started.emit()

            # 运行服务器（会阻塞直到服务器停止）
            asyncio.run(self.server.serve())
        except Exception as e:
            self.server_error.emit(f"启动失败: {str(e)}")
        finally:
            self._is_running = False
            self.server_stopped.emit()

    def stop(self):
        """停止服务器"""
        if self.server and self._is_running:
            self.server.should_exit = True
            self._is_running = False

class ServerManager:
    """服务器管理类（封装逻辑）"""
    def __init__(self):
        self.worker: Optional[ServerWorker] = None
        self.is_running = False

    def start(self, port: int, on_started=None, on_error=None):
        """启动服务器"""
        if self.is_running:
            return False

        self.worker = ServerWorker(port)
        self.worker.server_started.connect(self._on_started)
        self.worker.server_error.connect(self._on_error)
        self.worker.server_stopped.connect(self._on_stopped)
        if on_started:
            self.worker.server_started.connect(on_started)
        if on_error:
            self.worker.server_error.connect(on_error)
        self.worker.start()
        return True

    def stop(self):
        """停止服务器"""
        if self.worker and self.is_running:
            self.worker.stop()

    def _on_started(self):
        """服务器启动成功回调"""
        self.is_running = True

    def _on_error(self, error_msg: str):
        """服务器错误回调"""
        self.is_running = False
        print(error_msg)

    def _on_stopped(self):
        """服务器停止回调"""
        self.is_running = False


class AccountPoolDialog(QDialog):
    """账号池健康检查对话框"""

    pool_loaded = pyqtSignal(object)
    pool_failed = pyqtSignal(str)

    def __init__(self, parent: QWidget, fetch_payload):
        super().__init__(parent)
        self.fetch_payload = fetch_payload
        self._loading = False
        self.pool_loaded.connect(self._on_pool_loaded)
        self.pool_failed.connect(self._on_pool_failed)
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("账号池健康检查")
        self.resize(980, 560)
        self.setStyleSheet(Styles.get_style())

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self.summary_label = QLabel("点击刷新查看账号池状态")
        self.summary_label.setStyleSheet("color: #bbbbbb; font-size: 12px;")
        self.summary_label.setWordWrap(True)

        self.btn_refresh = QPushButton("刷新状态")
        self.btn_refresh.setProperty("class", "ActionBtn")
        self.btn_refresh.clicked.connect(self.refresh_pool)

        toolbar.addWidget(self.summary_label, 1)
        toolbar.addWidget(self.btn_refresh, 0)
        root_layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "账号 ID",
            "健康状态",
            "启用",
            "优先级",
            "已选次数",
            "失败次数",
            "冷却(s)",
            "凭证文件",
            "错误信息",
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)
        root_layout.addWidget(self.table, 1)

    def refresh_pool(self):
        if self._loading:
            return
        self._set_loading(True)
        threading.Thread(target=self._load_worker, daemon=True).start()

    def _set_loading(self, loading: bool):
        self._loading = loading
        self.btn_refresh.setEnabled(not loading)
        self.btn_refresh.setText("刷新中..." if loading else "刷新状态")
        if loading:
            self.summary_label.setText("正在获取账号池状态，请稍候...")

    def _load_worker(self):
        try:
            payload = self.fetch_payload()
            self.pool_loaded.emit(payload)
        except Exception as e:
            self.pool_failed.emit(str(e))

    def _safe_int(self, value: object, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _resolve_health_status(self, row: Dict[str, object]):
        enabled = bool(row.get("enabled"))
        available = bool(row.get("available"))
        cooldown = self._safe_int(row.get("cooldown_seconds"), 0)
        if enabled and available:
            return "可用", QColor("#34d399")
        if enabled and cooldown > 0:
            return f"冷却 {cooldown}s", QColor("#f59e0b")
        if enabled:
            return "不可用", QColor("#ff6b6b")
        return "禁用", QColor("#888888")

    @pyqtSlot(object)
    def _on_pool_loaded(self, payload: object):
        self._set_loading(False)
        if not isinstance(payload, dict):
            self.summary_label.setText("账号池状态格式错误：返回值不是 JSON 对象")
            return

        mode = str(payload.get("mode") or "-")
        strategy = str(payload.get("routing_strategy") or "-")
        total = self._safe_int(payload.get("total_accounts"), 0)
        available = self._safe_int(payload.get("available_accounts"), 0)
        creds_dir = str(payload.get("creds_dir") or "-")
        ts = datetime.now().strftime("%H:%M:%S")
        self.summary_label.setText(
            f"模式：{mode}    策略：{strategy}    可用：{available}/{total}    凭证目录：{creds_dir}    更新时间：{ts}"
        )

        rows = payload.get("accounts")
        if not isinstance(rows, list):
            rows = []

        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                row = {}
            status_text, status_color = self._resolve_health_status(row)
            values = [
                str(row.get("account_id") or "unknown"),
                status_text,
                "是" if bool(row.get("enabled")) else "否",
                str(self._safe_int(row.get("priority"), 0)),
                str(self._safe_int(row.get("selected_count"), 0)),
                str(self._safe_int(row.get("failure_count"), 0)),
                str(self._safe_int(row.get("cooldown_seconds"), 0)),
                str(row.get("file") or "-"),
                str(row.get("last_error") or ""),
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 1:
                    item.setForeground(status_color)
                if col == 8 and value:
                    item.setToolTip(value)
                self.table.setItem(row_index, col, item)

    @pyqtSlot(str)
    def _on_pool_failed(self, error_message: str):
        self._set_loading(False)
        self.summary_label.setText(f"账号池状态获取失败：{error_message}")


# ==============================
# 主窗口（核心优化）
# ==============================
class MainWindow(QMainWindow):
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.server_manager = ServerManager()
        self.log_entries = deque(maxlen=200)
        self.seen_request_keys = set()
        self.current_port = DEFAULT_PORT
        self.settings = QSettings(APP_ID, "Console")
        self.tray_icon = None
        self.account_pool_dialog: Optional[AccountPoolDialog] = None
        self._proxy_loop_ready = threading.Event()
        self._proxy_loop_thread: Optional[threading.Thread] = None
        self._proxy_loop: Optional[asyncio.AbstractEventLoop] = None
        self._allow_close = False
        self.log_signal.connect(self.update_log)
        self.init_ui()
        self.update_log("系统就绪 / Waiting for commands...", level="info")
        self.init_tray()
        self.load_settings()
        self.init_timer()
        self.connect_server_signals()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(APP_TITLE)
        self.app_icon = QIcon(ICON_PATH)
        self.setWindowIcon(self.app_icon)
        self.setFixedSize(*WINDOW_SIZE)
        self.setStyleSheet(Styles.get_style())
        # 设置无边框
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 中心部件
        central = QWidget()
        central.setObjectName("CentralWidget")
        central.setStyleSheet("#CentralWidget { background-color: #050505; border: 1px solid #ff5500; border-radius: 10px; }")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 0, 10, 10) 
        layout.setSpacing(0)

        # 自定义标题栏 (参照第二张图)
        title_bar_widget = QWidget()
        title_bar_layout = QHBoxLayout(title_bar_widget)
        title_bar_layout.setContentsMargins(8, 0, 8, 0) # 进一步压缩
        
        # 标题栏左侧：图标 + 文字
        title_info = QHBoxLayout()
        icon_label = QLabel("🔆") 
        icon_label.setStyleSheet("font-size: 13px; color: #ff7733;")
        title_text = QLabel("iFlow2API")
        title_text.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 13px; color: #bbbbbb; font-weight: bold;")
        title_info.addWidget(icon_label)
        title_info.addWidget(title_text)
        title_bar_layout.addLayout(title_info)
        
        title_bar_layout.addStretch()
        
        # 标题栏右侧：最小化 + 关闭
        btn_min = QPushButton("－")
        btn_min.setFixedSize(26, 26)
        btn_min.setStyleSheet("QPushButton { background: transparent; color: #888; font-size: 15px; border: none; } QPushButton:hover { color: #ffffff; background: #333333; }")
        btn_min.clicked.connect(self.on_minimize_clicked)
        
        btn_close = QPushButton("×")
        btn_close.setFixedSize(26, 26)
        btn_close.setStyleSheet("QPushButton { background: transparent; color: #888; font-size: 18px; border: none; border-top-right-radius: 10px; } QPushButton:hover { color: #ffffff; background: #ff5555; }")
        btn_close.clicked.connect(self.close)
        
        title_bar_layout.addWidget(btn_min)
        title_bar_layout.addWidget(btn_close)
        
        layout.addWidget(title_bar_widget)
        # 移除多余间距，额头更窄
        layout.addSpacing(0)

        # 顶部容器（LOGO + 统计）
        self._init_top_container(layout)
        layout.addSpacing(5)

        # 中间按钮区域
        self._init_button_container(layout)
        layout.addSpacing(5)

        # 移除中间的 Stretch，改用固定间距，让日志向上填满空间
        # layout.addStretch(1) 

        # 底部日志区域
        self._init_log_container(layout)
        layout.addStretch(1) # 把 Stretch 移到最下面，确保日志撑开后剩余空间在底部

    # 支持无边框窗口拖动
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()
            self.setCursor(QCursor(Qt.OpenHandCursor))

    def mouseMoveEvent(self, event):
        if Qt.LeftButton and self.m_drag:
            self.move(event.globalPos() - self.m_DragPosition)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.m_drag = False
        self.setCursor(QCursor(Qt.ArrowCursor))

    def on_minimize_clicked(self):
        self.showMinimized()

    def closeEvent(self, event):
        if self._allow_close:
            self.server_manager.stop()
            self.timer.stop()
            self._shutdown_proxy_loop()
            event.accept()
            return
        if self.tray_icon:
            self._hide_to_tray(show_notice=True)
            event.ignore()
            return
        self.server_manager.stop()
        self.timer.stop()
        self._shutdown_proxy_loop()
        event.accept()

    def _ensure_proxy_loop(self):
        if (
            self._proxy_loop is not None
            and not self._proxy_loop.is_closed()
            and self._proxy_loop_thread is not None
            and self._proxy_loop_thread.is_alive()
        ):
            return

        self._proxy_loop_ready.clear()
        loop = asyncio.new_event_loop()
        self._proxy_loop = loop

        def loop_worker():
            asyncio.set_event_loop(loop)
            self._proxy_loop_ready.set()
            loop.run_forever()

        self._proxy_loop_thread = threading.Thread(target=loop_worker, daemon=True)
        self._proxy_loop_thread.start()
        if not self._proxy_loop_ready.wait(timeout=2.0):
            raise RuntimeError("本地事件循环启动超时")

    def _shutdown_proxy_loop(self):
        loop = self._proxy_loop
        thread = self._proxy_loop_thread
        self._proxy_loop = None
        self._proxy_loop_thread = None
        self._proxy_loop_ready.clear()
        if loop is None:
            return

        try:
            if not loop.is_closed():
                loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass

        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)

        try:
            if not loop.is_closed():
                loop.close()
        except Exception:
            pass

    def _run_proxy_coroutine(self, coro_factory: Callable[[], Awaitable[Any]], timeout: float = 15.0):
        last_error: Optional[Exception] = None

        for _ in range(2):
            self._ensure_proxy_loop()
            loop = self._proxy_loop
            if loop is None or loop.is_closed():
                self._shutdown_proxy_loop()
                continue
            try:
                future = asyncio.run_coroutine_threadsafe(coro_factory(), loop)
                return future.result(timeout=timeout)
            except TimeoutError:
                future.cancel()
                raise TimeoutError("本地代理请求超时")
            except RuntimeError as e:
                # loop 可能在并发关闭过程中失效，重建后重试一次
                last_error = e
                self._shutdown_proxy_loop()
                continue

        if last_error is not None:
            raise RuntimeError(f"本地代理调用失败: {last_error}")
        raise RuntimeError("本地代理调用失败")

    def _hide_to_tray(self, show_notice: bool = True):
        if not self.tray_icon:
            return
        self.hide()
        if show_notice:
            self.tray_icon.showMessage(
                APP_TITLE,
                "已最小化到托盘，双击图标可恢复",
                QSystemTrayIcon.Information,
                1500,
            )

    def _init_top_container(self, parent_layout: QVBoxLayout):
        """初始化顶部容器"""
        top_frame = QFrame()
        top_frame.setProperty("class", "MainContainer")
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(20, 20, 20, 20)

        # 左侧LOGO
        logo_layout = QVBoxLayout()
        logo_layout.setSpacing(0)
        self.logo = DoubleStrokeLabel(LOGO_TEXT)
        logo_layout.addWidget(self.logo)
        logo_layout.addStretch()
        top_layout.addLayout(logo_layout, stretch=1)

        # 右侧统计网格
        stats_layout = QGridLayout()
        stats_layout.setHorizontalSpacing(8)
        stats_layout.setVerticalSpacing(6)

        # 状态
        lbl = QLabel("状态")
        lbl.setProperty("class", "StatLabel")
        stats_layout.addWidget(lbl, 0, 0, Qt.AlignRight)
        self.status_val = QLabel("已停止")
        self.status_val.setProperty("class", "StatValue")
        self.status_val.setStyleSheet("color: #ff5555;")
        stats_layout.addWidget(self.status_val, 0, 1)

        # 成功率
        lbl = QLabel("成功率")
        lbl.setProperty("class", "StatLabel")
        stats_layout.addWidget(lbl, 1, 0, Qt.AlignRight)
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setFixedSize(118, 9)
        self.rate_val = QLabel("0.0%")
        self.rate_val.setProperty("class", "StatValue")
        prog_container = QWidget()
        prog_layout = QHBoxLayout(prog_container)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        prog_layout.addWidget(self.prog_bar)
        prog_layout.addWidget(self.rate_val)
        stats_layout.addWidget(prog_container, 1, 1)

        # 总请求
        lbl = QLabel("总请求")
        lbl.setProperty("class", "StatLabel")
        stats_layout.addWidget(lbl, 2, 0, Qt.AlignRight)
        self.total_val = QLabel("0")
        self.total_val.setProperty("class", "StatValue")
        stats_layout.addWidget(self.total_val, 2, 1)

        # 端口（增加合法性校验）
        lbl = QLabel("端口")
        lbl.setProperty("class", "StatLabel")
        stats_layout.addWidget(lbl, 3, 0, Qt.AlignRight)
        self.port_input = QLineEdit(str(DEFAULT_PORT))
        self.port_input.setFixedWidth(80)
        self.port_input.setFixedHeight(28)
        # 仅允许输入数字，且范围在1024-65535
        self.port_input.setValidator(QIntValidator(PORT_MIN, PORT_MAX))
        stats_layout.addWidget(self.port_input, 3, 1)

        top_layout.addLayout(stats_layout)
        parent_layout.addWidget(top_frame)

    def _init_button_container(self, parent_layout: QVBoxLayout):
        """初始化按钮容器（两列布局）"""
        btn_layout = QGridLayout()
        btn_layout.setSpacing(8)
        btn_layout.setContentsMargins(5, 5, 5, 5)

        btn_container = QFrame()
        btn_container.setLayout(btn_layout)
        btn_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # 按钮定义
        self.btn_start = QPushButton("启动服务")
        self.btn_start.clicked.connect(self.toggle_server)
        self.btn_start.setProperty("class", "ActionBtn")

        self.btn_admin = QPushButton("管理面板")
        self.btn_admin.clicked.connect(self.open_admin_panel)
        self.btn_admin.setProperty("class", "ActionBtn")
        self.btn_admin.setEnabled(False)

        self.btn_clear = QPushButton("清空日志")
        self.btn_clear.clicked.connect(self.clear_logs)
        self.btn_clear.setProperty("class", "ActionBtn")

        self.btn_add_account = QPushButton("账号添加")
        self.btn_add_account.clicked.connect(self.add_account)
        self.btn_add_account.setProperty("class", "ActionBtn")

        self.btn_account_pool = QPushButton("账号池")
        self.btn_account_pool.clicked.connect(self.check_account_pool)
        self.btn_account_pool.setProperty("class", "ActionBtn")

        self.btn_sysinfo = QPushButton("模型列表")
        self.btn_sysinfo.clicked.connect(self.show_system_info)
        self.btn_sysinfo.setProperty("class", "ActionBtn")

        self.btn_api = QPushButton("API示例")
        self.btn_api.clicked.connect(self.show_api_examples)
        self.btn_api.setProperty("class", "ActionBtn")

        self.btn_github = QPushButton("GitHub")
        self.btn_github.clicked.connect(lambda: webbrowser.open("https://github.com/rtiy1/iflow2api"))
        self.btn_github.setProperty("class", "ActionBtn")

        # 两行布局：2行×4列
        btn_layout.addWidget(self.btn_start, 0, 0)
        btn_layout.addWidget(self.btn_admin, 0, 1)
        btn_layout.addWidget(self.btn_clear, 0, 2)
        btn_layout.addWidget(self.btn_add_account, 0, 3)
        btn_layout.addWidget(self.btn_account_pool, 1, 0)
        btn_layout.addWidget(self.btn_sysinfo, 1, 1)
        btn_layout.addWidget(self.btn_api, 1, 2)
        btn_layout.addWidget(self.btn_github, 1, 3)

        # 设置选项
        settings_row = QWidget()
        settings_layout = QHBoxLayout(settings_row)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(12)

        self.chk_autostart = QCheckBox("开机自启")
        self.chk_autostart.toggled.connect(self.on_autostart_toggled)

        settings_layout.addWidget(self.chk_autostart)
        settings_layout.addStretch()
        btn_layout.addWidget(settings_row, 2, 0, 1, 4)

        parent_layout.addWidget(btn_container)

    def _init_log_container(self, parent_layout: QVBoxLayout):
        """初始化日志容器（优化为滚动文本框）"""
        log_frame = QFrame()
        log_frame.setProperty("class", "LogArea")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(8, 2, 8, 2)

        # 日志标题
        log_title_layout = QHBoxLayout()
        self.log_icon = QLabel("⚡")
        self.log_icon.setStyleSheet("color: #ffbb00; font-size: 13px;")
        log_title = QLabel("系统日志")
        log_title.setStyleSheet("color: #888888; font-size: 13px;")
        log_title_layout.addWidget(self.log_icon)
        log_title_layout.addWidget(log_title)
        log_title_layout.addStretch()

        # 滚动日志区域
        self.log_text = QTextEdit()
        self.log_text.setProperty("class", "LogText")
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(130)
        self.log_text.setHtml("")

        log_layout.addLayout(log_title_layout)
        log_layout.addWidget(self.log_text)
        parent_layout.addWidget(log_frame)

    def init_timer(self):
        """初始化定时器"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(REFRESH_INTERVAL)

    def connect_server_signals(self):
        """连接服务器信号"""
        pass

    def init_tray(self):
        """初始化系统托盘"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self.app_icon if hasattr(self, "app_icon") else QIcon(ICON_PATH)
        self.tray_icon = QSystemTrayIcon(icon, self)
        menu = QMenu()
        action_toggle = QAction("显示/隐藏", self)
        action_toggle.triggered.connect(self.toggle_visibility)
        action_quit = QAction("退出", self)
        action_quit.triggered.connect(self.exit_app)
        menu.addAction(action_toggle)
        menu.addSeparator()
        menu.addAction(action_quit)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.setVisible(True)

    def load_settings(self):
        """加载本地设置"""
        autostart = self.settings.value(SETTINGS_AUTOSTART, False, type=bool)

        self.chk_autostart.blockSignals(True)
        self.chk_autostart.setChecked(autostart)
        self.chk_autostart.blockSignals(False)

        if autostart:
            ok, msg = self._set_autostart_enabled(True)
            if not ok:
                self.update_log(msg, level="warning")
                self.chk_autostart.setChecked(False)

    def on_autostart_toggled(self, checked: bool):
        ok, msg = self._set_autostart_enabled(checked)
        if not ok:
            self.update_log(msg, level="warning")
            self.chk_autostart.blockSignals(True)
            self.chk_autostart.setChecked(not checked)
            self.chk_autostart.blockSignals(False)
            return
        self.settings.setValue(SETTINGS_AUTOSTART, checked)
        self.update_log("开机自启已开启" if checked else "开机自启已关闭", level="info")

    def _get_startup_dir(self) -> str:
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            return ""
        return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")

    def _get_python_executable(self) -> str:
        exe_path = sys.executable
        if exe_path.lower().endswith("python.exe"):
            pythonw = os.path.join(os.path.dirname(exe_path), "pythonw.exe")
            if os.path.exists(pythonw):
                return pythonw
        return exe_path

    def _build_autostart_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'start "" "{sys.executable}"'
        exe_path = self._get_python_executable()
        script_path = os.path.abspath(__file__)
        return f'start "" "{exe_path}" "{script_path}"'

    def _set_autostart_enabled(self, enabled: bool) -> (bool, str):
        if platform.system() != "Windows":
            return False, "开机自启目前仅支持 Windows"
        startup_dir = self._get_startup_dir()
        if not startup_dir or not os.path.isdir(startup_dir):
            return False, "无法定位系统启动文件夹"
        bat_path = os.path.join(startup_dir, STARTUP_BAT_NAME)
        try:
            if enabled:
                command = self._build_autostart_command()
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write("@echo off\n")
                    f.write(command + "\n")
            else:
                if os.path.exists(bat_path):
                    os.remove(bat_path)
            return True, ""
        except Exception as e:
            return False, f"设置开机自启失败：{e}"

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.toggle_visibility()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()
            self.raise_()

    def exit_app(self):
        self._allow_close = True
        self.close()

    @pyqtSlot()
    def on_server_started(self):
        """服务器启动成功回调"""
        self.status_val.setText("运行中")
        self.status_val.setStyleSheet("color: #44ff44;")
        self.btn_start.setText("停止服务")
        self.port_input.setEnabled(False)
        self.btn_admin.setEnabled(True)
        self.update_log(f"服务已启动，端口：{self.current_port}", level="success")

    @pyqtSlot(str)
    def on_server_error(self, error_msg: str):
        """服务器错误回调"""
        self.update_log(error_msg, level="error")

    @pyqtSlot()
    def toggle_server(self):
        """切换服务器状态（启动/停止）"""
        if not self.server_manager.is_running:
            # 启动服务
            try:
                port = int(self.port_input.text())
                if not (PORT_MIN <= port <= PORT_MAX):
                    self.update_log(f"错误：端口必须在{PORT_MIN}-{PORT_MAX}之间", level="warning")
                    return

                self.current_port = port
                self.server_manager.start(port, self.on_server_started, self.on_server_error)
            except ValueError:
                self.update_log("错误：端口必须是数字", level="warning")
            except Exception as e:
                self.update_log(f"启动失败：{str(e)}", level="error")
        else:
            # 停止服务
            self.server_manager.stop()
            self.status_val.setText("已停止")
            self.status_val.setStyleSheet("color: #ff5555;")
            self.btn_start.setText("启动服务")
            self.port_input.setEnabled(True)
            self.btn_admin.setEnabled(False)
            self.update_log("服务已停止", level="warning")

    @pyqtSlot()
    def open_admin_panel(self):
        """打开管理面板"""
        try:
            port = int(self.port_input.text())
            webbrowser.open(f"http://127.0.0.1:{port}/admin")
        except Exception as e:
            self.update_log(f"打开管理面板失败：{str(e)}", level="error")

    @pyqtSlot()
    def update_stats(self):
        """更新统计信息（优化：仅数据变化时更新）"""
        # 更新总请求数
        current_total = stats.get('total', 0)
        if current_total != int(self.total_val.text()):
            self.total_val.setText(f"{current_total}")

        # 更新成功率
        if current_total > 0:
            success = stats.get('success', 0)
            rate = (success / current_total) * 100
            if int(self.prog_bar.value()) != int(rate):
                self.prog_bar.setValue(int(rate))
                self.rate_val.setText(f"{rate:.1f}%")
        else:
            if self.prog_bar.value() != 0:
                self.prog_bar.setValue(0)
                self.rate_val.setText("0.0%")

        # 更新请求日志（按 request_id 去重，按状态着色）
        if request_logs:
            for entry in reversed(list(request_logs)):
                log_key = self._build_request_log_key(entry)
                if log_key in self.seen_request_keys:
                    continue
                self.seen_request_keys.add(log_key)
                level = self._status_to_level(entry.get("status", 0))
                model = entry.get("effective_model") or entry.get("model", "")
                latency = entry.get("latency_ms")
                latency_text = f" {latency}ms" if isinstance(latency, (int, float)) else ""
                msg = (
                    f"{entry.get('time', '')} {entry.get('method', '')} {entry.get('path', '')} "
                    f"[{entry.get('status', '')}] {model}{latency_text}"
                ).strip()
                self.update_log(msg, level=level)

            # 防止去重集合无限增长
            if len(self.seen_request_keys) > 1000:
                self.seen_request_keys = {self._build_request_log_key(item) for item in request_logs}

    def _build_request_log_key(self, entry: Dict[str, object]) -> str:
        request_id = str(entry.get("request_id", "") or "").strip()
        if request_id:
            return request_id
        return (
            f"{entry.get('time', '')}|{entry.get('method', '')}|{entry.get('path', '')}|"
            f"{entry.get('status', '')}|{entry.get('model', '')}|{entry.get('latency_ms', '')}"
        )

    def _status_to_level(self, status: object) -> str:
        try:
            status_num = int(status)
        except Exception:
            return "info"
        if status_num >= 500:
            return "error"
        if status_num >= 400:
            return "warning"
        return "success"

    def update_log(self, msg: str, level: str = "info"):
        """更新日志（最多保留 200 条，按级别着色）"""
        level_colors = {
            "info": "#ff9966",
            "success": "#34d399",
            "warning": "#f59e0b",
            "error": "#ff6b6b",
        }
        level_key = level if level in level_colors else "info"
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_entries.append((ts, msg, level_key))

        html_lines = []
        for line_ts, line_msg, line_level in self.log_entries:
            color = level_colors.get(line_level, level_colors["info"])
            html_lines.append(f"<span style='color:{color}'>[{line_ts}] {html.escape(str(line_msg))}</span>")

        self.log_text.setHtml("<br>".join(html_lines))
        self.log_text.moveCursor(self.log_text.textCursor().End)

    @pyqtSlot()
    def clear_logs(self):
        """清空日志"""
        request_logs.clear()
        stats['total'] = 0
        stats['success'] = 0
        stats['error'] = 0
        self.update_stats()
        self.log_entries.clear()
        self.seen_request_keys.clear()
        self.log_text.clear()
        self.update_log("日志已清空 / Logs cleared", level="info")

    @pyqtSlot()
    def add_account(self):
        """通过 OAuth 添加账号并写入凭证池"""
        self.log_signal.emit("正在启动账号添加（OAuth 授权）...")
        try:
            from iflow_oauth import start_oauth_flow

            def run_oauth():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    def open_browser(url):
                        self.log_signal.emit("正在打开浏览器进行账号授权...")
                        webbrowser.open(url)

                    credentials = loop.run_until_complete(start_oauth_flow(on_auth_url=open_browser))
                    account_id, saved_path, replaced, removed_count = self._save_account_to_pool(credentials)
                    if replaced:
                        self.log_signal.emit(f"✓ 检测到同账号，已更新凭证：{account_id}")
                    else:
                        self.log_signal.emit(f"✓ 账号添加成功：{account_id}")
                    if removed_count > 0:
                        self.log_signal.emit(f"✓ 已清理 {removed_count} 个重复凭证文件")
                    self.log_signal.emit(f"凭证文件已写入：{saved_path}")
                except Exception as e:
                    self.log_signal.emit(f"✗ 账号添加失败: {e}")
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)

            threading.Thread(target=run_oauth, daemon=True).start()
        except Exception as e:
            self.log_signal.emit(f"启动账号添加失败: {e}")

    @pyqtSlot()
    def check_account_pool(self):
        """打开账号池健康检查窗口"""
        if self.account_pool_dialog is None:
            self.account_pool_dialog = AccountPoolDialog(self, self._fetch_account_pool_payload)
        self.account_pool_dialog.show()
        self.account_pool_dialog.raise_()
        self.account_pool_dialog.activateWindow()
        self.account_pool_dialog.refresh_pool()
        self.log_signal.emit("已打开账号池健康检查窗口")

    def _fetch_account_pool_payload(self) -> Dict[str, object]:
        import httpx

        if self.server_manager.is_running:
            response = httpx.get(f"http://localhost:{self.current_port}/admin/accounts", timeout=8.0)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("账号池接口返回格式错误")
            return payload

        proxy = get_proxy()
        payload = self._run_proxy_coroutine(lambda: proxy.get_account_pool_status(), timeout=10.0)

        if not isinstance(payload, dict):
            raise ValueError("账号池数据返回格式错误")
        return payload

    def _resolve_creds_dir(self) -> Path:
        configured = ""
        if isinstance(CONFIG, dict):
            configured = str(CONFIG.get("creds_dir") or "").strip()
        if not configured:
            configured = str(Path.home() / ".iflow2api" / "creds")
        return Path(configured).expanduser()

    def _save_account_to_pool(self, credentials: Dict[str, object]):
        api_key = str(credentials.get("apiKey") or "").strip()
        if not api_key:
            raise ValueError("未获取到 apiKey，无法写入账号池")
        refresh_token = str(credentials.get("refresh_token") or "").strip()
        account_identity = str(
            credentials.get("account_identity")
            or credentials.get("email")
            or credentials.get("phone")
            or ""
        ).strip().lower()
        account_seed = account_identity or api_key
        account_id_base = f"acct_{hashlib.sha1(account_seed.encode('utf-8')).hexdigest()[:12]}"

        creds_dir = self._resolve_creds_dir()
        creds_dir.mkdir(parents=True, exist_ok=True)

        matched_files: List[Path] = []
        matched_account_id = ""
        for existing_file in sorted(creds_dir.glob("*.json")):
            if existing_file.name.lower() == "index.json":
                continue
            try:
                existing_payload = json.loads(existing_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(existing_payload, dict):
                continue
            existing_api_key = str(existing_payload.get("apiKey") or existing_payload.get("api_key") or "").strip()
            existing_refresh = str(existing_payload.get("refresh_token") or "").strip()
            existing_identity = str(
                existing_payload.get("account_identity")
                or existing_payload.get("email")
                or existing_payload.get("phone")
                or ""
            ).strip().lower()
            same_identity = bool(account_identity) and bool(existing_identity) and existing_identity == account_identity
            same_api_key = bool(api_key) and existing_api_key == api_key
            same_refresh_token = bool(refresh_token) and bool(existing_refresh) and existing_refresh == refresh_token
            if not (same_identity or same_api_key or same_refresh_token):
                continue
            matched_files.append(existing_file)
            if matched_account_id:
                continue
            matched_account_id = str(existing_payload.get("account_id") or existing_payload.get("id") or existing_file.stem).strip()
            if not matched_account_id:
                matched_account_id = existing_file.stem

        replaced = len(matched_files) > 0
        removed_count = 0
        if replaced:
            matched_file = matched_files[0]
            account_id = matched_account_id
            file_path = matched_file
            for duplicate_file in matched_files[1:]:
                try:
                    duplicate_file.unlink()
                    removed_count += 1
                except Exception:
                    pass
        else:
            account_id = account_id_base
            file_path = creds_dir / f"{account_id}.json"
            idx = 1
            while file_path.exists():
                account_id = f"{account_id_base}_{idx}"
                file_path = creds_dir / f"{account_id}.json"
                idx += 1

        payload = dict(credentials)
        payload["account_id"] = account_id
        payload["enabled"] = True
        payload["priority"] = int(payload.get("priority") or 0)
        if account_identity:
            payload["account_identity"] = account_identity
        file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        return account_id, str(file_path), replaced, removed_count

    @pyqtSlot()
    def show_system_info(self):
        """显示模型列表对话框"""
        info = "正在加载模型列表..."
        try:
            import httpx

            if self.server_manager.is_running:
                response = httpx.get(f"http://localhost:{self.current_port}/v1/models", timeout=10.0)
                response.raise_for_status()
                payload = response.json()
            else:
                proxy = get_proxy()
                payload = self._run_proxy_coroutine(lambda: proxy.get_models(), timeout=12.0)

            model_ids: List[str] = []
            data = payload.get("data", [])
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        model_id = item.get("id")
                        if isinstance(model_id, str) and model_id:
                            model_ids.append(model_id)

            if model_ids:
                model_lines = "\n".join(f"- {model_id}" for model_id in model_ids)
                info = f"模型总数: {len(model_ids)}\n\n{model_lines}"
            else:
                info = "模型列表为空"
        except Exception as e:
            info = f"获取模型列表失败:\n{e}"

        dialog = QDialog(self)
        dialog.setWindowTitle("模型列表")
        dialog.setFixedSize(560, 440)
        dialog.setStyleSheet(Styles.get_style())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        text = QTextEdit()
        text.setObjectName("DialogText")
        text.setReadOnly(True)
        text.setText(info)
        layout.addWidget(text)
        dialog.exec_()

    @pyqtSlot()
    def show_api_examples(self):
        """显示API使用示例对话框"""
        port = self.current_port
        examples = f"""# OpenAI 格式 - 对话补全
curl http://localhost:{port}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{{"model": "glm-4.7", "messages": [{{"role": "user", "content": "Hello"}}]}}'

# Anthropic 格式 - 消息对话
curl http://localhost:{port}/v1/messages \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{{"model": "glm-4.7", "messages": [{{"role": "user", "content": "Hello"}}], "max_tokens": 1024}}'

# 思考模式 - GLM-4.7
curl http://localhost:{port}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{{"model": "glm-4.7", "messages": [{{"role": "user", "content": "Solve: 2+2"}}], "reasoning_effort": "high"}}'"""

        dialog = QDialog(self)
        dialog.setWindowTitle("API 使用示例")
        dialog.setFixedSize(780, 560)
        dialog.setStyleSheet(Styles.get_style())
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        text = QTextEdit()
        text.setObjectName("DialogText")
        text.setReadOnly(True)
        text.setLineWrapMode(QTextEdit.NoWrap)
        text.setText(examples)
        layout.addWidget(text)
        dialog.exec_()

# ==============================
# 程序入口
# ==============================
def run_gui():
    """GUI 入口"""
    # 启用高DPI缩放
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass

    app_qt = QApplication(sys.argv)
    app_qt.setWindowIcon(QIcon(ICON_PATH))

    GUI_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    single_instance_lock = QLockFile(str(GUI_LOCK_FILE))
    single_instance_lock.setStaleLockTime(0)
    if not single_instance_lock.tryLock(0):
        QMessageBox.information(None, APP_TITLE, "程序已经在运行中。")
        return
    app_qt.single_instance_lock = single_instance_lock

    window = MainWindow()
    window.show()
    sys.exit(app_qt.exec_())


if __name__ == "__main__":
    run_gui()
