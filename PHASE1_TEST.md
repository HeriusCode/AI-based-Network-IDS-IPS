# Kiem thu tich hop AI - Giai doan 1

Giai doan nay dung file CSV de kiem tra duong di day du:

`CSV -> giao dien PySide6 -> AI API -> detection/classification -> bang va bieu do`

Day la buoc kiem thu offline. Du lieu live tu Mininet va SDN Controller chua duoc noi truc tiep vao giao dien.

## 1. Khoi dong AI API

```powershell
cd D:\AI-Network-IDS
.\.venv\Scripts\Activate.ps1
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Kiem tra `http://127.0.0.1:8000/health`. API san sang khi tra ve HTTP 200.

## 2. Khoi dong giao dien

Mo terminal khac:

```powershell
cd "D:\AI-based Network IDS_IPS"
.\.venv\Scripts\Activate.ps1
python main.py
```

Neu API chay tai dia chi khac, dat bien moi truong truoc khi mo giao dien:

```powershell
$env:IDS_AI_API_URL = "http://127.0.0.1:8000"
python main.py
```

## 3. Chay kiem thu

1. Mo trang **Detection**.
2. Dam bao trang thai hien **AI Backend Online**.
3. Bam **Chon CSV kiem thu**.
4. Co the chon file mau:

```text
D:\AI-Network-IDS\data\cicids2017\raw_metadata\Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv
```

5. Cho den khi giao dien bao phan tich hoan tat.

Moi lan chay chi doc toi da 20.000 dong dau, gui theo batch 500 flow va hien toi da 1.000 canh bao. Gioi han nay giup giao dien khong bi treo khi chon file CSV lon.

## Ket qua tham chieu

Voi file DDoS o tren, lan kiem thu hien tai cho ket qua:

- Tong flow: 20.000
- Benign: 19.702
- Attack: 298
- Canh bao muc cao: 9
- Thoi gian xu ly: khoang 16 giay tren may kiem thu

Con so nay chi dung de xac nhan pipeline hoat dong. No khong phai ket qua danh gia chinh thuc hay cam ket khi trien khai production.

## Gioi han cua giai doan 1

- Chua nhan flow truc tiep tu Mininet/Ryu/ONOS.
- Chua tu dong chan IP hoac day rule xuong switch.
- Forecast khong duoc tinh tu tung flow; no can chuoi thong ke luu luong theo cua so thoi gian.
- API tu choi request thieu feature bang HTTP 422, tranh viec dien gia tri 0 va tra ve BENIGN sai.
