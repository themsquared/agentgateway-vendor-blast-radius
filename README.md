# agentgateway-vendor-blast-radius

On 2026-11-06, Fireworks AI (an LLM inference vendor) [disclosed a second security
incident in a matter of weeks](https://news.ycombinator.com/item?id=50437106). Notion
[confirmed](https://www.notion.com/en-gb/security/advisories/security-incident-involving-a-third-party-ai-vendor)
that AI chat transcripts from its Insights feature were exposed, routed through
Fireworks on Notion's behalf. Notion's own systems weren't touched. A vendor two hops
downstream was, and that was enough.

This repo is not about Fireworks or Notion specifically. It's about the architecture
question their incident raises for anyone routing LLM traffic through a third-party
inference vendor: **when that vendor gets breached, what does it cost you, and how
fast can you find out?**

## The value proposition

Two properties change the blast radius of a vendor breach, and both are gateway
features, not app code:

1. **The calling app never holds the vendor's API key.** If the credential lives only
   at the gateway, a vendor-side leak of "every API key we ever saw" never included one
   that sat in application code, because the app never had it -- only gateway-to-vendor
   traffic carries it.
2. **A team keeps its own audit trail of what left its boundary, and when.** A vendor's
   breach disclosure arrives on the vendor's own timeline. If every request to that
   vendor is logged locally, "were we affected" becomes a query a team can run the
   moment a bulletin names a window -- not a wait on the vendor to say more.

This repo demonstrates both patterns with [agentgateway](https://agentgateway.dev), an
open source AI gateway, fronting a mock stand-in for a generic third-party inference
vendor.

## What's in this repo

- `compose.yaml` -- two services: `agentgateway` (the real thing,
  `cr.agentgateway.dev/agentgateway:v1.7.0`) and `mock-vendor` (a ~70-line Python
  stdlib HTTP server that plays the role Fireworks played for Notion: it accepts chat
  completions requests, but only with the vendor's own API key).
- `agentgateway-config/config.yaml` -- an agentgateway `custom` LLM provider pointing
  at the mock vendor, with the vendor's API key injected from an environment variable
  the client-side caller never needs to know.
- `mock-vendor/` -- the stand-in vendor. It isn't reachable from the host at all
  (no published port, only `expose`), so the only path to it is through the gateway.

## Quickstart (under 15 minutes)

All commands below were run against this repo on 2026-11-10 with Docker 29.9.2.

```bash
cp .env.example .env
# edit .env and set MOCK_VENDOR_API_KEY to any string -- this is the vendor's key,
# and after this step you (the "client") never need to type it again
docker compose up -d --build
```

Confirm both services are up:

```bash
docker compose ps
```

### 1. Call the gateway. Never touch the vendor key.

```bash
curl -sS http://localhost:4000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{
    "model": "vendor/vendor-chat-small",
    "messages": [{"role":"user","content":"hello from the client, which never saw a vendor API key"}]
  }'
```

Expected output (a mock response from `mock-vendor`, proxied back through
agentgateway):

```json
{"model":"vendor-chat-small","usage":{"prompt_tokens":12,"completion_tokens":8,"total_tokens":20},"choices":[{"message":{"content":"[mock-vendor saw: 'hello from the client, which never saw a vendor API key'] response from vendor-chat-small","role":"assistant"},"index":0,"finish_reason":"stop"}],"id":"chatcmpl-...","object":"chat.completion","created":...}
```

No `Authorization` header was sent by that `curl`. Look at `agentgateway-config/config.yaml`
-- the key comes from `params.apiKey: "$MOCK_VENDOR_API_KEY"`, read once at gateway
startup. The gateway is the only thing that ever holds it.

### 2. Confirm the vendor is actually unreachable except through the gateway

```bash
curl -sS -m 3 http://localhost:8080/v1/chat/completions -d '{}'
# curl: (7) Failed to connect to localhost port 8080: Couldn't connect to server
```

`mock-vendor` has no published port in `compose.yaml` -- only `expose: ["8080"]` on
the Docker network. The only route to it is through agentgateway.

### 3. Play the vendor's incident bulletin, then answer "were we affected" yourself

This is the part that would otherwise mean waiting on the vendor. agentgateway
persists every LLM request to a local SQLite database by default
(`config.database.url` in `config.yaml`), so you already have the data:

```bash
sqlite3 -header -column agentgateway-config/data.db \
  "SELECT started_at, gen_ai_provider_name, gen_ai_request_model, http_status, total_tokens
   FROM request_logs
   WHERE started_at BETWEEN '2026-11-10T00:00:00' AND '2026-11-11T00:00:00';"
```

Swap the two timestamps for whatever window the vendor's bulletin names, and you have
your answer: every request that crossed your boundary to that vendor in that window,
with no dependency on the vendor's own incident timeline. (Schema reference:
[agentgateway's access-log database docs](https://agentgateway.dev/docs/standalone/latest/documentation/observability/access-logs/database/).)

### Cleanup

```bash
docker compose down
```

## What this doesn't claim

This is not a drop-in Fireworks/Notion fix, and it is not a general DLP or PII-redaction
product -- agentgateway doesn't ship a redaction policy today, so this demo scopes to
the two controls it does ship and that map directly onto this incident: credential
injection at the edge, and a request-level audit trail you own. A real deployment would
pair this with least-privilege vendor API keys and network egress policy, not replace
them.

## Background reading

- [Notion's advisory on the Fireworks AI incident](https://www.notion.com/en-gb/security/advisories/security-incident-involving-a-third-party-ai-vendor)
- [HN discussion](https://news.ycombinator.com/item?id=50437106)
- [agentgateway: Credential Injection Patterns for AI Agents (series)](https://agentgateway.dev/blog/2026-07-27-credential-injection-ai-agent-egress-cb4a/)
- [agentgateway: custom LLM providers](https://agentgateway.dev/docs/standalone/latest/integrations/llm/providers/custom/)

## Topics

`agentgateway` `ai-gateway` `mcp` `ai-agents` `llm-security` `supply-chain-security`
