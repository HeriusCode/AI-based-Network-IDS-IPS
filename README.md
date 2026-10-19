# AI Network IDS/IPS — Desktop Demo

Ứng dụng desktop PySide6 cho đồ án giám sát mạng. Hiện dự án hoàn thành **Bước 1**: khung cửa sổ, điều hướng, topbar và giao diện tối. Mọi trang nghiệp vụ đang là màn hình chờ ghi rõ giai đoạn triển khai. Không có kết nối mạng, mô hình AI hay quy tắc chặn lưu lượng đang hoạt động.

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

## Cấu trúc

- `main.py`: khởi chạy Qt và áp dụng theme.
- `app/core/`: tên ứng dụng, bảng màu, cấu hình điều hướng và tải theme.
- `app/ui/`: cửa sổ, sidebar, topbar, icon SVG và trang chờ.
- `app/assets/styles/dark.qss`: giao diện tối.
- `app/services/`, `app/models/`: vị trí dành cho adapter dữ liệu và model ở các bước sau.

## Đã có ở Bước 1

- Điều hướng qua 9 mục, tô sáng mục hiện tại và thu gọn sidebar.
- Topbar có tiêu đề trang, đồng hồ địa phương, trạng thái demo/backend và nút thông báo/Settings.
- Trang chờ cuộn được, ghi rõ tính năng dự kiến và chưa có dữ liệu thực.

## Tiếp theo

Bước 2 sẽ xây dựng Dashboard với metric cards, biểu đồ PyQtGraph và danh sách cảnh báo mô phỏng. Các giá trị demo phải luôn được ghi nhãn rõ ràng.
