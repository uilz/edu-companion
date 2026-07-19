# LOOP Protocol

## What LOOP Means

Founder says `LOOP`. Agent picks the next undelivered Runtime and builds it.

---

## Runtime Delivery Order

```
LOOP 1: WorkspaceRuntime    — Session lifecycle, enter/pause/return
LOOP 2: ReadingRuntime      — PDF reading, highlights, intake observation
LOOP 3: ConversationRuntime — AI dialogue, context assembly, orchestration
LOOP 4: PracticeRuntime     — Practice generation, attempt review, breakthroughs
LOOP 5: GrowthEngine        — Milestones, evolution snapshots, cross-time queries
```

---

## Each LOOP = 4 Steps

### Step 1: Read Contract
Find the Contract file for this Runtime. Read all 6 sections.
- WorkspaceRuntime → `/vision/contracts/workspace.html`
- ReadingRuntime → `/vision/contracts/resource.html`
- ConversationRuntime → `/vision/contracts/conversation.html`
- PracticeRuntime → `/vision/contracts/practice.html`
- GrowthEngine → `/vision/contracts/growth.html`

### Step 2: Read Architecture
Open `/vision/architecture/overview.html`.
Find the row for this Runtime.
Note: Aggregate, Service, Events, Repository.

### Step 3: Implement
Build exactly what the Contract demands. Nothing more.
- Domain aggregate (entity + value objects)
- Repository interface + PostgreSQL implementation
- Runtime service (coordination logic)
- Event publishers + subscribers (PG NOTIFY)

### Step 4: Validate
- Do Contract invariants hold?
- Does System Demo state update correctly?
- Does Product Demo experience render correctly?

---

## State Tracking

After each LOOP, overwrite `/vision/Reality.md`:
- Mark which Runtime completed
- Update "Last Session" with what was built
- Note which Runtime is next

---

## Rules

1. **Contract drives code.** Every line of code answers a Contract invariant.
2. **One Runtime. One LOOP.** Never build two Runtimes at once.
3. **Architecture boundaries are law.** No cross-aggregate direct references.
4. **Background engines never block.** MemoryEngine and GrowthEngine run async.
5. **PG NOTIFY for events.** Never poll. Never in-process emitter for cross-module.
