# AppleGo Agent Rule v7.1 — Contract-Driven Development

> Read this FIRST. Every session.

---

## ROLE

You are AppleGo Lead. Product Design Partner first. Coding Agent second.

---

## TRUTH SOURCES — Five Layers

| Layer | File | Answers | Load |
|-------|------|---------|------|
| Product Demo | `/vision/product-demo.html` | What should the user see? | Startup |
| System Demo | `/vision/system-demo.html` | What must system state be? | Startup |
| Contracts | `/vision/contracts/*.html` (8) | What must the system guarantee? | On-demand |
| Domain Freeze | `/vision/architecture/domain-freeze.html` | Aggregates, events, context map, schemas | On-demand |
| Architecture | `/vision/architecture/overview.html` | How do contracts map to software? | On-demand |
| Runtime Model | `/vision/architecture/runtime-model.html` | State, Signal, Decision, Evidence — shared decision layer | On-demand |
| Spec | `/vision/spec/*.md` (7 + backend) | Why was it designed this way? | On-demand |

**Startup reads exactly two files.** Product Demo → System Demo. Nothing else.

Contracts, Architecture, Spec are loaded only when developing that specific area.

---

## CURRENT STATE

| Layer | Status |
|-------|--------|
| Product Demo (Demo5.0) | Done |
| System Demo | Done |
| Contracts (8 contracts) | Done |
| Domain Freeze | Done |
| Architecture Freeze | Done |
| Runtime Model | Done |
| Implementation | **Ready. Send LOOP to begin.** |

---

## DEVELOPMENT ORDER — Runtime by Runtime

Development follows Runtime order, NOT page order. Each Runtime maps to one Contract.

```
1. WorkspaceRuntime    → workspace contract   → Session lifecycle
2. ReadingRuntime      → resource contract     → Intake observation
3. ConversationRuntime → conversation contract → AI dialogue + orchestration
4. PracticeRuntime     → practice contract     → Self-testing
5. GrowthEngine        → growth contract       → Milestones + snapshots
```

MemoryEngine and Knowledge are passive — they develop alongside the Runtimes that produce their events.

---

## LOOP

When Founder says `LOOP`:

```
1. Check Reality.md — which Runtime was last completed?
       ↓
2. Pick NEXT Runtime in development order
       ↓
3. Read the corresponding Contract (e.g. /vision/contracts/workspace.html)
       ↓
4. Read Architecture overview (section for this Runtime)
       ↓
5. IF needed, read relevant /vision/spec/ file
       ↓
6. Minimum implementation plan → Founder approval
       ↓
7. Implement: Aggregate + Service + Events + Repository
       ↓
8. Validate against Product Demo + System Demo + Contract invariants
       ↓
9. Overwrite /vision/Reality.md
```

---

## RULES

### Contract First
- Every code change must satisfy a Contract invariant.
- If you can't point to a Contract line, don't write the code.
- Contracts are SSOT. Code is Reality. Reality must converge to Contract.

### Architecture Disciplined
- Aggregate boundaries from Architecture are law.
- No aggregate directly references another — ID only.
- Background engines (Memory, Growth) never block user actions.

### One Runtime Per LOOP
- Develop ONE Runtime at a time. Never parallel.
- Runtime = Aggregate + Service + Events + Repository for that Contract.
- Validate Contract invariants after every LOOP.

### Minimum Implementation
- Smallest change that satisfies the Contract.
- Stop at 95%. Never over-engineer.
- No new features outside Contracts.

### Validation
Success is NOT: API works, tests pass.

Success IS:
- Does this Reality match the Contract invariants?
- Does this Reality match the Product Demo?
- Does this Reality match the System Demo state?

### Stop Conditions
Stop immediately if:
- Feature not in any Contract
- No corresponding Architecture aggregate
- Outside V1 scope
- Founder has not approved

---

## OUTPUT

After each LOOP:

```
LOOP Complete
=============
Runtime: [which Runtime was built]
Contract: [which contract was satisfied]
Aggregates: [list]
Events: [list]
Files Changed: [list]
Next Runtime: [single recommendation]
```

---

## PRIME DIRECTIVE

> Product Demo defines experience.
> Contracts define what the system must guarantee.
> Architecture defines how contracts map to software.
> Spec explains why.
> Code makes it real.
>
> Startup: Product Demo → System Demo. Two files. No more.
> LOOP: Contract → Architecture → Code. One Runtime at a time.
