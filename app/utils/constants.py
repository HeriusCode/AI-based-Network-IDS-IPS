"""Safety limits and shared constants."""

APP_NAME = "Traffic Generator"
APP_VERSION = "1.0.0"

MIN_DURATION = 5
MAX_DURATION = 120
MIN_PACKET_RATE = 1
MAX_PACKET_RATE = 1_000
MIN_PACKET_SIZE = 32
MAX_PACKET_SIZE = 1_472
MIN_CONNECTIONS = 1
MAX_CONNECTIONS = 50
MIN_PORT = 1
MAX_PORT = 65_535

DEFAULT_ALLOWED_NETWORKS = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
]
DEFAULT_APPROVED_PORTS = [22, 53, 80, 443, 8000, 8080]
SUPPORTED_PROTOCOLS = ("TCP", "UDP", "ICMP")
PORT_SCAN_PORTS = (22, 53, 80, 443, 8000, 8080)
SCENARIO_PROTOCOLS = {
    "NORMAL": ("TCP", "UDP", "ICMP"),
    "CUSTOM": ("TCP", "UDP", "ICMP"),
    "DOS": ("TCP",),
    "DDOS": ("UDP",),
    "PORT_SCAN": ("TCP",),
    "BRUTE_FORCE": ("TCP",),
    "WEB_ATTACK": ("TCP",),
}
CUSTOM_PATTERNS = ("CONSTANT", "RATE_BURST", "CONNECTION_BURST")
SUPPORTED_SCENARIOS = tuple(SCENARIO_PROTOCOLS)
SCENARIO_PRESETS = {
    "NORMAL": {
        "title": "Normal Traffic", "protocol": "TCP", "duration": 5,
        "packet_rate": 10, "packet_size": 64, "connections": 1,
        "source": "h1", "target": "h3", "port": 8000, "color": "#34D399",
        "expected_label": "Normal / Benign",
        "description": "TCP/UDP/ICMP ổn định để tạo mốc lưu lượng bình thường.",
    },
    "CUSTOM": {
        "title": "Custom Traffic", "protocol": "TCP", "duration": 10,
        "packet_rate": 25, "packet_size": 256, "connections": 5,
        "source": "h1", "target": "h3", "port": 8000, "color": "#2DD4BF",
        "expected_label": "Phụ thuộc cấu hình AI",
        "description": "Tự chọn host, protocol, port, tốc độ, kích thước và kiểu phát lưu lượng trong Mininet.",
    },
    "DOS": {
        "title": "DoS Simulation", "protocol": "TCP", "duration": 5,
        "packet_rate": 100, "packet_size": 40, "connections": 1,
        "source": "h1", "target": "h3", "port": 80, "color": "#FB7185",
        "expected_label": "DoS",
        "description": "Mô phỏng DoS bằng TCP SYN dồn dập từ một host, có giới hạn an toàn.",
    },
    "DDOS": {
        "title": "DDoS Simulation", "protocol": "UDP", "duration": 5,
        "packet_rate": 200, "packet_size": 512, "connections": 1,
        "source": "h2", "target": "h3", "port": 53, "color": "#FBBF24",
        "expected_label": "DDoS",
        "description": "Hai host Mininet phối hợp gửi UDP burst tới cùng một đích, có giới hạn an toàn.",
    },
    "PORT_SCAN": {
        "title": "Port Scan Simulation", "protocol": "TCP", "duration": 10,
        "packet_rate": 6, "packet_size": 40, "connections": 1,
        "source": "h1", "target": "h3", "port": 8080, "color": "#60A5FA",
        "expected_label": "Port Scan",
        "description": "Thử kết nối các port lab được phê duyệt, tối đa sáu port.",
    },
    "BRUTE_FORCE": {
        "title": "Brute Force Simulation", "protocol": "TCP", "duration": 8,
        "packet_rate": 12, "packet_size": 96, "connections": 1, "port": 22,
        "source": "h1", "target": "h3", "color": "#C084FC",
        "expected_label": "Brute Force",
        "description": "Gửi nhiều lần đăng nhập giả lập tới dịch vụ lab trên TCP/22.",
    },
    "WEB_ATTACK": {
        "title": "Web Attack Simulation", "protocol": "TCP", "duration": 8,
        "packet_rate": 10, "packet_size": 256, "connections": 1, "port": 8080,
        "source": "h1", "target": "h3", "color": "#F472B6",
        "expected_label": "Web Attack",
        "description": "Gửi HTTP request chứa chuỗi SQLi/XSS mẫu tới web receiver trong Mininet.",
    },
}

STATUS_IDLE = "Idle"
STATUS_PREPARING = "Preparing"
STATUS_RUNNING = "Running"
STATUS_STOPPED = "Stopped"
STATUS_COMPLETED = "Completed"
STATUS_ERROR = "Error"
