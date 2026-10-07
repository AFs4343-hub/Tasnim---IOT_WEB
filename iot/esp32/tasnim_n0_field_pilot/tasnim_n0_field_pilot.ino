 /*
  ======================================================
   PROYEK : MONITORING KUALITAS AIR (ESP32) + FIREBASE
   Sensor : - Modul pH (PH-4502C)
            - TDS Meter (analog)
            - Turbidity / kekeruhan (analog, jenis SEN0189) -- OPSIONAL
              per node lewat HAS_TURBIDITY, lihat KONFIGURASI NODE di bawah.
            - OLED SSD1306 (I2C, 128x64)
            - 3 LED status (hijau / kuning / merah)
            - microSD (backup lokal, CSV)       -- BARU, CANDIDATE
            - RTC DS3231 (timekeeper cadangan)  -- BARU, CANDIDATE
            - GPS NEO-6M (metadata lokasi node) -- BARU, CANDIDATE

   Fitur  : - Klasifikasi otomatis pakai Fuzzy Logic
              - pH          -> ASAM   / NORMAL / BASA
              - Kualitas Air (TDS) -> JERNIH / SEDANG / KERUH
              - Kekeruhan   -> JERNIH / SEDANG / KERUH (jika HAS_TURBIDITY)
            - Analitik lokal (statistik, deteksi anomali, tren,
              indeks kekeruhan berbasis AI 0-100, health index,
              rekomendasi teks) tetap berjalan di ESP32 HANYA untuk
              OLED/Serial/LED lokal. Ini BUKAN output AI penelitian
              TASNIM dan TIDAK dikirim ke Firebase pada tahap ini.
            - Integrasi Firebase tahap TASNIM hardware_test: satu
              packet mentah (ph, tds, turbidity, timestamp, sequence,
              rssi) dikirim ke /hardware_test/nodes/{NODE_ID}/latest tiap
              firebasePushInterval (default 5 detik), HANYA jika
              timestamp pengukuran valid (NTP atau RTC fallback, lihat
              dapatkanWaktuPengukuran() -- fail-closed, tidak pernah
              kirim epoch palsu).
            - Write lama ke /ecosense/latest, /ecosense/history,
              /ecosense/stats DINONAKTIFKAN (dormant) pada tahap ini;
              fungsinya masih ada di kode tapi sengaja tidak dipanggil.
            - OLED dan LED status tetap berfungsi sebagai indikator
              fisik langsung di perangkat (tidak dihapus).

   ======================================================
   STATUS FIRMWARE INI: CANDIDATE / NOT TESTED
   ======================================================
   Firmware ini BELUM pernah di-compile, di-upload, atau diuji di
   hardware fisik oleh asisten (tidak ada akses toolchain ESP32 di
   sandbox ini). Status ini berlaku untuk SEMUA bagian baru di bawah,
   sampai ada bukti compile/upload/test dari pengguna.

   PERUBAHAN MALAM INI DIBANDING BASELINE N0/N1 (hardware_test) YANG
   SUDAH PERNAH BERHASIL:

   1. [BARU] KONFIGURASI NODE terpusat: NODE_ID dan HAS_TURBIDITY kini
      jadi SATU bagian config di bagian atas file (lihat di bawah),
      supaya SATU source code yang sama dipakai untuk N0/N1/N2 --
      cukup ubah 2 baris config lalu compile ulang per unit fisik.
   2. [BARU] Kalibrasi voltage debug (Phase 1): bacaTegangan() kini
      punya parameter tambahan untuk mengeluarkan tegangan ADC mentah
      (SEBELUM faktor divider), ditampilkan terpisah dari tegangan
      sensor (SESUDAH divider) di Serial Monitor lewat blok [CAL].
      Rumus/alur sinyal yang SUDAH ADA (vPH/vTDS/vTurb, hitungPH,
      hitungTDS, hitungNTU) TIDAK diubah sama sekali.
   3. [BARU] Penanganan sensor turbidity yang hilang (HAS_TURBIDITY):
      kalau false, GPIO turbidity TIDAK dibaca sama sekali (bukan
      dianggap 0), Serial/OLED menampilkan "MISSING", CSV menulis
      "NA", dan packet Firebase mengirim literal JSON null untuk key
      "turbidity" -- key tetap ada, isinya null (BUKAN 0/field baru).
      Health index & deteksi anomali lokal ikut disesuaikan (lihat di
      bawah) supaya ketiadaan sensor tidak dibaca sebagai "air sangat
      keruh".
   4. [BARU] microSD sebagai backup lokal (VSPI: CS=5, SCK=18, MISO=19,
      MOSI=23 -- lihat PIN MAP, status DESIGN DECISION, BELUM
      diverifikasi ke wiring fisik). CSV per node: /tasnim_{NODE_ID}.csv,
      kolom: timestamp,node,sequence,ph,tds,turbidity,rssi. Baris SD
      dan packet Firebase dibangun dari SATU measurement cycle yang
      sama (sequence & timestamp identik) lewat prosesMeasurementCycle().
      SD gagal tidak menghentikan Firebase, dan sebaliknya.
   5. [BARU] RTC DS3231 berbagi bus I2C dengan OLED (SDA=21, SCL=22,
      status DESIGN DECISION). Hierarki waktu (dapatkanWaktuPengukuran()):
      NTP tersedia -> pakai NTP + sinkronkan RTC; NTP tidak tersedia ->
      pakai RTC (dengan sanity-check tahun >= 2024); kalau NTP DAN RTC
      sama-sama tidak valid -> timestamp dianggap INVALID, SD dan
      Firebase cycle itu DILEWATI (tidak pernah membuat epoch palsu).
   6. [BARU] GPS NEO-6M via UART2 (RX=16, TX=17, baud 9600 [INFERENCE],
      status DESIGN DECISION, library TinyGPSPlus). Dibaca non-blocking
      tiap loop(); begitu dapat fix PERTAMA KALI, lat/lng disimpan SEKALI
      ke /metadata_{NODE_ID}.csv di SD (bukan tiap siklus 5 detik, dan
      TIDAK ditambahkan ke packet Firebase hardware_test). Kegagalan GPS
      tidak menghentikan sensor/SD/RTC/WiFi/Firebase.
   7. [FIX KECIL] Task UID Firebase yang sebelumnya hardcode
      "setN0LatestTask" (dipakai di baseline N0 MAUPUN N1 apa adanya)
      sekarang dibangun dari NODE_ID ("set" + NODE_ID + "LatestTask").
      Ini HANYA label debug untuk processFirebaseResult() di Serial
      Monitor -- TIDAK mengubah HARDWARE_TEST_PATH maupun isi packet,
      yang memang sudah memakai NODE_ID dengan benar sebelumnya.

   TIDAK diubah malam ini (sesuai instruksi): /field, Firebase Rules,
   kalibrasi sensor (slope/offset pH, formula TDS/turbidity), AI/analitik
   jadi output penelitian, backlog sync SD->Firebase saat reconnect
   (lihat TODO di dekat prosesMeasurementCycle()).

   PERUBAHAN TASNIM (SUDAH ADA SEBELUM MALAM INI):
   - Kredensial WiFi/Firebase dipindah ke secrets.h (lihat
     secrets.example.h), tidak lagi hardcode di file ini.
   - Target Firebase diarahkan ke /hardware_test/nodes/{NODE_ID}/latest
     sesuai data contract riset TASNIM, bukan lagi /ecosense/*.

  ============== SKEMA PENGKABELAN ====================
  1) OLED SSD1306 (I2C) -- TIDAK BERUBAH
     VDD -> 3.3V | GND -> GND | SDA -> D21 | SCL -> D22

  2) TDS Meter (Analog) -- TIDAK BERUBAH
     VCC -> 3.3V | GND -> GND | A -> D35

  3) Modul pH (PH-4502C) -- TIDAK BERUBAH
     V+ -> VIN / 5V | G -> GND | Po -> pembagi tegangan -> D34
     (To dan Do dibiarkan kosong)

  4) Turbidity (analog) -- TIDAK BERUBAH (hanya dipakai jika HAS_TURBIDITY)
     VCC -> VIN / 5V | GND -> GND | OUT -> pembagi tegangan -> D32

  5) Pembagi tegangan (WAJIB untuk pH dan turbidity, karena keluaran
     sensor bisa melebihi 3,3 V sedangkan ADC ESP32 maksimal 3,3 V):
       keluaran sensor --[R1 10 kOhm]--+--[R2 20 kOhm]-- GND
                                       |
                                    ke pin ADC
     Faktor pembagi = 1,5 (sudah dipakai di kode: DIV_PH, DIV_TURB).

  6) LED status (masing-masing pakai resistor +-220 Ohm ke GND) -- TIDAK BERUBAH
     Hijau -> D25 | Kuning -> D13 | Merah -> D14

  7) microSD (SPI, VSPI) -- BARU, DESIGN DECISION, BELUM VERIFIED hardware
     CS -> D5 | SCK -> D18 | MISO -> D19 | MOSI -> D23 | VCC -> 3.3V | GND -> GND

  8) RTC DS3231 (I2C, berbagi bus dengan OLED) -- BARU, DESIGN DECISION, BELUM VERIFIED hardware
     SDA -> D21 | SCL -> D22 | VCC -> 3.3V | GND -> GND

  9) GPS NEO-6M (UART2) -- BARU, DESIGN DECISION, BELUM VERIFIED hardware
     GPS TX -> ESP32 RX2 (D16) | GPS RX -> ESP32 TX2 (D17) | VCC -> sesuai modul | GND -> GND
     ASUMSI: modul UART standar (bukan I2C). Kalau modul fisik ternyata
     punya breakout I2C (SDA/SCL), BAGIAN GPS INI TIDAK BERLAKU -- laporkan
     [CONFLICT], jangan dipakai dulu.

  Semua GND harus disatukan.
  ======================================================

  ============ LIBRARY YANG HARUS DI-INSTALL ===========

    SUDAH DIPAKAI DI BASELINE (tidak berubah):
    1. "Adafruit GFX Library"  - by Adafruit
    2. "Adafruit SSD1306"      - by Adafruit
    3. "FirebaseClient"        - by Mobizt (cari "FirebaseClient" di
       Library Manager, BUKAN "Firebase ESP32 Client" yang lama).
       Kode ini dites terhadap pola API versi 2.x milik library
       tersebut (async, berbasis callback).
    WiFi.h, WiFiClientSecure.h, time.h sudah tersedia bersama board ESP32.

    BARU MALAM INI:
    4. "SD" dan "SPI"          - sudah bundel di board package ESP32,
       TIDAK perlu diinstall manual dari Library Manager.
    5. "RTClib"                - by Adafruit. Install dari Library
       Manager (biasanya otomatis menarik dependency "Adafruit BusIO").
    6. "TinyGPSPlus"           - by Mikal Hart. Install dari Library
       Manager.
  ======================================================

  ================ SETUP FIREBASE (SEKALI SAJA) =================
  1. Buat project baru di https://console.firebase.google.com
  2. Build > Authentication > Get started > aktifkan metode
     "Email/Password". Lalu tab Users > Add user, buat satu akun
     (email + password bebas, ini KHUSUS untuk autentikasi ESP32,
     bukan email pribadi yang dipakai untuk hal lain).
  3. Build > Realtime Database > Create Database > pilih lokasi
     terdekat > mode "Start in test mode" (untuk uji coba; sebelum
     dipakai serius, atur security rules yang lebih ketat).
     Salin URL database yang muncul (formatnya seperti
     https://nama-project-default-rtdb.asia-southeast1.firebasedatabase.app)
  4. Project Settings (ikon gerigi) > scroll ke "Your apps" > klik
     ikon web "</>" > daftarkan sebuah web app > salin "apiKey"
     dari firebaseConfig yang muncul.
  5. Isi keempat konstanta tersebut (API_KEY, DATABASE_URL,
     USER_EMAIL, USER_PASS) di file secrets.h (salin dari
     secrets.example.h), BUKAN di file ini.
  ======================================================
*/

#define ENABLE_USER_AUTH
#define ENABLE_DATABASE


#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <FirebaseClient.h>
#include <time.h>

// ---- BARU malam ini: microSD, RTC DS3231, GPS NEO-6M ----
#include <SPI.h>
#include <SD.h>
#include <RTClib.h>
#include <TinyGPSPlus.h>

// ---------------- KONFIGURASI WIFI & FIREBASE ----------------
// Kredensial dipindah ke secrets.h (tidak ikut Git). Lihat secrets.example.h.
#include "secrets.h"

// Node root lama, DORMANT -- hanya dipakai fungsi kirimHistoriKeFirebase()
// yang sekarang tidak dipanggil lagi. Dibiarkan agar tidak menghapus kode.
const String DB_ROOT = "/ecosense";

// =====================================================================
// KONFIGURASI NODE -- UBAH HANYA DI SINI UNTUK TIAP UNIT FISIK (N0/N1/N2)
// =====================================================================
// NODE_ID: compile-time, menentukan Firebase path, nama file CSV/metadata
// SD, label debug Serial, dan metadata GPS. Ganti ke "N1" atau "N2" sesuai
// unit fisik yang akan di-flash, lalu compile ulang untuk unit itu.
#define NODE_ID "N0"

// HAS_TURBIDITY: set false HANYA untuk node yang saat ini belum punya
// sensor turbidity terpasang (sensor pengganti masih dalam pengiriman).
// Saat false: GPIO turbidity TIDAK dibaca, Serial/OLED menampilkan
// "MISSING", CSV mencatat "NA", packet Firebase mengirim null untuk key
// "turbidity" (key tetap ada). [BELUM DIKONFIRMASI pengguna node mana yang
// kehilangan sensor ini -- default di bawah "true", UBAH SESUAI KONDISI
// FISIK unit yang sedang di-flash sebelum compile.]
const bool HAS_TURBIDITY = true;

const String HARDWARE_TEST_PATH = String("/hardware_test/nodes/") + NODE_ID + "/latest";

// =====================================================================
// TASNIM FIELD SHADOW — TAMBAHAN MINIMAL
// =====================================================================
// Default FALSE supaya firmware working lama tetap berperilaku persis seperti
// sebelumnya sampai Firebase Rules untuk /field sudah siap.
// Setelah rules siap dan akan diuji, ubah menjadi true lalu compile/upload.
const bool ENABLE_FIELD_SHADOW = true;

// Snapshot realtime FIELD: tetap mengikuti siklus Firebase existing (5 detik).
const String FIELD_LATEST_PATH =
  String("/field/nodes/") + NODE_ID + "/latest";

// Dataset penelitian: tepat satu child per canonical slot 5 menit.
const uint64_t FIELD_HISTORY_SLOT_MS = 300000ULL;

// 0 aman sebagai sentinel karena epoch timestamp valid selalu > 0.
uint64_t lastFieldHistorySlotMs = 0;

// ---------------- KONFIGURASI PIN ----------------
#define OLED_SDA    21
#define OLED_SCL    22
#define PH_PIN      34   // ADC1, input-only
#define TDS_PIN     35   // ADC1, input-only
#define TURB_PIN    32   // ADC1 (hanya dibaca jika HAS_TURBIDITY == true)

// ---------------- KONFIGURASI LED STATUS ----------------
#define LED_HIJAU_PIN   25   // AMAN     (skor >= 70, tanpa anomali)
#define LED_KUNING_PIN  13   // WASPADA  (skor 50-69, tanpa anomali)
#define LED_MERAH_PIN   14   // KRITIS   (skor < 50, atau ada anomali sensor)

// ---------------- BARU: KONFIGURASI microSD (VSPI) ----------------
// STATUS: [DESIGN DECISION] dari pengguna (belum diverifikasi ke wiring
// fisik). VSPI default ESP32; tidak bentrok dengan pin sensor/OLED/LED di
// atas (34/35/32/21/22/25/13/14). Kalau source/foto nanti menunjukkan pin
// ini dipakai fungsi lain, STOP dan laporkan [CONFLICT] -- jangan diam-diam
// diganti.
#define SD_CS_PIN    5
#define SD_MOSI_PIN  23
#define SD_MISO_PIN  19
#define SD_SCK_PIN   18

// ---------------- BARU: KONFIGURASI GPS NEO-6M (UART2) ----------------
// STATUS: [DESIGN DECISION] dari pengguna. ASUMSI modul UART standar
// (bukan I2C) -- lihat catatan di header file.
#define GPS_RX_PIN   16   // ESP32 RX2 <- GPS TX
#define GPS_TX_PIN   17   // ESP32 TX2 -> GPS RX
#define GPS_BAUD     9600 // [INFERENCE] umum untuk NEO-6M, belum dikonfirmasi dari modul fisik

// ---------------- KONFIGURASI OLED ----------------
#define SCREEN_WIDTH   128
#define SCREEN_HEIGHT  64
#define OLED_RESET     -1
#define OLED_ADDRESS   0x3C   // jika layar tidak muncul, coba 0x3D
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ---------------- KONFIGURASI ADC ----------------
const int ADC_SAMPLES = 20;   // jumlah sampel per pembacaan
const int ADC_TRIM    = 4;    // buang 4 terendah & 4 tertinggi sebelum dirata-rata

// Faktor pembagi tegangan: V_sensor = V_ADC * DIV
const float DIV_PH   = 1.5;   // R1 10k, R2 20k
const float DIV_TDS  = 1.0;   // tanpa pembagi (keluaran 0-2,3 V)
const float DIV_TURB = 1.5;   // R1 10k, R2 20k

// ---------------- KALIBRASI pH (DUA TITIK) ----------------
// ISI DARI HASIL PENGUKURANMU. Nilai di bawah hanya placeholder.
// Celupkan probe ke buffer, tunggu stabil, catat "V_pH" dari Serial Monitor,
// lalu isi di sini. Setelah diisi, ubah PH_SUDAH_KALIBRASI menjadi true.
// TIDAK diubah malam ini -- kalibrasi dijadwalkan besok (lihat header).
const bool  PH_SUDAH_KALIBRASI = false;
const float PH_BUF1 = 6.86, PH_V1 = 2.50;   // tegangan (V) saat di buffer pH 6,86
const float PH_BUF2 = 4.01, PH_V2 = 3.05;   // tegangan (V) saat di buffer pH 4,01

// Suhu air untuk kompensasi TDS (°C). Ganti dengan pembacaan DS18B20 bila ada.
float suhuAir = 25.0;

// ---------------- WAKTU (NTP) ----------------
// Dipakai supaya data yang dikirim ke Firebase punya timestamp asli (epoch
// Unix, detik), bukan cuma millis() sejak boot.
const char* ntpServer = "pool.ntp.org";
const long  gmtOffset_sec = 7 * 3600;  // WIB = UTC+7

const int   daylightOffset_sec = 0;
bool waktuTersinkron = false;

unsigned long getEpochTime() {
  time_t now;
  time(&now);
  return (unsigned long)now;
}

// ---------------- OBJEK FIREBASE ----------------
void processFirebaseResult(AsyncResult &aResult);

UserAuth user_auth(API_KEY, USER_EMAIL, USER_PASS);
FirebaseApp app;
WiFiClientSecure ssl_client;
using AsyncClient = AsyncClientClass;
AsyncClient aClient(ssl_client);
RealtimeDatabase Database;

// ---------------- VARIABEL GLOBAL ----------------
float vPH = 0, vTDS = 0, vTurb = 0;   // tegangan mentah di sisi sensor (V)
// [PHASE 1 -- BARU] tegangan ADC mentah (V), SEBELUM dikali faktor divider.
// Hanya untuk observasi/kalibrasi, TIDAK dipakai di perhitungan mana pun.
float adcPH = 0, adcTDS = 0, adcTurb = 0;
// [BARU] true kalau turbidity benar-benar dibaca cycle ini (HAS_TURBIDITY
// true DAN sudah sempat dibaca minimal sekali). Dipakai di banyak tempat
// untuk membedakan "sensor tidak ada" dari "sensor ada tapi nilainya 0".
bool turbidityValid = false;

float phValue  = 7.0;
float tdsValue = 0;
float ntuValue = 0;

unsigned long lastRead = 0;
const unsigned long interval = 2500;   // siklus baca sensor lokal (OLED/LED)

unsigned long lastWifiCheck = 0;
const unsigned long wifiCheckInterval = 10000;
bool wifiWasConnected = false;


// Kirim snapshot "terbaru" ke Firebase tiap interval ini. BARU malam ini:
// interval yang sama juga dipakai sebagai siklus measurement bersama
// (SD + Firebase), lihat prosesMeasurementCycle().
unsigned long lastFirebasePush = 0;
const unsigned long firebasePushInterval = 5000;

// ---------------- INIT-ONCE NETWORK SERVICES ----------------
// Guard supaya configTime() dan setup Firebase (initializeApp, Database.url,
// dst.) hanya dijalankan SATU KALI -- termasuk kasus WiFi baru tersambung
// belakangan (bukan saat boot), lihat inisialisasiLayananJaringanJikaPerlu().
bool ntpConfigured = false;
bool firebaseInitialized = false;

// ---------------- PACKET TASNIM hardware_test ----------------
// Naik 1x untuk setiap PACKET BARU yang dibangun -- bukan per retry packet
// yang sama (lihat prosesMeasurementCycle()). Reset ke 0 tiap reboot; belum
// ada persistence (NVS). Sesuai instruksi malam ini: KNOWN LIMITATION,
// jangan dikarang seolah persistent -- lihat catatan di prosesMeasurementCycle().
uint32_t sequenceCounter = 0;

// Timestamp WAKTU PENGUKURAN (bukan waktu kirim), di-capture di bacaSensor()
// lewat dapatkanWaktuPengukuran() [BARU]. Sumber waktu: NTP (presisi 1 detik,
// 3 digit terakhir epoch ms selalu 000 -- valid, bukan bug) dengan fallback
// ke RTC DS3231 kalau NTP tidak tersedia. Dipakai apa adanya nanti oleh
// prosesMeasurementCycle() -- BUKAN timestamp baru saat kirim/tulis SD.
uint64_t latestMeasurementTimestampMs = 0;
bool latestMeasurementTimestampValid = false;

// Retry sinkronisasi NTP berkala, tidak agresif tiap loop.
unsigned long lastNtpRetryAttempt = 0;
const unsigned long ntpRetryInterval = 30000;

// =====================================================================
// BARU malam ini: OBJEK & STATUS microSD, RTC DS3231, GPS NEO-6M
// =====================================================================
RTC_DS3231 rtc;
bool rtcAvailable = false;   // diisi di setup() setelah rtc.begin()

bool sdAvailable = false;    // diisi di setup() setelah SD.begin()

TinyGPSPlus gps;
bool gpsMetadataSaved = false;             // true setelah metadata ditulis SEKALI
unsigned long lastGpsWaitPrint = 0;
const unsigned long gpsWaitPrintInterval = 5000;   // throttle print "[GPS] Waiting..."
// [BARU -- DIAGNOSTIK] Penghitung total byte mentah yang pernah diterima dari
// modul GPS lewat UART2. Ini membedakan dua kemungkinan:
//  - angka ini TETAP 0 selamanya -> wiring RX/TX/GND/VCC ke modul GPS putus,
//    atau arah RX/TX terbalik -- bukan soal fix satelit sama sekali.
//  - angka ini NAIK terus -> wiring UART sudah benar, modul mengirim data,
//    tinggal menunggu fix satelit (atau cek baud rate / posisi antena).
unsigned long gpsRawByteCount = 0;
unsigned long lastGpsByteCountPrint = 0;
const unsigned long gpsByteCountPrintInterval = 5000;

// Nama file CSV per node (NODE_ID, bukan hardcode).
String sdCsvFilename() {
  return String("/tasnim_") + NODE_ID + ".csv";
}
String sdMetadataFilename() {
  return String("/metadata_") + NODE_ID + ".csv";
}

// Inisialisasi NTP & Firebase, idempotent (aman dipanggil tiap loop).
// Memperbaiki kondisi: sebelumnya configTime()/initializeApp() hanya
// dijalankan di setup() saat WiFi berhasil connect SAAT BOOT. Kalau WiFi
// baru tersedia belakangan (lewat reconnect di cekKoneksiWiFi()), NTP dan

// Firebase sebelumnya TIDAK PERNAH diinisialisasi sama sekali.
void inisialisasiLayananJaringanJikaPerlu() {
  if (WiFi.status() != WL_CONNECTED) return;

  if (!ntpConfigured) {
    configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
    ntpConfigured = true;
    Serial.println("NTP dikonfigurasi.");
  }

  if (!firebaseInitialized) {
    ssl_client.setInsecure();
    ssl_client.setConnectionTimeout(1000);
    ssl_client.setHandshakeTimeout(5);

    initializeApp(aClient, app, getAuth(user_auth), processFirebaseResult, "authTask");
    app.getApp<RealtimeDatabase>(Database);
    Database.url(DATABASE_URL);

    firebaseInitialized = true;
    Serial.println("Firebase diinisialisasi.");
  }
}

// Cek berkala apakah waktu sudah tersedia. Tidak memanggil configTime() lagi
// di sini -- itu tugas inisialisasiLayananJaringanJikaPerlu(). Timeout
// getLocalTime() dibuat pendek (100ms) supaya tidak memblokir loop lama.
void cobaSinkronisasiWaktu() {
  if (waktuTersinkron) return;
  if (WiFi.status() != WL_CONNECTED) return;
  if (lastNtpRetryAttempt != 0 && millis() - lastNtpRetryAttempt < ntpRetryInterval) return;


  lastNtpRetryAttempt = millis();
  struct tm timeinfo;
  if (getLocalTime(&timeinfo, 100)) {
    waktuTersinkron = true;
    Serial.println("Waktu NTP tersinkron (retry berkala).");
    // [BARU] NTP tersedia -> sinkronkan RTC dari NTP (hierarki waktu).
    if (rtcAvailable) {
      rtc.adjust(DateTime((uint32_t)getEpochTime()));
      Serial.println("[RTC] Disinkronkan dari NTP (retry berkala).");
    }
  } else {
    Serial.println("Retry NTP: waktu belum tersedia, dicoba lagi nanti.");
  }
}

// [BARU] Hierarki sumber waktu pengukuran: NTP (utama) -> RTC DS3231
// (fallback kalau NTP tidak tersedia) -> INVALID (kalau keduanya gagal;
// TIDAK PERNAH membuat epoch palsu/millis() sebagai pengganti).
// Sanity-check "tahun >= 2024" pada RTC: DS3231 yang belum pernah diset
// (atau kehilangan baterai backup) biasanya melaporkan tahun default/lampau
// yang tidak masuk akal -- ini [DESIGN DECISION] penulis, bukan dari
// datasheet, untuk mencegah RTC yang belum valid dianggap sumber waktu sah.
void dapatkanWaktuPengukuran(uint64_t &outMs, bool &outValid) {
  if (waktuTersinkron) {
    outMs = (uint64_t)getEpochTime() * 1000ULL;
    outValid = true;
    return;
  }

  if (rtcAvailable) {
    DateTime now = rtc.now();
    if (now.year() >= 2024) {
      outMs = (uint64_t)now.unixtime() * 1000ULL;
      outValid = true;
      Serial.println("[TIME] Menggunakan RTC (NTP tidak tersedia).");
      return;
    }
  }

  outValid = false;
}

// ================= SMART ANALYTICS ENGINE =================
// "AI" di sini adalah analitik berbasis aturan (rule-based) yang berjalan
// lokal di ESP32, HANYA untuk OLED/Serial/LED. BUKAN output AI penelitian
// TASNIM, dan TIDAK dikirim ke Firebase pada tahap ini.

const int HISTORY_SIZE = 120;                  // hingga ~2 jam bila 1 data/menit
const unsigned long HISTORY_INTERVAL = 60000;  // simpan 1 sampel per menit

float histHealth[HISTORY_SIZE];
float histPH[HISTORY_SIZE];
float histTDS[HISTORY_SIZE];
float histTurb[HISTORY_SIZE];        // NTU mentah -- dipakai untuk tren/anomali
float histTurbScore[HISTORY_SIZE];   // Indeks AI 0-100 -- dipakai untuk statistik
unsigned long histMillis[HISTORY_SIZE];

int historyCount = 0;
int historyHead = 0;
unsigned long lastHistorySample = 0;

bool prevValidTDS = false;
bool prevValidTurb = false;
float prevTDS = 0;

float prevNTU = 0;

// ================= RIWAYAT 10 PEMBACAAN TERAKHIR =================
const int RECENT_SIZE = 10;
float recentPH[RECENT_SIZE];
float recentTDS[RECENT_SIZE];
float recentTurb[RECENT_SIZE];
unsigned long recentMillis[RECENT_SIZE];
int recentHead = 0;
int recentCount = 0;

float clamp100(float x) {
  if (x < 0) return 0;
  if (x > 100) return 100;
  return x;
}

float scoreRange(float x, float idealMin, float idealMax,
                 float lowLimit, float highLimit) {
  if (x >= idealMin && x <= idealMax) return 100.0;
  if (x < lowLimit || x > highLimit) return 0.0;

  if (x < idealMin) {
    return 35.0 + 65.0 * ((x - lowLimit) / (idealMin - lowLimit));
  }
  return 35.0 + 65.0 * ((highLimit - x) / (highLimit - idealMax));
}

// pH ideal 6,5-8,5; di luar 5,0-10,0 skornya 0.
float scorePH(float ph) {
  return scoreRange(ph, 6.5, 8.5, 5.0, 10.0);
}


float scoreTDS(float tds) {
  if (tds <= 200) return 100;
  if (tds <= 400) return 92 - (tds - 200) * 0.10;
  if (tds <= 600) return 72 - (tds - 400) * 0.16;
  if (tds <= 900) return 40 - (tds - 600) * 0.08;
  return clamp100(16 - (tds - 900) * 0.01);
}

// Kekeruhan (NTU): <=3 sempurna, 5 NTU = 92, 25 NTU = 40, 100 NTU = 10.
float scoreTurb(float ntu) {
  if (ntu <= 3) return 100;
  if (ntu <= 5) return 100 - (ntu - 3) * 4.0;
  if (ntu <= 25) return 92 - (ntu - 5) * 2.6;
  if (ntu <= 100) return 40 - (ntu - 25) * 0.4;
  return clamp100(10 - (ntu - 100) * 0.01);
}

// [DIUBAH untuk HAS_TURBIDITY] Kalau turbidity tidak tersedia, bobot
// dialihkan ke pH (50%) dan TDS (50%) -- [DESIGN DECISION] penulis, supaya
// ketiadaan sensor TIDAK dibaca seolah "turbidity sempurna/0 NTU" (yang akan
// menaikkan skor secara palsu) maupun diperlakukan sebagai kegagalan (yang
// akan menurunkan skor secara palsu). Saat HAS_TURBIDITY true, rumus bobot
// ASLI (35/35/30) tidak berubah sama sekali.
float getHealthIndex() {
  float sPH   = scorePH(phValue);
  float sTDS  = scoreTDS(tdsValue);

  if (!turbidityValid) {
    return clamp100(0.5 * sPH + 0.5 * sTDS);
  }

  float sTurb = scoreTurb(ntuValue);
  float total = 0.35 * sPH
              + 0.35 * sTurb
              + 0.30 * sTDS;
  return clamp100(total);
}

String healthStatus(float score) {
  if (score >= 85) return "SANGAT BAIK";

  if (score >= 70) return "BAIK";
  if (score >= 50) return "WASPADA";
  return "BAHAYA";
}

String anomalySensor = "";
String anomalyDetail = "";

// [DIUBAH untuk HAS_TURBIDITY] Blok pengecekan anomali Turbidity dilewati
// total kalau !turbidityValid -- tidak ada gunanya mendeteksi anomali pada
// sensor yang memang tidak terpasang. Blok pH dan TDS TIDAK diubah.
void checkAnomaly() {
  if (isnan(phValue) || phValue < 0 || phValue > 14 || vPH < 0.1) {
    anomalySensor = "pH";
    anomalyDetail = "Nilai pH di luar 0-14 atau tegangan modul nyaris nol; periksa kalibrasi, probe, kabel, dan pembagi tegangan.";
    return;
  }

  if (tdsValue < 0 || tdsValue > 5000 ||
      (prevValidTDS && fabs(tdsValue - prevTDS) > 1500)) {
    anomalySensor = "TDS";
    anomalyDetail = "Perubahan TDS sangat tajam; periksa probe, kabel, dan konektor.";
    return;
  }

  if (turbidityValid) {
    if (vTurb < 0.5 ||
        (prevValidTurb && fabs(ntuValue - prevNTU) > 1500)) {
      anomalySensor = "Turbidity";
      anomalyDetail = "Tegangan sensor kekeruhan nyaris nol atau berubah tidak wajar; periksa suplai 5V, kabel, dan pembagi tegangan.";
      return;
    }
  }

  anomalySensor = "";
  anomalyDetail = "";
}


bool anomalyDetected() {
  return anomalySensor.length() > 0;
}

String getRecommendationCore() {
  if (anomalyDetected()) {
    return "Status Sensor: PERLU PEMERIKSAAN — terdeteksi pembacaan anomali pada sensor " +
           anomalySensor + ". " + anomalyDetail;
  }

  float score = getHealthIndex();
  bool phNormal = (phValue >= 6.5 && phValue <= 8.5);

  if (score >= 85 && phNormal && (!turbidityValid || ntuValue <= 5) && tdsValue <= 350) {
    return "Kualitas air stabil. pH, TDS, dan kekeruhan berada pada kondisi yang mendukung proses monitoring dan filtrasi lanjutan.";
  }

  if (turbidityValid && ntuValue > 25) {
    return "Peringatan: kekeruhan air tinggi. Periksa media filtrasi dan tahap penyaringan awal, lalu pastikan tidak ada sedimen yang terbawa.";
  }

  if (tdsValue > 750) {
    return "Peringatan: nilai TDS tinggi. Periksa kondisi media filtrasi dan lakukan evaluasi kualitas air sebelum tahap berikutnya.";
  }

  if (phValue < 6.5) {
    return "pH air di bawah 6,5 (cenderung asam). Periksa sumber air dan kondisi media filtrasi, dan pastikan probe pH sudah dikalibrasi.";
  }

  if (phValue > 8.5) {
    return "pH air di atas 8,5 (cenderung basa). Periksa sumber air dan kondisi media filtrasi, dan pastikan probe pH sudah dikalibrasi.";

  }

  if (turbidityValid && ntuValue > 5) {
    return "Kekeruhan air mulai meningkat. Pantau tren dan periksa tahap penyaringan bila nilainya terus naik.";
  }

  if (score >= 70) {
    return "Kondisi keseluruhan masih tergolong baik. Sistem memantau perubahan sensor secara real-time dan akan memberi peringatan jika tren memburuk.";
  }

  return "Sistem mendeteksi kondisi yang perlu diperhatikan. Pantau sensor yang memiliki skor terendah untuk menentukan tindakan berikutnya.";
}

String getRecommendation() {
  String pesan = getRecommendationCore();
  if (!PH_SUDAH_KALIBRASI && !anomalyDetected()) {
    pesan += " Catatan: kalibrasi pH belum dilakukan, jadi nilai pH belum bisa dijadikan acuan.";
  }
  if (!turbidityValid) {
    pesan += " Catatan: sensor turbidity belum terpasang pada node ini (HAS_TURBIDITY=false); parameter kekeruhan tidak dipantau sementara.";
  }
  return pesan;
}

// [DIUBAH untuk HAS_TURBIDITY] histTurb/histTurbScore diisi NAN (sentinel,
// BUKAN 0) kalau turbidity tidak tersedia cycle ini -- supaya statistik/tren
// turbidity tidak diam-diam menganggap "tidak ada data" sebagai "0 NTU".
void pushHistory() {
  if (historyCount > 0 && millis() - lastHistorySample < HISTORY_INTERVAL) return;

  histHealth[historyHead] = getHealthIndex();
  histPH[historyHead] = phValue;
  histTDS[historyHead] = tdsValue;
  if (turbidityValid) {
    histTurb[historyHead] = ntuValue;
    histTurbScore[historyHead] = getTurbAIIndex();
  } else {
    histTurb[historyHead] = NAN;
    histTurbScore[historyHead] = NAN;
  }
  histMillis[historyHead] = millis();

  historyHead = (historyHead + 1) % HISTORY_SIZE;

  if (historyCount < HISTORY_SIZE) historyCount++;
  lastHistorySample = millis();

  // DINONAKTIFKAN untuk tahap hardware_test: tidak ada write ke
  // /ecosense/history atau /ecosense/stats. Fungsi kirimHistoriKeFirebase()
  // sengaja DIBIARKAN di bawah, hanya pemanggilannya diputus di sini.
  //
  // if (app.ready()) {
  //   kirimHistoriKeFirebase();
  // }
}

int historyIndexFromNewest(int offset) {
  if (offset < 0 || offset >= historyCount) return -1;
  int idx = historyHead - 1 - offset;
  if (idx < 0) idx += HISTORY_SIZE;
  return idx;
}

float avgHistory(const float arr[], int startOffset, int count) {
  if (count <= 0 || startOffset >= historyCount) return 0;
  float sum = 0;
  int used = 0;
  for (int i = startOffset; i < startOffset + count && i < historyCount; i++) {
    int idx = historyIndexFromNewest(i);
    if (idx >= 0) {
      sum += arr[idx];
      used++;
    }
  }
  return used ? sum / used : 0;
}


String getTrendInsight() {
  if (historyCount < 10) {
    return "Analisis tren sedang membangun histori. Minimal 10 sampel diperlukan agar wawasan perubahan lebih stabil.";
  }

  int recentN = min(6, historyCount);
  int olderStart = recentN;
  int olderN = min(6, historyCount - olderStart);

  float healthDelta = avgHistory(histHealth, 0, recentN) - avgHistory(histHealth, olderStart, olderN);
  float phDelta     = avgHistory(histPH,     0, recentN) - avgHistory(histPH,     olderStart, olderN);
  float tdsDelta    = avgHistory(histTDS,    0, recentN) - avgHistory(histTDS,    olderStart, olderN);
  float turbDelta   = avgHistory(histTurb,   0, recentN) - avgHistory(histTurb,   olderStart, olderN);

  if (healthDelta > 4) {
    return "Tren meningkat: skor kualitas air naik sekitar " + String(healthDelta, 1) +
           " poin dibanding periode sebelumnya. Kondisi air menunjukkan perbaikan.";
  }

  if (healthDelta < -4) {
    if (turbDelta > 3) {
      return "Tren menurun: skor kualitas air turun sekitar " + String(fabs(healthDelta), 1) +
             " poin, terutama karena kekeruhan meningkat. Periksa tahap penyaringan.";
    }
    if (tdsDelta > 80) {
      return "Tren menurun: skor kualitas air turun sekitar " + String(fabs(healthDelta), 1) +
             " poin karena TDS meningkat. Evaluasi tahap pemurnian air.";
    }
    if (fabs(phDelta) > 0.5) {
      return "Tren menurun: skor kualitas air turun sekitar " + String(fabs(healthDelta), 1) +
             " poin karena pH bergeser. Periksa sumber air dan kalibrasi probe pH.";

    }
    return "Tren menurun: skor kualitas air turun sekitar " + String(fabs(healthDelta), 1) +
           " poin. Periksa sensor dengan perubahan terbesar.";
  }

  return "Tren relatif stabil. Dalam histori terbaru, tidak terlihat perubahan besar pada skor kualitas air terintegrasi.";
}

float projectedHealth() {
  if (historyCount < 10) return getHealthIndex();
  int n = min(6, historyCount);
  float recent = avgHistory(histHealth, 0, n);
  float older = avgHistory(histHealth, n, min(n, historyCount - n));
  return clamp100(recent + (recent - older));
}

// =======================================================
//     STATISTIK: MEAN, STANDAR DEVIASI, MIN/MAX, CV
// =======================================================
void computeStats(const float arr[], int n, int bufSize, int head,
                   int &outCount, float &outMean, float &outStdDev,
                   float &outMin, float &outMax, float &outCV) {
  outCount = 0; outMean = 0; outStdDev = 0; outMin = 0; outMax = 0; outCV = 0;
  if (n <= 0) return;

  int use = min(n, bufSize);
  float sum = 0;
  float minV = 1e12, maxV = -1e12;

  for (int i = 0; i < use; i++) {
    int idx = head - 1 - i;
    if (idx < 0) idx += bufSize;

    float v = arr[idx];
    sum += v;
    if (v < minV) minV = v;
    if (v > maxV) maxV = v;
  }
  float mean = sum / use;

  float sqSum = 0;
  for (int i = 0; i < use; i++) {
    int idx = head - 1 - i;
    if (idx < 0) idx += bufSize;
    float d = arr[idx] - mean;
    sqSum += d * d;
  }
  float sd = sqrt(sqSum / use);

  outCount  = use;
  outMean   = mean;
  outStdDev = sd;
  outMin    = minV;
  outMax    = maxV;
  outCV     = (mean != 0) ? (sd / fabs(mean)) * 100.0 : 0;
}

// Klasifikasi stabilitas berdasarkan koefisien variasi (CV).
String klasifikasiStabilitas(float cv, int count) {
  if (count < 5) return "MENGUMPULKAN DATA";
  if (cv <= 8)  return "SANGAT STABIL";
  if (cv <= 18) return "STABIL";
  if (cv <= 35) return "FLUKTUATIF";
  return "SANGAT FLUKTUATIF";
}


// Indeks Kekeruhan berbasis AI (0-100, makin tinggi makin jernih).
// [DIUBAH untuk HAS_TURBIDITY] Mengembalikan -1 sebagai sentinel "tidak ada
// data" kalau turbidity tidak tersedia -- pemanggil wajib cek -1 sebelum
// menampilkan sebagai angka.
int getTurbAIIndex() {
  if (!turbidityValid) return -1;
  return (int)round(scoreTurb(ntuValue));
}

// Tren kekeruhan dari histTurbScore. Skor naik = kekeruhan turun.
String getTurbTrendLabel() {
  if (!turbidityValid) return "MISSING";
  if (historyCount < 10) return "MENGUMPULKAN DATA";
  int recentN = min(6, historyCount);
  int olderStart = recentN;
  int olderN = min(6, historyCount - olderStart);
  float recentScore = avgHistory(histTurbScore, 0, recentN);
  float olderScore  = avgHistory(histTurbScore, olderStart, olderN);
  float delta = recentScore - olderScore;
  if (delta < -8) return "MENINGKAT";  // skor turun tajam -> kekeruhan naik
  if (delta > 8)  return "MENURUN";    // skor naik tajam -> kekeruhan turun
  return "STABIL";
}

// Rekomendasi AI khusus kekeruhan: gabungan klasifikasi fuzzy + tren + statistik.
// [DIUBAH untuk HAS_TURBIDITY] Balik pesan khusus kalau sensor tidak terpasang.
String getTurbAIRecommendation() {
  if (!turbidityValid) {
    return "Sensor kekeruhan belum terpasang pada node ini (HAS_TURBIDITY=false). Parameter pH dan TDS tetap dipantau seperti biasa.";
  }

  if (anomalySensor == "Turbidity") {
    return "Sensor kekeruhan menunjukkan pembacaan tidak wajar: " + anomalyDetail;
  }

  String label = klasifikasiTurbidity(ntuValue);
  String trend = getTurbTrendLabel();
  int idx = getTurbAIIndex();

  int tCount; float tMean, tStd, tMin, tMax, tCV;
  computeStats(histTurbScore, historyCount, HISTORY_SIZE, historyHead,
               tCount, tMean, tStd, tMin, tMax, tCV);
  String stab = klasifikasiStabilitas(tCV, tCount);


  String msg = "Kekeruhan air saat ini tergolong " + label + " (" + String(ntuValue, 1) +
               " NTU, indeks AI " + String(idx) + "/100).";

  if (trend == "MENINGKAT") {
    msg += " Analisis tren AI mendeteksi kenaikan kekeruhan dibanding periode sebelumnya - periksa media filtrasi dan sumber partikel tersuspensi.";
  } else if (trend == "MENURUN") {
    msg += " Tren menunjukkan penurunan kekeruhan; air makin jernih dibanding periode sebelumnya.";
  } else if (trend == "STABIL") {
    msg += " Tren relatif stabil, tidak ada perubahan signifikan pada histori terbaru.";
  } else {
    msg += " Sistem masih mengumpulkan histori untuk analisis tren yang lebih akurat.";
  }

  if (stab == "FLUKTUATIF" || stab == "SANGAT FLUKTUATIF") {
    msg += " Variasi indeks tergolong " + stab + " (CV " + String(tCV, 1) + "%), disarankan cek posisi sensor, gelembung udara di jalur air, dan kestabilan catu daya 5V.";
  }

  return msg;
}

// Skor per sensor (dipertahankan untuk keperluan analisis/log).
float getPHScore()   { return scorePH(phValue); }
float getTDSScore()  { return scoreTDS(tdsValue); }
float getTurbScore() { return turbidityValid ? scoreTurb(ntuValue) : NAN; }

// =======================================================
//        RIWAYAT 10 PEMBACAAN MENTAH TERAKHIR
// =======================================================
void pushRecent() {
  recentPH[recentHead] = phValue;
  recentTDS[recentHead] = tdsValue;

  recentTurb[recentHead] = turbidityValid ? ntuValue : NAN;
  recentMillis[recentHead] = millis();

  recentHead = (recentHead + 1) % RECENT_SIZE;
  if (recentCount < RECENT_SIZE) recentCount++;
}

int recentIndexFromNewest(int offset) {
  if (offset < 0 || offset >= recentCount) return -1;
  int idx = recentHead - 1 - offset;
  if (idx < 0) idx += RECENT_SIZE;
  return idx;
}

// =======================================================
//                  INDIKATOR LED STATUS
// =======================================================
// Merah diprioritaskan kalau ada anomali sensor, karena data yang tidak
// wajar tetap butuh perhatian meski skor kebetulan tinggi.
void updateLEDStatus() {
  float score = getHealthIndex();

  bool kritis  = anomalyDetected() || score < 50;
  bool waspada = !kritis && score < 70;
  bool aman    = !kritis && !waspada;

  digitalWrite(LED_HIJAU_PIN,  aman    ? HIGH : LOW);
  digitalWrite(LED_KUNING_PIN, waspada ? HIGH : LOW);
  digitalWrite(LED_MERAH_PIN,  kritis  ? HIGH : LOW);
}

void setup() {

  Serial.begin(115200);

  Wire.begin(OLED_SDA, OLED_SCL);

  // ---- [BARU -- DIAGNOSTIK] I2C scanner, dijalankan SEBELUM display.begin() ----
  // Ditaruh di sini (bukan setelah OLED) supaya tetap jalan walau OLED gagal,
  // dan supaya kita tahu PERSIS alamat I2C apa saja yang benar-benar terdeteksi
  // secara elektrik di bus ini (GPIO21=SDA, GPIO22=SCL) -- termasuk RTC DS3231
  // (alamat umum 0x68), sebelum library mana pun mencoba menginisialisasinya.
  // Ini murni untuk diagnosis, TIDAK mengubah perilaku program lainnya.
  Serial.println("[I2C] Scan bus (SDA=GPIO21, SCL=GPIO22)...");
  {
    int i2cFound = 0;
    for (uint8_t addr = 1; addr < 127; addr++) {
      Wire.beginTransmission(addr);
      uint8_t err = Wire.endTransmission();
      if (err == 0) {
        Serial.print("[I2C] Perangkat ditemukan di alamat 0x");
        if (addr < 16) Serial.print("0");
        Serial.println(addr, HEX);
        i2cFound++;
      }
    }
    if (i2cFound == 0) {
      Serial.println("[I2C] TIDAK ADA perangkat terdeteksi di bus ini sama sekali -- cek wiring SDA/SCL/GND/VCC untuk OLED maupun RTC.");
    } else {
      Serial.print("[I2C] Total perangkat ditemukan: ");
      Serial.println(i2cFound);
      Serial.println("[I2C] Catatan: OLED SSD1306 umumnya di 0x3C atau 0x3D, RTC DS3231 umumnya di 0x68.");
    }
  }

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("OLED tidak terdeteksi! Cek pengkabelan SDA/SCL.");
    while (true) delay(1000);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Inisialisasi sensor...");
  display.display();

  // ---- LED Status (Hijau=Aman, Kuning=Waspada, Merah=Kritis) ----
  pinMode(LED_HIJAU_PIN, OUTPUT);
  pinMode(LED_KUNING_PIN, OUTPUT);
  pinMode(LED_MERAH_PIN, OUTPUT);
  digitalWrite(LED_HIJAU_PIN, LOW);
  digitalWrite(LED_KUNING_PIN, LOW);
  digitalWrite(LED_MERAH_PIN, LOW);

  // ESP32 ADC: 12-bit, attenuation 11dB supaya bisa membaca sampai ~3,3 V
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  delay(1000);

  // =====================================================================
  // BARU malam ini: inisialisasi microSD, RTC DS3231, GPS NEO-6M.
  // Ditempatkan SEBELUM blok WiFi karena ketiganya tidak bergantung WiFi,
  // dan sesuai fail-safe: kegagalan salah satu TIDAK menghentikan yang lain
  // atau menghentikan sensor/WiFi/Firebase di bawah.
  // =====================================================================
  Serial.println("--- Inisialisasi microSD, RTC, GPS (CANDIDATE) ---");

  // ---- microSD (VSPI) ----
  SPI.begin(SD_SCK_PIN, SD_MISO_PIN, SD_MOSI_PIN, SD_CS_PIN);
  sdAvailable = SD.begin(SD_CS_PIN);
  if (sdAvailable) {
    Serial.println("[SD] OK (terdeteksi).");
    // ---- [BARU -- DIAGNOSTIK] Tipe & ukuran kartu, untuk membedakan
    // "kartu benar-benar terdeteksi secara elektrik" dari sekadar
    // SD.begin() yang kebetulan tidak gagal. CARD_NONE di sini berarti
    // SPI/wiring menyala tapi tidak ada kartu yang terbaca sama sekali.
    uint8_t cardType = SD.cardType();
    switch (cardType) {
      case CARD_NONE:
        Serial.println("[SD] DIAGNOSTIK: cardType() = CARD_NONE -- wiring SPI mungkin OK tapi kartu TIDAK terbaca. Cek kartu/slot/format (FAT32).");
        break;
      case CARD_MMC:
        Serial.println("[SD] DIAGNOSTIK: cardType() = MMC");
        break;
      case CARD_SD:
        Serial.println("[SD] DIAGNOSTIK: cardType() = SDSC");
        break;
      case CARD_SDHC:
        Serial.println("[SD] DIAGNOSTIK: cardType() = SDHC/SDXC");
        break;
      default:
        Serial.println("[SD] DIAGNOSTIK: cardType() = UNKNOWN");
        break;
    }
    uint64_t cardSizeMB = SD.cardSize() / (1024 * 1024);
    Serial.print("[SD] DIAGNOSTIK: ukuran kartu = ");
    Serial.print(cardSizeMB);
    Serial.println(" MB");
  } else {
    Serial.println("[SD] ERROR (tidak terdeteksi). Firebase/sensor tetap lanjut.");
    Serial.println("[SD] DIAGNOSTIK: SD.begin() gagal total -- cek CS/MOSI/MISO/SCK, VCC (5V atau 3.3V sesuai modul), dan GND bersama ke ESP32.");
  }

  // ---- RTC DS3231 (berbagi bus I2C dengan OLED, Wire sudah di-begin di atas) ----
  rtcAvailable = rtc.begin();
  if (rtcAvailable) {
    Serial.println("[RTC] OK (terdeteksi).");
    if (rtc.lostPower()) {
      Serial.println("[RTC] PERINGATAN: lostPower() true -- waktu RTC kemungkinan tidak valid sampai disinkronkan dari NTP.");
    }
    DateTime now = rtc.now();
    Serial.print("[RTC] Waktu saat ini (sebelum sinkron NTP): ");
    Serial.print(now.year()); Serial.print("-");
    Serial.print(now.month()); Serial.print("-");
    Serial.println(now.day());
  } else {
    Serial.println("[RTC] ERROR (tidak terdeteksi). Timestamp akan mengandalkan NTP saja.");
  }

  // ---- GPS NEO-6M (UART2) ----
  Serial2.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  Serial.println("[GPS] UART2 dimulai, menunggu fix pertama (non-blocking, lihat loop()).");

  // ---- Koneksi WiFi ----
  display.clearDisplay();

  display.setCursor(0, 0);
  display.println("Menghubungkan WiFi...");
  display.display();

  WiFi.mode(WIFI_STA);

  // Diagnostik: tampilkan daftar WiFi yang terdeteksi ESP32,
  // supaya nama SSID (huruf besar/kecil, spasi, dll) bisa dicocokkan persis.
  Serial.println("Mencari jaringan WiFi di sekitar...");
  int jumlahJaringan = WiFi.scanNetworks();
  if (jumlahJaringan == 0) {
    Serial.println("  Tidak ada jaringan WiFi terdeteksi sama sekali!");
  } else {
    for (int i = 0; i < jumlahJaringan; i++) {
      Serial.print("  ");
      Serial.print(i + 1);
      Serial.print(". \"");
      Serial.print(WiFi.SSID(i));
      Serial.print("\" (");
      Serial.print(WiFi.RSSI(i));
      Serial.println(" dBm)");
    }
  }
  Serial.println();

  WiFi.begin(ssid, password);
  Serial.print("Menghubungkan ke WiFi \"");
  Serial.print(ssid);
  Serial.print("\"");

  unsigned long wifiStart = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 20000) {

    delay(300);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi terhubung. Alamat IP: ");
    Serial.println(WiFi.localIP());

    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("WiFi Tersambung!");
    display.setCursor(0, 16);
    display.println(WiFi.localIP());
    display.setCursor(0, 30);
    display.println("Menyiapkan Firebase...");
    display.display();

    // NTP & Firebase diinisialisasi lewat fungsi bersama (idempotent), supaya
    // jalur boot ini identik dengan kasus WiFi baru tersambung belakangan
    // di loop() -- lihat inisialisasiLayananJaringanJikaPerlu().
    inisialisasiLayananJaringanJikaPerlu();

    // Percobaan sinkronisasi waktu SEKALI saat boot (blocking, maks 8 detik).
    // Perilaku ini SAMA seperti kode sebelumnya -- hanya dipindah setelah
    // configTime() dijalankan lewat fungsi di atas. Kalau WiFi baru tersambung
    // belakangan (bukan saat boot), blocking call ini TIDAK dipakai; waktu
    // akan disinkronkan lewat retry non-blocking cobaSinkronisasiWaktu() di loop().
    struct tm timeinfo;
    if (!waktuTersinkron && getLocalTime(&timeinfo, 8000)) {
      waktuTersinkron = true;
      Serial.println("Waktu NTP tersinkron.");
      // [BARU] NTP tersedia saat boot -> sinkronkan RTC dari NTP.
      if (rtcAvailable) {
        rtc.adjust(DateTime((uint32_t)getEpochTime()));
        Serial.println("[RTC] Disinkronkan dari NTP (saat boot).");
      }

    } else if (!waktuTersinkron) {
      Serial.println("Gagal sinkron waktu NTP saat boot (akan di-retry non-blocking).");
    }

    delay(2000);
  } else {
    Serial.println("Gagal konek WiFi. Sensor tetap jalan, tapi data TIDAK terkirim ke Firebase.");
    Serial.print("Kode status WiFi: ");
    Serial.println(WiFi.status());
    Serial.println("(0=idle, 1=SSID tdk ditemukan, 4=koneksi gagal, 5/6=terputus saat handshake -> biasanya password salah)");
    Serial.println("Cocokkan nama SSID di kode dengan daftar jaringan di atas.");
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("WiFi gagal konek!");
    display.println("Cek SSID/Password");
    display.println("(lihat Serial Monitor)");
    display.display();
    delay(3000);
  }

  wifiWasConnected = (WiFi.status() == WL_CONNECTED);

  if (!PH_SUDAH_KALIBRASI) {
    Serial.println("PERINGATAN: kalibrasi pH belum dilakukan (PH_SUDAH_KALIBRASI = false).");
  }
  if (!HAS_TURBIDITY) {
    Serial.println("INFO: HAS_TURBIDITY = false -- node ini berjalan tanpa sensor turbidity (CANDIDATE mode).");
  }

  delay(500);
}

void loop() {
  cekKoneksiWiFi();


  // Idempotent: menjamin NTP+Firebase diinisialisasi begitu WiFi connect,
  // baik saat boot maupun belakangan lewat reconnect di cekKoneksiWiFi().
  inisialisasiLayananJaringanJikaPerlu();
  cobaSinkronisasiWaktu();

  // app.loop() HANYA dijalankan setelah Firebase diinisialisasi -- sebelum
  // itu, app/Database belum valid untuk diproses.
  if (firebaseInitialized) {
    app.loop();
  }

  // [BARU] GPS dibaca non-blocking tiap loop, tidak menunggu/blocking.
  gpsLoopNonBlocking();

  if (millis() - lastRead >= interval) {
    lastRead = millis();
    bacaSensor();
    updateLEDStatus();
    tampilkanOLED();
    tampilkanSerial();
  }

  // [DIUBAH] Sebelumnya blok ini HANYA memanggil Firebase, dan HANYA kalau
  // firebaseInitialized && app.ready(). Sekarang trigger-nya cuma timer --
  // SD harus tetap jalan walau Firebase/WiFi belum siap ("WiFi mati -> SD
  // tetap logging"). Keputusan kirim-atau-tidak ke Firebase dipindah KE
  // DALAM prosesMeasurementCycle(), supaya SD tidak ikut terhenti.
  if (millis() - lastFirebasePush >= firebasePushInterval) {
    lastFirebasePush = millis();
    prosesMeasurementCycle();
  }
}

// Cek koneksi WiFi berkala dan coba sambung ulang bila putus.
void cekKoneksiWiFi() {
  if (millis() - lastWifiCheck < wifiCheckInterval) return;
  lastWifiCheck = millis();

  bool connectedNow = (WiFi.status() == WL_CONNECTED);


  if (!connectedNow) {
    if (wifiWasConnected) {
      Serial.println("WiFi terputus, mencoba menyambung ulang...");
    }
    WiFi.disconnect();
    WiFi.begin(ssid, password);
  } else if (!wifiWasConnected) {
    Serial.print("WiFi tersambung kembali. Alamat IP: ");
    Serial.println(WiFi.localIP());
  }

  wifiWasConnected = connectedNow;
}

// =======================================================
//                    PEMBACAAN SENSOR
// =======================================================
// [PHASE 1 -- BARU] Parameter ke-4 (outAdcVoltage) WAJIB diisi di semua
// call site (TIDAK diberi default value) -- kalau diberi default (misal
// "= nullptr"), Arduino IDE akan auto-generate prototype di atas file
// SEBELUM definisi aslinya terbaca, dan itu memicu error compile "default
// argument given for parameter ... after its first declaration". Ini
// pelajaran dari kode base ini sendiri (lihat komentar lama terkait bug
// auto-prototype struct) -- BELUM diverifikasi ulang via compile oleh
// asisten, statusnya "secara statis terlihat konsisten, tetapi belum
// VERIFIED sampai compile/upload dilakukan".
float bacaTegangan(uint8_t pin, float faktorDiv, float *outAdcVoltage) {
  uint32_t buf[ADC_SAMPLES];
  for (int i = 0; i < ADC_SAMPLES; i++) {
    buf[i] = analogReadMilliVolts(pin);
    delay(5);
  }
  for (int i = 1; i < ADC_SAMPLES; i++) {
    uint32_t key = buf[i];
    int j = i - 1;
    while (j >= 0 && buf[j] > key) {
      buf[j + 1] = buf[j];
      j--;
    }
    buf[j + 1] = key;

  }
  uint32_t sum = 0;
  for (int i = ADC_TRIM; i < ADC_SAMPLES - ADC_TRIM; i++) sum += buf[i];
  float mv = sum / (float)(ADC_SAMPLES - 2 * ADC_TRIM);
  float adcVolt = mv / 1000.0f;
  if (outAdcVoltage != nullptr) {
    *outAdcVoltage = adcVolt;
  }
  return adcVolt * faktorDiv;
}

// pH: interpolasi linear dua titik dari hasil kalibrasi buffer.
float hitungPH(float v) {
  return PH_BUF1 + (v - PH_V1) * (PH_BUF2 - PH_BUF1) / (PH_V2 - PH_V1);
}

// TDS dengan kompensasi suhu (rumus standar modul TDS Gravity).
float hitungTDS(float v, float tC) {
  float koef = 1.0 + 0.02 * (tC - 25.0);
  float vc = v / koef;
  float tds = (133.42 * vc * vc * vc - 255.86 * vc * vc + 857.39 * vc) * 0.5;
  return tds < 0 ? 0 : tds;
}

// Kekeruhan: kurva umum sensor jenis SEN0189 (suplai 5 V), valid ±2,5-4,2 V.
float hitungNTU(float v) {
  if (v < 2.5) return 3000;
  float ntu = -1120.4 * v * v + 5742.3 * v - 4352.9;
  if (ntu < 0) return 0;
  if (ntu > 3000) return 3000;
  return ntu;
}

// [DIUBAH untuk HAS_TURBIDITY + PHASE 1] Kalau HAS_TURBIDITY false, GPIO
// turbidity TIDAK dibaca sama sekali (bukan dianggap 0) -- sesuai instruksi
// "JANGAN membaca GPIO turbidity sebagai data valid".
void bacaSensor() {
  vPH   = bacaTegangan(PH_PIN,   DIV_PH,   &adcPH);
  vTDS  = bacaTegangan(TDS_PIN,  DIV_TDS,  &adcTDS);

  if (HAS_TURBIDITY) {
    vTurb = bacaTegangan(TURB_PIN, DIV_TURB, &adcTurb);
    turbidityValid = true;
  } else {
    vTurb = 0;
    adcTurb = 0;
    turbidityValid = false;
  }

  phValue  = hitungPH(vPH);
  tdsValue = hitungTDS(vTDS, suhuAir);
  ntuValue = turbidityValid ? hitungNTU(vTurb) : NAN;

  checkAnomaly();

  prevTDS = tdsValue; prevValidTDS = true;
  if (turbidityValid) {
    prevNTU = ntuValue; prevValidTurb = true;
  }

  // [BARU] Timestamp WAKTU PENGUKURAN ini, lewat hierarki NTP->RTC->INVALID.
  // Dipakai apa adanya nanti oleh prosesMeasurementCycle() -- BUKAN timestamp
  // baru saat kirim/tulis SD.
  dapatkanWaktuPengukuran(latestMeasurementTimestampMs, latestMeasurementTimestampValid);

  pushHistory();   // histori lokal 1x/menit (kirim ke Firebase lama sudah nonaktif)
  pushRecent();    // riwayat 10 pembacaan mentah terakhir
}

// =======================================================
//            FUZZY LOGIC - FUNGSI KEANGGOTAAN
// =======================================================
float trapesium(float x, float a, float b, float c, float d) {
  if (x <= a || x >= d) return 0.0;
  if (x >= b && x <= c) return 1.0;
  if (x > a && x < b) return (x - a) / (b - a);
  if (x > c && x < d) return (d - x) / (d - c);

  return 0.0;
}

// ---------- FUZZY pH ----------
String klasifikasiPH(float ph) {
  float asam   = trapesium(ph, -10, -10, 6.0, 6.5);
  float normal = trapesium(ph, 6.0, 6.5, 8.5, 9.0);
  float basa   = trapesium(ph, 8.5, 9.0, 100, 100);

  if (asam >= normal && asam >= basa) return "ASAM";
  if (basa >= normal && basa >= asam) return "BASA";
  return "NORMAL";
}

// ---------- FUZZY KUALITAS AIR (TDS ppm) ----------
String klasifikasiAir(float tds) {
  float jernih = trapesium(tds, -100, -100, 200, 400);
  float sedang = trapesium(tds, 300, 450, 600, 750);
  float keruh  = trapesium(tds, 650, 900, 5000, 5000);

  if (jernih >= sedang && jernih >= keruh) return "JERNIH";
  if (keruh  >= sedang && keruh  >= jernih) return "KERUH";
  return "SEDANG";
}

// ---------- FUZZY KEKERUHAN (NTU) ----------
// [DIUBAH untuk HAS_TURBIDITY] Guard di awal: kalau turbidity tidak
// tersedia (dilewatkan NAN oleh pemanggil), kembalikan "MISSING" tanpa
// menjalankan fuzzy logic sama sekali.
String klasifikasiTurbidity(float ntu) {
  if (isnan(ntu)) return "MISSING";

  float jernih = trapesium(ntu, -100, -100, 3, 5);
  float sedang = trapesium(ntu, 3, 5, 15, 25);
  float keruh  = trapesium(ntu, 15, 25, 10000, 10000);

  if (jernih >= sedang && jernih >= keruh) return "JERNIH";

  if (keruh  >= sedang && keruh  >= jernih) return "KERUH";
  return "SEDANG";
}

// =======================================================
//                     TAMPILAN OLED
// =======================================================
// [DIUBAH untuk HAS_TURBIDITY] Baris Turbidity menampilkan "MISSING"
// kalau !turbidityValid, menggantikan angka NTU + label fuzzy.
void tampilkanOLED() {
  String labelPH   = klasifikasiPH(phValue);
  String labelAir  = klasifikasiAir(tdsValue);
  float score = getHealthIndex();

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  display.setCursor(0, 0);
  display.println("MONITOR KUALITAS AIR");
  display.drawLine(0, 9, 128, 9, SSD1306_WHITE);

  display.setCursor(0, 11);
  display.print("pH  :");
  display.print(phValue, 2);
  display.print(" [");
  display.print(labelPH);
  display.println("]");

  display.setCursor(0, 20);
  display.print("TDS :");
  display.print(tdsValue, 0);
  display.print("ppm[");

  display.print(labelAir);
  display.println("]");

  display.setCursor(0, 29);
  display.print("Turb:");
  if (turbidityValid) {
    display.print(ntuValue, ntuValue < 100 ? 1 : 0);
    display.print("NTU[");
    display.print(klasifikasiTurbidity(ntuValue));
    display.println("]");
  } else {
    display.println("MISSING");
  }

  display.setCursor(0, 38);
  display.print("Skor:");
  display.print((int)round(score));
  display.print(" ");
  display.print(healthStatus(score));

  display.setCursor(0, 47);
  if (anomalyDetected()) {
    display.print("! Cek sensor ");
    display.print(anomalySensor);
  } else if (!PH_SUDAH_KALIBRASI) {
    display.print("pH belum dikalibrasi");
  } else {
    display.print("Sensor: normal");
  }

  display.setCursor(0, 56);
  if (WiFi.status() == WL_CONNECTED) {
    display.print(app.ready() ? "Firebase: terhubung" : "Firebase: menyiapkan");
  } else {
    display.print("WiFi: terputus");
  }


  display.display();
}

// =======================================================
//                  TAMPILAN SERIAL MONITOR
// =======================================================
// [DIUBAH untuk HAS_TURBIDITY] Baris Turbidity menampilkan "MISSING" kalau
// !turbidityValid. [PHASE 1 -- BARU] Blok [CAL] di akhir fungsi ini
// menampilkan tegangan ADC mentah (SEBELUM divider) terpisah dari tegangan
// sensor (SESUDAH divider), untuk persiapan kalibrasi -- TIDAK mengubah
// baris-baris di atasnya yang sudah ada sebelumnya.
void tampilkanSerial() {
  Serial.println("=========================================");
  Serial.print("Tegangan   : pH "); Serial.print(vPH, 3);
  Serial.print(" V | TDS "); Serial.print(vTDS, 3);
  if (turbidityValid) {
    Serial.print(" V | Turb "); Serial.print(vTurb, 3); Serial.println(" V");
  } else {
    Serial.println(" V | Turb MISSING");
  }
  Serial.print("pH         : "); Serial.print(phValue, 2); Serial.print(" -> "); Serial.println(klasifikasiPH(phValue));
  Serial.print("TDS        : "); Serial.print(tdsValue, 0); Serial.print(" ppm -> "); Serial.println(klasifikasiAir(tdsValue));
  if (turbidityValid) {
    Serial.print("Turbidity  : "); Serial.print(ntuValue, 1); Serial.print(" NTU | Indeks AI: "); Serial.print(getTurbAIIndex()); Serial.print("/100 -> "); Serial.println(klasifikasiTurbidity(ntuValue));
  } else {
    Serial.println("Turbidity  : MISSING (HAS_TURBIDITY=false)");
  }
  Serial.print("Firebase   : "); Serial.println(app.ready() ? "terhubung" : "belum siap");
  Serial.print("SD         : "); Serial.println(sdAvailable ? "tersedia" : "tidak tersedia");
  Serial.print("RTC        : "); Serial.println(rtcAvailable ? "tersedia" : "tidak tersedia");

  // ---- [PHASE 1 -- BARU] CALIBRATION DEBUG OUTPUT ----
  Serial.println("-----------------------------------------");
  Serial.print("[CAL] NODE="); Serial.println(NODE_ID);

  Serial.print("Timestamp   : ");
  if (latestMeasurementTimestampValid) {
    Serial.println((unsigned long long)latestMeasurementTimestampMs);
  } else {
    Serial.println("UNKNOWN (NTP/RTC belum valid)");
  }

  Serial.print("Sequence    : "); Serial.print(sequenceCounter);
  Serial.println(" (naik saat packet terkirim/ditulis, bukan per siklus baca)");

  Serial.println();
  Serial.print("pH ADC V    : "); Serial.print(adcPH, 3); Serial.println(" V  (langsung dari ADC ESP32, SEBELUM divider)");
  Serial.print("pH Sensor V : "); Serial.print(vPH, 3);   Serial.print(" V  (ADC V x faktor divider "); Serial.print(DIV_PH, 2); Serial.println(")");
  Serial.print("pH Value    : "); Serial.println(phValue, 2);

  Serial.println();
  Serial.print("TDS ADC V   : "); Serial.print(adcTDS, 3); Serial.println(" V  (langsung dari ADC ESP32, SEBELUM divider)");
  Serial.print("TDS SensorV : "); Serial.print(vTDS, 3);   Serial.print(" V  (ADC V x faktor divider "); Serial.print(DIV_TDS, 2); Serial.println(" -- identik dengan ADC V karena divider 1.0)");
  Serial.print("TDS Value   : "); Serial.print(tdsValue, 1); Serial.println(" ppm");

  Serial.println();
  if (turbidityValid) {
    Serial.print("Turb ADC V  : "); Serial.print(adcTurb, 3); Serial.println(" V  (langsung dari ADC ESP32, SEBELUM divider)");
    Serial.print("Turb SensorV: "); Serial.print(vTurb, 3);   Serial.print(" V  (ADC V x faktor divider "); Serial.print(DIV_TURB, 2); Serial.println(")");
    Serial.print("Turbidity   : "); Serial.print(ntuValue, 1); Serial.println(" NTU");
  } else {
    Serial.println("Turb ADC V  : MISSING (HAS_TURBIDITY=false, GPIO tidak dibaca)");
    Serial.println("Turb SensorV: MISSING");
    Serial.println("Turbidity   : MISSING");
  }
  Serial.println("-----------------------------------------");
}

// =======================================================
//         BANGUN & KIRIM JSON KE FIREBASE
// =======================================================

// Escape tanda kutip/backslash/newline supaya teks bebas (rekomendasi,
// detail anomali) tidak merusak struktur JSON.
String jsonEscape(const String &input) {
  String out;
  out.reserve(input.length() + 8);
  for (size_t i = 0; i < input.length(); i++) {
    char c = input.charAt(i);
    if (c == '"' || c == '\\') {
      out += '\\';
      out += c;

    } else if (c == '\n') {
      out += "\\n";
    } else if (c == '\r') {
      // dilewati
    } else {
      out += c;
    }
  }
  return out;
}

// Array JSON [{"v":..,"s":..}, ...] dari buffer "recent" (10 pembacaan
// terakhir). Urutan hasil: TERBARU -> TERLAMA.
String recentArrayJsonFloat(const float arr[], int decimals) {
  String out = "[";
  unsigned long now = millis();
  for (int i = 0; i < recentCount; i++) {
    int idx = recentIndexFromNewest(i);
    if (idx < 0) continue;
    if (i > 0) out += ",";
    out += "{\"v\":" + String(arr[idx], decimals) +
           ",\"s\":" + String((now - recentMillis[idx]) / 1000) + "}";
  }
  out += "]";
  return out;
}

String statToJson(int count, float mean, float stddev, float minV, float maxV, float cv) {
  String out = "{";
  out += "\"count\":" + String(count) + ",";
  out += "\"mean\":" + String(mean, 2) + ",";
  out += "\"stddev\":" + String(stddev, 2) + ",";

  out += "\"min\":" + String(minV, 2) + ",";
  out += "\"max\":" + String(maxV, 2) + ",";
  out += "\"cv\":" + String(cv, 2);
  out += "}";
  return out;
}

// Packet 6-field sesuai data contract TASNIM -> /hardware_test/nodes/{NODE_ID}/latest.
// TIDAK memuat field analitik (health index, anomaly, recommendation, dll) --
// itu hanya untuk OLED/Serial lokal (lihat buildLatestJson() di bawah, dormant).
// [DIUBAH untuk HAS_TURBIDITY] Key "turbidity" TETAP ADA, tapi isinya literal
// JSON null kalau !turbidityValid -- BUKAN field baru, BUKAN angka 0.
// [INFERENCE] belum diverifikasi apakah FirebaseClient (Mobizt) menerima
// string JSON mentah berisi "null" lewat object_t() apa adanya -- secara
// sintaks JSON valid, tapi penerimaannya oleh library/Firebase RTDB baru
// bisa dipastikan lewat test upload nyata.
String buildHardwarePacketJson(uint32_t seq) {
  // uint64_t tidak selalu aman lewat String() di semua versi core ESP32,
  // jadi dikonversi manual via snprintf supaya tidak ambigu/overflow.
  char timestampBuf[24];
  snprintf(timestampBuf, sizeof(timestampBuf), "%llu",
           (unsigned long long)latestMeasurementTimestampMs);

  String json = "{";
  json += "\"ph\":" + String(phValue, 2) + ",";
  json += "\"tds\":" + String(tdsValue, 1) + ",";
  if (turbidityValid) {
    json += "\"turbidity\":" + String(ntuValue, 1) + ",";
  } else {
    json += "\"turbidity\":null,";
  }
  json += "\"timestamp\":" + String(timestampBuf) + ",";
  json += "\"sequence\":" + String(seq) + ",";
  json += "\"rssi\":" + String(WiFi.RSSI());
  json += "}";
  return json;
}

// Packet khusus /field.
// Berbeda dari hardware_test hanya pada missing turbidity:
// jika sensor tidak tersedia, key "turbidity" DIHILANGKAN, bukan dikirim 0/null.
String buildFieldPacketJson(uint32_t seq) {
  char timestampBuf[24];
  snprintf(timestampBuf, sizeof(timestampBuf), "%llu",
           (unsigned long long)latestMeasurementTimestampMs);

  String json = "{";
  json += "\"ph\":" + String(phValue, 2) + ",";
  json += "\"tds\":" + String(tdsValue, 1) + ",";

  if (turbidityValid) {
    json += "\"turbidity\":" + String(ntuValue, 1) + ",";
  }

  json += "\"timestamp\":" + String(timestampBuf) + ",";
  json += "\"sequence\":" + String(seq) + ",";
  json += "\"rssi\":" + String(WiFi.RSSI());
  json += "}";
  return json;
}

// Canonical 5-minute slot.
// Contoh 13:05:01, 13:05:03, 13:05:04 -> slot 13:05 yang sama.
uint64_t getFieldHistorySlotMs(uint64_t capturedTimestampMs) {
  return (capturedTimestampMs / FIELD_HISTORY_SLOT_MS) *
         FIELD_HISTORY_SLOT_MS;
}

// Path aman untuk uint64_t:
// /field/history/<slot_timestamp_ms>/<NODE_ID>
String getFieldHistoryPath(uint64_t slotMs) {
  char slotBuf[24];
  snprintf(slotBuf, sizeof(slotBuf), "%llu",
           (unsigned long long)slotMs);

  return String("/field/history/") +
         String(slotBuf) +
         "/" +
         NODE_ID;
}

// DORMANT -- tidak dipanggil lagi. Dibiarkan agar tidak menghapus kode.
// Snapshot lengkap (analitik+recent) yang dulu dikirim ke "/ecosense/latest".
String buildLatestJson() {
  float health = getHealthIndex();


  String json = "{";
  json += "\"timestamp\":" + String(getEpochTime()) + ",";
  json += "\"ph\":" + String(phValue, 2) + ",";
  json += "\"labelPH\":\"" + klasifikasiPH(phValue) + "\",";
  json += "\"tds\":" + String(tdsValue, 0) + ",";
  json += "\"labelAir\":\"" + klasifikasiAir(tdsValue) + "\",";
  json += "\"ntu\":" + String(ntuValue, 1) + ",";
  json += "\"labelTurb\":\"" + klasifikasiTurbidity(ntuValue) + "\",";
  json += "\"turbAIIndex\":" + String(getTurbAIIndex()) + ",";
  json += "\"vPH\":" + String(vPH, 3) + ",";
  json += "\"vTDS\":" + String(vTDS, 3) + ",";
  json += "\"vTurb\":" + String(vTurb, 3) + ",";
  json += "\"phCalibrated\":" + String(PH_SUDAH_KALIBRASI ? "true" : "false") + ",";
  json += "\"healthIndex\":" + String(health, 1) + ",";
  json += "\"healthStatus\":\"" + healthStatus(health) + "\",";
  json += "\"phScore\":" + String(getPHScore(), 1) + ",";
  json += "\"tdsScore\":" + String(getTDSScore(), 1) + ",";
  json += "\"turbScore\":" + String(getTurbScore(), 1) + ",";
  json += "\"projectedHealth\":" + String(projectedHealth(), 1) + ",";
  json += "\"recommendation\":\"" + jsonEscape(getRecommendation()) + "\",";
  json += "\"anomaly\":" + String(anomalyDetected() ? "true" : "false") + ",";
  json += "\"anomalySensor\":\"" + jsonEscape(anomalySensor) + "\",";
  json += "\"anomalyDetail\":\"" + jsonEscape(anomalyDetail) + "\",";
  json += "\"recentPH\":" + recentArrayJsonFloat(recentPH, 2) + ",";
  json += "\"recentTDS\":" + recentArrayJsonFloat(recentTDS, 0) + ",";
  json += "\"recentNTU\":" + recentArrayJsonFloat(recentTurb, 1);
  json += "}";
  return json;
}

// DORMANT -- tidak dipanggil lagi.

String buildHistoryEntryJson() {
  String json = "{";
  json += "\"timestamp\":" + String(getEpochTime()) + ",";
  json += "\"health\":" + String(getHealthIndex(), 1) + ",";
  json += "\"ph\":" + String(phValue, 2) + ",";
  json += "\"tds\":" + String(tdsValue, 0) + ",";
  json += "\"turb\":" + String(ntuValue, 1) + ",";
  json += "\"turbScore\":" + String(getTurbAIIndex());
  json += "}";
  return json;
}

// DORMANT -- tidak dipanggil lagi.
String buildStatsJson() {
  int phCount, tdsCount, turbCount;
  float phMean, phStd, phMin, phMax, phCV;
  float tdsMean, tdsStd, tdsMin, tdsMax, tdsCV;
  float turbMean, turbStd, turbMin, turbMax, turbCV;

  computeStats(histPH, historyCount, HISTORY_SIZE, historyHead,
               phCount, phMean, phStd, phMin, phMax, phCV);
  computeStats(histTDS, historyCount, HISTORY_SIZE, historyHead,
               tdsCount, tdsMean, tdsStd, tdsMin, tdsMax, tdsCV);
  computeStats(histTurbScore, historyCount, HISTORY_SIZE, historyHead,
               turbCount, turbMean, turbStd, turbMin, turbMax, turbCV);

  String json = "{";
  json += "\"timestamp\":" + String(getEpochTime()) + ",";
  json += "\"ph\":" + statToJson(phCount, phMean, phStd, phMin, phMax, phCV) + ",";
  json += "\"phStability\":\"" + klasifikasiStabilitas(phCV, phCount) + "\",";
  json += "\"tds\":" + statToJson(tdsCount, tdsMean, tdsStd, tdsMin, tdsMax, tdsCV) + ",";
  json += "\"tdsStability\":\"" + klasifikasiStabilitas(tdsCV, tdsCount) + "\",";

  json += "\"turb\":" + statToJson(turbCount, turbMean, turbStd, turbMin, turbMax, turbCV) + ",";
  json += "\"turbStability\":\"" + klasifikasiStabilitas(turbCV, turbCount) + "\",";
  json += "\"turbTrend\":\"" + getTurbTrendLabel() + "\",";
  json += "\"insight\":\"" + jsonEscape(getTrendInsight()) + "\",";
  json += "\"turbAIRecommendation\":\"" + jsonEscape(getTurbAIRecommendation()) + "\"";
  json += "}";
  return json;
}

// =====================================================================
// BARU malam ini: microSD (CSV) + measurement cycle bersama (SD + Firebase)
// =====================================================================

// Format baris CSV sesuai kontrak: timestamp,node,sequence,ph,tds,turbidity,rssi
// Turbidity ditulis "NA" (teks, bukan 0) kalau !turbidityValid.
String buildCsvRow(uint32_t seq) {
  String row = String((unsigned long long)latestMeasurementTimestampMs) + ",";
  row += String(NODE_ID) + ",";
  row += String(seq) + ",";
  row += String(phValue, 2) + ",";
  row += String(tdsValue, 1) + ",";
  row += turbidityValid ? String(ntuValue, 1) : String("NA");
  row += ",";
  row += String(WiFi.RSSI());
  return row;
}

// Tulis satu baris CSV ke /tasnim_{NODE_ID}.csv (append-only; header ditulis
// sekali kalau file belum ada). SD gagal HANYA di-log ke Serial, TIDAK
// menghentikan apa pun yang lain (fail-safe). Tidak ada retry/backoff
// khusus malam ini -- "jangan buat persistence rumit" sesuai instruksi.
void tulisSDJikaTersedia(uint32_t seq) {
  if (!sdAvailable) {
    Serial.println("[SD] ERROR (tidak tersedia, baris dilewati)");
    return;
  }

  String filename = sdCsvFilename();
  bool needHeader = !SD.exists(filename);

  File f = SD.open(filename, FILE_APPEND);
  if (!f) {
    Serial.println("[SD] ERROR (gagal membuka file untuk ditulis)");
    return;
  }

  if (needHeader) {
    f.println("timestamp,node,sequence,ph,tds,turbidity,rssi");
  }
  f.println(buildCsvRow(seq));
  f.close();

  Serial.print("[SD] OK (baris ditulis ke "); Serial.print(filename); Serial.println(")");
}

// Simpan metadata lokasi node SEKALI (dipanggil dari gpsLoopNonBlocking()
// begitu fix pertama didapat) ke /metadata_{NODE_ID}.csv.
// Format: node,latitude,longitude,gps_valid
void simpanMetadataGPS(float lat, float lng, bool valid) {
  if (!sdAvailable) {
    Serial.println("[GPS] Metadata TIDAK disimpan: SD tidak tersedia.");
    return;
  }

  String filename = sdMetadataFilename();
  bool needHeader = !SD.exists(filename);

  File f = SD.open(filename, FILE_APPEND);
  if (!f) {
    Serial.println("[GPS] Metadata TIDAK disimpan: SD.open() gagal.");
    return;
  }

  if (needHeader) {
    f.println("node,latitude,longitude,gps_valid");
  }
  f.print(NODE_ID); f.print(",");
  f.print(lat, 6); f.print(",");
  f.print(lng, 6); f.print(",");
  f.println(valid ? 1 : 0);
  f.close();

  Serial.print("[GPS] Metadata disimpan ke "); Serial.println(filename);
}

// Baca byte GPS yang tersedia di UART2 dan umpankan ke parser TinyGPSPlus.
// Non-blocking -- TIDAK menunggu fix, hanya memproses apa yang sudah ada di
// buffer UART tiap kali loop() berjalan. Begitu fix VALID pertama kali
// didapat, metadata lokasi disimpan SEKALI dan tidak diulang lagi
// (gpsMetadataSaved). GPS TIDAK dimasukkan ke packet Firebase hardware_test.
void gpsLoopNonBlocking() {
  while (Serial2.available() > 0) {
    gps.encode(Serial2.read());
    gpsRawByteCount++;   // [BARU -- DIAGNOSTIK] hitung byte mentah, terlepas dari valid/tidaknya fix
  }

  // [BARU -- DIAGNOSTIK] Laporkan berkala, supaya kelihatan apakah UART2
  // benar-benar menerima apa pun dari modul GPS atau tidak sama sekali.
  if (millis() - lastGpsByteCountPrint >= gpsByteCountPrintInterval) {
    lastGpsByteCountPrint = millis();
    Serial.print("[GPS] DIAGNOSTIK: total byte mentah diterima sejak boot = ");
    Serial.println(gpsRawByteCount);
    if (gpsRawByteCount == 0) {
      Serial.println("[GPS] DIAGNOSTIK: 0 byte sama sekali -- ini BUKAN soal menunggu fix satelit. Cek wiring RX/TX (kemungkinan terbalik), GND bersama, VCC modul, dan baud rate (asumsi saat ini 9600).");
    }
  }

  if (gpsMetadataSaved) return;

  if (gps.location.isValid() && gps.location.isUpdated()) {
    float lat = gps.location.lat();
    float lng = gps.location.lng();
    simpanMetadataGPS(lat, lng, true);
    gpsMetadataSaved = true;
    Serial.print("[GPS] Fix didapat. lat=");
    Serial.print(lat, 6);
    Serial.print(" lng=");
    Serial.println(lng, 6);
    return;
  }

  if (millis() - lastGpsWaitPrint >= gpsWaitPrintInterval) {
    lastGpsWaitPrint = millis();
    Serial.println("[GPS] Waiting for fix...");
  }
}

// [BARU] Satu siklus measurement bersama, dipanggil dari loop() tiap
// firebasePushInterval (5 detik). Sesuai arsitektur yang diminta:
//   Sensor (sudah dibaca SATU KALI di bacaSensor(), lihat globals di atas)
//     -> measurement object (packet JSON / baris CSV, dibangun di sini)
//        -> microSD
//        -> Firebase
// SD dan Firebase memakai sequence+timestamp YANG SAMA (sequenceCounter
// di-increment SEKALI di sini, bukan di dalam cabang SD atau Firebase
// masing-masing). Fail-closed: kalau timestamp belum valid (NTP dan RTC
// keduanya belum siap), SELURUH cycle dilewati -- tidak pernah membuat
// epoch palsu untuk SD maupun Firebase.
// TODO (ditangguhkan, sesuai instruksi "jangan buat backlog sync kompleks
// malam ini"): saat WiFi/Firebase kembali tersedia setelah offline, baris
// CSV yang terlanjur tertulis selama offline BELUM di-replay otomatis ke
// Firebase. Ini KNOWN LIMITATION, bukan bug yang diklaim sudah diperbaiki.
void prosesMeasurementCycle() {
  if (!latestMeasurementTimestampValid) {
    Serial.println("[TIME] INVALID - lewati siklus SD & Firebase ini (NTP dan RTC belum valid).");
    return;
  }

  sequenceCounter++;

  // ---- microSD: local backup, TIDAK boleh dihentikan oleh status Firebase ----
  tulisSDJikaTersedia(sequenceCounter);

  // ---- Firebase: hanya kalau sudah initialized + ready; gagal di sini
  //      TIDAK menghentikan/mengulang penulisan SD di atas ----
  if (firebaseInitialized && app.ready()) {

    // ==========================================================
    // 1) JALUR WORKING LAMA — TETAP DIPERTAHANKAN
    // ==========================================================
    String hardwareJson = buildHardwarePacketJson(sequenceCounter);
    String hardwareTaskUid =
      String("set") + NODE_ID + "LatestTask";

    Database.set<object_t>(
      aClient,
      HARDWARE_TEST_PATH,
      object_t(hardwareJson.c_str()),
      processFirebaseResult,
      hardwareTaskUid.c_str()
    );

    // ==========================================================
    // 2) FIELD SHADOW — HANYA AKTIF JIKA FLAG TRUE
    // ==========================================================
    if (ENABLE_FIELD_SHADOW) {

      String fieldJson =
        buildFieldPacketJson(sequenceCounter);

      // ---- realtime latest: update mengikuti siklus existing 5 detik ----
      String fieldLatestTaskUid =
        String("set") + NODE_ID + "FieldLatestTask";

      Database.set<object_t>(
        aClient,
        FIELD_LATEST_PATH,
        object_t(fieldJson.c_str()),
        processFirebaseResult,
        fieldLatestTaskUid.c_str()
      );

      // ---- history penelitian: SATU record per canonical 5 menit ----
      uint64_t slotMs =
        getFieldHistorySlotMs(
          latestMeasurementTimestampMs
        );

      if (
        slotMs > 0 &&
        slotMs != lastFieldHistorySlotMs
      ) {
        String historyPath =
          getFieldHistoryPath(slotMs);

        String historyTaskUid =
          String("set") +
          NODE_ID +
          "FieldHistoryTask";

        Database.set<object_t>(
          aClient,
          historyPath,
          object_t(fieldJson.c_str()),
          processFirebaseResult,
          historyTaskUid.c_str()
        );

        // Ditandai setelah request dijadwalkan.
        // Jika koneksi benar-benar gagal setelah scheduling, SD tetap menjadi
        // backup lokal; replay backlog belum termasuk scope patch ini.
        lastFieldHistorySlotMs = slotMs;

        Serial.print("[FIELD] History slot scheduled: ");
        Serial.println(
          (unsigned long long)slotMs
        );
      }
    }

  } else {
    Serial.println("[FIREBASE] Dilewati cycle ini (belum initialized/ready). SD tetap berjalan seperti di atas.");
  }
}

// DORMANT -- superseded oleh prosesMeasurementCycle() malam ini. Fungsi ini
// SENGAJA DIBIARKAN (tidak dihapus, tidak dipanggil) mengikuti konvensi
// kode ini sendiri untuk fungsi yang digantikan (lihat kirimHistoriKeFirebase()
// di bawah). Perilakunya identik dengan versi baseline asli -- HANYA kirim
// Firebase, tanpa SD, dan increment sequenceCounter sendiri (jangan panggil
// fungsi ini BERSAMA prosesMeasurementCycle() dalam siklus yang sama, karena
// sequenceCounter akan naik dua kali untuk satu measurement).
void kirimLatestKeFirebase() {
  // Fail-closed: jangan kirim kalau belum ada timestamp pengukuran valid.
  // Tidak pernah mengirim epoch palsu/1970. Guard firebaseInitialized+
  // app.ready() sudah dicek di call site (loop()) pada versi baseline asli.
  if (!latestMeasurementTimestampValid) {
    Serial.println("Lewati kirim ke hardware_test: timestamp pengukuran belum valid (NTP belum sinkron).");
    return;
  }

  sequenceCounter++;

  String json = buildHardwarePacketJson(sequenceCounter);
  String taskUid = String("set") + NODE_ID + "LatestTask";
  Database.set<object_t>(aClient, HARDWARE_TEST_PATH, object_t(json.c_str()),
                          processFirebaseResult, taskUid.c_str());
}

// DORMANT -- tidak dipanggil lagi (lihat pushHistory()). Dibiarkan agar
// tidak menghapus kode; menulis ke /ecosense/history dan /ecosense/stats
// kalau suatu saat dipanggil kembali.
void kirimHistoriKeFirebase() {
  String histJson = buildHistoryEntryJson();
  Database.push<object_t>(aClient, DB_ROOT + "/history", object_t(histJson.c_str()),
                           processFirebaseResult, "pushHistoryTask");


  String statsJson = buildStatsJson();
  Database.set<object_t>(aClient, DB_ROOT + "/stats", object_t(statsJson.c_str()),
                          processFirebaseResult, "setStatsTask");
}

// Callback hasil operasi async Firebase (dipanggil oleh library, bukan
// dipanggil manual). Dipakai untuk log ke Serial Monitor saja.
void processFirebaseResult(AsyncResult &aResult) {
  if (!aResult.isResult())
    return;

  if (aResult.isEvent())
    Serial.printf("Firebase event [%s]: %s (code %d)\n",
                     aResult.uid().c_str(), aResult.eventLog().message().c_str(),
                     aResult.eventLog().code());

  if (aResult.isError())
    Serial.printf("Firebase ERROR [%s]: %s (code %d)\n",
                     aResult.uid().c_str(), aResult.error().message().c_str(),
                     aResult.error().code());
}
