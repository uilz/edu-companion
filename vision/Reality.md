# Reality — Auto-generated LOOP checkpoint

> Last generated: 2026-07-19  
> LOOPs completed: 5 / 5  
> Architecture Freeze: complete

## LOOP Summary

| # | Runtime | Status | Tables | Events |
|---|---------|--------|--------|--------|
| 1 | WorkspaceRuntime | done | workspaces, sessions, session_artifacts | WorkspaceCreated, WorkspaceActivated, SessionCreated, SessionPaused, SessionResumed, SessionEnded, WorkspaceEnded |
| 2 | ReadingRuntime | done | resources, reading_states | ResourceOpened, ReadingProgressed, HighlightCreated, ResourceClosed, ResourceCompleted |
| 3 | ConversationRuntime | done | conv_conversations, turns, context_snapshots | ConversationStarted, TurnCreated, ResponseComplete, OrchestrationDecided, ConversationPaused, ConversationClosed |
| 4 | PracticeRuntime | done | practices, practice_questions, practice_attempts | PracticeStarted, AttemptSubmitted, BreakthroughDetected, PracticeCompleted |
| 5 | GrowthEngine | done | milestones, evolution_snapshots | MilestoneDetected, EvolutionSnapshotComputed, TrajectoryUpdated |

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

## Next

All 5 LOOPs complete. Development phase transitions to frontend integration and event subscriber wiring.
