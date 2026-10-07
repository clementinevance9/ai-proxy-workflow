# Small OpenAI-compatible reverse proxy

This repository shows a deliberately small Python reverse proxy that keeps an upstream key on the server while presenting familiar Responses, chat completions, and image paths to a trusted local client. **[ArgoLink](https://argolink.io/gh-ai-proxy-workflow) is an example upstream, not a hard-coded brand.** The proxy is a reference implementation, not a production gateway. Last checked: 2026-10-07.

## What it does

The server accepts only three POST paths, caps request bodies at two megabytes, adds a User-Agent, forwards JSON to UPSTREAM_BASE_URL, and returns the upstream status and body. The client never sees UPSTREAM_API_KEY. LISTEN_HOST defaults to loopback. There is no automatic retry, request cache, streaming relay, auth layer, rate limiter, or persistence. Those omissions are deliberate: adding them without a deployment contract would create false security.

## Run locally

Set UPSTREAM_BASE_URL to a compatible base and UPSTREAM_API_KEY in the server environment, then run python3 proxy/server.py. Point a local SDK at http://127.0.0.1:8080 and provide only its client-side key if your local caller needs one. For ArgoLink, the upstream base is https://argolink.io/v1 and the server should receive the key through a secret manager. Never put the key in this README, a compose file, or an issue.

## Deploying safely

Place TLS and authentication in front of the process. Allowlist the client network, set a process timeout, and use a supervisor with a health check. Run as an unprivileged user. Redact Authorization headers and signed media URLs in logs. Pin the Python runtime and audit dependencies. The example catches upstream exceptions and returns 502; it does not reveal the upstream key, but the exception string still belongs in a private log policy. Limit request size before parsing JSON.

The proxy forwards POST bodies but does not know whether a provider's operation is idempotent. If a connection drops after forwarding, do not replay a generation automatically. Video generation is asynchronous and should use a separate explicit submit/status/content runner; this proxy intentionally does not invent a video route.

## Compatibility

The OpenAI-compatible paths still depend on the upstream's exact model IDs and supported features. Responses, chat completions, and images are not interchangeable contracts. Validate tools, streaming, structured output, image sizes, and usage fields with a local mock before production. The model page or provider docs win over this example.

## Tests and FAQ

python3 -m unittest discover -s tests checks the body cap and User-Agent source without network access. **Why no client authentication?** Add a real auth middleware before exposing it beyond localhost. **Can it hide a key?** It keeps the upstream key server-side, but deployment controls access. **Why 502?** The upstream transport failed; inspect private logs. **Does it support streaming?** No; implement and test streaming separately rather than buffering a production stream accidentally.
