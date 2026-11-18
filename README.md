# AI Network IDS

Baseline phát hiện lưu lượng mạng bất thường trên bộ dữ liệu CSE-CIC-IDS2018
(đồng thời nhận CSV CIC-IDS2017). Dự án
có hai mô hình:

- `detection`: phân loại nhị phân `BENIGN` / `ATTACK`.
- `prediction`: phân loại đa lớp để dự đoán loại tấn công cụ thể.

> Bản model đang triển khai cho demo Mininet được train lại bằng dữ liệu thu từ
> chính packet extractor của Traffic Generator. CIC-IDS2018 vẫn được giữ làm
> dữ liệu nền với trọng số thấp. Xem `results/mininet_training_report.md`.

## Mininet lab retraining

Thu lại dữ liệu có nhãn từ VM:

```powershell
python src/collect_mininet_lab.py --runs 8 --duration 5
python src/collect_mininet_lab.py --runs 24 --run-offset 8 --scenarios NORMAL --append
```

Train ba artifact và đánh giá theo session độc lập:

```powershell
.venv\Scripts\python.exe src/train_mininet_lab.py
```

Các model CIC cũ được sao lưu một lần trong `models/baseline_cic/`. Model mới:

- `detection_model.joblib`: BENIGN/ATTACK, version `mininet-lab-1`.
- `attack_type_model.joblib`: năm loại kịch bản lab.
- `traffic_forecast.joblib`: dự báo packets/s và bytes/s theo bước 1 giây.

Kiểm tra toàn tuyến bằng sáu session có tham số trung gian:

```powershell
python src/verify_mininet_integration.py
```

## 1. Cài đặt

Yêu cầu Python 3.10 trở lên. Trên PowerShell:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 2. Chuẩn bị dữ liệu

Chép các file CSV hoặc Parquet đã gán nhãn vào `data/raw/`. Không cần PCAP cho
baseline này và không commit dataset vào Git.

```powershell
python src/preprocess.py
```

Lệnh tạo `data/processed/cse_cic_ids2018_clean.parquet`, thêm `target` và
`source_file`, rồi in số dòng cùng phân bố nhãn. Dữ liệu được đọc theo batch để
không phải nạp toàn bộ dataset vào RAM. Có thể thử nhanh trước bằng:

```powershell
python src/preprocess.py --max-rows-per-file 10000
```

## 3. Huấn luyện và đánh giá

```powershell
python src/train_detection.py
python src/evaluate.py
python src/train_prediction.py
```

Mặc định detection lấy mẫu đại diện 500.000 flow; mô hình đa lớp lấy 1.000.000
flow để giữ đủ các nhãn hiếm. Cả hai dùng 100 cây, phù hợp hơn với máy 16 GB RAM.
Dùng `--max-rows 0` nếu máy đủ RAM và muốn dùng toàn bộ dữ liệu.

Detection mặc định chia theo ngày để tránh rò rỉ: train trên các file từ
14–23/02/2018 và test trên 28/02–02/03/2018. Hai tập không dùng chung
`source_file`:

```powershell
python src/train_detection.py --split-strategy day
python src/evaluate.py
```

Để tái tạo baseline random-split (chỉ dùng làm mốc so sánh):

```powershell
python src/train_detection.py --split-strategy random --model models/detection_model_random.joblib
python src/evaluate.py --model models/detection_model_random.joblib
```

Kết quả của từng chiến lược được lưu với hậu tố `_day` hoặc `_random` trong
`results/`. Với day-split hiện tại, `Bot` và `Infilteration` là các họ tấn công
chưa xuất hiện trong train; đây là bài kiểm tra generalization, không phải
closed-set classification.

### Leave-one-day-out

Một mốc chia duy nhất chỉ cho biết kết quả của đúng ba ngày test. Để có nhiều
điểm đo hơn, chạy leave-one-day-out: mỗi lần giữ đúng một ngày làm test và
train trên các ngày còn lại.

```powershell
python src/train_detection.py --split-strategy lodo
```

Mỗi fold dùng tối đa 500.000 flow để train và 200.000 flow của ngày bị giữ lại
để test. Trên máy 16 GB RAM, 10 fold mất khoảng 15 phút. Kết quả:

- `results/lodo_metrics.json`: metric từng fold, tổng hợp và metric theo nhãn.
- `results/lodo_summary.csv`: một dòng mỗi fold, mở được bằng Excel.
- `results/lodo_report.md`: báo cáo bảng biểu kèm diễn giải.

Các fold được chia theo hai cấp để tách hai nguyên nhân khác nhau:

- `label_seen` / `label_unseen`: xét theo nhãn cụ thể. `label_seen` đo khả năng
  tổng quát theo thời gian khi nhãn đã có trong train (ví dụ `Infil1` so với
  `Infil2`).
- `family_seen` / `family_unseen`: xét theo họ tấn công (DDoS, DoS, BruteForce,
  Web, Bot, Infiltration). `family_unseen` đo khả năng phát hiện họ tấn công mới.
  Một nhãn mới vẫn có thể thuộc họ đã thấy, ví dụ `DDOS attack-HOIC` được nhận ra
  nhờ `DDoS attacks-LOIC-HTTP` trong train.

Chạy thử nhanh vài fold trước:

```powershell
python src/train_detection.py --split-strategy lodo --only-sources Infil1 Web1 `
    --max-rows 50000 --max-test-rows 20000 --trees 20
```

Model từng fold chỉ được lưu khi bật `--save-fold-models` (vào `models/lodo/`).
Mỗi model như vậy là một bundle day-split hợp lệ nên vẫn dùng được với
`evaluate.py` và `predict.py`:

```powershell
python src/train_detection.py --split-strategy lodo --only-sources Botnet --save-fold-models
python src/evaluate.py --model models/lodo/fold_01_Botnet-Friday-02-03-2018_TrafficForML_CICFlowMeter.joblib
```

Model được lưu trong `models/`; báo cáo JSON, CSV và biểu đồ được lưu trong
`results/`. Cách chia ngẫu nhiên chỉ phù hợp làm baseline. Đánh giá chính thức
nên chia dữ liệu theo ngày/phiên thu thập để giảm rò rỉ giữa train và test.

### Audit dữ liệu DoS2/DDoS2

`src/audit_days.py` kiểm tra nhãn, trùng lặp, AUC đơn biến trong ngày, drift của
benign so với các ngày khác, và điểm của model train trên các ngày còn lại.

```powershell
python src/audit_days.py --sources DoS2 DDoS2
```

Kết quả (`results/audit_days.md`):

- Nhãn sạch: 0 dòng trùng đặc trưng, 0 nhóm trùng nhưng khác nhãn.
- Tách lớp **trong cùng ngày** rất mạnh: AUC đơn biến 0,004–0,03; Hulk/HOIC có
  packet nhỏ hơn benign.
- Benign của ngày tấn công bị dịch cực mạnh: DDoS2 có `Flow Bytes/s` median
  842.217 so với 1.270 ở 9 ngày còn lại; `Flow IAT Mean` 244 µs so với 68,8 ms.
  DoS2 có `Fwd Packet Length Max` median 935 so với 49.
- Model train trên 9 ngày còn lại: DDoS2 AUC 0,843; DoS2 AUC 0,165 (đảo hạng).

Kết luận: **không phải lỗi nhãn**. "Benign" trên ngày tấn công là lưu lượng hợp
lệ của chính server đang bị tấn công, nên mang đặc trưng giống tấn công đối với
model học từ những ngày yên tĩnh. Đây là lý do LODO rất khó cho hai ngày này.

### Chuẩn hoá đặc trưng theo ngày

`src/train_normalized.py` thử bỏ khác biệt phân bố giữa các ngày bằng thống kê
tính riêng trên từng batch (không dùng nhãn):

- `robust`: `sign(x)·log1p(|x|)` rồi `(x - median) / (IQR/1.349)` theo ngày.
- `rank`: percentile của từng đặc trưng trong ngày.
- `union`: giữ cả đặc trưng gốc và robust.
- `rate`: chỉ chuẩn hoá các đặc trưng tốc độ (`/s`) và `IAT`.
- `select`: train cả raw và robust, chọn theo AUC trên ngày validation.

```powershell
python src/train_normalized.py --normaliser robust
python src/train_normalized.py --normaliser raw --only-sources Botnet Bruteforce DoS2 DDoS2 `
    --max-rows 200000 --max-val-rows 60000 --max-test-rows 60000 --trees 50
```

Run đầy đủ ghi `results/normalized_<biến thể>_metrics.json`, `_summary.csv`,
`_report.md`. Run `--only-sources` ghi thêm hậu tố `_<số>fold` (ví dụ `_4fold`)
để không ghi đè kết quả đầy đủ.

Kết quả đầy đủ 10 fold (`results/normalization_report.md`):

| Ngày test | AUC baseline (9 ngày) | AUC robust (8 ngày) |
|---|---:|---:|
| 14/02 Bruteforce | 0,922 | 0,405 |
| 16/02 DoS2 | 0,163 | **0,994** |
| 21/02 DDoS2 | 0,843 | **1,000** |
| 22/02 Web1 | 0,959 | 0,999 |
| 02/03 Botnet | 0,960 | 0,435 |

Ở mục tiêu FPR 5%, robust tăng recall từ 31,9% lên 66,0% và F1 từ 0,328
lên 0,567, với FPR gần như không đổi (16,5% so với 15,4%). Nhưng nó **phá**
Botnet/Bruteforce vì hai loại này dựa vào biên độ tuyệt đối của counts/durations.
Các biến thể `union`, `rank`, `rate` và `select` đều không giải quyết được
trade-off; `select` còn chọn sai vì ngày validation không đại diện cho ngày test.

Kết luận: chuẩn hoá theo ngày là **detector song song có mục tiêu** cho môi
trường flood, không phải phép biến đổi mặc định. Ngưỡng vẫn phải calibration
trên mạng đích. Bảng so sánh đầy đủ: `results/comparison_all.md`.

### Ngân sách cảnh báo (top-k / top-q)

Một ngưỡng cố định không trả lời được câu hỏi vận hành: mỗi ngày SOC chỉ xử lý
được k alert thì bắt được bao nhiêu tấn công? `src/evaluate_budget.py` xếp hạng
score trên từng ngày test của LODO và báo cáo precision/recall theo ngân sách,
không dùng nhãn test để chọn ngưỡng.

```powershell
python src/train_normalized.py --normaliser raw --save-scores
python src/train_normalized.py --normaliser robust --save-scores
python src/evaluate_budget.py --variants raw robust
```

Score từng flow được lưu trong `results/lodo_scores/<variant>/fold_*.parquet`.
Kết quả: `results/budget_metrics.json`, `budget_summary.csv`,
`budget_report.md`.

Cách đọc:

- `top-k`: đúng k alert mỗi ngày, xếp theo score.
- `top-q`: alert q% số flow mỗi ngày; phù hợp hơn khi lưu lượng các ngày khác
  nhau.
- `Recall ceiling`: recall tối đa có thể đạt với ngân sách đó, ngay cả khi mọi
  alert đều là tấn công. Nếu recall thực tế gần ceiling, nút thắt là ngân sách;
  nếu thấp hơn nhiều, nút thắt là thứ hạng của model.
- `Alert thực tế/ngày`: số alert nếu triển khai bằng ngưỡng tại vị trí k; có thể
  lớn hơn k vì score Random Forest bị trùng.

Lưu ý quan trọng: alert theo **flow** với ngân sách nhỏ (ví dụ 100/ngày) có
recall ceiling rất thấp vì một chiến dịch DDoS/DoS sinh ra hàng nghìn đến hàng
chục nghìn flow. Trong triển khai thật nên gộp theo `source IP` + cửa sổ thời
gian rồi mới áp top-k cho từng thực thể. Dataset sạch hiện không giữ cột IP nên
báo cáo này chỉ đo được mức flow.

Kết quả đầy đủ 10 fold (`results/budget_report.md`):

| Ngân sách | Raw recall | Raw precision | Robust recall | Robust precision | Recall ceiling |
|---|---:|---:|---:|---:|---:|
| 100 alert/ngày | 0,10% | 41,4% | 0,10% | 38,3% | 0,25% |
| 1% flow/ngày (~2.000 alert) | 1,89% | 37,6% | 1,88% | 37,4% | 4,09% |
| 5% flow/ngày (~10.000 alert) | 9,18% | 36,4% | 8,91% | 35,4% | 20,22% |
| 20% flow/ngày (~40.000 alert) | 39,10% | 38,8% | 35,65% | 35,4% | 67,00% |

- 100 alert/ngày có recall ceiling 0,25%: không khả thi nếu alert theo flow.
- 1% flow/ngày chỉ đạt khoảng 1,9% recall; ngay cả xếp hạng hoàn hảo cũng không
  vượt 4,09%.
- 5% flow/ngày đạt khoảng 9% recall; 20% flow/ngày đạt khoảng 39% (raw) / 36%
  (robust), vẫn rất xa mục tiêu.
- Để đạt 50% recall, budget trung vị cần khoảng 21,4% flow/ngày (raw) hoặc
  33,6% (robust); 80% recall cần khoảng 60,2% / 47,7%.
- Ở cùng ngân sách flow, raw và robust gần như ngang nhau về recall gộp:
  robust nhỉnh hơn ở DDoS/Web, raw tốt hơn rõ ở Botnet; BruteForce kém ở cả hai.
- Không nên so trực tiếp với ngưỡng calibrated: robust đạt recall 32,2% ở mục
  tiêu FPR 1% nhưng cần khoảng 33.076 alert/ngày và FPR thực 12,66%; raw chỉ cần
  khoảng 3.324 alert/ngày và FPR 1,47% nhưng recall 2,42%.

Kết luận: nút thắt ở ngân sách nhỏ là **độ hạt flow**, không chỉ model. Cần gộp
theo `source IP` + cửa sổ thời gian trước khi áp top-k. Detector theo họ tấn công
chỉ khả thi khi có nhiều ngày cùng họ; với các họ một ngày trong LODO, train trên
chính họ đó sẽ leakage.

### Fusion raw + robust (bước 3)

Chạy hai detector song song rồi fusion score, không cần train lại:

```powershell
python src/evaluate_fusion.py
```

Kết quả: `results/fusion_report.md`, `fusion_metrics.json`,
`fusion_summary.csv`. Quyết định kiến trúc: `results/architecture_decision.md`.

| Ngân sách top-k | Raw recall | Robust recall | `rank_min_tb` recall | `rank_min_tb` precision |
|---|---:|---:|---:|---:|
| 1% flow/ngày | 1,89% | 1,88% | **2,03%** | **40,18%** |
| 5% flow/ngày | 9,18% | 8,91% | **10,63%** | **42,17%** |

`rank_min_tb` là fusion percentile của hai detector, có tie-break để triển khai
bằng ngưỡng. Nó cải thiện Botnet/DoS/DDoS/Infiltration nhưng vẫn thua raw ở Web
và thua raw ở một số ngày (DoS1, Web2). Nếu SOC đủ năng lực cho high-recall, dùng
`fusion_mean`: top-q 10% cho recall 21,73%, precision 43,12%; top-q 20% cho
44,16% / 43,81%. `fusion_max` ở 5% danh nghĩa chỉ đạt 19,59% với khoảng 14.126
alert/ngày, nên không phải lựa chọn high-recall tốt nhất. Ngân sách trung vị cho
50% recall là khoảng 26,09% flow/ngày với `rank_min_tb`, 15,92% với `fusion_mean`
và 18,99% với `fusion_max`; cho 80% là 61,42% / 39,31% / 42,23%. Tuy nhiên top-q
20% của `fusion_mean` chỉ đạt 44,16%, nên để đạt 50% gộp vẫn cần trên 20% flow.

Không chọn `union` feature-level: 4 fold có AUC Bruteforce 0,467, DoS2 0,994,
DDoS2 0,862, Botnet 0,881; full run dừng sớm vì Bruteforce AUC 0,092 và DoS1 FPR
calibrated 21,88%. `rate` cũng không giải quyết trade-off.

### Holdout 3 ngày và CLI fusion

Train lại raw + robust trên cùng 7 ngày, test trên 3 ngày chưa thấy
(Botnet/Infil1/Infil2). Đây là holdout hẹp, không có flood, chỉ dùng để kiểm tra
packaging; LODO 10 fold vẫn là tham chiếu chính.

| Ngân sách | raw | robust | `rank_min_tb` | `fusion_mean` |
|---|---:|---:|---:|---:|
| 1% flow/ngày | 0,75% | 1,35% | **1,57%** | 0,79% |
| 5% flow/ngày | 4,13% | **4,49%** | 4,25% | 4,37% |

Ở 5%, robust nhỉnh hơn fusion 0,24 điểm phần trăm; ở 1%, `rank_min_tb` tốt nhất.
Holdout không xác nhận fusion vượt trội ở 5%, nên giữ `rank_min_tb` làm mặc định
LODO và dùng `fusion_mean` làm fallback đơn giản.

```powershell
python src/evaluate_holdout_fusion.py
python src/evaluate_holdout_variants.py

# Chấm alert queue trên một file flow; mặc định 5% flow/ngày
python src/predict_fusion.py --input flows.parquet --output alerts.csv `
    --budget-q 0.05 --fusion-method rank_min_tb --alerts-only

# Giới hạn tuyệt đối 10.000 alert/ngày thay vì 5% flow
python src/predict_fusion.py --input flows.parquet --output alerts.csv `
    --budget-k 10000 --fusion-method rank_min_tb --alerts-only

# Chế độ high-recall: fusion_mean ở 10% flow/ngày
python src/predict_fusion.py --input flows.parquet --output alerts_high_recall.csv `
    --budget-q 0.10 --fusion-method mean --alerts-only
```

Model `models/holdout_fusion_raw.joblib` và `holdout_fusion_robust.joblib` là
artifact thử nghiệm. Báo cáo: `results/holdout_fusion_report.md`,
`results/holdout_fusion_variants.md`.

Đã thử thêm cascade hai tầng (top 10–20% ứng viên rồi xếp lại bằng score khác):
LODO tăng recall 5% từ 10,63% lên 11,70%, nhưng holdout chỉ còn 4,20% so với
4,25% của `rank_min_tb` và 4,49% của robust; ở 1% cascade còn tệ hơn nhiều. Vì
vậy **không đưa cascade vào kiến trúc**. Chi tiết: `results/cascade_experiment.md`.

### Entity-level (source IP + cửa sổ thời gian)

Đã có harness `src/evaluate_entities.py` và pipeline giữ metadata IP/timestamp
xuyên suốt bước xuất score. Tuy nhiên **chưa có kết quả entity đa ngày** vì cả
parquet sạch và score hiện tại đều không có `Source IP`/`Timestamp`.

Đã kiểm tra bucket chính thức: **chỉ DDoS1 ngày 20/02/2018 có `Src IP`**; 9 ngày
còn lại chỉ có `Dst Port` và `Timestamp`. Vì vậy không thể chạy entity LODO đầy
đủ từ CSV processed chính thức. Có thể chạy case study một ngày DDoS1:

```powershell
python src/fetch_cic_ids2018.py --check
python src/fetch_cic_ids2018.py --download --only-with-ip

python src/build_metadata_dataset.py `
    --metadata-csv data/raw_with_metadata/Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv `
    --output data/processed/cse_cic_ids2018_with_meta_partial.parquet

python src/train_normalized.py `
    --data data/processed/cse_cic_ids2018_with_meta_partial.parquet `
    --normaliser raw --only-sources DDoS1 --save-scores `
    --score-dir results/lodo_scores_meta_partial

python src/evaluate_entities.py `
    --scores results/lodo_scores_meta_partial/raw_1fold `
    --window-minutes 5 --budget-flows 10000 --entity-score sum `
    --output results/entity_ddos1_raw_5m_sum_10kflows.json `
    --report results/entity_ddos1_raw_5m_sum_10kflows.md
```

Kết quả case study DDoS1 cho thấy cách gộp score rất quan trọng: `max`/`mean` chỉ
đạt recall flow 0,1–4,3% ở ngân sách 1–5% entity, trong khi `sum` (ưu tiên source
IP có nhiều flow) đạt **98,5% recall flow / 99,2% precision** với 134 entity
alert và 14.402 flow review. Cửa sổ 1 phút, `sum` 0,5% cho 509 alert, 12.394 flow,
recall 84,1%, precision 98,4%. Đúng ngân sách **10k flow review**, cửa sổ 5 phút
cho 84 alert/10.043 flow với recall 69,2%, precision 100%; cửa sổ 1 phút cho 392
alert/10.015 flow với recall 68,6%, precision 99,4%. Đây là **một ngày flood**,
không phải LODO; `sum` có thể bỏ sót stealth/Botnet ít flow, nên chỉ là queue bổ
sung cho flood. Chi tiết: `results/entity_ddos1_case_study.md`.

Script đo cả flow recall/precision, entity recall/precision và số flow phải review;
so sánh với baseline xếp hạng flow ở cùng số alert hoặc cùng số flow review. Chi
tiết, inventory và các lựa chọn (PCAP/CIC-IDS2017 proxy):
`results/data_acquisition.md`, `results/entity_aggregation.md`.

**CIC-IDS2017 proxy (đã chạy):** bộ `GeneratedLabelledFlows` 8 CSV / 5 ngày trong
`data/cicids2017/raw_metadata/` có đủ `Flow ID`, `Source IP`, `Timestamp` nên dùng
được cho entity + LODO theo ngày (Monday chỉ benign nên chỉ train/validation).
Đã dựng dataset giữ metadata và chạy LODO raw 4 fold:

```powershell
python src/preprocess_cicids2017.py `
    --output data/processed/cicids2017_with_meta.parquet

python src/audit_dataset.py `
    --input data/processed/cicids2017_with_meta.parquet `
    --report results/cicids2017_metadata_audit.json

python src/train_normalized.py `
    --data data/processed/cicids2017_with_meta.parquet `
    --prefix cicids2017_normalized --normaliser raw `
    --only-sources CICIDS2017-04 CICIDS2017-05 CICIDS2017-06 CICIDS2017-07 `
    --trees 100 --max-rows 500000 --max-val-rows 0 --max-test-rows 0 `
    --save-scores --score-dir results/lodo_scores_cicids2017

python src/evaluate_entities.py `
    --scores results/lodo_scores_cicids2017/raw_4fold `
    --entity-score sum --window-minutes 5 `
    --budget-flows 10000 --review-per-entity 200 `
    --output results/cicids2017_entity_sum_5min_10kflows_cap200.json `
    --report results/cicids2017_entity_sum_5min_10kflows_cap200.md
```

Kết luận ngắn: baseline flow top-10k đạt flow recall 3,87% và phủ 23,24% entity;
gộp entity review toàn bộ không vừa ngân sách và không vượt baseline; gộp entity
có trần review nâng entity recall lên 27–33% nhưng hạ flow recall. Vì vậy vẫn giữ
flow-level 5% làm mặc định, entity chỉ là queue bổ sung. Chi tiết:
`results/cicids2017_proxy_report.md`, `results/cicids2017_entity_policy_matrix.md`.

### Calibration ngưỡng

Xác suất của Random Forest bị lệch khi chuyển sang ngày mới, nên ngưỡng 0,5 cố
định bỏ sót phần lớn tấn công. `src/calibrate.py` chọn ngưỡng theo phân vị
`1 - FPR` của điểm benign trên một ngày validation mà model chưa từng thấy.

```powershell
python src/calibrate.py --mode lodo   # 10 fold, validation = ngày liền trước
python src/calibrate.py --mode day    # train 14-22/02, validation 23/02, test 28/02-02/03
```

- `--mode lodo` ghi `results/calibration_metrics.json`, `calibration_summary.csv`,
  `calibration_report.md` với recall/precision/F1/FPR ở các mức FPR mục tiêu
  0,1% / 0,5% / 1% / 2% / 5%.
- `--mode day` ghi thêm `results/calibration_day.json` và model
  `models/detection_model_calibrated.joblib` có trường `decision_threshold`.

`predict.py` và API đọc `decision_threshold` từ bundle, có thể ghi đè khi cần:

```powershell
python src/predict.py --input flows.csv --model models/detection_model_calibrated.joblib
python src/predict.py --input flows.csv --model models/detection_model_calibrated.joblib --threshold 0.02
$env:IDS_MODEL = "models/detection_model_calibrated.joblib"; uvicorn src.api:app
```

Kết quả LODO 10 fold cho thấy calibration **không chuyển được** sang ngày mới:

| Ngưỡng | Recall | Precision | F1 | FPR thực tế |
|---|---:|---:|---:|---:|
| cố định 0,5 | 0,1195 | 0,7730 | 0,2070 | 0,87% |
| mục tiêu FPR 1% | 0,1513 | 0,3893 | 0,2179 | 5,88% |

FPR thực tế gấp gần 6 lần mục tiêu. Nguyên nhân: phân bố điểm benign thay đổi
theo ngày (location, scale và cả đuôi). Fold DDoS2 có AUC 0,16 trong protocol
này vì ngày validation là DDoS1 và bị loại khỏi train; với 9 ngày train, DDoS2
đạt AUC 0,84. Tuy vậy, ngay cả khi bỏ fold DDoS2, calibration chỉ cải thiện F1
từ 0,061 lên 0,082.
Vì vậy `detection_model_calibrated.joblib` là **artifact thử nghiệm**: trên
day-split cố định nó chọn ngưỡng 0,03 và chỉ đạt recall 3,0% với FPR 5,1%.
Trong triển khai thật, hãy calibration lại trên mẫu benign gần nhất của chính
mạng đích thay vì dùng ngưỡng từ ngày khác.

### Phát hiện bất thường không giám sát

Random Forest học ranh giới từ các nhãn đã thấy, nên khi sang ngày mới điểm số
lệch mạnh và ngưỡng 0,5 gần như bỏ sót hết. `src/train_anomaly.py` thử hướng
bổ sung: huấn luyện Isolation Forest **chỉ trên flow benign** và calibrate
ngưỡng theo cùng giao thức validation.

```powershell
python src/train_anomaly.py --mode lodo   # đánh giá trên 10 ngày
python src/train_anomaly.py --mode day    # model deployable
```

Kết quả: `results/anomaly_metrics.json`, `anomaly_summary.csv`,
`anomaly_report.md` và `models/anomaly_model.joblib`. Bundle anomaly có
`task="anomaly_detection"`; `predict.py`/API tự dùng `decision_function` và trả
`anomaly_score` thay vì `attack_probability`.

Isolation Forest **chưa đủ tốt** để thay Random Forest:

| Mô hình | Ngưỡng | Recall | Precision | F1 | FPR thực tế |
|---|---|---:|---:|---:|---:|
| Random Forest | calibrated 1% | 0,1513 | 0,3893 | 0,2179 | 5,88% |
| Isolation Forest | calibrated 1% | 0,0112 | 0,1684 | 0,0210 | 1,37% |
| Isolation Forest | mặc định sklearn | 0,0815 | 0,0906 | 0,0858 | 20,26% |

AUC từng fold của Isolation Forest dao động rất mạnh: 0,90 ở Bruteforce nhưng
0,01 ở DDoS2 và 0,51 ở Infiltration. Detector chỉ học được "benign trông như
thế nào" trên các ngày train, không ổn định qua ngày mới.

### Chẩn đoán chuẩn hoá điểm theo batch

`src/batch_calibration.py` kiểm tra xem chuẩn hoá median/MAD theo từng batch có
cứu được ngưỡng không. Kết quả không nhất quán: trên fold DDoS1, batch z-score
nâng F1 từ 0,004 lên 0,763, nhưng trên Bruteforce và Botnet lại cho F1 xấp xỉ 0.
Nghĩa là điểm số khác nhau cả về độ lớn lẫn hình dạng phân bố, không chỉ lệch
một hằng số. Chi tiết: `results/batch_calibration.md`.

### So sánh và kết luận

Bảng so sánh đầy đủ: `results/comparison.md` và `results/comparison_all.md`.
Tóm tắt:

- Random Forest vẫn là mô hình chính; ở ngưỡng 0,5 nó có precision cao nhưng
  recall rất thấp trên ngày mới.
- Calibration theo ngày validation cải thiện recall nhưng không kiểm soát được
  FPR vì drift giữa các ngày.
- Isolation Forest không thay thế được Random Forest và cũng gặp đúng vấn đề
  ngưỡng; chỉ nên xem là tín hiệu phụ.
- Audit xác nhận nhãn DoS2/DDoS2 sạch; nguyên nhân là benign của ngày tấn công
  bị dịch mạnh, không phải lỗi nhãn.
- Chuẩn hoá đặc trưng theo ngày sửa được flood (DoS2/DDoS2) nhưng phá
  Botnet/Bruteforce; đây là detector song song có mục tiêu, không phải mặc định.
- Ngân sách alert theo flow: 100 alert/ngày có recall ceiling 0,25%; 1% flow/ngày
  chỉ đạt khoảng 1,9% recall. Cần gộp theo thực thể/thời gian, không nên dùng
  top-k theo flow với ngân sách nhỏ. Harness entity đã có, nhưng CSV processed
  chính thức chỉ có IP ở DDoS1; 9 ngày còn lại thiếu `Source IP`, nên chưa thể
  kết luận entity đa ngày. Case study DDoS1 cho thấy gộp `sum` rất mạnh cho
  flood: 134 entity alert/14.402 flow review đạt 98,5% recall flow, 99,2%
  precision; `max`/`mean` kém hơn nhiều. Đây là một ngày, không thay thế LODO;
  `sum` có thể bỏ sót stealth/Botnet ít flow.
- Nút thắt hiện tại vẫn là **khả năng tổng quát theo ngày của đặc trưng/mô hình**
  và **threshold transfer**, không phải ngưỡng đơn thuần.
- Kiến trúc đề xuất: raw + robust song song, fusion `rank_min_tb` cho hàng đợi
  ngân sách chặt; stream `fusion_mean` ở 10–20% flow cho high-recall. Vẫn chưa
  đạt recall cao ở ngân sách nhỏ.
- Ngân sách chốt hiện tại là **5% flow/ngày (~10k alert)**. Holdout 3 ngày
  (Botnet/Infil) cho recall 4,13–4,49%, không xác nhận fusion vượt trội ở mức
  này; `rank_min_tb` vẫn là mặc định LODO, `fusion_mean` là fallback. CLI:
  `src/predict_fusion.py`.
- Detector supervised theo họ chỉ khả thi khi có nhiều ngày cùng họ. Với các họ
  một ngày trong LODO, train trên chính họ đó sẽ leakage; cần thu thêm dữ liệu
  hoặc dùng anomaly/few-shot.

## 4. Dự đoán

### 4.1. Detection trên flow

Dự đoán một hoặc nhiều dòng trong CSV:

```powershell
python src/predict.py --input duong-dan/toi/flows.csv --output results/predictions.csv
```

Output thêm các cột `prediction`, `prediction_label`, `attack_probability`, `threshold`.

Tạo alert queue theo ngân sách:

```powershell
python src/predict_fusion.py `
    --input duong-dan/toi/flows.csv `
    --budget-q 0.05 --alerts-only `
    --output results/alerts.csv
```

### 4.2. Dự báo lưu lượng packets/s, bytes/s

Module mới gồm ba bước: tạo chuỗi thời gian → train → dự báo.

**Bước 1 — Tạo chuỗi thời gian từ flow**

```powershell
python src/build_traffic_series.py `
    --data data/processed/cicids2017_with_meta.parquet `
    --interval-seconds 60 `
    --output data/processed/traffic_series_60s.csv
```

CIC-IDS2017 chỉ có timestamp độ phân giải phút, nên dùng `60`. Với dữ liệu
5 giây thật từ Mininet/OVS, dùng `--interval-seconds 5`.

Nếu Người B đã cung cấp file rate trực tiếp với các cột `timestamp`,
`packets_per_second`, `bytes_per_second` thì bỏ qua bước này và train trực tiếp
ở bước 2 (thêm `--interval-seconds 5`).

**Bước 2 — Train baseline**

```powershell
python src/train_traffic_forecast.py `
    --data data/processed/traffic_series_60s.csv `
    --interval-seconds 60 `
    --lags 12 --windows 3,6,12,24 `
    --trees 150 --max-depth 20 `
    --model models/traffic_forecast.joblib
```

Kết quả:

- `models/traffic_forecast.joblib`
- `results/traffic_forecast_metrics.json`
- `results/traffic_forecast_report.md`

Baseline dùng `RandomForestRegressor`, chia **chronological** (train → validation
→ test), so sánh với persistence và moving average. Không dùng random split.

Model mặc định train cho **1 bước**; `predict_traffic.py --horizon N` dự báo đệ
quy N bước. Nếu muốn direct multi-step, cần thiết kế lại target và inference
tương ứng, không chỉ đổi `--horizon` khi train.

**Bước 3 — Dự báo**

```powershell
python src/predict_traffic.py `
    --input data/processed/traffic_series_60s.csv `
    --model models/traffic_forecast.joblib `
    --horizon 12 `
    --output results/traffic_forecast.csv
```

Output: `timestamp`, `step`, `packets_per_second`, `bytes_per_second`,
`risk_level`. Risk dùng p95/p99 của traffic active trong train.

### 4.3. Dự đoán loại tấn công

```powershell
python src/train_prediction.py `
    --data data/processed/cse_cic_ids2018_clean.parquet `
    --model models/attack_type_model.joblib `
    --max-rows 500000 --trees 60 --max-depth 24 `
    --version attack-type-demo-1
```

Kết quả:

- `models/attack_type_model.joblib` (~76 MB)
- `results/attack_type_report.md`
- `results/prediction_metrics.json`

Dự đoán batch:

```powershell
python src/predict_attack_type.py `
    --input duong-dan/toi/flows.csv `
    --model models/attack_type_model.joblib `
    --output results/attack_types.csv
```

Output thêm `attack_type`, `attack_type_confidence`, `attack_type_top_1..k`.

Lưu ý: model này dùng **random stratified split** để demo phân loại 15 lớp; không
phải LODO và không phải dự báo tương lai. Các lớp hiếm như SQL Injection,
FTP-BruteForce có thể có recall 0; confidence chưa được calibration.

### 4.4. API

Khởi động:

```powershell
uvicorn src.api:app --reload
```

Mở `http://127.0.0.1:8000/docs`.

| Endpoint | Chức năng |
|---|---|
| `GET /health` | Trạng thái model, version, threshold |
| `POST /detect` | Phát hiện flow hiện tại là BENIGN/ATTACK |
| `POST /classify-attack` | Phân loại loại tấn công của flow hiện tại |
| `POST /forecast/traffic` | Dự báo packets/s, bytes/s trong tương lai |

`POST /detect` nhận object hoặc mảng object, tên trường trùng feature dataset.

`POST /classify-attack` nhận cùng format; cũng chấp nhận
`{"features": {...}}`.

`POST /forecast/traffic`:

```json
{
  "history": [
    {"timestamp": "2017-07-07 12:58:00", "packets_per_second": 120, "bytes_per_second": 45000},
    {"timestamp": "2017-07-07 12:59:00", "packets_per_second": 135, "bytes_per_second": 48000}
  ],
  "horizon": 6
}
```

Ví dụ trên chỉ minh họa format; thực tế cần ít nhất `max(lags, windows) + 1`
điểm lịch sử (mặc định 25 điểm).

Có thể đổi model bằng biến môi trường:

```powershell
$env:IDS_MODEL = "models/detection_model.joblib"
$env:IDS_TRAFFIC_MODEL = "models/traffic_forecast.joblib"
$env:IDS_ATTACK_TYPE_MODEL = "models/attack_type_model.joblib"
uvicorn src.api:app --port 8001
```

Các route cũ `/predict`, `/predict/type` và `/forecast` vẫn hoạt động như alias
tương thích ngược nhưng được ẩn khỏi Swagger để tránh nhầm detection với dự báo
tương lai.


Khởi động hệ thống demo
cd D:\AI-Network-IDS
.venv\Scripts\Activate.ps1

$env:IDS_MODEL = "models/detection_model.joblib"
$env:IDS_TRAFFIC_MODEL = "models/traffic_forecast.joblib"
$env:IDS_ATTACK_TYPE_MODEL = "models/attack_type_model.joblib"

python -m uvicorn src.api:app --port 8000

Mở bằng
http://127.0.0.1:8000/docs
