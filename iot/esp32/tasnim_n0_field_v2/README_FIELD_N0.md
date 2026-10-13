# TASNIM — N0 FIELD v2 (berdasarkan firmware N0 working fisik)

SUMBER: firmware N0 yang diunggah pada 7 Oktober 2026 (1936 baris).
STATUS: perubahan FIELD diuji SECARA STATIS, BELUM diverifikasi compile/upload di ESP32.

## PERUBAHAN
- Menambah ENABLE_FIELD_SHADOW (default **false**, aman saat kalibrasi).
- Menambah /field/nodes/N0/latest (interval siklus existing sekitar 5 detik).
- Menambah /field/history/<slotUTC5menit>/N0 (satu record per slot 300000 ms).
- pH/TDS/turbidity/timestamp/sequence/rssi dari measurement yang sama dengan CSV/hardware_test.
- Turbidity hilang: jangan isi 0/null dalam FIELD JSON, hilangkan key.
- Jalur existing /hardware_test/nodes/N0/latest TIDAK diubah.
- Tidak menambah backup replay SD->Firebase; koneksi terputus = CSV saja.

## HARDWARE DIPERTAHANKAN PERSIS DARI FILE WORKING
RTC bus kedua: SDA 25, SCL 26 (TwoWire WireRTC).
LED hijau: GPIO16.
GPS UART2: RX 27, TX 4.
SD VSPI: CS 5, MOSI 23, MISO 19, SCK 18.
OLED I2C: SDA21, SCL22.
NODE_ID N0; HAS_TURBIDITY=true.

## HAL PENTING
1. Selama kalibrasi JANGAN upload firmware ini; N0 existing dibiarkan bekerja.
2. Firmware working dasar masih memakai konstanta KALIBRASI MANUAL. Hasil kalibrasi yang disetujui harus dimasukkan ke PH_V1/PH_V2, TDS_CAL_SLOPE/OFFSET, serta PH_SUDAH_KALIBRASI (true). Jika memakai firmware lain dengan auto-calibration NVS, jangan otomatis menimpanya dengan versi ini.
3. Setelah validasi kalibrasi, pada file baru set ENABLE_FIELD_SHADOW=true, lalu Arduino IDE Verify dan Upload N0.
4. Sesudah upload, pastikan melalui Serial/Firebase: hardware_test N0/latest tetap jalan; field/nodes/N0/latest terisi; field/history/<slot>/N0 terbentuk; CSV microSD terus bertambah.
5. Untuk FIELD, pemakaian larutan kalibrasi harus dilakukan dengan FIELD dimatikan agar data standar tidak masuk sebagai data lapangan.
6. Firebase callback ERROR = write gagal; log "History scheduled" bukan bukti DB sukses. Cek langsung di RTDB.
7. File ini belum membawa guard kalibrasi interaktif karena firmware dasar manual, bukan auto-calibration. Default FIELD=false menjaga larutan kalibrasi tidak tertulis ke /field.
8. Jangan pernah commit secrets.h atau serviceAccountKey.json.
9. Gunakan file ino dalam folder dengan NAMA YANG SAMA (tasnim_n0_field_v2/) saat Arduino IDE Verify.

## RENCANA KEMUDIAN
Setelah N0 FIELD terbukti barulah buat N1 dan N2 dari versi paling baru, menyamakan wiring sesuai fisik masing-masing; lalu aktifkan AI/Web FIELD ketika satu slot lengkap valid.
