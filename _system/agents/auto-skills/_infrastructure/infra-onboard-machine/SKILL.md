---
name: infra-onboard-machine
description: Onboards, rebuilds, replaces, recovers, or accepts a Mac or Linux machine as a complete fleet member. Use when the user asks to set up a new primary Mac, add a worker Mac, add a Linux worker, rebuild or replace a machine, enroll it in fleet access, or finish machine acceptance.
---

# Infra · Onboard Machine

Read `$infra-code-folder-and-computer-topology`, its role model, private config README, registries, and the selected machine convention before operating.

1. Read [[shared-onboarding-and-acceptance|Shared Onboarding and Acceptance]] and keep every applicable gate visible until verified or explicitly excluded.
2. Route by role: [[primary-mac-onboarding-and-acceptance|Primary Mac]], [[worker-mac-onboarding-and-acceptance|Worker Mac]], or [[linux-worker-onboarding-and-acceptance|Linux Worker]].
3. Keep the registry entry disabled until the selected role document's reboot acceptance passes.
4. Use `$infra-sync-code-workspaces` during onboarding for Code repositories and primary-owned Codex and Claude configuration. Do not recreate that sync here.
5. Use `$infra-manage-fleet-terminal-workspaces` for terminal packages, profiles, Warp, cmux, tmux, workmux, and terminal acceptance.
6. Use [[sops-key-enrollment-and-rotation|SOPS Key Enrollment and Rotation]] only when an owning repository requires shared SOPS access.

Preview every supported mutation first. Never transmit machine-local credentials. Stop at the exact manual checkpoint for identity choice, GUI approval, authentication, physical access, or separately authorized destructive work, then resume the same procedure after the user completes it.
