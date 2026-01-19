from typing import Optional, Dict, List
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QGridLayout,
    QProgressBar, QSizePolicy, QScrollArea, QTextEdit,
    QGraphicsDropShadowEffect, QDialog
)
from PyQt5.QtCore import (
    Qt, QTimer, QSize, pyqtSignal, pyqtSlot, QThread, QPoint
)
from PyQt5.QtGui import QFont, QColor, QPainter, QIntValidator, QCursor, QIcon
import sys
import threading
import asyncio
import uvicorn
import webbrowser
import platform
import psutil
import os
import time
from datetime import datetime
from main import app, request_logs, stats, CONFIG

start_time = time.time()

# ==============================
# 常量定义（统一管理，便于维护）
# ==============================
APP_TITLE = "iFlow2API Console"
WINDOW_SIZE = (380, 320)  # 第二轮等比例缩小，适配“内层”尺寸
REFRESH_INTERVAL = 500  # 定时器刷新间隔(ms)
PORT_MIN = 1024
PORT_MAX = 65535
DEFAULT_PORT = 8000
LOGO_TEXT = "IFLOW\nTO API"
VERSION_TEXT = "永久版"

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
        font-size: 9px;
        font-weight: normal;
    }

    QLabel.StatValue {
        color: #ff9966;
        font-size: 10px;
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
        font-size: 8px;
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
        height: 18px;
    }

    QPushButton:disabled {
        background: #1a1a1a;
        border-color: #555555;
        color: #888888;
    }

    /* Input */
    QLineEdit {
        background: #1a0d05;
        color: #ff9966;
        border: 1px solid #ff5500;
        border-radius: 3px;
        padding: 1px 3px;
        font-size: 9px;
    }

    QLineEdit:disabled {
        background: #222222;
        border-color: #663300;
        color: #999999;
    }

    /* Log Area */
    QFrame.LogArea {
        background-color: #000000;
        border-top: 1px solid #331100;
    }

    QTextEdit.LogText {
        background-color: #000000;
        color: #ff9966;
        font-size: 9px;
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
        self.setFixedSize(180, 75) # 适配内层尺寸
        
        # 缓存字体和颜色，避免重复创建
        self.font = QFont("Courier New", 26, QFont.Bold) # 减小字号适配 compact 布局
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
        self._is_running = True
        try:
            config = uvicorn.Config(app, host="0.0.0.0", port=self.port, log_config=None)
            self.server = uvicorn.Server(config)

            # 标记服务器已启动（在实际运行前）
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

# ==============================
# 主窗口（核心优化）
# ==============================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.server_manager = ServerManager()
        self.last_log = ""  # 缓存最后一条日志，避免重复更新
        self.current_port = DEFAULT_PORT
        self.init_ui()
        self.init_timer()
        self.connect_server_signals()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon("icon.ico"))
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
        icon_label.setStyleSheet("font-size: 10px; color: #ff7733;")
        title_text = QLabel("畅享 Claude Code")
        title_text.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 10px; color: #bbbbbb; font-weight: bold;")
        title_info.addWidget(icon_label)
        title_info.addWidget(title_text)
        title_bar_layout.addLayout(title_info)
        
        title_bar_layout.addStretch()
        
        # 标题栏右侧：最小化 + 关闭
        btn_min = QPushButton("－")
        btn_min.setFixedSize(20, 20) # 再次缩小
        btn_min.setStyleSheet("QPushButton { background: transparent; color: #888; font-size: 12px; border: none; } QPushButton:hover { color: #ffffff; background: #333333; }")
        btn_min.clicked.connect(self.showMinimized)
        
        btn_close = QPushButton("×")
        btn_close.setFixedSize(20, 20) # 再次缩小
        btn_close.setStyleSheet("QPushButton { background: transparent; color: #888; font-size: 14px; border: none; border-top-right-radius: 10px; } QPushButton:hover { color: #ffffff; background: #ff5555; }")
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
        stats_layout.setHorizontalSpacing(10)
        stats_layout.setVerticalSpacing(5)

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
        self.prog_bar.setFixedSize(100, 6)
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
        self.port_input.setFixedWidth(50)
        # 仅允许输入数字，且范围在1024-65535
        self.port_input.setValidator(QIntValidator(PORT_MIN, PORT_MAX))
        stats_layout.addWidget(self.port_input, 3, 1)

        # 版本
        lbl = QLabel("版本")
        lbl.setProperty("class", "StatLabel")
        stats_layout.addWidget(lbl, 4, 0, Qt.AlignRight)
        version_lbl = QLabel(VERSION_TEXT)
        version_lbl.setProperty("class", "StatValue")
        stats_layout.addWidget(version_lbl, 4, 1)

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

        self.btn_oauth = QPushButton("OAuth认证")
        self.btn_oauth.clicked.connect(self.start_oauth)
        self.btn_oauth.setProperty("class", "ActionBtn")

        self.btn_health = QPushButton("健康检查")
        self.btn_health.clicked.connect(self.check_health)
        self.btn_health.setProperty("class", "ActionBtn")

        self.btn_sysinfo = QPushButton("系统信息")
        self.btn_sysinfo.clicked.connect(self.show_system_info)
        self.btn_sysinfo.setProperty("class", "ActionBtn")

        self.btn_api = QPushButton("API示例")
        self.btn_api.clicked.connect(self.show_api_examples)
        self.btn_api.setProperty("class", "ActionBtn")

        self.btn_github = QPushButton("GitHub")
        self.btn_github.clicked.connect(lambda: webbrowser.open("https://github.com/rtiy1/ifow2api"))
        self.btn_github.setProperty("class", "ActionBtn")

        # 两行布局：2行×4列
        btn_layout.addWidget(self.btn_start, 0, 0)
        btn_layout.addWidget(self.btn_admin, 0, 1)
        btn_layout.addWidget(self.btn_clear, 0, 2)
        btn_layout.addWidget(self.btn_oauth, 0, 3)
        btn_layout.addWidget(self.btn_health, 1, 0)
        btn_layout.addWidget(self.btn_sysinfo, 1, 1)
        btn_layout.addWidget(self.btn_api, 1, 2)
        btn_layout.addWidget(self.btn_github, 1, 3)

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
        self.log_icon.setStyleSheet("color: #ffbb00; font-size: 10px;")
        log_title = QLabel("系统日志")
        log_title.setStyleSheet("color: #888888; font-size: 10px;")
        log_title_layout.addWidget(self.log_icon)
        log_title_layout.addWidget(log_title)
        log_title_layout.addStretch()

        # 滚动日志区域
        self.log_text = QTextEdit()
        self.log_text.setProperty("class", "LogText")
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(80) # 进一步压缩最小高度
        self.log_text.setText("系统就绪 / Waiting for commands...")

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

    @pyqtSlot()
    def on_server_started(self):
        """服务器启动成功回调"""
        self.status_val.setText("运行中")
        self.status_val.setStyleSheet("color: #44ff44;")
        self.btn_start.setText("停止服务")
        self.port_input.setEnabled(False)
        self.btn_admin.setEnabled(True)
        self.update_log(f"服务已启动，端口：{self.current_port}")

    @pyqtSlot(str)
    def on_server_error(self, error_msg: str):
        """服务器错误回调"""
        self.update_log(error_msg)

    @pyqtSlot()
    def toggle_server(self):
        """切换服务器状态（启动/停止）"""
        if not self.server_manager.is_running:
            # 启动服务
            try:
                port = int(self.port_input.text())
                if not (PORT_MIN <= port <= PORT_MAX):
                    self.update_log(f"错误：端口必须在{PORT_MIN}-{PORT_MAX}之间")
                    return

                self.current_port = port
                self.server_manager.start(port, self.on_server_started, self.on_server_error)
            except ValueError:
                self.update_log("错误：端口必须是数字")
            except Exception as e:
                self.update_log(f"启动失败：{str(e)}")
        else:
            # 停止服务
            self.server_manager.stop()
            self.status_val.setText("已停止")
            self.status_val.setStyleSheet("color: #ff5555;")
            self.btn_start.setText("启动服务")
            self.port_input.setEnabled(True)
            self.btn_admin.setEnabled(False)
            self.update_log("服务已停止")

    @pyqtSlot()
    def open_admin_panel(self):
        """打开管理面板"""
        try:
            port = int(self.port_input.text())
            webbrowser.open(f"http://127.0.0.1:{port}/admin")
        except Exception as e:
            self.update_log(f"打开管理面板失败：{str(e)}")

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

        # 更新最新日志（仅日志变化时更新）
        if request_logs:
            latest = request_logs[0]
            log_str = (
                f"{latest.get('time', '')} "
                f"{latest.get('method', '')} "
                f"{latest.get('path', '')} "
                f"[{latest.get('status', '')}]"
            )
            if log_str != self.last_log:
                self.last_log = log_str
                self.update_log(log_str)

    def update_log(self, msg: str):
        """更新日志（追加模式，保留历史）"""
        current_text = self.log_text.toPlainText()
        # 保留最近10条日志，避免文本过长
        log_lines = current_text.split('\n')[-9:]
        log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        self.log_text.setText('\n'.join(log_lines))
        # 滚动到最后一行
        self.log_text.moveCursor(self.log_text.textCursor().End)

    @pyqtSlot()
    def clear_logs(self):
        """清空日志"""
        request_logs.clear()
        stats['total'] = 0
        stats['success'] = 0
        stats['error'] = 0
        self.update_stats()
        self.log_text.setText("日志已清空 / Logs cleared")
        self.last_log = ""

    @pyqtSlot()
    def start_oauth(self):
        """启动 OAuth 认证"""
        self.update_log("正在启动 OAuth 认证...")
        try:
            from iflow_oauth import start_oauth_flow, generate_auth_url, IFLOW_OAUTH_CONFIG
            import asyncio
            import secrets

            state = secrets.token_urlsafe(16)
            port = IFLOW_OAUTH_CONFIG["callback_port"]
            auth_url, _ = generate_auth_url(state, port)

            self.update_log(f"正在打开浏览器进行授权...")
            webbrowser.open(auth_url)

            def run_oauth():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    credentials = loop.run_until_complete(start_oauth_flow())
                    self.update_log(f"✓ OAuth 认证成功！API Key: {credentials['apiKey'][:20]}...")
                except Exception as e:
                    self.update_log(f"✗ OAuth 认证失败: {e}")

            threading.Thread(target=run_oauth, daemon=True).start()
        except Exception as e:
            self.update_log(f"启动 OAuth 失败: {e}")

    @pyqtSlot()
    def check_health(self):
        """检查服务健康状态"""
        if not self.server_manager.is_running:
            self.update_log("服务未运行，无法检查健康状态")
            return

        try:
            import httpx
            port = self.current_port

            def check():
                try:
                    response = httpx.get(f"http://localhost:{port}/health", timeout=5.0)
                    if response.status_code == 200:
                        data = response.json()
                        self.update_log(f"✓ 健康检查通过: {data.get('status', 'ok')}")
                    else:
                        self.update_log(f"✗ 健康检查失败: HTTP {response.status_code}")
                except Exception as e:
                    self.update_log(f"✗ 健康检查失败: {e}")

            threading.Thread(target=check, daemon=True).start()
        except Exception as e:
            self.update_log(f"健康检查错误: {e}")

    @pyqtSlot()
    def show_system_info(self):
        """显示系统信息对话框"""
        uptime_seconds = int(time.time() - start_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        uptime_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

        info = f"""Python版本: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}
平台: {platform.system()} {platform.release()}
CPU使用: {psutil.cpu_percent(interval=0.1):.1f}%
内存使用: {psutil.virtual_memory().percent:.1f}%
运行时间: {uptime_str}
进程PID: {os.getpid()}"""

        dialog = QDialog(self)
        dialog.setWindowTitle("系统信息")
        dialog.setFixedSize(300, 200)
        dialog.setStyleSheet(Styles.get_style())
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setText(info)
        text.setStyleSheet("QTextEdit { background: #1a0d05; color: #ff9966; border: 1px solid #ff5500; padding: 10px; }")
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
        dialog.setFixedSize(600, 400)
        dialog.setStyleSheet(Styles.get_style())
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setText(examples)
        text.setStyleSheet("QTextEdit { background: #000000; color: #ff9966; border: 1px solid #ff5500; padding: 10px; font-family: 'Consolas', monospace; font-size: 9px; }")
        layout.addWidget(text)
        dialog.exec_()

    def closeEvent(self, event):
        """窗口关闭事件（优雅退出）"""
        self.server_manager.stop()
        self.timer.stop()
        event.accept()

# ==============================
# 程序入口
# ==============================
if __name__ == "__main__":
    # 启用高DPI缩放
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    app_qt = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app_qt.exec_())