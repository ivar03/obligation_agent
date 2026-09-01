# Obligation Agent — Privacy & Data Governance Map

## 1. Data Classification Matrix

| Data Class | Description | Storage Location | Retention Period | Access Roles | Encryption at Rest | Redaction / Masking | Deletion Policy |
|---|---|---|---|---|---|---|---|
| **User Identity & Auth** | Emails, password hashes, display names, sessions | PostgreSQL / SQLite `users`, `workspaces` | Duration of account active | User, Admin, Owner | Hashed (Argon2/bcrypt) | Password never visible | Hard delete upon workspace purge |
| **Obligations & Graphs** | Action text, owners, beneficiaries, deadlines, dependency edges | PostgreSQL / SQLite `obligations`, `obligation_edges` | Workspace lifecycle | Viewer, Member, Operator, Admin, Owner | Database encryption | PII scrubbed on export | Workspace admin export/purge |
| **Evidence Records** | Event excerpts, message references, timestamps | PostgreSQL / SQLite `obligation_evidence` | Workspace lifecycle | Member, Operator, Admin, Owner | Database encryption | Credentials redacted (`[REDACTED]`) | Soft/Hard delete by Admin |
| **Event Inbox & Queues** | Buffered webhook payloads, stream keys, error reasons | PostgreSQL / SQLite `event_inbox`, `background_jobs` | 30 days (auto-pruned) | Operator, Admin, Owner | Database encryption | Signing secrets scrubbed | Auto-pruned after processing / DLQ resolution |
| **Operational Audit Log** | Infrastructure events, login events, DLQ transitions, permissions | PostgreSQL / SQLite `operational_audit_records` | Immutable (7 years) | Operator, Admin, Owner | SHA-256 Hash Chained | Sensitive metadata redacted | Append-only; cryptographic provenance |
| **LLM Inference Telemetry** | Prompts, completions, tokens, latency, validation status | PostgreSQL / SQLite `llm_analysis_records` | 90 days | Operator, Admin, Owner | Database encryption | Raw secrets redacted in prompt preview | Prunable operational telemetry |
| **Integration Secrets** | Slack Bot Tokens, OAuth secrets, Webhook secrets | PostgreSQL / SQLite `integration_connections` | Until disconnected | Admin, Owner | Symmetric AES (Fernet) | Masked in API (`xoxb-****`) | Cryptographic shredding upon disconnect |
| **System Backups** | Full encrypted database and state snapshots | Restricted filesystem / object store | Configurable (e.g. 30 days) | Owner | Fernet AES encrypted tarball | Secrets encrypted | Retention auto-prune |

---

## 2. Data Minimization Principles

1. **Egress Scrubbing**: External LLM providers receive only the minimal token footprint necessary for semantic reasoning; internal database IDs and personal identifiers are mapped to anonymized labels where practical.
2. **Zero Plaintext Credentials in Logs & Traces**: Access logs, operational audit records, error traces, and metrics emit only hash digests or `[REDACTED]` markers.
3. **Tenant Boundary Enforcement**: Data belonging to Workspace A is never indexed, aggregated, or exposed to Workspace B under any circumstances.
