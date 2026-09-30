# PurposeBus Codex controller boundary

This package is intentionally non-runnable. It contains only a machine-checkable
authority ceiling for a future first controller proof. It does not expose a
console script, call Codex App Server, create or resume a Codex session, launch
subagents, use the network, or mutate PurposeBus.

Implementing a controller is a later phase. It requires a separately accepted
lifecycle contract, version-matched Codex App Server schema, explicit process
ownership, an audit journal, and user authorization for every new state-changing
surface.
