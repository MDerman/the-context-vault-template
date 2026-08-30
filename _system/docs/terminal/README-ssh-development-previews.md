---
type: agent-reference
status: enabled
---
## SSH development previews

Workers expose useful development previews to Mattbook through SSH reverse forwarding. The development server and the Mattbook listener both remain loopback-only; LAN, Tailscale, and WireGuard provide transport for the canonical SSH alias rather than hosting the service directly.

Do this proactively when all three conditions hold:

- changes can be inspected through a localhost service;
- the preview would be valuable for Matt to inspect;
- Matt did not request an immediate commit or a commit and push.

Run the server on worker loopback, then initiate the tunnel from that worker. For a worker service on port `3000`:

```bash
ssh -NT \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=3 \
  -R 127.0.0.1:3000:127.0.0.1:3000 \
  mattbook
```

Return `http://127.0.0.1:3000` as the clickable Mattbook URL. Prefer the same port at both ends. There is no fixed offset convention; if the port is occupied on Mattbook, select any free Mattbook loopback port and report the exact mapping and URL.

Keep the server and tunnel alive while inspection remains useful. A tunnel failure must not be worked around by binding either listener to `0.0.0.0`, a LAN address, or a mesh address. Mattbook SSH must permit TCP forwarding; `GatewayPorts` is unnecessary because its listener stays on `127.0.0.1`.

Global agent behavior is sourced from `_system/agents/_package/instance/instructions/AGENTS.md` and distributed through [[Agent Sync]].
