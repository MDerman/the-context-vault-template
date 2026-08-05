---
name: infra-onboard-machine
description: Adds, registers, enrolls, rebuilds, replaces, or recovers a Mac or Linux machine as a complete fleet member. Use for new-machine setup, machine registration, SSH or WireGuard enrollment, worker vault bootstrap, shared dependency installation, SOPS enrollment, global agent deployment, and reboot acceptance; registration alone is not completion.
---

# Infra · Onboard Machine

Read [[new-machine-onboarding|New Machine Onboarding]] first and keep every applicable gate visible until verified or explicitly excluded.

1. Use `$infra-code-folder-and-computer-topology` to load the primary/worker model, private config README, machine and repository registries, current clone identity, and target convention.
2. Confirm whether the machine is new or rebuilt, primary or worker, Mac or Linux, and whether any destructive installation is explicitly authorized.
3. For a worker Mac, use `$infra-onboard-worker-mac` for its Screen-Sharing-first overlay before continuing the generic workflow. Migration Assistant is optional.
4. Read [[new-mac-or-linux-machine-setup|New Mac or Linux Machine Setup]] for the platform procedure. Read [[linux-machine-dependencies|Linux Machine Dependencies]] only for Linux.
5. Read [[mattbook-remote-access-prerequisites|Primary Machine Remote Access Prerequisites]] before changing primary-host access. Resolve WireGuard and image repositories through topology config and follow their owning docs.
6. Use [[sops-key-enrollment-and-rotation|SOPS Key Enrollment and Rotation]] only when an owning repository requires shared SOPS access.
7. Use `$infra-manage-fleet-terminal-workspaces` for terminal packages, profiles, Warp/cmux layouts, workmux, and terminal acceptance gates.
8. Keep a new registry record disabled until dependencies, target-local authentication, access routes, sparse vault identity, hooks, skills, terminal integration, and reboot acceptance pass.

Use bundled scripts from this skill directory for SOPS enrollment, global `AGENTS.md` deployment, and Claude provider launchers. Preview every supported mutation first, never transmit machine-local credentials, and stop with an exact manual checkpoint for GUI approval, authentication, physical access, or destructive work.
