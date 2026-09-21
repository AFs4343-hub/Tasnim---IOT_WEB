# TASNIM Field Data Contract v1

## Tujuan

Dokumen ini mendefinisikan struktur data yang digunakan
oleh perangkat ESP32 TASNIM pada pengambilan data lapangan.

Data lapangan disimpan di namespace:

field/

Data simulator tidak boleh ditulis ke namespace field.


## Struktur Firebase

field/
├── nodes/
│   ├── N0/latest
│   ├── N1/latest
│   └── N2/latest
│
├── history/
│   └── <timestamp_ms>/
│       ├── N0
│       ├── N1
│       ├── N2
│       ├── meta
│       ├── ground_truth
│       └── analysis
│
└── analysis/
    └── latest


## Paket Setiap Node

Setiap node wajib menghasilkan:

{
  "ph": 7.21,
  "tds": 218.4,
  "turbidity": 8.7,
  "timestamp": 1789351500000,
  "sequence": 152,
  "rssi": -63
}


## Penjelasan Field

ph
Nilai sensor pH.

tds
Nilai Total Dissolved Solids.

turbidity
Nilai turbiditas.

timestamp
Waktu pengukuran dalam Unix epoch millisecond.

sequence
Nomor urut paket per node.
Dipakai untuk mengevaluasi paket hilang dan transmission success.

rssi
Kekuatan sinyal Wi-Fi ESP32 dalam dBm.


## Metadata Record

Contoh:

{
  "data_source": "FIELD",
  "session_id": "FIELD_2026_09_18",
  "record_version": 1,
  "mode": "OBSERVATION"
}


## Ground Truth

Ground truth BERBEDA dengan hasil AI.

Default:

{
  "label": "UNLABELED",
  "source": "NONE",
  "experiment_id": null
}

Pada eksperimen terkontrol:

{
  "label": "ANOMALI_N1",
  "source": "CONTROLLED_EXPERIMENT",
  "experiment_id": "EXP_001"
}


Label yang diperbolehkan:

NORMAL
ANOMALI_N0
ANOMALI_N1
ANOMALI_N2
UNLABELED


## Analysis

Bagian analysis TIDAK dikirim sensor.

Bagian ini ditambahkan sistem AI setelah data sensor diterima.

Contoh:

analysis/
├── status
├── location
├── random_forest
├── isolation_forest
├── dominant_zscore
├── model_version
└── inference_timestamp_ms


## Aturan Penting

1. Simulator hanya boleh menulis ke /simulation.
2. Perangkat lapangan hanya boleh menulis ke /field.
3. Prediksi AI tidak boleh digunakan sebagai ground truth.
4. Timestamp harus berasal dari waktu pengukuran.
5. Sequence dihitung secara independen untuk setiap node.
6. Data mentah sensor harus disimpan sebelum analisis AI.
7. Setiap perubahan struktur data harus menaikkan record_version.
