# Frontend2 Mock Page Replica Design

## Context

`frontend/` already contains a fuller React application with session and workspace
page layouts, router structure, and component styling. `frontend2/` currently only
contains a minimal Vite scaffold.

The immediate goal is not to connect real APIs, Redux, or SSE. The goal is to build
an independently runnable `frontend2/` that visually follows the existing
`frontend/` session and workspace pages closely enough to unblock UI review and later
backend integration.

## Goal

Build a mock-driven `frontend2/` that:

- reproduces the session page layout from `frontend/`
- reproduces the workspace page layout from `frontend/`
- uses static in-memory mock data only
- does not depend on the current `frontend/` Redux, RTK Query, or stream logic

## Non-Goals

- real backend API integration
- Redux / RTK Query reuse
- live SSE session stream integration
- complete CRUD interactions
- exact field-level backend contract alignment

## Chosen Approach

Use a lightweight page-shell replica approach:

- preserve the route structure and primary page composition
- reuse the visual language and CSS structure from `frontend/` where useful
- rewrite the page components in `frontend2/` as simple mock-driven components

This avoids copying the existing frontend's data layer and runtime complexity while
still producing a close visual replica.

## Scope

### Pages

Implement two pages in `frontend2/`:

- Session page
- Workspace page

### Layout

Implement a shared main layout with:

- left navigation/sidebar
- main routed content area

### Session Page

The session page should include:

- a center chat panel with session title, messages, and composer shell
- a right runtime panel showing plan, summary, waiting items, and agent status
- static mock typing / running state only if useful for visual fidelity

### Workspace Page

The workspace page should include:

- workspace browser/tree panel
- file/detail panel
- enough mock data to show realistic nested content

## Data Strategy

All data comes from local mock modules inside `frontend2/src/mocks/`.

Mock data should cover:

- session list
- active session metadata
- message timeline
- runtime overview data
- source workspace list
- workspace tree entries
- selected file content / detail

## Component Strategy

`frontend2/` should keep focused presentational components rather than duplicating
the entire component tree from `frontend/`.

Target components:

- `MainLayout`
- `Sidebar`
- `ChatPanel`
- `RuntimePanel`
- `WorkspaceBrowser`
- `WorkspaceDetailPanel`

These components should remain mock-driven and prop-based.

## Styling Strategy

Reuse or closely adapt the visual structure from `frontend/` CSS files where
possible, especially for:

- main layout shell
- chat page shell
- workspace page shell
- sidebar
- runtime panel
- chat panel

The objective is visual continuity, not a byte-for-byte file copy.

## Routing Strategy

`frontend2/` should use `react-router-dom` with the same basic route shape:

- `/chat`
- `/workspace`

The default route should redirect to `/chat`.

## Verification

The implementation is considered complete when:

1. `frontend2/` builds and runs
2. `/chat` renders a complete mock session page
3. `/workspace` renders a complete mock workspace page
4. the UI visually follows the existing `frontend/` layout conventions
5. no real backend integration is required for the pages to render
