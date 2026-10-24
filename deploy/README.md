# Deployment: intentionally gated

Do not deploy this repository to Maya1 / Maya3: it contains a tested decision model, not an end-to-end VPN. There is currently NO secure public one-command installer.

One-command foreign installation is an absolute end-state feature, but releasing a dummy `curl | bash` installation script before signed artifacts, enrollment identity and both gateway validation exist would violate docs/SECURITY.md.

The future command will use a version-pinned verified release, ephemeral enrollment over authenticated HTTPS, non-root daemon, per-node isolated systemd unit, idempotent setup, health checks, auditable rollback and removal only after operator authorization. The command must not contain credentials in shell history or URL query strings.

DO NOT copy the existing frp-tunnel autoheal service into Mega Tunnel. Its old version has a known Bash nounset bug and restarts are the wrong recovery primitive for IP blocks.
