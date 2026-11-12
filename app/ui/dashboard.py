"""Live overview page."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.controller import AppController
from app.ui.widgets import Card, LivePlot, MetricCard, ProtocolBarChart, StatusPill, format_bytes
from app.utils.network import primary_local_ipv4


class DashboardPage(QScrollArea):
    open_generator = Signal()

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.setObjectName("dashboardScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("dashboardContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(16)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Tổng quan kết nối và phiên tạo lưu lượng đang chạy")
        subtitle.setObjectName("pageSubtitle")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch()
        quick = QPushButton("Quick Start")
        quick.setObjectName("primaryButton")
        quick.clicked.connect(self.open_generator)
        stop = QPushButton("STOP")
        stop.setObjectName("dangerButton")
        stop.clicked.connect(controller.stop_traffic)
        header.addWidget(quick)
        header.addWidget(stop)
        root.addLayout(header)

        metrics = QGridLayout()
        metrics.setSpacing(12)
        cfg = controller.config_manager.config
        self.connection_card = MetricCard("Connection Status", "Disconnected", "#94A3B8", "Chưa kiểm tra Máy 2")
        self.server_ip_card = MetricCard("IDS/IPS Server IP", cfg.server_ip, "#60A5FA", "Máy 2")
        self.server_port_card = MetricCard("API Server Port", str(cfg.api_port), "#A78BFA", "REST management")
        self.local_ip_card = MetricCard("Local Machine IP", primary_local_ipv4(), "#38BDF8", "Máy 1 · tự động")
        self.target_card = MetricCard("Target", "—", "#38BDF8", "IP và traffic port")
        self.packets_card = MetricCard("Total Packets Sent", "0", "#34D399", "0 packet/s")
        self.bytes_card = MetricCard("Total Bytes Sent", "0 B", "#A78BFA", "0 B/s")
        self.protocol_card = MetricCard("Current Protocol", "—", "#FBBF24", "Chưa có phiên")
        self.scenario_card = MetricCard("Current Scenario", "—", "#FB7185", "Chưa có phiên")
        for index, card in enumerate(
            (
                self.connection_card,
                self.server_ip_card,
                self.server_port_card,
                self.local_ip_card,
                self.target_card,
                self.packets_card,
                self.bytes_card,
                self.protocol_card,
                self.scenario_card,
            )
        ):
            metrics.addWidget(card, index // 3, index % 3)
            metrics.setColumnStretch(index % 3, 1)
        root.addLayout(metrics)

        charts = QGridLayout()
        charts.setSpacing(12)
        self.packet_plot = LivePlot("Packets per Second", "#38BDF8")
        self.byte_plot = LivePlot("Bytes per Second", "#34D399")
        self.timeline_plot = LivePlot("Traffic Over Time (total packets)", "#FBBF24")
        self.protocol_plot = ProtocolBarChart()
        for plot in (self.packet_plot, self.byte_plot, self.timeline_plot, self.protocol_plot):
            plot.setMinimumHeight(175)
        charts.addWidget(self.packet_plot, 0, 0)
        charts.addWidget(self.byte_plot, 0, 1)
        charts.addWidget(self.timeline_plot, 1, 0)
        charts.addWidget(self.protocol_plot, 1, 1)
        charts.setColumnStretch(0, 1)
        charts.setColumnStretch(1, 1)
        root.addLayout(charts, 1)

        status_card = Card("Traffic Generation Status")
        status_row = QHBoxLayout()
        self.status_pill = StatusPill(controller.current_status)
        self.elapsed = QLabel("Thời gian: 0.0 giây")
        self.elapsed.setObjectName("muted")
        status_row.addWidget(self.status_pill)
        status_row.addWidget(self.elapsed)
        status_row.addStretch()
        status_card.box.addLayout(status_row)
        root.addWidget(status_card)

        controller.stats_updated.connect(self.update_stats)
        controller.traffic_status_changed.connect(self.status_pill.set_status)
        controller.connection_changed.connect(self.update_connection)
        controller.configuration_changed.connect(self.refresh_server_config)
        controller.session_finished.connect(lambda _: self.refresh_config())
        self.setWidget(content)

    def refresh_config(self) -> None:
        config = self.controller.last_config
        if config is None:
            return
        self.target_card.set_value(f"{config.destination_ip}:{config.destination_port}")
        self.protocol_card.set_value(config.protocol)
        self.scenario_card.set_value(config.scenario.replace("_", " "))

    def update_connection(self, connected: bool, message: str) -> None:
        self.connection_card.set_value("Connected" if connected else "Disconnected", message)
        self.refresh_server_config()

    def refresh_server_config(self) -> None:
        cfg = self.controller.config_manager.config
        self.server_ip_card.set_value(cfg.server_ip, "Máy 2 · AI-based IDS/IPS")
        self.server_port_card.set_value(str(cfg.api_port), "REST management")
        self.local_ip_card.set_value(primary_local_ipv4(), "Máy 1 · tự động")

    def update_stats(self, stats: dict) -> None:
        self.refresh_config()
        pps = float(stats.get("packets_per_second", 0))
        bps = float(stats.get("bytes_per_second", 0))
        self.packets_card.set_value(f"{int(stats.get('total_packets', 0)):,}", f"{pps:,.1f} packet/s")
        self.bytes_card.set_value(format_bytes(float(stats.get("total_bytes", 0))), f"{format_bytes(bps)}/s")
        self.packet_plot.append(pps)
        self.byte_plot.append(bps)
        total_packets = int(stats.get("total_packets", 0))
        self.timeline_plot.append(total_packets)
        config = self.controller.last_config
        if config is not None:
            self.protocol_plot.set_protocol_value(config.protocol, total_packets)
        self.elapsed.setText(f"Thời gian: {float(stats.get('elapsed_seconds', 0)):.1f} giây")
