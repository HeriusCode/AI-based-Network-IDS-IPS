# Traffic Generator

Ứng dụng Desktop PySide6 độc lập dùng để tạo lưu lượng TCP, UDP và ICMP có giới hạn trong mạng lab, phục vụ kiểm thử hệ thống AI-based Network IDS/IPS.

## Tính năng đã triển khai

- Dashboard realtime: trạng thái kết nối, target API/traffic, packet, byte, protocol, scenario và trạng thái phiên.
- Bốn biểu đồ Dashboard: packet/s, byte/s, traffic timeline và protocol distribution.
- Kiểm tra Máy 2 qua `GET /api/health` trên worker nền.
- Traffic Engine thực tế bằng Python socket, không thực thi shell command từ giao diện.
- TCP stream, UDP datagram, ICMP Echo Request (ICMP cần quyền Administrator trên Windows).
- Kịch bản `NORMAL`, `BURST`, `CONNECTION_BURST`, `CUSTOM`.
- START, STOP tức thời, RESET và kiểm tra cấu hình trước khi chạy.
- Thống kê realtime và biểu đồ PyQtGraph.
- Lưu lịch sử phiên vào SQLite, tìm kiếm/lọc/xóa/xuất CSV.
- Cấu hình mặc định, mạng lab và port được phê duyệt trong `data/config.json`.
- API Client tách riêng cho các endpoint tích hợp dự kiến của Máy 2.

Không có dữ liệu giả. Giao diện bắt đầu từ `0` và chỉ thay đổi khi có kết nối hoặc traffic thật.

## Giới hạn an toàn mặc định

- Chỉ IPv4 thuộc `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`.
- Port mặc định: `22, 53, 80, 443, 8000, 8080`.
- Tối đa 1.000 packet/s.
- Tối đa 120 giây mỗi phiên.
- Tối đa 1.472 byte mỗi packet.
- Tối đa 50 kết nối đồng thời trong Connection Burst.
- Một phiên chạy tại một thời điểm và tự dừng khi hết thời gian.
- API key chỉ đọc từ biến môi trường `TRAFFIC_GENERATOR_API_KEY`, không ghi plaintext.
- Host Mininet không được điều khiển trực tiếp từ Windows. Khi chọn `h1/h2/h3`, ứng dụng báo cần backend điều khiển đã xác thực trên Máy 2.

Chỉ mở rộng `allowed_networks` và `approved_ports` cho mạng lab mà bạn có quyền kiểm thử.

## Cài đặt

Yêu cầu Python 3.10 trở lên.

```powershell
cd "D:\Traffic Generator"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Chạy ứng dụng

```powershell
python main.py
```

Luồng sử dụng:

1. Vào **Connection Settings**, nhập IP Máy 2 và API port, nhấn **Test Connection**.
2. Vào **Settings**, xác nhận mạng lab và port được phép.
3. Mở **Traffic Generator**, nhập traffic destination và chọn protocol/scenario.
4. Nhấn **TEST**, sau đó **START**.
5. Theo dõi **Dashboard** hoặc **Traffic Statistics**; nhấn **STOP** khi cần.
6. Xem phiên đã lưu trong **Logs**.

## REST API Máy 2

`ApiClient` hỗ trợ các endpoint dự kiến:

- `GET /api/health`
- `POST /api/traffic/start`
- `POST /api/traffic/stop`
- `GET /api/traffic/status`
- `GET /api/traffic/statistics`

Ứng dụng chỉ sử dụng `/api/health` để kiểm tra kết nối. Các endpoint điều khiển không được tự động giả định là đã có; chúng sẵn sàng để nối vào backend thực tế sau này.

Thiết lập API key cho phiên PowerShell hiện tại:

```powershell
$env:TRAFFIC_GENERATOR_API_KEY = "your-lab-token"
python main.py
```

## Kiểm thử

```powershell
cd "D:\Traffic Generator"
python -m unittest discover -s tests -v
```

Test hiện có:

- Health API bằng HTTP server cục bộ.
- Từ chối IP công cộng ngoài lab.
- Phiên UDP cục bộ thực tế, thống kê packet và STOP trước thời hạn.

## Cấu trúc chính

```text
traffic-generator/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── config.py
│   ├── controller.py
│   ├── models/
│   │   ├── traffic_config.py
│   │   └── traffic_session.py
│   ├── services/
│   │   ├── api_client.py
│   │   ├── log_service.py
│   │   ├── statistics_service.py
│   │   ├── traffic_engine.py
│   │   └── traffic_worker.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── dashboard.py
│   │   ├── connection_page.py
│   │   ├── generator_page.py
│   │   ├── scenarios_page.py
│   │   ├── statistics_page.py
│   │   ├── logs_page.py
│   │   ├── settings_page.py
│   │   └── widgets.py
│   └── resources/styles/dark_theme.qss
├── data/
│   ├── config.json          # tạo khi người dùng lưu cấu hình
│   └── traffic_logs.db      # tạo tự động khi chạy
└── tests/
    ├── test_api_client.py
    └── test_traffic_engine.py
```

## Các giai đoạn đã hoàn thành

1. Cấu trúc dự án và shell giao diện.
2. Sidebar, Dashboard và 7 màn hình chức năng.
3. Connection Settings và API Client.
4. Traffic Engine và các kịch bản có giới hạn.
5. Thống kê và biểu đồ realtime.
6. SQLite logs, lọc, xóa và CSV.
7. Test kết nối local, kiểm tra safety validation và STOP.
8. README, lệnh cài đặt và hướng dẫn vận hành.

## Chạy máy ảo

1. Terminal 1 — Chạy OS-Ken Controller
cd ~/ai-network-ids-ips

source ~/sdn-venv/bin/activate

osken-manager --ofp-tcp-listen-port 6653 backend/controller/ids_controller.py

2. Terminal 2 — Chạy Mininet
cd ~/ai-network-ids-ips

sudo python3 topology.py

Lệnh	                            Chức năng
nodes	                            Xem các host và switch
net	                                Xem kết nối mạng
pingall	                            Ping giữa tất cả host
h1 ping -c 5 10.0.0.3	            Ping từ h1 đến h3
h2 ping -c 5 10.0.0.3	            Ping từ h2 đến h3
h1 ip addr	                        Xem IP của h1
exit	                            Thoát Mininet

3. Terminal 3 — Kiểm tra Open vSwitch
Xem trạng thái switch và Controller: sudo ovs-vsctl show
Xem bảng flow: sudo ovs-ofctl -O OpenFlow13 dump-flows s1
