# TASNIM — Security Review 46B

Status: DRAFT — DO NOT DEPLOY.

## Candidate Architecture

Backend-only ingestion is being considered.

Client read access requires authenticated users
with a trusted, server-assigned custom claim:

- tasnim_role = admin
- tasnim_role = manager
- tasnim_role = viewer

All client writes are denied in this candidate.

ESP32 direct-to-Firebase upload is NOT supported
by these candidate Rules.

A backend using Firebase Admin SDK can still write
because Admin SDK bypasses Database Security Rules.

## Not Yet Implemented

- Website login and invitations
- Server-side role assignment
- Secure ESP32 ingestion gateway
- Device authentication
- Firebase Emulator authorization tests
- Atomic history writes
- Monotonic latest updates
- Backlog synchronization

## Deployment Blockers

Do NOT deploy these Rules yet.

The production website currently uses simulation
without the proposed login system.

Deploying this candidate now would break its
existing unauthenticated data access and deny
current direct ESP32 writes.

Legacy paths are also restricted in this candidate.

The team must approve its final ingestion strategy
before Rules can be finalized.

The existing database.rules.json stays unchanged.
No LIVE Rules modification is authorized.
