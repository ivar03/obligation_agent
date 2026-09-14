# Strands Runtime Operator Guide

Operator guide for the **Strands** agent orchestration runtime in the intelligence layer. This is the Phase 11 cutover companion to the [SRE & Incident Response Runbook](./runbook.md) and the [Production Deployment Guide](./deployment.md).

---

## What Strands Is Here

Strands is the agent/tool-orchestration runtime that drives the two agentic workflows — investigation and recommendation. **Gemini remains the model.** Strands adds structured agent orchestration, tool calling, and structured output on top of `GeminiModel`; it does not replace the LLM.

```
external signals → Strands agent → Gemini → structured proposal
      → deterministic validation → trusted domain services
      → decision plan → human authorization → controlled execution → audit
```

**No AWS credentials are required.** Strands is an AWS-authored open-source SDK, **not** an AWS service. This deployment uses `GeminiModel`. It pulls `boto3` transitively for a Bedrock provider that is never used, so the absence of any AWS credentials, roles, or region configuration is expected and correct.

---

## Configuration

All Strands settings live in `backend/.env` and are read by `pydantic-settings` from the process's working directory — **the app is started from `backend/`**, so `.env` must be readable there.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `mock` | Active provider: `mock` (offline/test) \| `gemini` (live Google Gemini) \| `strands` (Strands agent runtime over Gemini) |
| `LLM_MODEL` | `gemini-1.5-flash` | Target Gemini model identifier used by the Strands agent |
| `GEMINI_API_KEY` | `""` | Google AI Studio API key. Required by both `gemini` and `strands` (both route to Gemini). |
| `STRANDS_MAX_TOOL_CALLS` | `6` | Hard cap on tool invocations per agent run (int) |
| `STRANDS_TIMEOUT_SECONDS` | `60.0` | Wall-clock budget for an entire agent run (float) |
| `LLM_FALLBACK_TO_DETERMINISTIC` | `True` | Fall back to the deterministic mock provider when a keyed provider is unconfigured |
| `LLM_TIMEOUT_SECONDS` | `5.0` | Timeout threshold for LLM requests |
| `LLM_MAX_REQUESTS_PER_MINUTE` | `60` | Client rate limit for Gemini API calls |
| `LLM_MAX_TOKENS_PER_REQUEST` | `2048` | Maximum tokens per LLM request |

---

## Cutover Procedure (Phase 11)

1. Run the shadow comparison harness over representative inputs covering the two agent flows:
   ```bash
   python -m app.ops.shadow_compare "<text>"
   ```
2. Review the harness output. It reports three things:
   - `agreed` — whether every requested provider succeeded and returned identical output.
   - `degraded` — any provider that silently fell back to another (almost always a missing
     `GEMINI_API_KEY`). **If this list is non-empty, `agreed` is forced to `false` and the
     run proves nothing.** Two fallbacks agreeing with each other is not evidence that
     Strands matches Gemini. Fix the credentials and re-run before reading anything into it.
   - per-provider `latency_ms` and `ok`/failure, so you can compare cost and failure rate.
3. When agreement is acceptable and the failure rate is stable, switch the active provider:
   ```env
   LLM_PROVIDER=strands
   ```
4. Monitor runtime status and agent metrics (see [Observability](#observability)).

**Watch this signal:** a Strands provider without a configured `GEMINI_API_KEY` **degrades silently to the mock provider** rather than erroring (the registry falls back when `LLM_FALLBACK_TO_DETERMINISTIC` is true). It will not fail loudly. The definitive indicator is `GET /api/intelligence/llm/status` returning `api_key_configured: false`. Example healthy response while strands is active:

```json
{
  "llm_enabled": true,
  "provider_name": "strands",
  "model_name": "gemini-1.5-flash",
  "api_key_configured": true,
  "service_status": "ready",
  "status_message": "Strands (Gemini) provider active with model 'gemini-1.5-flash'.",
  "fallback_to_deterministic": true,
  "timeout_seconds": 5.0,
  "temperature": 0.0,
  "registered_providers": ["mock", "gemini", "strands"]
}
```

If `api_key_configured` is `false`, the runtime is serving mock responses while `provider_name` still reports the selected provider — traffic is not actually hitting Gemini.

---

## Rollback

Set the active provider back to the keyed Gemini path:

```env
LLM_PROVIDER=gemini
```

No code change, no data migration. This is precisely why Phase 12 removes nothing — the Gemini path remains fully intact as the durable rollback target.

---

## Observability

### Agent Metrics

All agent run telemetry is emitted via the existing metrics registry (Prometheus-compatible, available at `GET /api/metrics`). Every metric carries the `agent` label.

| Metric | Type | Label | Meaning |
|---|---|---|---|
| `agent.runs_total` | counter | `agent` | Total agent runs started |
| `agent.success_total` | counter | `agent` | Successful agent runs |
| `agent.failure_total` | counter | `agent` | Failed agent runs |
| `agent.latency_ms` | gauge/histogram | `agent` | Per-run latency in milliseconds |
| `agent.tool_calls` | gauge/histogram | `agent` | Tool calls consumed per run |

### Audit Actions

| Audit Action | `entity_type` | Result |
|---|---|---|
| `AGENT_RUN_COMPLETED` | `agent_run` | `SUCCESS` |
| `AGENT_RUN_FAILED` | `agent_run` | `FAILED` |

### Audit Metadata Fields

Every agent-run audit entry records the following metadata:

`agent_run_id`, `agent_name`, `obligation_id`, `trace_id`, `request_id`, `tool_calls`, `latency_ms`

(On failure, an additional `error` field carries the exception message.)

### Known Limitation (failure audit rows)

There is a `ponytail:` comment in `app/services/agents/agent_run_recorder.py` documenting this honestly:

- **Failure audit rows ride the request session.** When a 500 triggers `get_db`'s rollback, the pending `AGENT_RUN_FAILED` row is discarded along with the request's other uncommitted work.
- **Success rows commit normally.** `AGENT_RUN_COMPLETED` is written and committed with the happy-path request.
- **Implication:** a failed run reliably bumps `agent.failure_total` but may be absent from the audit chain.
- **Upgrade path:** the fix is a dedicated short-lived session for the failure write, so `AGENT_RUN_FAILED` commits independently of the request session's fate.

---

## Safety Invariants

Agent capabilities are deliberately constrained:

- **Tools are read-only.** Strands tools never mutate trusted state.
- **`workspace_id` is closed over** by the tool factory and appears in **no** tool schema — the model cannot request or steer workspace scoping.
- **Tool calls are capped** by `STRANDS_MAX_TOOL_CALLS` (`6`).
- **The run is wall-clock bounded** by `STRANDS_TIMEOUT_SECONDS` (`60.0`).
- **Agents recommend, they never authorize or execute.** Authorization and dispatch stay in the trusted service/execution layers behind the human authorization gateway.
- **`requires_human_authorization` is set by the service, never by the model.**

---

## Endpoints

All LLM endpoints live under `/api/intelligence/llm`. Endpoint paths as registered in the OpenAPI schema:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/intelligence/llm/investigate` | `POST` | Investigation agent |
| `/api/intelligence/llm/recommend` | `POST` | Recommendation agent |
| `/api/intelligence/llm/status` | `GET` | Runtime status |
| `/api/intelligence/llm/providers` | `GET` | Registered providers list |
| `/api/intelligence/llm/health` | `GET` | Provider health checks |
| `/api/intelligence/llm/analyze` | `POST` | LLM analysis |
| `/api/intelligence/llm/semantic-event` | `POST` | Semantic event classification |
| `/api/intelligence/llm/explain` | `POST` | Grounded explanation |
| `/api/intelligence/llm/history` | `GET` | Agent run history |
| `/api/intelligence/llm/history/{record_id}` | `GET` | Single run record |
| `/api/intelligence/llm/review/{record_id}` | `POST` | Review a stored run |

### Agentic Examples

Investigation agent:

```bash
curl -X POST http://localhost:8000/api/intelligence/llm/investigate \
  -H "Content-Type: application/json" \
  -d '{"obligation_id": "obl-123", "workspace_id": "ws-default"}'
```

Recommendation agent:

```bash
curl -X POST http://localhost:8000/api/intelligence/llm/recommend \
  -H "Content-Type: application/json" \
  -d '{"obligation_id": "obl-123", "workspace_id": "ws-default"}'
```