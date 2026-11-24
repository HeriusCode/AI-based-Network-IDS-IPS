# Traffic Generator

Ứng dụng Desktop PySide6 độc lập dùng để tạo lưu lượng TCP, UDP và ICMP có giới hạn trong mạng lab, phục vụ kiểm thử hệ thống AI-based Network IDS/IPS.

## Tính năng đã triển khai

- Dashboard realtime: trạng thái kết nối, target API/traffic, packet, byte, protocol, scenario và trạng thái phiên.
- Bốn biểu đồ Dashboard: packet/s, byte/s, traffic timeline và protocol distribution.
- Kiểm tra Máy 2 qua `GET /api/health` trên worker nền.
- Traffic Engine thực tế bằng Python socket, không thực thi shell command từ giao diện.
- TCP stream, UDP datagram, ICMP Echo Request (ICMP cần quyền Administrator trên Windows).
- Sáu kịch bản: Normal Traffic, SYN Flood Simulation, UDP Flood Simulation,
  ICMP Flood Simulation, Port Scan Simulation và TCP Connection Burst.
- START, STOP tức thời, RESET và kiểm tra cấu hình trước khi chạy.
- Thống kê realtime và biểu đồ PyQtGraph.
- Lưu lịch sử phiên vào SQLite, tìm kiếm/lọc/xóa/xuất CSV.
- Cấu hình mặc định, mạng lab và port được phê duyệt trong `data/config.json`.
- API Client tách riêng cho các endpoint tích hợp dự kiến của Máy 2.
- Điều khiển traffic h1/h2/h3 trong VM qua SSH key và Mininet agent chỉ nghe trên localhost của VM.

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
- Traffic Mininet chỉ chạy giữa hai host khác nhau trong `h1/h2/h3`; SSH key xác thực và agent giới hạn cùng một phiên, 120 giây, 1.000 lần gửi/s.
- Các kịch bản mô phỏng tấn công chỉ chạy giữa hai host Mininet. SYN dùng IP nguồn
  thật của host, không giả mạo IP; Port Scan chỉ thử các port lab được phê duyệt
  trong `22, 53, 80, 443, 8000, 8080`.

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

1. Vào **Connection Settings**, nhập IP Máy 2 và API port, nhấn **Test Connection**. Nếu dùng Mininet, kiểm tra riêng **Test Mininet VM**.
2. Vào **Settings**, xác nhận mạng lab và port được phép.
3. Mở **Traffic Generator**, chọn `Local/Local` để phát từ Windows hoặc chọn hai host `h1/h2/h3` khác nhau để phát trong VM. Khi chọn host Mininet làm đích, IP đích được điền tự động.

Trong **Traffic Scenarios**, nút **Chọn kịch bản** nạp giao thức, host và thông
số demo vào form. Có thể điều chỉnh thời lượng/tốc độ trong giới hạn trước khi
nhấn **START**:

| Kịch bản | Cách phát trên VM | Preset |
| --- | --- | --- |
| Normal Traffic | h1 → h3, TCP/8000 mặc định | 10 packet/s, 64 byte, 5 giây |
| DoS Simulation | h1 → h3, TCP SYN/80 | 100 SYN/s, 5 giây |
| DDoS Simulation | h1+h2 → h3, UDP/53 | 200 packet/s tổng, 512 byte, 5 giây |
| Port Scan Simulation | h1 → h3, tối đa sáu port lab | 6 lần/s, 10 giây |
| Brute Force Simulation | h1 → h3, TCP/22 | 12 lần/s, 8 giây |
| Web Attack Simulation | h1 → h3, TCP/8080 | 10 request/s, 8 giây |
| Custom Traffic | Tự chọn host, protocol, port và pattern | Vẫn chịu mọi giới hạn lab |

Custom hỗ trợ `Constant Stream` cho TCP/UDP/ICMP, `Rate Burst` cho UDP/ICMP và
`Connection Burst` cho TCP. Có thể tự chỉnh host nguồn/đích, port, packet rate,
packet size, thời lượng và số kết nối trong giới hạn tối đa 1.000 packet/s,
120 giây, 1.472 byte và 50 kết nối.

Tên kịch bản chỉ mô tả traffic được phát. Model AI vẫn quyết định BENIGN/ATTACK
từ đặc trưng flow, không ép nhãn theo tên preset.
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

Ứng dụng dùng `/api/health` để kiểm tra kết nối và `POST /api/flows` để chuyển
flow Mininet đã bắt tới IDS/IPS. Các endpoint điều khiển traffic phía IDS/IPS
không được tự động giả định là đã có.

### Mininet VM agent

Agent nằm trong `vm_agent/`, chạy riêng trên VM và chỉ bind `127.0.0.1:9000`.
Traffic Generator tự dùng khóa ở `~/.ssh/traffic-generator-vm` để mở SSH tunnel;
khóa công khai cần có trong `~root/.ssh/authorized_keys` trên VM. Giao diện chỉ
cần IP VM, SSH user và cổng agent trong **Connection Settings**.

Triển khai từ Windows sau khi VM đã có Python venv `~/ai-network-ids-ips/api-venv`:

```powershell
ssh root@192.168.201.130 'mkdir -p ~/ai-network-ids-ips/vm_agent'
scp vm_agent/mininet_agent.py vm_agent/mininet_worker.py vm_agent/mininet_capture.py root@192.168.201.130:~/ai-network-ids-ips/vm_agent/
scp vm_agent/mininet-traffic-agent.service root@192.168.201.130:/etc/systemd/system/
ssh root@192.168.201.130 'systemctl daemon-reload && systemctl enable --now mininet-traffic-agent'
```

Khởi chạy OS-Ken và `topology.py` như hướng dẫn bên dưới, rồi nhấn **Test Mininet VM**.
Với TCP/UDP, agent mở receiver tạm trên host đích, phát từ host nguồn và dọn receiver
khi phiên kết thúc. UI hiển thị số byte receiver nhận. ICMP dùng Echo Request và
không cần receiver ứng dụng.

Đây là traffic **nội bộ Mininet qua OVS**. Agent bắt packet thật trên veth của
host nguồn (`h1-eth0`/`h2-eth0`/`h3-eth0`), tổng hợp flow theo 5-tuple và
trả flow qua SSH tunnel cho Traffic Generator. Traffic Generator chuyển flow
tới `POST /api/flows` của IDS/IPS; IDS/IPS gọi AI API `/detect` và cập nhật
trang **Phát hiện bất thường** theo thời gian chạy. Host Mininet không cần route
trực tiếp tới `192.168.1.21` vì kênh quản lý chuyển kết quả flow qua VM host.

Đặc trưng packet có cùng 77 tên cột với model nhưng được tính bằng extractor
nhẹ, **xấp xỉ CICFlowMeter**. Kết quả AI live chỉ dùng cho demo và có thể lệch
so với đánh giá trên CIC-IDS2018. Một phiên báo lỗi nếu không bắt được packet
hoặc IDS/IPS không phân tích được flow; trạng thái Connected chỉ xác nhận API.

Nếu đặt `IDS_INGEST_TOKEN` cho IDS/IPS, đặt cùng giá trị vào
`TRAFFIC_GENERATOR_API_KEY` trước khi chạy Traffic Generator. Khi không đặt
token, IDS/IPS chỉ nhận flow từ cùng máy Windows.

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
