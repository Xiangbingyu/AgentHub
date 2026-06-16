# Backend Leader Callback Hint Persistence Design

## Context

The worker callback wakeup chain now reaches the leader runtime correctly:

- worker `TeamSay` reaches the leader inbox
- `run_wakeup(input_msg=None)` is triggered
- `InboxMiddleware` injects the `HintBlock`

However, the injected hint does not reliably become a persisted artifact that the
product layer can read back through `session detail.messages`.

This means the current runtime chain consumes the callback in memory, but does not
complete the product-visible mainline.

## Problem Statement

For worker callback wakeups, AgentScope's inbox-driven execution does not guarantee
that an injected `HintBlock` will be persisted as a readable message, durable state,
or replayable event after the wakeup run ends.

As a result, the user-visible product contract is incomplete: the callback was
processed, but the leader session may still appear to have no visible result.

## Goal

Complete the product mainline so that, after the leader consumes a worker callback,
the callback hint is stably visible in `session detail.messages`.

## Non-Goals

- Redefine replay log semantics
- Change ordinary user-message execution
- Change waiting / confirm handling
- Persist arbitrary middleware side effects beyond callback hint messages

## Chosen Semantics

`messages` is the authoritative persisted result for worker callback hints.

After a worker callback is consumed by the leader wakeup path, the system must ensure
that the leader session has at least one persisted assistant message containing the
callback hint block.

This guarantee must not depend on:

- replay log trim timing
- whether the model continues and produces a normal reply
- whether the injected hint remains present in the final in-memory runtime state

## Mainline Behavior

### Trigger

The behavior applies only to the leader callback wakeup path:

- worker callback arrives through inbox
- leader wakeup run executes with `input_msg=None`

### Persistence Rule

After the wakeup run consumes the inbox callback hint:

1. If the wakeup run already produced a persisted leader assistant message that
   contains the hint block, keep it as-is.
2. Otherwise, persist a minimal assistant message whose content is the consumed hint
   block.

### Message Shape

The persisted fallback message should:

- belong to the leader session
- use assistant role / assistant message type
- contain the original hint block content only
- avoid fabricating extra explanatory text

## Implementation Direction

The persistence logic belongs in the runtime wakeup path, not in query-time
projection.

That means the fix should live around `run_wakeup()` and the leader runtime state /
message persistence path, rather than being reconstructed later in
`SessionQueryService`.

## Read Path Contract

After the fix:

- `GET /sessions/{session_id}` must be able to read the hint from persisted messages
- stream/replay remain observational channels, not the source of truth for callback
  visibility

## Verification

The following must hold after implementation:

1. worker callback reaches leader wakeup path
2. leader wakeup path persists a readable assistant hint message
3. `session detail.messages` shows the hint reliably
4. callback tests no longer depend on race windows or replay log residue
