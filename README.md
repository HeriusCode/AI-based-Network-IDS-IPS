# AI Network IDS/IPS — Desktop Demo

Ứng dụng desktop PySide6 cho đồ án giám sát mạng. Trang **Phát hiện bất thường**
hỗ trợ phân tích CSV và nhận flow live từ Traffic Generator/Mininet.

## Model Mininet live

Ứng dụng nhận 77 đặc trưng flow từ Traffic Generator, gọi detector nhị phân và
chỉ gọi model loại tấn công cho flow được gắn nhãn ATTACK. Trang Dự đoán lưu
lượng dùng lịch sử packet/byte rate được tổng hợp từ chính các flow Mininet và
gọi `/forecast/traffic` theo chu kỳ. Model hiện tại dự báo ba bước, mỗi bước một
giây; cần khởi động lại UI sau khi cập nhật mã để nạp trang dự báo mới.

## Yêu cầu

- Python 3.11+
- Windows, macOS hoặc Linux có môi trường desktop hỗ trợ Qt

## Cài đặt và chạy

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Trên macOS/Linux, thay lệnh kích hoạt bằng `source .venv/bin/activate`.

### Cấu hình riêng cho từng máy

Ứng dụng không đọc IP và mật khẩu runtime từ repository. Mỗi máy lưu cấu hình
trong thư mục người dùng (`%LOCALAPPDATA%\AI-based Network IDS-IPS` trên
Windows hoặc `~/.config/ai-network-ids-ips` trên Linux). Có thể đổi thư mục bằng
`IDS_IPS_CONFIG_DIR`.

Trước lần đăng nhập đầu tiên, sao chép `db_config.example.json` thành
`db_config.json` trong thư mục trên và điền PostgreSQL/Supabase của môi trường.
Ngoài ra có thể dùng `IDS_DB_CONFIG` để trỏ tới file khác hoặc đặt các biến
`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

Endpoint nhận flow tự chọn IPv4 đang hoạt động của máy và tự khởi động sau khi
đăng nhập. Nếu DHCP làm IP thay đổi, cấu hình cũ sẽ bị bỏ qua ở lần chạy kế tiếp.
Có thể đặt `IDS_SERVER_CONFIG` nếu muốn dùng một file cấu hình cụ thể.

## Cấu trúc

- `main.py`: khởi chạy Qt và áp dụng theme.
- `app/core/`: tên ứng dụng, bảng màu, cấu hình điều hướng và tải theme.
- `app/ui/`: cửa sổ, sidebar, topbar, icon SVG và trang chờ.
- `app/assets/styles/dark.qss`: giao diện tối.
- `app/services/`, `app/models/`: vị trí dành cho adapter dữ liệu và model ở các bước sau.

## Flow live từ Mininet

Chạy AI API (mặc định `http://127.0.0.1:8000`) và mở IDS/IPS
server trên cổng quản lý đã cấu hình (ví dụ `192.168.1.21:8000`). Traffic
Generator gửi đặc trưng packet đã bắt từ Mininet tới `POST /api/flows` trên
server này. Server gọi `/detect` của AI API, giữ tối đa 500 flow gần nhất trong
bộ nhớ, và cập nhật trang **Phát hiện bất thường** cả với flow BENIGN lẫn ATTACK.
`GET /api/flows` cho phép kiểm tra kết quả gần nhất. Dữ liệu live không được lưu
sau khi đóng ứng dụng.

Khi không đặt `IDS_INGEST_TOKEN`, endpoint POST chỉ nhận từ máy chạy IDS/IPS.
Nếu dùng token, đặt cùng giá trị vào `TRAFFIC_GENERATOR_API_KEY` cho Traffic
Generator. Đặc trưng live xấp xỉ CICFlowMeter nên score AI chỉ phù hợp demo;
không xem nhãn ATTACK/BENIGN là kết luận bảo mật đã hiệu chuẩn.

## IPS qua OS-Ken và Open vSwitch

Tab **Giảm thiểu rủi ro (IPS)** kết nối tới Mininet agent ở VM qua SSH tunnel,
sau đó agent chuyển tiếp các endpoint cố định tới REST API loopback của OS-Ken.
OS-Ken cài rule OpenFlow 1.3 thật lên bridge `s1`:

- `Alert`: chỉ ghi audit log, không thay đổi traffic.
- `Block IP`: drop toàn bộ IPv4 từ một host Mininet.
- `Block Flow`: drop theo IP nguồn/đích, giao thức và cổng đích.
- `Rate Limit`: tạo OpenFlow meter rồi gắn meter vào flow.

Phạm vi được khóa ở `10.0.0.0/8`; thời hạn rule từ 5 giây đến 1 giờ và có thể
gỡ ngay trên UI. Chế độ tự động mặc định tắt. Khi bật, policy engine dùng kết
quả AI live: DoS/DDoS được rate-limit, Port Scan và Brute Force cần nhiều bằng
chứng trong cửa sổ thời gian, còn các flow Web/Botnet/Infiltration có độ tin cậy
cao được chặn theo flow. Kết quả chưa xác định hoặc score thấp chỉ tạo cảnh báo.

Cấu hình cũ mặc định là VM `192.168.201.130`, user `root`, agent `9000`, và
khóa `~/.ssh/traffic-generator-vm`. Có thể thay bằng các biến
`MININET_VM_IP`, `MININET_VM_USER`, `MININET_AGENT_PORT`,
`MININET_SSH_KEY` và `MININET_AGENT_URL`.

### Tự động phát hiện Tailscale, tunnel và VMware

Sau khi đăng nhập, trang **Cài đặt → Kết nối hệ thống** tự kiểm tra mỗi 30 giây
theo thứ tự:

1. Tunnel local tại `http://127.0.0.1:19000` hoặc `MININET_AGENT_URL`.
2. Peer Tailscale có hostname `duy-server` từ `tailscale status --json`.
3. IP cấu hình trong biến môi trường hoặc file Traffic Generator cục bộ.
4. VMware DHCP lease và ARP `192.168.201.x`.

Ứng dụng xác thực hostname, SSH key và health của Mininet agent; nó thử SSH user
trong `MININET_VM_USER`, rồi `trafficuser` và `root`. Khi dùng Tailscale,
IP Tailscale của máy IDS/IPS được chọn làm endpoint để Traffic Generator trên
máy khác kết nối. Nếu Traffic Generator nằm cùng máy, file
`Traffic Generator/data/config.json` cũng được đồng bộ; nếu không có file này,
việc tự cấu hình IDS/IPS vẫn tiếp tục bình thường.

Nút **Phát hiện & đồng bộ ngay** cho phép kiểm tra thủ công. Cổng OpenFlow
`6653` và REST `8080` của OS-Ken là kết nối nội bộ trong VM, không cần nhập
trong UI desktop.

## Đã có ở Bước 1

- Điều hướng qua 9 mục, tô sáng mục hiện tại và thu gọn sidebar.
- Topbar có tiêu đề trang, đồng hồ địa phương, trạng thái demo/backend và nút thông báo/Settings.
- Trang chờ cuộn được, ghi rõ tính năng dự kiến và chưa có dữ liệu thực.

## Tiếp theo

Bước 2 sẽ xây dựng Dashboard với metric cards, biểu đồ PyQtGraph và danh sách cảnh báo mô phỏng. Các giá trị demo phải luôn được ghi nhãn rõ ràng.
