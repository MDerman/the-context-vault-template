---
type: agent-reference
status: enabled
---
# Obsidian Profile

Back up the root `.obsidian` profile:

```bash
vault backup
```

This writes a timestamped local copy under `_master/system/backup/obsidian-profile/`. The backup folder is git-ignored because plugin bundles are large.

Implementation script: `_master/system/scripts/backup.py`.

Create/update the iPhone-safe `.obsidian-mobile` profile:

```bash
vault mobile-profile
```

This writes `.obsidian-mobile/community-plugins.json`, copies the approved mobile plugin folders/settings, copies the current theme and enabled CSS snippets, syncs key core settings such as `daily-notes.json`, and prunes unapproved mobile plugin/theme/snippet folders by default. On iPhone, Obsidian must have `Settings → Files and links → Override config folder` set to `.obsidian-mobile`.

Implementation script: `_master/system/scripts/mobile_profile.py`.
