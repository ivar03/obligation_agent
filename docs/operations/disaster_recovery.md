# Disaster Recovery & Business Continuity Plan

## Target Recovery Objectives
- **RPO (Recovery Point Objective)**: <= 1 Hour (hourly scheduled snapshots / live WAL replication).
- **RTO (Recovery Time Objective)**: <= 15 Minutes (containerized restore with automated manifest verification).

---

## Backup Procedures

### Automated Daily / Hourly Backups
Run via Kubernetes CronJob, ECS task, or crontab:
```bash
python -m app.ops.scheduled_backup
```

### Manual Backup Execution
```bash
python -m app.ops.backup_restore backup /path/to/custom_backup.db
```

### Backup Manifests & Checksums
Every backup creates a companion `.manifest.json` containing:
- SHA-256 integrity hash
- Exact timestamp and byte size
- Database backend type and application version

---

## Restoration Procedures

```bash
# 1. Stop active API instances
docker-compose stop backend worker

# 2. Execute restore with SHA-256 verification
python -m app.ops.backup_restore restore ./backups/obligation_db_backup_YYYYMMDD_HHMMSS.db

# 3. Verify integrity
python -m app.ops.integrity_checker

# 4. Restart services
docker-compose start backend worker
```
