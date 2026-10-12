# TASNIM HMAC-SHA256 V1 — Language Interoperability Test Vector

This vector uses a **public, fake secret** only for firmware unit tests.
NEVER ship this test key in field firmware.

- Node: `N0`
- X-Tasnim-Time: `1791724501000`
- X-Tasnim-Nonce: `testnonce000000001`
- Secret (hex): `1111111111111111111111111111111111111111111111111111111111111111`
- Header X-Tasnim-Signature must equal:
  `e1fa88237d22368249922eea3858c8108dd25c8f4d36d93af561cec8e526f90a`

Exact UTF-8 request body **on one line, without a terminating LF**:

```json
{"node_id":"N0","ph":7.2,"quality_flags":[],"rssi":-49,"sample_id":"N0_1791724501000_3","schema_version":2,"sequence":3,"tds":240.0,"timestamp":1791724501000,"turbidity":16.0}
```

Compute HMAC over:

```python
message = (
    b"TASNIM-DEVICE-V1\\nN0\\n1791724501000\\ntestnonce000000001\\n"
    .replace(b"\\\\n", b"\\n")
    + body
)
expected = hmac.new(bytes.fromhex("11" * 32), message, hashlib.sha256).hexdigest()
```

Cross-language contract: ESP32 Arduino and Python must compute the exact
same hex digest. Differences in floating-point formatting, field order or
whitespace alter raw signed bytes; this is expected. Build the HMAC over the
actual body buffer *after* serialization, then send that buffer byte-for-byte.

This vector is for signature interoperability **only**; it is not a request
that should be sent today (request timestamps outside the +/-5-minute window
are rejected by the server).
