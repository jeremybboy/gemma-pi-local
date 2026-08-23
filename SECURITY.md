# Security

## Supported version

Only the latest commit on `main` receives security fixes during this experimental phase.

## Deployment boundary

V0 is designed for one user on a trusted private LAN. It has no authentication, authorization, TLS, rate limiting, or user isolation.

- Keep LiteRT-LM bound to `127.0.0.1`.
- Do not expose port 8080 through router port forwarding, a public IP, or an untrusted wireless network.
- Use a host firewall or private overlay network if the LAN is not fully trusted.
- Treat prompts, uploads, and model answers as untrusted data.
- Review logs before sharing them; prompts or upstream errors may appear there.

The gateway rejects remote media URLs and limits message, request, and attachment sizes, but these controls do not make it safe for public hosting. A reachable client can still consume CPU, memory, storage bandwidth, and inference time.

## Reporting a vulnerability

Do not open a public issue for an unpatched vulnerability. Use GitHub's private vulnerability reporting for this repository if available, or contact the maintainer through the private contact method on their GitHub profile. Include a minimal reproduction, affected commit, impact, and suggested mitigation; do not include real credentials or private media.
