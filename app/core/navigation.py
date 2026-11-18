"""Single source of truth for application navigation."""

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
            ("Thẻ chỉ số", "Biểu đồ lưu lượng", "Cảnh báo gần đây"), "Bước 2"),
    NavItem("monitoring", "Giám sát mạng", "activity", "Luồng mạng và trạng thái giao diện mạng.",
            ("Biểu đồ gói tin", "Bảng luồng", "Bộ lọc giao thức"), "Bước 3"),
    NavItem("detection", "Phát hiện bất thường", "shield", "Kết quả phát hiện bất thường mô phỏng.",
            ("Kết quả phát hiện", "Bộ lọc rủi ro", "Trạng thái mô hình"), "Bước 4"),
    NavItem("prediction", "Dự đoán lưu lượng", "trend", "Dự báo xu hướng lưu lượng mô phỏng.",
            ("Biểu đồ dự báo", "Khoảng dự đoán", "Mức độ rủi ro"), "Bước 4"),
    NavItem("mitigation", "Giảm thiểu rủi ro (IPS)", "lock", "Quản lý chính sách giảm thiểu ở chế độ demo.",
            ("Quản lý quy tắc", "Lịch sử hành động", "Xác nhận thao tác"), "Bước 5"),
    NavItem("topology", "Sơ đồ mạng", "nodes", "Sơ đồ mạng SDN mô phỏng.",
            ("Các nút tương tác", "Thu phóng", "Chi tiết thiết bị"), "Bước 5"),
    NavItem("alerts", "Cảnh báo an ninh", "bell", "Danh sách cảnh báo và quy trình xem xét.",
            ("Tìm kiếm và lọc", "Chi tiết cảnh báo", "Xuất CSV"), "Bước 6"),
    NavItem("reports", "Báo cáo & Nhật ký", "document", "Lịch sử giám sát, sự kiện và nhật ký.",
            ("Lịch sử", "Bộ lọc ngày", "Xuất CSV"), "Bước 6"),
    NavItem("settings", "Cài đặt hệ thống", "settings", "Cấu hình ứng dụng và kết nối backend.",
            ("Cài đặt chung", "Cấu hình kết nối", "Lưu cục bộ"), "Bước 6"),
)
