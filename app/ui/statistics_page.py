"""Realtime statistics page."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.controller import AppController
from app.ui.widgets import LivePlot, MetricCard, format_bytes


class StatisticsPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(16)
        title = QLabel("Traffic Statistics")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Thống kê trực tiếp từ Traffic Engine, không sử dụng dữ liệu mô phỏng")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        metrics = QGridLayout()
        metrics.setSpacing(12)
        self.cards = {
            "total_packets": MetricCard("Total Packets Sent", "0", "#38BDF8"),
            "total_bytes": MetricCard("Total Bytes Sent", "0 B", "#34D399"),
            "packets_per_second": MetricCard("Packets per Second", "0", "#A78BFA"),
            "bytes_per_second": MetricCard("Bytes per Second", "0 B/s", "#FBBF24"),
            "successful_connections": MetricCard("Successful Connections", "0", "#22C55E"),
            "failed_connections": MetricCard("Failed Connections", "0", "#FB7185"),
            "elapsed_seconds": MetricCard("Traffic Duration", "0.0 s", "#60A5FA"),
        }
        for index, card in enumerate(self.cards.values()):
            metrics.addWidget(card, index // 4, index % 4)
            metrics.setColumnStretch(index % 4, 1)
        root.addLayout(metrics)

        charts = QHBoxLayout()
        self.packet_plot = LivePlot("Packet Rate Chart", "#38BDF8")
        self.bandwidth_plot = LivePlot("Bandwidth Chart (byte/s)", "#34D399")
        self.timeline_plot = LivePlot("Traffic Timeline (total packets)", "#FBBF24")
        self.packet_plot.setMinimumHeight(300)
        self.bandwidth_plot.setMinimumHeight(300)
        self.timeline_plot.setMinimumHeight(300)
        charts.addWidget(self.packet_plot, 1)
        charts.addWidget(self.bandwidth_plot, 1)
        charts.addWidget(self.timeline_plot, 1)
        root.addLayout(charts, 1)
        controller.stats_updated.connect(self.update_stats)

    def update_stats(self, stats: dict) -> None:
        pps = float(stats.get("packets_per_second", 0))
        bps = float(stats.get("bytes_per_second", 0))
        self.cards["total_packets"].set_value(f"{int(stats.get('total_packets', 0)):,}")
        self.cards["total_bytes"].set_value(format_bytes(float(stats.get("total_bytes", 0))))
        self.cards["packets_per_second"].set_value(f"{pps:,.1f}")
        self.cards["bytes_per_second"].set_value(f"{format_bytes(bps)}/s")
        self.cards["successful_connections"].set_value(str(int(stats.get("successful_connections", 0))))
        self.cards["failed_connections"].set_value(str(int(stats.get("failed_connections", 0))))
        self.cards["elapsed_seconds"].set_value(f"{float(stats.get('elapsed_seconds', 0)):.1f} s")
        self.packet_plot.append(pps)
        self.bandwidth_plot.append(bps)
        self.timeline_plot.append(float(stats.get("total_packets", 0)))
