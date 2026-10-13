# TASNIM FIELD DATA CONTRACT v1

Status: LOCKED DRAFT
Deployment: NOT YET
Active dashboard mode: SIMULATION

## 1. Data Roots

Production field structure:

field/
├── nodes/
│   ├── N0/latest
│   ├── N1/latest
│   └── N2/latest
│
├── history/
│   └── <slot_timestamp_ms>/
│       ├── N0
│       ├── N1
│       ├── N2
│       └── analysis
│
├── analysis/
│   └── latest
│
├── metadata/
│   ├── N0/location
│   ├── N1/location
│   └── N2/location
│
└── system/
    └── nodes/
        ├── N0
        ├── N1
        └── N2


## 2. Node Measurement Packet

Required for storage:

- ph
- tds
- timestamp

Optional:

- turbidity
- sequence
- rssi

Example complete packet:

{
  "ph": 7.21,
  "tds": 218.4,
  "turbidity": 8.7,
  "timestamp": 1789351500000,
  "sequence": 152,
  "rssi": -63
}

If turbidity is unavailable:

{
  "ph": 7.21,
  "tds": 218.4,
  "timestamp": 1789351500000,
  "sequence": 152,
  "rssi": -63
}

Never fabricate missing sensor data.

Firebase:
- omit missing sensor key.

Local CSV:
- use NA.


## 3. AI Requirements

Storage-valid does NOT mean AI-analyzable.

AI multi-node analysis requires all of:

- N0 exists
- N1 exists
- N2 exists
- valid timestamp
- valid pH for all nodes
- valid TDS for all nodes
- valid turbidity for all nodes

RSSI and sequence are telemetry only.

Missing RSSI or sequence must NOT stop AI.

Missing pH, TDS, turbidity, node, or valid timestamp MUST skip
AI processing for that slot.


## 4. Timestamp

captured timestamp:
actual measurement time in Unix epoch milliseconds.

Canonical slot:

slot_ms =
  floor(captured_timestamp_ms / 300000)
  * 300000

300000 ms = 5 minutes.

Example:

N0 capture 08:05:01
N1 capture 08:05:03
N2 capture 08:05:04

All become the same 08:05 slot.

Epoch timestamps remain UTC-based.

Local display:
Gorontalo = WITA / UTC+8.

Timezone must never be manually added to Unix epoch.


## 5. Time Hierarchy

Firmware:

NTP valid
→ use NTP
→ synchronize RTC

NTP unavailable
→ valid RTC
→ use RTC

NTP invalid AND RTC invalid
→ do not publish FIELD measurement

Never use millis() or fake epoch as research timestamp.


## 6. Write Ownership

Each ESP writes only its own child.

N0:
field/history/<slot>/N0

N1:
field/history/<slot>/N1

N2:
field/history/<slot>/N2

Never write the complete slot object from an ESP32.

Correct:

Database.set(
  field/history/<slot>/N0,
  packet
)

Incorrect:

Database.set(
  field/history/<slot>,
  wholeSlot
)


## 7. Latest

Each valid FIELD measurement also updates:

field/nodes/<NODE_ID>/latest

latest contains captured timestamp, not slot timestamp.


## 8. Sampling

Research FIELD history target:

one record per canonical 5-minute slot per node.

Local sensor refresh may be faster.

hardware_test may remain faster during commissioning.

FIELD history must not be written every 5 seconds.


## 9. GPS Metadata

Nodes are fixed installations.

GPS is metadata, not a measurement feature.

Path:

field/metadata/<NODE_ID>/location

Recommended payload:

{
  "latitude": ...,
  "longitude": ...,
  "captured_timestamp": ...,
  "satellites": ...,
  "hdop": ...
}

GPS failure:

- does not stop sensor acquisition
- does not stop Firebase measurements
- does not stop AI
- does not fabricate coordinates

Exact GPS metadata should not be made public until its visibility
is intentionally approved.


## 10. microSD

microSD and Firebase must operate independently.

SD failure:
Firebase continues.

Firebase failure:
SD continues.

Recommended FIELD CSV:

captured_timestamp_ms,
slot_timestamp_ms,
node,
sequence,
ph,
tds,
turbidity,
rssi,
time_source

Missing value:

NA


## 11. System Health

Future node health path:

field/system/nodes/<NODE_ID>

Recommended fields:

{
  "last_seen": ...,
  "time_source": "NTP",
  "rtc_ok": true,
  "gps_ok": true,
  "sd_ok": true,
  "wifi_rssi": -63,
  "firmware_version": "..."
}

System-health fields are telemetry.

They do NOT become AI water-quality features.


## 12. AI Ownership

ESP32 NEVER writes:

field/analysis
field/history/<slot>/analysis

Research AI owns these outputs.


## 13. Simulation Isolation

iot/simulator.py remains permanently bound to:

simulation

It must never write to field.


## 14. Activation Order

Before switching activeDataRoot to field:

1. Working physical firmware is archived.
2. FIELD firmware write contract is implemented.
3. Firebase rules are tested.
4. N0/N1/N2 successfully write FIELD packets.
5. canonical slots verified.
6. missing sensor behavior verified.
7. AI reads FIELD successfully.
8. AI writes analysis successfully.
9. web reads FIELD successfully.
10. only then switch configuration to FIELD.
