# TASNIM — Hardware Test Security Design

Status: DRAFT — NOT DEPLOYED
Branch: infra/field-data

## 1. Security Objective

The TASNIM monitoring application is private.

Only authorized developers, managers and invited
viewers may access protected monitoring data.

Firebase authentication and database authorization
must be enforced independently.

## 2. Human Roles

ADMIN:
- Authorized dashboard access.
- User and role administration through a trusted tool.
- No uncontrolled sensor history editing.

MANAGER:
- Read latest measurements, history and AI results.
- No direct sensor writes.

VIEWER:
- Read permitted monitoring information.
- No writes.

Users must be explicitly approved.
Public sign-up does not grant monitoring access.

Proposed implementation:
Firebase Authentication with server-assigned roles,
such as Firebase custom claims.

Users must not be able to assign their own roles.

## 3. ESP32 Identity

N0, N1 and N2 must have separate device identities.

A node may only submit its own measurements.

Device authentication method remains an
OPEN DECISION:

A. Dedicated per-device Firebase authentication.
B. Secure ingestion gateway.

Never embed a Firebase Admin service-account
private key in ESP32 firmware.

## 4. AI Backend

The AI backend is a trusted server-side component.

It reads validated measurement history and
writes analysis results.

Admin SDK credentials must remain server-side.

Firebase Admin SDK operations bypass Realtime
Database Security Rules, so backend permissions
and code must be reviewed independently.

## 5. Database Ownership

hardware_test/nodes/Nx/latest:
  ESP32 measurement pipeline.

hardware_test/history/slot/Nx:
  ESP32 measurement pipeline.

hardware_test/history/slot/analysis:
  Trusted AI backend only.

hardware_test/analysis/latest:
  Trusted AI backend only.

Legacy simulation, real_test and field roots must
be reviewed before any production security release.

## 6. Required Protections

- Default deny.
- No unrestricted authenticated-user writes.
- No unauthorized dashboard reads.
- No direct browser writes to sensor history.
- No ESP32 writes to AI analysis.
- No cross-node ESP32 writes.
- No overwriting different history records.
- No backward movement of latest during replay.
- Validate payload schema before persistence.
- Preserve test data isolation.
- Do not expose credentials in repository.

## 7. Important Rule Design Constraint

Firebase Realtime Database permissions cascade.

A broad parent .read or .write cannot be revoked
by a more restrictive child rule.

Therefore avoid broad write permission on
/hardware_test.

## 8. Security Acceptance Tests

Using Firebase Emulator:

1. Unauthenticated user cannot read measurements.
2. Unauthorized account cannot read measurements.
3. Authorized viewer can read allowed data.
4. Viewer cannot write sensor data.
5. Manager cannot write sensor data.
6. Sensor N0 can write permitted N0 data.
7. Sensor N0 cannot write N1/N2 data.
8. Sensor cannot write AI analysis.
9. Invalid sensor payload is rejected.
10. Different history payload cannot silently overwrite.
11. Old replay cannot replace newer latest.
12. Legacy data permissions match privacy policy.

## 9. Release Policy

Do not deploy candidate Rules to LIVE until:

- Authentication strategy approved.
- Rules tested in Firebase Emulator.
- Existing data paths reviewed.
- Authorized access tested.
- Rollback plan prepared.
- Explicit deployment approval obtained.

This is a design draft, not a deployed policy.
