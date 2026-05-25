# Plan-Delegate-Callback Document

## Overview

The Plan-Delegate-Callback pattern is a distributed execution model used in AgentHub for orchestrating multi-agent workflows. This document describes the flow and its components.

## Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ Orchestrator │─────▶│   Worker    │─────▶│  Callback   │
│   (Plan)     │      │  (Delegate) │      │  (Result)   │
└─────────────┘      └─────────────┘      └─────────────┘
```

## Flow Steps

### 1. Plan Phase
The orchestrator analyzes the task and creates an execution plan:
- Decompose complex tasks into subtasks
- Identify required capabilities and agents
- Define execution order and dependencies
- Set up runtime context

### 2. Delegate Phase
Tasks are delegated to specialized workers:
- Worker receives task with full context
- Worker executes within its capabilities
- Framework adapters handle tool access (Read, Write, Edit, Bash)
- Worker operates independently in its workspace

### 3. Callback Phase
Results are returned to the orchestrator:
- Worker reports execution status
- Artifacts and outputs are collected
- State is updated for next iteration
- Callback enables orchestrator to continue workflow

## Runtime Components

| Component | Description |
|-----------|-------------|
| `run_id` | Unique identifier for the execution run |
| `workspace_id` | Isolated workspace for the agent |
| `agent_id` | Unique identifier for the worker agent |
| `input_type` | Type of input (user_input, callback, etc.) |

## Worker Responsibilities

Workers are responsible for:
1. Executing assigned tasks within their workspace
2. Using framework capabilities to interact with the environment
3. Returning concise, actionable results
4. Not leaving placeholder files - write actual content

## Example Execution

```
Input: Create a documentation file
  ↓
Plan: Orchestrator identifies file creation task
  ↓
Delegate: Worker receives task with workspace context
  ↓
Execute: Worker creates file with actual content
  ↓
Callback: Result returned to orchestrator
```

## Key Principles

- **Isolation**: Each worker operates in its own workspace
- **Autonomy**: Workers execute independently without orchestrator intervention
- **Transparency**: All actions are tracked via run_id
- **Completeness**: Workers produce complete artifacts, not placeholders
