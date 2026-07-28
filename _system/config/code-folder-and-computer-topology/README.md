# Code Folder And Computer Topology Config

Private instance config consumed by `code-folder-and-computer-topology` and vault machine commands.

- `private/machines.json`: machine registry, sync roles, access routing, and terminal workspace profiles.
- `private/machine-notes/`: mutable per-machine observations.
- `private/repositories.json`: logical repository IDs, local paths, access method, and optional env loader.
- `private/fleet-observations.md`: mutable current fleet observations and operational history.
- `private/remote-access-prerequisites.md`: current private network and operator-machine access details.
- `private/README-warp-cmux-execution-chain.md`: current terminal execution chain and verification observations.
- `private/retired-syncthing-code-folder.md`: retired replication recovery paths and history.

All files under `private/` stay in private vault Git and are excluded from public bootstrap export. Generic setup and recovery procedures stay in skill folder.

Terminal controllers copy machine registry to `~/.config/workmux/machines.json` with mode `0600`; deployed cmux/Warp helpers read that runtime copy instead of embedding aliases or home paths.
