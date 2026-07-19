# Reality — Auto-generated LOOP checkpoint

> Last generated: 2026-07-19  
> LOOPs completed: 10 / 10  
> Architecture Freeze: complete

## LOOP Summary

### Phase 1: Backend Runtimes (LOOP 1-5)

| # | Runtime | Status | Tables | Events |
|---|---------|--------|--------|--------|
| 1 | WorkspaceRuntime | done | workspaces, sessions, session_artifacts | WorkspaceCreated, WorkspaceActivated, SessionCreated, SessionPaused, SessionResumed, SessionEnded, WorkspaceEnded |
| 2 | ReadingRuntime | done | resources, reading_states | ResourceOpened, ReadingProgressed, HighlightCreated, ResourceClosed, ResourceCompleted |
| 3 | ConversationRuntime | done | conv_conversations, turns, context_snapshots | ConversationStarted, TurnCreated, ResponseComplete, OrchestrationDecided, ConversationPaused, ConversationClosed |
| 4 | PracticeRuntime | done | practices, practice_questions, practice_attempts | PracticeStarted, AttemptSubmitted, BreakthroughDetected, PracticeCompleted |
| 5 | GrowthEngine | done | milestones, evolution_snapshots | MilestoneDetected, EvolutionSnapshotComputed, TrajectoryUpdated |

### Phase 2: Frontend Integration (LOOP 6-9)

| # | Runtime | Status | Files |
|---|---------|--------|-------|
| 6 | WorkspaceRuntime | done | workspace-api.ts, Landing.tsx, page.tsx |
| 7 | ReadingRuntime | done | resource-runtime-api.ts, useResourceRuntime.ts |
| 8 | ConversationRuntime | done | conversation-runtime-api.ts, useConversationRuntime.ts |
| 9 | GrowthEngine | done | growth-runtime-api.ts, useGrowthRuntime.ts, GrowthPage.tsx (milestones + snapshots) |

### Phase 3: Event Wiring (LOOP 10)

| # | Task | Status | Details |
|---|------|--------|---------|
| 10 | Event Subscribers + Validation | done | growth_engine_v2 initialized, 5 Demo6.0 event consumers wired |

## Event Subscriber Wiring

GrowthEngine v2 now consumes all Demo6.0 runtime events:

| Runtime Event | Consumer Method | Action |
|---------------|----------------|--------|
| WorkspaceCreated | on_workspace_created | Track new workspace |
| SessionCreated | on_session_created | Count sessions → detect habit milestones (7/21/50/100) |
| SessionEnded | on_session_ended | Compute evolution snapshot (I4) |
| ResourceCompleted | on_resource_completed | Detect completion milestone |
| BreakthroughDetected | on_breakthrough_detected | Create breakthrough milestone |

## Contract Coverage

| Contract | Invariants | Covered |
|----------|-----------|---------|
| Workspace | I1-I5 | I1 (user_id), I2 (permanent), I3 (unique index), I5 (user-only API) |
| Resource | I1-I7 | I1 (unique reading_state), I2 (debounced position), I3 (highlight), lifecycle (closed↔open→completed) |
| Conversation | I1-I8 | I1 (context snapshot), I6 (replayable turns), I8 (orchestration) |
| Practice | I1-I7 | I1 (workspace-scoped), I3 (immutable), I4 (review), I7 (concept context) |
| Growth | I1-I7 | I1 (ws+user), I2 (consumer), I3 (derived), I4 (snapshots), I5 (upsert), I6 (trajectory) |

## Database

| Migration | Tables |
|-----------|--------|
| 001 | workspaces, sessions, session_artifacts, projects, learning_events |
| 002 | resources, reading_states |
| 003 | conv_conversations, turns, context_snapshots |
| 004 | practices, practice_questions, practice_attempts |
| 005 | milestones, evolution_snapshots |

## Frontend Architecture

```
src/
├── hooks/
│   ├── useConversationRuntime.ts  ← conversation-runtime-api
│   ├── useGrowthRuntime.ts        ← growth-runtime-api (milestones + snapshots)
│   ├── usePracticeRuntime.ts      ← practice-runtime-api
│   └── useResourceRuntime.ts      ← resource-runtime-api (debounced positions)
├── lib/api/
│   ├── workspace-api.ts           ← /api/workspaces/*
│   ├── resource-runtime-api.ts    ← /api/resources/*
│   ├── conversation-runtime-api.ts ← /api/conversations/*
│   ├── practice-runtime-api.ts    ← /api/practices/*
│   └── growth-runtime-api.ts      ← /api/growth/*
└── components/
    ├── growth/GrowthPage.tsx      ← integrated with useGrowthRuntime
    ├── studio/Landing.tsx         ← integrated with workspace-api
    └── app/page.tsx               ← integrated with workspace-api
```

## Next

All 10 LOOPs complete. Full-stack runtime integration done.
Backend: 5 runtimes + 5 event subscribers.
Frontend: 5 API clients + 4 hooks + integrated pages.
