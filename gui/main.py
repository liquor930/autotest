"""
蓝牙自动化测试平台 GUI 主界面

基于 PySide6，通过调用 CLI 实现功能。
采用 MVC 架构，使用 QThread 避免界面卡顿。
"""

import sys
import os
import subprocess
import threading
from datetime import datetime
from typing import Optional

# 确保能导入 modules/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTabWidget, QPushButton, QLabel, QTextEdit, QListWidget,
        QLineEdit, QComboBox, QGroupBox, QSplitter, QMessageBox,
        QFileDialog, QProgressBar, QTableWidget, QTableWidgetItem,
        QHeaderView, QStatusBar, QFrame, QGridLayout,
    )
    from PySide6.QtCore import Qt, QThread, Signal, QSize
    from PySide6.QtGui import QFont, QIcon, QTextCursor

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False
    print("PySide6 未安装，运行: pip install PySide6")


# ==================== 后台任务线程 ====================

class CliWorker(QThread):
    """在后台执行 CLI 命令，通过信号返回结果"""
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, cmd: list):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            result = subprocess.run(self.cmd, capture_output=True, text=True, timeout=60)
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            self.finished.emit(output)
        except subprocess.TimeoutExpired:
            self.error.emit("Command timed out")
        except Exception as e:
            self.error.emit(str(e))


# ==================== 设备管理面板 ====================

class DevicePanel(QWidget):
    """设备管理标签页"""

    def __init__(self):
        super().__init__()
        self._worker: Optional[CliWorker] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 设备列表
        group = QGroupBox("ADB Devices")
        gl = QVBoxLayout(group)

        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_health = QPushButton("Health Check")
        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(self.btn_disconnect)
        btn_row.addWidget(self.btn_health)
        btn_row.addStretch()
        gl.addLayout(btn_row)

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["Device ID", "Model", "Version", "Status"])
        self.device_table.horizontalHeader().setStretchLastSection(True)
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        gl.addWidget(self.device_table)
        layout.addWidget(group)

        # 连接输入
        conn_group = QGroupBox("Manual Connect")
        conn_layout = QHBoxLayout(conn_group)
        conn_layout.addWidget(QLabel("IP:Port"))
        self.connect_input = QLineEdit()
        self.connect_input.setPlaceholderText("192.168.1.100:5555")
        conn_layout.addWidget(self.connect_input)
        self.btn_connect_manual = QPushButton("Connect")
        conn_layout.addWidget(self.btn_connect_manual)
        conn_layout.addStretch()
        layout.addWidget(conn_group)

        # 串口
        serial_group = QGroupBox("Serial Ports")
        s_layout = QHBoxLayout(serial_group)
        s_layout.addWidget(QLabel("Port:"))
        self.serial_port = QComboBox()
        self.serial_port.setEditable(True)
        self.serial_port.setMinimumWidth(150)
        s_layout.addWidget(self.serial_port)
        s_layout.addWidget(QLabel("Baud:"))
        self.serial_baud = QComboBox()
        self.serial_baud.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800"])
        self.serial_baud.setCurrentText("115200")
        s_layout.addWidget(self.serial_baud)
        self.btn_serial_connect = QPushButton("Open")
        self.btn_serial_send = QPushButton("Send AT")
        s_layout.addWidget(self.btn_serial_connect)
        s_layout.addWidget(self.btn_serial_send)
        s_layout.addStretch()
        layout.addWidget(serial_group)

        layout.addStretch()

        # Connections
        self.btn_refresh.clicked.connect(self._refresh_devices)
        self.btn_connect_manual.clicked.connect(self._manual_connect)

    def _refresh_devices(self):
        self.device_table.setRowCount(0)
        self._run_cli(['python', '-m', 'cli.bt_adb.cli', 'list'])

    def _manual_connect(self):
        text = self.connect_input.text().strip()
        if not text:
            return
        if ':' in text:
            ip, port = text.split(':')
        else:
            ip, port = text, '5555'
        self._run_cli(['python', '-m', 'cli.bt_adb.cli', 'connect', ip, port])

    def _run_cli(self, cmd):
        self._worker = CliWorker(cmd)
        self._worker.finished.connect(self._on_cli_result)
        self._worker.error.connect(lambda e: self._append_output(f"Error: {e}"))
        self._worker.start()

    def _on_cli_result(self, output):
        self._append_output(output)
        # Parse and populate table
        for line in output.split('\n'):
            if line.startswith('- '):
                parts = line[2:].split(' (')
                if len(parts) >= 1:
                    row = self.device_table.rowCount()
                    self.device_table.insertRow(row)
                    self.device_table.setItem(row, 0, QTableWidgetItem(parts[0]))

    def _append_output(self, text):
        if hasattr(self.parent(), '_log'):
            self.parent()._log.append(text)


# ==================== 测试执行面板 ====================

class TestPanel(QWidget):
    """测试执行标签页"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 配置
        cfg_group = QGroupBox("Configuration")
        cfg_layout = QVBoxLayout(cfg_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Config File:"))
        self.config_path = QLineEdit()
        self.config_path.setPlaceholderText("Select YAML/JSON config...")
        row1.addWidget(self.config_path)
        self.btn_browse = QPushButton("Browse")
        row1.addWidget(self.btn_browse)
        self.btn_validate = QPushButton("Validate")
        row1.addWidget(self.btn_validate)
        cfg_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Name:"))
        self.test_name = QLineEdit()
        self.test_name.setPlaceholderText("Optional test name")
        row2.addWidget(self.test_name)
        row2.addWidget(QLabel("Workers:"))
        self.workers = QComboBox()
        self.workers.addItems(["1", "2", "4", "8"])
        self.workers.setCurrentText("4")
        row2.addWidget(self.workers)
        row2.addStretch()
        cfg_layout.addLayout(row2)
        layout.addWidget(cfg_group)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_run = QPushButton("Run")
        self.btn_stop = QPushButton("Stop")
        self.btn_pause = QPushButton("Pause")
        self.btn_list = QPushButton("List Sessions")
        self.btn_run.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        ctrl_layout.addWidget(self.btn_run)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_pause)
        ctrl_layout.addWidget(self.btn_list)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        # Sessions table
        self.session_table = QTableWidget()
        self.session_table.setColumnCount(6)
        self.session_table.setHorizontalHeaderLabels(["Session ID", "Name", "Status", "Progress", "Pass/Fail", "Time"])
        self.session_table.horizontalHeader().setStretchLastSection(True)
        self.session_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.session_table)

        # Report
        report_layout = QHBoxLayout()
        report_layout.addWidget(QLabel("Session ID:"))
        self.report_input = QLineEdit()
        self.report_input.setPlaceholderText("Session ID for report...")
        report_layout.addWidget(self.report_input)
        self.btn_report = QPushButton("Generate Report")
        report_layout.addWidget(self.btn_report)
        report_layout.addStretch()
        layout.addLayout(report_layout)

        self.btn_browse.clicked.connect(self._browse_config)
        self.btn_validate.clicked.connect(self._validate_config)
        self.btn_run.clicked.connect(self._run_test)
        self.btn_list.clicked.connect(self._list_sessions)

    def _browse_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Config", "", "YAML/JSON (*.yaml *.yml *.json)")
        if path:
            self.config_path.setText(path)

    def _validate_config(self):
        path = self.config_path.text().strip()
        if path:
            self._run_cli(['python', '-m', 'cli.bt_test.cli', 'config', path])

    def _run_test(self):
        args = ['python', '-m', 'cli.bt_test.cli', 'run']
        path = self.config_path.text().strip()
        if path:
            args.append(path)
        else:
            args.extend(['--name', self.test_name.text() or 'QuickTest'])
        self._run_cli(args)

    def _list_sessions(self):
        self._run_cli(['python', '-m', 'cli.bt_test.cli', 'list'])

    def _run_cli(self, cmd):
        worker = CliWorker(cmd)
        worker.finished.connect(self._on_result)
        worker.error.connect(lambda e: self._append(f"Error: {e}"))
        worker.start()

    def _on_result(self, output):
        self._append(output)
        # Parse sessions list into table
        self.session_table.setRowCount(0)
        for line in output.split('\n'):
            if line.strip() and not line.startswith('-') and not line.startswith('Session') and not line.startswith('No'):
                parts = line.split()
                if len(parts) >= 4:
                    row = self.session_table.rowCount()
                    self.session_table.insertRow(row)
                    for i, p in enumerate(parts[:6]):
                        self.session_table.setItem(row, i, QTableWidgetItem(p))

    def _append(self, text):
        if hasattr(self.parent(), '_log'):
            self.parent()._log.append(text)


# ==================== 日志面板 ====================

class LogPanel(QWidget):
    """日志浏览标签页"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Log File:"))
        self.log_path = QLineEdit()
        self.log_path.setPlaceholderText("Path to btsnoop or logcat file...")
        ctrl.addWidget(self.log_path)
        self.btn_browse = QPushButton("Browse")
        ctrl.addWidget(self.btn_browse)
        self.btn_parse = QPushButton("Parse")
        ctrl.addWidget(self.btn_parse)
        self.btn_analyze = QPushButton("Analyze")
        ctrl.addWidget(self.btn_analyze)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # Results
        splitter = QSplitter(Qt.Vertical)

        self.entry_table = QTableWidget()
        self.entry_table.setColumnCount(3)
        self.entry_table.setHorizontalHeaderLabels(["Timestamp", "Level", "Message"])
        self.entry_table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.entry_table)

        self.analysis_output = QTextEdit()
        self.analysis_output.setReadOnly(True)
        self.analysis_output.setMaximumHeight(150)
        splitter.addWidget(self.analysis_output)

        layout.addWidget(splitter)

        self.btn_browse.clicked.connect(self._browse)
        self.btn_parse.clicked.connect(self._parse)
        self.btn_analyze.clicked.connect(self._analyze)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Log File")
        if path:
            self.log_path.setText(path)

    def _parse(self):
        path = self.log_path.text().strip()
        if not path:
            return
        self.entry_table.setRowCount(0)
        self._run(['python', '-m', 'cli.bt_logger.cli', 'parse', path])

    def _analyze(self):
        path = self.log_path.text().strip()
        if not path:
            return
        self._run(['python', '-m', 'cli.bt_logger.cli', 'analyze', path])

    def _run(self, cmd):
        worker = CliWorker(cmd)
        worker.finished.connect(self._on_result)
        worker.error.connect(lambda e: self.analysis_output.append(f"Error: {e}"))
        worker.start()

    def _on_result(self, output):
        self.analysis_output.append(output)
        # Try to parse entries into table
        parsing = False
        for line in output.split('\n'):
            if '总条目数' in line or 'Total' in line:
                parsing = True
                continue
            if parsing and '[' in line and ']' in line:
                row = self.entry_table.rowCount()
                self.entry_table.insertRow(row)
                self.entry_table.setItem(row, 2, QTableWidgetItem(line.strip()[:200]))


# ==================== LOG 输出面板 ====================

class LogOutput(QTextEdit):
    """统一的日志输出面板"""
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 9))
        self.setMaximumHeight(200)
        self.append("=== Bluetooth Auto Test Platform ===\n")

    def append(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        super().append(f"[{ts}] {text}")


# ==================== 主窗口 ====================

class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bluetooth Auto Test Platform")
        self.setMinimumSize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Tabs
        self.tabs = QTabWidget()
        self.tab_device = DevicePanel()
        self.tab_test = TestPanel()
        self.tab_log = LogPanel()
        self.tabs.addTab(self.tab_device, "Devices")
        self.tabs.addTab(self.tab_test, "Test")
        self.tabs.addTab(self.tab_log, "Logs")
        layout.addWidget(self.tabs)

        # Log output
        self._log = LogOutput()
        layout.addWidget(self._log)

        # Status bar
        self.statusBar().showMessage("Ready")

        # Back-reference for child panels
        self.tab_device.parent = lambda: self
        self.tab_test.parent = lambda: self
        self.tab_log.parent = lambda: self

    def log(self, text: str):
        self._log.append(text)
        self.statusBar().showMessage(text[:60])


# ==================== 入口 ====================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
