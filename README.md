# Small OpenAI-compatible reverse proxy

This repository is a deliberately small Python reverse proxy that keeps an upstream key on the server while presenting a trusted local client with four JSON POST paths: Responses, chat completions, image generations, and JSON image edits. **[ArgoLink](https://argolink.io/gh-ai-proxy-workflow) is an example upstream, not a hard-coded brand.** Checked 2026-10-07.

It is a reference implementation, not a production gateway. It has no retry engine, cache, streaming relay, persistence, rate limiter, or provider discovery. Those features need a deployment contract and separate tests.

## What it does

- binds to loopback by default (`127.0.0.1:8080`);
- accepts only `POST /responses`, `/chat/completions`, `/images/generations`, and JSON `/images/edits`;
- rejects missing or oversized `Content-Length` before JSON parsing (2 MB request cap, 20 MB response cap);
- optionally authenticates a local caller with `PROXY_API_KEY` using a constant-time comparison;
- rewrites only explicit model aliases from `MODEL_ALIASES='{"fast":"gpt-6-sol"}'`;
- sends the upstream credential in a server-side `Authorization` header and a descriptive `User-Agent`;
- returns upstream status, JSON content type, request ID, and `Retry-After` without forwarding the upstream key;
- returns generic transport errors to the client rather than leaking exception strings.

The proxy accepts JSON image edits with `image_url` references. It does not parse multipart uploads. Video is intentionally absent: video generation has a separate asynchronous submit/status/content lifecycle and should use a dedicated client.

## Run locally

```bash
export UPSTREAM_BASE_URL='https://argolink.io/v1'
export UPSTREAM_API_KEY='replace-with-a-development-key'
export PROXY_API_KEY='optional-local-client-key'
export MODEL_ALIASES='{"fast":"gpt-6-sol"}'
python3 proxy/server.py
```

Point a local SDK at `http://127.0.0.1:8080` and choose a model ID that the upstream catalog actually exposes. The proxy does not translate provider-specific fields: Responses, chat completions, and images remain different contracts. For ArgoLink, model IDs and limits come from `GET https://argolink.io/v1/models` and the corresponding model page.

Never put a real key in this README, a compose file, an issue, or a request log. In a shared deployment, put TLS and authentication in front of the process, run as an unprivileged user, allowlist client networks and upstream hosts, and use a supervisor with a health check. Pin the Python runtime and audit dependencies.

## Failure and retry policy

The proxy never retries. A validation 4xx should be fixed by the caller; a 429 should preserve `Retry-After`; a connection failure before a request is written may be retried by a higher-level policy; a timeout after a POST may have created a billable generation and requires request-ID reconciliation. Do not add automatic POST retries without an idempotency contract.

The proxy forwards upstream error bodies and status codes so the caller can make a policy decision, but it never exposes the upstream key. It forwards only `Content-Type`, `X-Upstream-Request-Id`, and `Retry-After` from the upstream response. Hop-by-hop headers are intentionally not copied.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Tests are offline and cover path/body limits, alias validation, JSON rewriting, request URL/auth/User-Agent construction, and source hygiene. They do not call an upstream or require an API key.
