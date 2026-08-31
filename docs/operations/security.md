# Security & Compliance Model

## 1. Authentication & Multi-Tenancy
- **JWT Authentication**: High-entropy tokens signed via HMAC-SHA256 (`HS256`).
- **Workspace Isolation**: Every database read/write query explicitly validates `workspace_id` tenancy boundaries.
- **Role Hierarchy**: `OWNER > ADMIN > OPERATOR > VIEWER` strictly enforced across all mutating actions.

## 2. Invariant & Authorization Enforcement
- **Non-Autonomous Invariant**: The system NEVER completes obligations, confirms evidence, or executes interventions without explicit human authorization.
- **Cryptographic Encryption at Rest**: Integration OAuth tokens and webhook secrets are symmetrically encrypted using Fernet (AES-128-CBC + HMAC-SHA256).

## 3. Secret Scrubbing & Data Sanitization
- **Access Logs**: All query parameters, authorization headers, cookies, and tokens are scrubbed prior to JSON log emission.
- **Audit Logs**: The `sanitizer` module recursively scrubs all sensitive keys before persisting immutable governance audit entries.
