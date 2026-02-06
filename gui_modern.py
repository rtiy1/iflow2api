#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iFlow2API 现代化 GUI - PyQt5
风格：深色主题，顶部标签导航，参考 Antigravity Tools
"""

import sys
import json
import os
import webbrowser
import subprocess
import psutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QTextEdit, QFrame,
    QStackedWidget, QGraphicsDropShadowEffect, QScrollArea, QSizePolicy,
    QMessageBox, QFileDialog, QComboBox, QCheckBox, QGridLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint
from PyQt5.QtGui import QColor, QPalette, QFont, QIcon, QPainter, QBrush, QPen

# 常量定义
CONFIG_DIR = Path.home() / ".iflow"
OAUTH_CREDS_FILE = CONFIG_DIR / "oauth_creds.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# 样式常量
COLORS = {
    "bg_primary": "#0f1115",
    "bg_secondary": "#1a1d29",
    "bg_card": "#252a3c",
    "bg_card_hover": "#2d3447",
    "text_primary": "#ffffff",
    "text_secondary": "#9ca3af",
    "accent_blue": "#3b82f6",
    "accent_purple": "#8b5cf6",
    "accent_green": "#10b981",
    "accent_red": "#ef4444",
    "accent_yellow": "#f59e0b",
    "border": "#374151",
}

STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS["bg_primary"]};
    color: {COLORS["text_primary"]};
}}

QWidget {{
    background-color: {COLORS["bg_primary"]};
    color: {COLORS["text_primary"]};
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}}

/* 导航栏样式 */
.nav-bar {{
    background-color: {COLORS["bg_secondary"]};
    border-bottom: 1px solid {COLORS["border"]};
    padding: 8px 16px;
}}

.nav-button {{
    background-color: transparent;
    color: {COLORS["text_secondary"]};
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    min-width: 80px;
}}

.nav-button:hover {{
    background-color: {COLORS["bg_card"]};
    color: {COLORS["text_primary"]};
}}

.nav-button.active {{
    background-color: {COLORS["bg_card"]};
    color: {COLORS["text_primary"]};
    font-weight: 600;
}}

/* 卡片样式 */
.card {{
    background-color: {COLORS["bg_card"]};
    border-radius: 12px;
    padding: 20px;
    border: 1px solid {COLORS["border"]};
}}

.card-title {{
    color: {COLORS["text_primary"]};
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 12px;
}}

.card-subtitle {{
    color: {COLORS["text_secondary"]};
    font-size: 13px;
    margin-bottom: 16px;
}}

/* 按钮样式 */
QPushButton.primary {{
    background-color: {COLORS["accent_blue"]};
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
}}

QPushButton.primary:hover {{
    background-color: #2563eb;
}}

QPushButton.primary:pressed {{
    background-color: #1d4ed8;
}}

QPushButton.secondary {{
    background-color: {COLORS["bg_card"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
}}

QPushButton.secondary:hover {{
    background-color: {COLORS["bg_card_hover"]};
}}

QPushButton.danger {{
    background-color: {COLORS["accent_red"]};
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
}}

QPushButton.danger:hover {{
    background-color: #dc2626;
}}

QPushButton.success {{
    background-color: {COLORS["accent_green"]};
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 14px;
}}

QPushButton.success:hover {{
    background-color: #059669;
}}

/* 输入框样式 */
QLineEdit {{
    background-color: {COLORS["bg_secondary"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    padding: 10px 12px;
    border-radius: 8px;
    font-size: 14px;
}}

QLineEdit:focus {{
    border-color: {COLORS["accent_blue"]};
}}

QLineEdit:disabled {{
    background-color: {COLORS["bg_card"]};
    color: {COLORS["text_secondary"]};
}}

/* 开关样式 */
QCheckBox {{
    spacing: 8px;
    color: {COLORS["text_primary"]};
    font-size: 14px;
}}

QCheckBox::indicator {{
    width: 44px;
    height: 24px;
    border-radius: 12px;
}}

QCheckBox::indicator:unchecked {{
    background-color: {COLORS["bg_card"]};
    border: 2px solid {COLORS["border"]};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS["accent_blue"]};
    border: 2px solid {COLORS["accent_blue"]};
}}

/* 下拉框样式 */
QComboBox {{
    background-color: {COLORS["bg_secondary"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    padding: 10px 12px;
    border-radius: 8px;
    font-size: 14px;
    min-width: 150px;
}}

QComboBox:focus {{
    border-color: {COLORS["accent_blue"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 30px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["bg_card"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    selection-background-color: {COLORS["accent_blue"]};
}}

/* 数字输入框 */
QSpinBox {{
    background-color: {COLORS["bg_secondary"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    padding: 10px;
    border-radius: 8px;
    font-size: 14px;
}}

/* 状态标签 */
.status-badge {{
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}}

.status-badge.running {{
    background-color: rgba(16, 185, 129, 0.2);
    color: {COLORS["accent_green"]};
}}

.status-badge.stopped {{
    background-color: rgba(239, 68, 68, 0.2);
    color: {COLORS["accent_red"]};
}}

/* 滚动条 */
QScrollBar:vertical {{
    background-color: {COLORS["bg_secondary"]};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS["border"]};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #4b5563;
}}

/* 标签样式 */
QLabel {{
    color: {COLORS["text_primary"]};
}}

QLabel.label-secondary {{
    color: {COLORS["text_secondary"]};
    font-size: 13px;
}}

/* 统计数字 */
.stat-number {{
    font-size: 32px;
    font-weight: 700;
    color: {COLORS["text_primary"]};
}}

.stat-label {{
    font-size: 13px;
    color: {COLORS["text_secondary"]};
}}
"""


class ServiceThread(QThread):
    """服务运行线程"""
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(bool)

    def __init__(self, port: int):
        super().__init__()
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.running = False

    def run(self):
        self.running = True
        try:
            cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(self.port)]
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8"
            )
            self.status_signal.emit(True)

            for line in self.process.stdout:
                if line:
                    self.log_signal.emit(line.strip())

        except Exception as e:
            self.log_signal.emit(f"服务启动失败: {e}")
            self.status_signal.emit(False)

    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.status_signal.emit(False)


class DashboardPage(QWidget):
    """仪表盘页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.init_ui()
        self.start_monitoring()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # 页面标题
        title = QLabel("仪表盘")
        title.setStyleSheet("font-size: 24px; font-weight: 700; margin-bottom: 8px;")
        layout.addWidget(title)

        subtitle = QLabel("服务状态和系统概览")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        # 状态卡片区域
        status_row = QHBoxLayout()
        status_row.setSpacing(16)

        # 服务状态卡片
        self.status_card = self.create_stat_card(
            "服务状态",
            "已停止",
            "status-badge stopped"
        )
        status_row.addWidget(self.status_card)

        # 总请求数卡片
        self.requests_card = self.create_stat_card(
            "总请求数",
            "0",
            "stat-number"
        )
        status_row.addWidget(self.requests_card)

        # 成功率卡片
        self.success_rate_card = self.create_stat_card(
            "成功率",
            "100%",
            "stat-number"
        )
        status_row.addWidget(self.success_rate_card)

        # 运行时间卡片
        self.uptime_card = self.create_stat_card(
            "运行时间",
            "00:00:00",
            "stat-number"
        )
        status_row.addWidget(self.uptime_card)

        status_row.addStretch()
        layout.addLayout(status_row)

        # 系统资源卡片
        resource_row = QHBoxLayout()
        resource_row.setSpacing(16)

        # CPU 使用率
        self.cpu_card = self.create_resource_card("CPU 使用率", "0%", COLORS["accent_blue"])
        resource_row.addWidget(self.cpu_card)

        # 内存使用率
        self.memory_card = self.create_resource_card("内存使用率", "0%", COLORS["accent_purple"])
        resource_row.addWidget(self.memory_card)

        resource_row.addStretch()
        layout.addLayout(resource_row)

        # 快捷操作区域
        layout.addSpacing(16)
        action_title = QLabel("快捷操作")
        action_title.setStyleSheet("font-size: 16px; font-weight: 600; margin-top: 16px;")
        layout.addWidget(action_title)

        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        self.start_btn = QPushButton("▶ 启动服务")
        self.start_btn.setProperty("class", "primary")
        self.start_btn.setStyleSheet(STYLESHEET)
        self.start_btn.clicked.connect(self.toggle_service)
        action_row.addWidget(self.start_btn)

        self.open_admin_btn = QPushButton("🔧 打开管理面板")
        self.open_admin_btn.setProperty("class", "secondary")
        self.open_admin_btn.setStyleSheet(STYLESHEET)
        self.open_admin_btn.clicked.connect(self.open_admin_panel)
        self.open_admin_btn.setEnabled(False)
        action_row.addWidget(self.open_admin_btn)

        action_row.addStretch()
        layout.addLayout(action_row)

        # 日志区域
        layout.addSpacing(16)
        log_title = QLabel("运行日志")
        log_title.setStyleSheet("font-size: 16px; font-weight: 600; margin-top: 16px;")
        layout.addWidget(log_title)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.document().setMaximumBlockCount(100)
        self.log_text.setStyleSheet(f"""
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_secondary']};
            border-radius: 8px;
            padding: 12px;
            font-family: 'Consolas', monospace;
            font-size: 12px;
            border: 1px solid {COLORS['border']};
        """)
        layout.addWidget(self.log_text)

        layout.addStretch()

    def create_stat_card(self, label: str, value: str, value_class: str) -> QFrame:
        """创建统计卡片"""
        card = QFrame()
        card.setProperty("class", "card")
        card.setStyleSheet(STYLESHEET)
        card.setMinimumWidth(180)

        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        value_label = QLabel(value)
        value_label.setProperty("class", value_class)
        value_label.setStyleSheet(STYLESHEET)
        if value_class == "stat-number":
            value_label.setStyleSheet(f"font-size: 32px; font-weight: 700; color: {COLORS['text_primary']};")
        layout.addWidget(value_label)

        label_widget = QLabel(label)
        label_widget.setProperty("class", "stat-label")
        label_widget.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']};")
        layout.addWidget(label_widget)

        # 保存引用以便更新
        card.value_label = value_label
        return card

    def create_resource_card(self, label: str, value: str, color: str) -> QFrame:
        """创建资源使用卡片"""
        card = QFrame()
        card.setProperty("class", "card")
        card.setStyleSheet(STYLESHEET)
        card.setMinimumWidth(200)

        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {color};")
        layout.addWidget(value_label)

        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']};")
        layout.addWidget(label_widget)

        card.value_label = value_label
        return card

    def toggle_service(self):
        """启动/停止服务"""
        if not self.parent_window.service_running:
            port = self.parent_window.proxy_page.port_input.value()
            self.parent_window.start_service(port)
            self.start_btn.setText("⏹ 停止服务")
            self.start_btn.setProperty("class", "danger")
            self.start_btn.setStyleSheet(STYLESHEET)
            self.open_admin_btn.setEnabled(True)
        else:
            self.parent_window.stop_service()
            self.start_btn.setText("▶ 启动服务")
            self.start_btn.setProperty("class", "primary")
            self.start_btn.setStyleSheet(STYLESHEET)
            self.open_admin_btn.setEnabled(False)

    def open_admin_panel(self):
        """打开管理面板"""
        port = self.parent_window.proxy_page.port_input.value()
        webbrowser.open(f"http://localhost:{port}/admin")

    def update_service_status(self, running: bool):
        """更新服务状态显示"""
        status_label = self.status_card.value_label
        if running:
            status_label.setText("运行中")
            status_label.setProperty("class", "status-badge running")
            status_label.setStyleSheet(f"""
                background-color: rgba(16, 185, 129, 0.2);
                color: {COLORS['accent_green']};
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 500;
            """)
        else:
            status_label.setText("已停止")
            status_label.setProperty("class", "status-badge stopped")
            status_label.setStyleSheet(f"""
                background-color: rgba(239, 68, 68, 0.2);
                color: {COLORS['accent_red']};
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 500;
            """)

    def append_log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def start_monitoring(self):
        """启动系统监控"""
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_system_stats)
        self.monitor_timer.start(1000)  # 每秒更新

    def update_system_stats(self):
        """更新系统统计信息"""
        # CPU 使用率
        cpu_percent = psutil.cpu_percent()
        self.cpu_card.value_label.setText(f"{cpu_percent:.1f}%")

        # 内存使用率
        memory = psutil.virtual_memory()
        self.memory_card.value_label.setText(f"{memory.percent:.1f}%")


class ProxyPage(QWidget):
    """API 反代页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # 页面标题
        title = QLabel("API 反代")
        title.setStyleSheet("font-size: 24px; font-weight: 700; margin-bottom: 8px;")
        layout.addWidget(title)

        subtitle = QLabel("配置代理服务和连接设置")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        # 基本设置卡片
        basic_card = QFrame()
        basic_card.setProperty("class", "card")
        basic_card.setStyleSheet(STYLESHEET)
        layout.addWidget(basic_card)

        basic_layout = QVBoxLayout(basic_card)
        basic_layout.setSpacing(16)
        basic_layout.setContentsMargins(20, 20, 20, 20)

        # 卡片标题
        card_title = QLabel("⚙️ 基本设置")
        card_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        basic_layout.addWidget(card_title)

        # 服务开关
        service_row = QHBoxLayout()
        service_label = QLabel("代理服务")
        service_label.setStyleSheet("font-size: 14px;")
        service_row.addWidget(service_label)

        self.service_toggle = QCheckBox()
        self.service_toggle.setChecked(False)
        self.service_toggle.stateChanged.connect(self.on_service_toggle)
        service_row.addWidget(self.service_toggle)

        service_status = QLabel("点击开关启动/停止服务")
        service_status.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        service_row.addWidget(service_status)

        service_row.addStretch()
        basic_layout.addLayout(service_row)

        # 端口设置
        port_row = QHBoxLayout()
        port_label = QLabel("监听端口")
        port_label.setStyleSheet("font-size: 14px;")
        port_label.setMinimumWidth(100)
        port_row.addWidget(port_label)

        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(8000)
        self.port_input.setEnabled(True)
        port_row.addWidget(self.port_input)

        port_hint = QLabel("范围: 1024-65535")
        port_hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        port_row.addWidget(port_hint)

        port_row.addStretch()
        basic_layout.addLayout(port_row)

        # 上游 API 地址
        api_row = QHBoxLayout()
        api_label = QLabel("上游 API")
        api_label.setStyleSheet("font-size: 14px;")
        api_label.setMinimumWidth(100)
        api_row.addWidget(api_label)

        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("https://apis.iflow.cn/v1")
        self.api_url_input.setText("https://apis.iflow.cn/v1")
        api_row.addWidget(self.api_url_input)

        api_row.addStretch()
        basic_layout.addLayout(api_row)

        # 高级设置卡片
        layout.addSpacing(16)
        advanced_card = QFrame()
        advanced_card.setProperty("class", "card")
        advanced_card.setStyleSheet(STYLESHEET)
        layout.addWidget(advanced_card)

        advanced_layout = QVBoxLayout(advanced_card)
        advanced_layout.setSpacing(16)
        advanced_layout.setContentsMargins(20, 20, 20, 20)

        # 卡片标题
        adv_title = QLabel("🔧 高级设置")
        adv_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        advanced_layout.addWidget(adv_title)

        # 重试次数
        retry_row = QHBoxLayout()
        retry_label = QLabel("重试次数")
        retry_label.setStyleSheet("font-size: 14px;")
        retry_label.setMinimumWidth(100)
        retry_row.addWidget(retry_label)

        self.retry_input = QSpinBox()
        self.retry_input.setRange(0, 10)
        self.retry_input.setValue(3)
        retry_row.addWidget(self.retry_input)

        retry_hint = QLabel("请求失败时的自动重试次数")
        retry_hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        retry_row.addWidget(retry_hint)

        retry_row.addStretch()
        advanced_layout.addLayout(retry_row)

        # 超时设置
        timeout_row = QHBoxLayout()
        timeout_label = QLabel("超时时间")
        timeout_label.setStyleSheet("font-size: 14px;")
        timeout_label.setMinimumWidth(100)
        timeout_row.addWidget(timeout_label)

        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(10, 300)
        self.timeout_input.setValue(60)
        self.timeout_input.setSuffix(" 秒")
        timeout_row.addWidget(self.timeout_input)

        timeout_hint = QLabel("请求超时时间")
        timeout_hint.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        timeout_row.addWidget(timeout_hint)

        timeout_row.addStretch()
        advanced_layout.addLayout(timeout_row)

        # 保存按钮
        layout.addSpacing(16)
        btn_row = QHBoxLayout()

        self.save_btn = QPushButton("💾 保存配置")
        self.save_btn.setProperty("class", "primary")
        self.save_btn.setStyleSheet(STYLESHEET)
        self.save_btn.clicked.connect(self.save_config)
        btn_row.addWidget(self.save_btn)

        self.reset_btn = QPushButton("↩️ 重置默认")
        self.reset_btn.setProperty("class", "secondary")
        self.reset_btn.setStyleSheet(STYLESHEET)
        self.reset_btn.clicked.connect(self.reset_config)
        btn_row.addWidget(self.reset_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()

    def on_service_toggle(self, state):
        """服务开关切换"""
        if self.parent_window:
            self.parent_window.dashboard_page.toggle_service()

    def save_config(self):
        """保存配置"""
        config = {
            "port": self.port_input.value(),
            "base_url": self.api_url_input.text(),
            "retry": self.retry_input.value(),
            "timeout": self.timeout_input.value(),
        }

        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            config_file = CONFIG_DIR / "gui_config.json"
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            QMessageBox.information(self, "成功", "配置已保存")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存配置失败: {e}")

    def reset_config(self):
        """重置默认配置"""
        self.port_input.setValue(8000)
        self.api_url_input.setText("https://apis.iflow.cn/v1")
        self.retry_input.setValue(3)
        self.timeout_input.setValue(60)


class AccountPage(QWidget):
    """账号管理页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.init_ui()
        self.load_credentials()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # 页面标题
        title = QLabel("账号管理")
        title.setStyleSheet("font-size: 24px; font-weight: 700; margin-bottom: 8px;")
        layout.addWidget(title)

        subtitle = QLabel("管理 OAuth 认证和 API 凭证")
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        # 认证状态卡片
        self.auth_card = QFrame()
        self.auth_card.setProperty("class", "card")
        self.auth_card.setStyleSheet(STYLESHEET)
        layout.addWidget(self.auth_card)

        auth_layout = QVBoxLayout(self.auth_card)
        auth_layout.setSpacing(16)
        auth_layout.setContentsMargins(20, 20, 20, 20)

        # 认证状态标题
        auth_title = QLabel("🔐 认证状态")
        auth_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        auth_layout.addWidget(auth_title)

        # 状态显示
        status_row = QHBoxLayout()
        status_label = QLabel("当前状态:")
        status_label.setStyleSheet("font-size: 14px;")
        status_row.addWidget(status_label)

        self.auth_status = QLabel("未认证")
        self.auth_status.setStyleSheet(f"""
            color: {COLORS['accent_red']};
            font-size: 14px;
            font-weight: 500;
        """)
        status_row.addWidget(self.auth_status)
        status_row.addStretch()
        auth_layout.addLayout(status_row)

        # 用户信息
        self.user_info_label = QLabel("点击「OAuth 认证」按钮进行登录")
        self.user_info_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        auth_layout.addWidget(self.user_info_label)

        # Token 信息
        self.token_info_label = QLabel("")
        self.token_info_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        auth_layout.addWidget(self.token_info_label)

        # 操作按钮
        btn_row = QHBoxLayout()

        self.oauth_btn = QPushButton("🔑 OAuth 认证")
        self.oauth_btn.setProperty("class", "primary")
        self.oauth_btn.setStyleSheet(STYLESHEET)
        self.oauth_btn.clicked.connect(self.start_oauth)
        btn_row.addWidget(self.oauth_btn)

        self.refresh_btn = QPushButton("🔄 刷新 Token")
        self.refresh_btn.setProperty("class", "secondary")
        self.refresh_btn.setStyleSheet(STYLESHEET)
        self.refresh_btn.clicked.connect(self.refresh_token)
        self.refresh_btn.setEnabled(False)
        btn_row.addWidget(self.refresh_btn)

        self.logout_btn = QPushButton("🚪 退出登录")
        self.logout_btn.setProperty("class", "danger")
        self.logout_btn.setStyleSheet(STYLESHEET)
        self.logout_btn.clicked.connect(self.logout)
        self.logout_btn.setEnabled(False)
        btn_row.addWidget(self.logout_btn)

        btn_row.addStretch()
        auth_layout.addLayout(btn_row)

        # API Key 配置卡片
        layout.addSpacing(16)
        apikey_card = QFrame()
        apikey_card.setProperty("class", "card")
        apikey_card.setStyleSheet(STYLESHEET)
        layout.addWidget(apikey_card)

        apikey_layout = QVBoxLayout(apikey_card)
        apikey_layout.setSpacing(16)
        apikey_layout.setContentsMargins(20, 20, 20, 20)

        # API Key 标题
        apikey_title = QLabel("📝 API Key 配置")
        apikey_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        apikey_layout.addWidget(apikey_title)

        # API Key 输入
        apikey_row = QHBoxLayout()
        apikey_label = QLabel("API Key:")
        apikey_label.setStyleSheet("font-size: 14px;")
        apikey_label.setMinimumWidth(80)
        apikey_row.addWidget(apikey_label)

        self.apikey_input = QLineEdit()
        self.apikey_input.setPlaceholderText("输入你的 iFlow API Key")
        self.apikey_input.setEchoMode(QLineEdit.Password)
        apikey_row.addWidget(self.apikey_input)

        self.show_key_btn = QPushButton("👁")
        self.show_key_btn.setFixedWidth(40)
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self.toggle_key_visibility)
        apikey_row.addWidget(self.show_key_btn)

        apikey_layout.addLayout(apikey_row)

        # API Key 按钮
        apikey_btn_row = QHBoxLayout()

        self.save_key_btn = QPushButton("💾 保存 API Key")
        self.save_key_btn.setProperty("class", "primary")
        self.save_key_btn.setStyleSheet(STYLESHEET)
        self.save_key_btn.clicked.connect(self.save_api_key)
        apikey_btn_row.addWidget(self.save_key_btn)

        self.load_key_btn = QPushButton("📂 从文件导入")
        self.load_key_btn.setProperty("class", "secondary")
        self.load_key_btn.setStyleSheet(STYLESHEET)
        self.load_key_btn.clicked.connect(self.load_api_key_from_file)
        apikey_btn_row.addWidget(self.load_key_btn)

        apikey_btn_row.addStretch()
        apikey_layout.addLayout(apikey_btn_row)

        layout.addStretch()

    def load_credentials(self):
        """加载已保存的凭证"""
        try:
            if OAUTH_CREDS_FILE.exists():
                with open(OAUTH_CREDS_FILE, "r", encoding="utf-8") as f:
                    creds = json.load(f)
                    self.update_auth_ui(True, creds)
            elif SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    if "api_key" in settings:
                        self.apikey_input.setText(settings["api_key"])
        except Exception as e:
            print(f"加载凭证失败: {e}")

    def update_auth_ui(self, authenticated: bool, creds: Dict = None):
        """更新认证 UI"""
        if authenticated:
            self.auth_status.setText("已认证")
            self.auth_status.setStyleSheet(f"""
                color: {COLORS['accent_green']};
                font-size: 14px;
                font-weight: 500;
            """)

            if creds:
                username = creds.get("username", "未知用户")
                self.user_info_label.setText(f"用户: {username}")

                # Token 过期时间
                expiry = creds.get("expiry_date", "")
                if expiry:
                    try:
                        expiry_dt = datetime.fromisoformat(expiry)
                        now = datetime.now()
                        if expiry_dt > now:
                            days_left = (expiry_dt - now).days
                            self.token_info_label.setText(f"Token 有效期: 剩余 {days_left} 天")
                        else:
                            self.token_info_label.setText("Token 已过期，请刷新")
                            self.token_info_label.setStyleSheet(f"color: {COLORS['accent_red']}; font-size: 12px;")
                    except:
                        pass

            self.refresh_btn.setEnabled(True)
            self.logout_btn.setEnabled(True)
        else:
            self.auth_status.setText("未认证")
            self.auth_status.setStyleSheet(f"""
                color: {COLORS['accent_red']};
                font-size: 14px;
                font-weight: 500;
            """)
            self.user_info_label.setText("点击「OAuth 认证」按钮进行登录")
            self.token_info_label.setText("")
            self.refresh_btn.setEnabled(False)
            self.logout_btn.setEnabled(False)

    def start_oauth(self):
        """启动 OAuth 认证"""
        try:
            subprocess.Popen([sys.executable, "iflow_auth_cli.py"])
            QMessageBox.information(
                self,
                "OAuth 认证",
                "已在浏览器中打开认证页面，请完成登录后返回本应用。\n\n"
                "完成后点击「刷新状态」查看认证结果。"
            )
        except Exception as e:
            QMessageBox.warning(self, "错误", f"启动认证失败: {e}")

    def refresh_token(self):
        """刷新 Token"""
        try:
            subprocess.run([sys.executable, "-c", "from iflow_token import refresh_token; refresh_token()"], check=True)
            self.load_credentials()
            QMessageBox.information(self, "成功", "Token 已刷新")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"刷新 Token 失败: {e}")

    def logout(self):
        """退出登录"""
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要删除所有认证信息吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                if OAUTH_CREDS_FILE.exists():
                    OAUTH_CREDS_FILE.unlink()
                if SETTINGS_FILE.exists():
                    SETTINGS_FILE.unlink()
                self.update_auth_ui(False)
                self.apikey_input.clear()
                QMessageBox.information(self, "成功", "已退出登录")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"退出失败: {e}")

    def toggle_key_visibility(self, checked):
        """切换 API Key 可见性"""
        if checked:
            self.apikey_input.setEchoMode(QLineEdit.Normal)
        else:
            self.apikey_input.setEchoMode(QLineEdit.Password)

    def save_api_key(self):
        """保存 API Key"""
        api_key = self.apikey_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "错误", "请输入 API Key")
            return

        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            settings = {}
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)

            settings["api_key"] = api_key

            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)

            QMessageBox.information(self, "成功", "API Key 已保存")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存失败: {e}")

    def load_api_key_from_file(self):
        """从文件导入 API Key"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择凭证文件",
            str(Path.home()),
            "JSON files (*.json);;All files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "api_key" in data:
                        self.apikey_input.setText(data["api_key"])
                    elif "apiKey" in data:
                        self.apikey_input.setText(data["apiKey"])
                    else:
                        QMessageBox.warning(self, "错误", "文件中未找到 API Key")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"读取文件失败: {e}")


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("iFlow2API")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        self.service_thread: Optional[ServiceThread] = None
        self.service_running = False

        self.init_ui()
        self.setStyleSheet(STYLESHEET)

    def init_ui(self):
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 导航栏
        nav_bar = QWidget()
        nav_bar.setProperty("class", "nav-bar")
        nav_bar.setFixedHeight(60)
        main_layout.addWidget(nav_bar)

        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setSpacing(8)
        nav_layout.setContentsMargins(16, 0, 16, 0)

        # Logo
        logo = QLabel("⚡ iFlow2API")
        logo.setStyleSheet("font-size: 18px; font-weight: 700; color: white;")
        nav_layout.addWidget(logo)

        nav_layout.addSpacing(32)

        # 导航按钮
        self.nav_buttons = []
        nav_items = [
            ("仪表盘", "dashboard"),
            ("账号管理", "account"),
            ("API 反代", "proxy"),
        ]

        for label, page_id in nav_items:
            btn = QPushButton(label)
            btn.setProperty("class", "nav-button")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, pid=page_id: self.switch_page(pid))
            nav_layout.addWidget(btn)
            self.nav_buttons.append((btn, page_id))

        nav_layout.addStretch()

        # 页面堆叠
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # 创建页面
        self.dashboard_page = DashboardPage(self)
        self.account_page = AccountPage(self)
        self.proxy_page = ProxyPage(self)

        self.stack.addWidget(self.dashboard_page)  # 0
        self.stack.addWidget(self.account_page)    # 1
        self.stack.addWidget(self.proxy_page)      # 2

        self.page_map = {
            "dashboard": 0,
            "account": 1,
            "proxy": 2,
        }

        # 默认显示仪表盘
        self.switch_page("dashboard")

    def switch_page(self, page_id: str):
        """切换页面"""
        if page_id in self.page_map:
            self.stack.setCurrentIndex(self.page_map[page_id])

            # 更新导航按钮样式
            for btn, pid in self.nav_buttons:
                if pid == page_id:
                    btn.setProperty("class", "nav-button active")
                else:
                    btn.setProperty("class", "nav-button")
                btn.setStyleSheet(STYLESHEET)

    def start_service(self, port: int):
        """启动服务"""
        if not self.service_running:
            self.service_thread = ServiceThread(port)
            self.service_thread.log_signal.connect(self.dashboard_page.append_log)
            self.service_thread.status_signal.connect(self.on_service_status_changed)
            self.service_thread.start()

    def stop_service(self):
        """停止服务"""
        if self.service_thread and self.service_running:
            self.service_thread.stop()
            self.service_thread.wait()

    def on_service_status_changed(self, running: bool):
        """服务状态变更回调"""
        self.service_running = running
        self.dashboard_page.update_service_status(running)

        # 同步代理页面的开关状态
        self.proxy_page.service_toggle.blockSignals(True)
        self.proxy_page.service_toggle.setChecked(running)
        self.proxy_page.service_toggle.blockSignals(False)

    def closeEvent(self, event):
        """关闭事件"""
        if self.service_running:
            reply = QMessageBox.question(
                self,
                "确认关闭",
                "服务正在运行中，确定要关闭应用吗？",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.stop_service()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置应用级调色板
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["bg_primary"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Base, QColor(COLORS["bg_secondary"]))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS["bg_card"]))
    palette.setColor(QPalette.Text, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Button, QColor(COLORS["bg_card"]))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["text_primary"]))
    app.setPalette(palette)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
