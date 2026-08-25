# Security

## Supported version

Only the latest commit on `main` receives security fixes during this experimental phase.

## Deployment boundary

V0 is designed for one user: on a trusted private LAN for the Pi profile, or localhost-only by default for the macOS profile. It has no authentication, authorization, TLS, rate limiting, or user isolation.

- Keep LiteRT-LM bound to `127.0.0.1`.
- Keep the macOS web UI bound to `127.0.0.1` unless a separate security layer is added.
- Do not expose port 8080 through router port forwarding, a public IP, or an untrusted wireless network.
- Use a host firewall or private overlay network if the LAN is not fully trusted.
- Treat prompts, uploads, and model answers as untrusted data.
- Treat search titles and snippets as untrusted external data; they are evidence, not instructions.
- Review logs before sharing them; prompts or upstream errors may appear there.

The gateway rejects remote media URLs and limits message, request, attachment, search-query, tool-call, and result sizes. It permits only one fixed `web_search` call per turn and does not fetch result pages or execute browser actions. These controls do not make it safe for public hosting: a reachable client can still consume CPU, memory, storage bandwidth, inference time, and outbound search capacity.

## Reporting a vulnerability

Do not open a public issue for an unpatched vulnerability. Use GitHub's private vulnerability reporting for this repository if available, or contact the maintainer through the private contact method on their GitHub profile. Include a minimal reproduction, affected commit, impact, and suggested mitigation; do not include real credentials or private media.
