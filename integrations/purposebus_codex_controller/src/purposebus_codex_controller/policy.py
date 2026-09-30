from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FirstProofPolicy:
    """Maximum authority for the first future controller proof.

    This policy does not start Codex or grant the controller any executable
    capability. It makes the future proof boundary machine-checkable now.
    """

    filesystem_read_only: bool = True
    network_access: bool = False
    max_codex_sessions: int = 1
    max_subagents: int = 0
    experimental_app_server_api: bool = False

    def __post_init__(self) -> None:
        if self.filesystem_read_only is not True:
            raise ValueError("first proof requires read-only filesystem access")
        if self.network_access is not False:
            raise ValueError("first proof forbids network access")
        if self.max_codex_sessions != 1:
            raise ValueError("first proof is limited to one Codex session")
        if self.max_subagents != 0:
            raise ValueError("first proof forbids subagents")
        if self.experimental_app_server_api is not False:
            raise ValueError("first proof forbids experimental App Server APIs")
