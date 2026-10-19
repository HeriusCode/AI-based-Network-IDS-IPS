"""Single source of truth for the desktop navigation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    key: str
    title: str
    icon: str
    description: str
    planned_features: tuple[str, ...]
    phase: str


NAV_ITEMS = (
    NavItem("dashboard", "Dashboard", "dashboard", "Tổng quan giám sát và tình trạng bảo mật.",
            ("Metric cards", "Traffic charts", "Recent alerts"), "Bước 2"),
    NavItem("monitoring", "Network Monitoring", "activity", "Luồng mạng và trạng thái giao diện mạng.",
            ("Packet / byte charts", "Flow table", "Protocol filters"), "Bước 3"),
    NavItem("detection", "AI Detection", "shield", "Kết quả phát hiện bất thường mô phỏng.",
            ("Detection results", "Risk filters", "Model status"), "Bước 4"),
    NavItem("prediction", "AI Prediction", "trend", "Dự báo xu hướng lưu lượng mô phỏng.",
            ("Forecast chart", "Prediction horizons", "Risk level"), "Bước 4"),
    NavItem("mitigation", "IPS Mitigation", "lock", "Quản lý chính sách giảm thiểu ở chế độ demo.",
            ("Rule management", "Action history", "Validation dialog"), "Bước 5"),
    NavItem("topology", "Network Topology", "nodes", "Sơ đồ mạng SDN mô phỏng.",
            ("Interactive nodes", "Zoom and pan", "Device details"), "Bước 5"),
    NavItem("alerts", "Security Alerts", "bell", "Danh sách cảnh báo và quy trình xem xét.",
            ("Search and filter", "Alert details", "CSV export"), "Bước 6"),
    NavItem("reports", "Reports & Logs", "document", "Lịch sử giám sát, sự kiện và nhật ký.",
            ("History views", "Date filters", "CSV export"), "Bước 6"),
    NavItem("settings", "Settings", "settings", "Cấu hình ứng dụng và kết nối backend tương lai.",
            ("General settings", "Connection settings", "Local persistence"), "Bước 6"),
)
