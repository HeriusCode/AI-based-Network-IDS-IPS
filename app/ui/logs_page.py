"""Persisted traffic session history."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controller import AppController
from app.ui.widgets import Card, format_bytes


class LogsPage(QWidget):
    HEADERS = (
        "Bắt đầu",
        "Kết thúc",
        "Destination",
        "Protocol",
        "Scenario",
        "Packets",
        "Bytes",
        "Status",
    )

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.rows: list[dict] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(16)
        title = QLabel("Logs")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Lịch sử phiên kiểm thử được lưu trong SQLite cục bộ")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        panel = Card("Traffic Session History")
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm session ID, IP hoặc scenario...")
        self.protocol = QComboBox()
        self.protocol.addItems(["Tất cả", "TCP", "UDP", "ICMP"])
        self.status = QComboBox()
        self.status.addItems(["Tất cả", "Completed", "Stopped", "Error"])
        refresh = QPushButton("Refresh")
        export = QPushButton("Export CSV")
        export.setObjectName("primaryButton")
        clear = QPushButton("Clear Logs")
        clear.setObjectName("dangerButton")
        tools.addWidget(self.search, 1)
        tools.addWidget(self.protocol)
        tools.addWidget(self.status)
        tools.addWidget(refresh)
        tools.addWidget(export)
        tools.addWidget(clear)
        panel.box.addLayout(tools)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        panel.box.addWidget(self.table, 1)
        self.count = QLabel("0 phiên")
        self.count.setObjectName("muted")
        panel.box.addWidget(self.count)
        root.addWidget(panel, 1)

        self.search.textChanged.connect(self.load_rows)
        self.protocol.currentTextChanged.connect(self.load_rows)
        self.status.currentTextChanged.connect(self.load_rows)
        refresh.clicked.connect(self.load_rows)
        export.clicked.connect(self.export_csv)
        clear.clicked.connect(self.clear_logs)
        controller.logs_changed.connect(self.load_rows)
        self.load_rows()

    def load_rows(self) -> None:
        self.rows = self.controller.log_service.list_sessions(
            self.search.text(), self.protocol.currentText(), self.status.currentText()
        )
        self.table.setRowCount(len(self.rows))
        for row_index, row in enumerate(self.rows):
            values = (
                row["started_at"].replace("T", " "),
                row["ended_at"].replace("T", " "),
                f"{row['destination_ip']}:{row['destination_port']}",
                row["protocol"],
                row["scenario"],
                f"{row['total_packets']:,}",
                format_bytes(row["total_bytes"]),
                row["status"],
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, item)
        self.count.setText(f"{len(self.rows)} phiên")

    def export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Xuất CSV", "traffic_sessions.csv", "CSV (*.csv)")
        if not path:
            return
        self.controller.log_service.export_csv(Path(path), self.rows)

    def clear_logs(self) -> None:
        answer = QMessageBox.question(
            self,
            "Xóa lịch sử",
            "Xóa toàn bộ lịch sử phiên traffic? Thao tác này không thể hoàn tác.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.controller.log_service.clear()
            self.load_rows()
