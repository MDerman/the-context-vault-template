## Vault Host Boundary

Vault reads and writes run only from the full iCloud Vault on a registered Mac. Linux and other non-iCloud machines are code-repository hosts only.

### Non-Mac hard stop

When the current task is on Linux or its working directory is a retired/non-iCloud Vault clone, stop before reading the requested Vault note, running `vault`, inspecting Vault Git, or following Vault links.

Do not:

- message, reuse, fork, create, hand off to, wait for, or poll another task;
- remain active as a coordinator;
- use SSH to make Mattbook publish or execute the Vault task;
- fetch, repair, recreate, or use a Linux Vault checkout.

Return one concise instruction:

> This Vault task was launched on a non-Vault host. Run it in the saved Mac Vault project. For code execution, run the repository-local plan from the owning Wootbook code project.

This is a terminal response for that task. Do not retry automatically.

### Executable plans

Long-running build, deployment, or repository plans intended for a code worker must have a self-contained copy in the owning code repository, including every binding requirement needed for execution. The repository copy is the code-worker entrypoint; the Vault copy is planning context and must clearly name the repository path and invocation.

Code workers record proposed Vault-facing updates in a repository evidence/change packet. A separately launched Mac Vault task may apply that packet later. Neither task waits for or polls the other.
