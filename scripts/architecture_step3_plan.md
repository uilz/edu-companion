# Step 3-5 架构重组方案

## 当前状态

```
backend/
├── infra/                    ← 7 个基础设施 (event_bus, llm, tts, svg...)
├── app/
│   ├── infrastructure/       ← 1 个文件 (crypto.py) — 空壳
│   ├── db/                   ← 3 个文件 (database, repositories, events_repo)
│   ├── services/ (88 files)  ← 混合: 编排 + 基础设施适配
│   │   ├── llm/              ← 基础设施 (OpenAI API)
│   │   ├── materials/        ← 基础设施 (文件系统 + 外部搜索)
│   │   └── common/           ← 混合: storage(基础设施) + classifier(编排)
│   └── domain/               ← 已清理完毕
```

## 目标结构

```
backend/app/
├── infrastructure/           ← 所有"依赖外部"的代码
│   ├── __init__.py
│   ├── db/                   ← 合并: 原 app/db/ + infra/ 中 DB 相关
│   │   ├── database.py
│   │   ├── repositories.py
│   │   ├── events_repository.py
│   │   └── pg_storage.py     ← 移入 services/common/pg_storage.py
│   │
│   ├── llm/                  ← 移入: 原 services/llm/
│   │   ├── llm_core.py
│   │   ├── llm_service.py
│   │   ├── prompts.py
│   │   ├── embedding_engine.py
│   │   ├── question_generator.py
│   │   ├── tool_repository.py
│   │   └── tool_dispatch.py / tool_executor.py
│   │
│   ├── media/                ← 移入: 原 services/materials/ + infra/
│   │   ├── bilibili_search.py
│   │   ├── material_search.py
│   │   ├── material_indexer.py
│   │   ├── material_parser.py
│   │   └── material_common.py
│   │
│   ├── tts/                  ← 移入: 原 infra/tts_client.py + infra/tts_text_cleaner.py
│   ├── svg_renderer.py       ← 移入: 原 infra/svg_renderer.py
│   ├── event_bus.py          ← 移入: 原 infra/event_bus.py
│   ├── crypto.py             ← 保留
│   └── embedding_utils.py    ← 移入: 原 services/common/embedding_utils.py
│
├── services/                 ← 保留: 纯业务编排
│   ├── conversation/         ← 保留 (context_pipeline, context_builder)
│   ├── practice/             ← 保留 (session, adaptive, scheduler, exam...)
│   ├── analytics/            ← 保留 (behavior_analyzer, achievement...)
│   ├── knowledge/            ← 保留 (cognitive_queries, tree_ops...)
│   └── common/               ← 保留: 仅编排类
│       ├── classifier_service.py
│       ├── organization_service.py
│       ├── organization_detector.py
│       └── *_stub.py         ← 5 个 stub 保留
│
└── domain/                   ← 保持不变 (已完成)
```

## 关键原则

| 放 infrastructure/ | 放 services/ |
|---|---|
| 含 `import openai` / `import asyncpg` / `import requests` | 只 import domain/ 和其他 services/ |
| 调用外部 API / 数据库查询 | 编排多个 infrastructure 调用 |
| 文件 I/O、序列化、缓存 | 不含直接的外部依赖 |
| `pg_storage.py` → DB 交互 | `classifier_service.py` → 纯编排 |

## 迁移方案对比

### 方案 A: 一步到位 (激进，2-3 天)
直接创建 infrastructure/ 目录结构，把 services/llm/、services/materials/ 整体搬入，然后改所有 import。
- 优点：一次性完成，架构清晰
- 缺点：改动量大，import 更新面广 (~40 文件)

### 方案 B: 两阶段 (温和，分两次 PR)
**Phase 1 (1天):** 先合并 `infra/` + `app/infrastructure/` + `app/db/` 到 `app/infrastructure/`
**Phase 2 (1-2天):** 再迁移 `services/llm/` 和 `services/materials/` 到 `infrastructure/`
- 优点：每次 PR 影响面小，容易 review
- 缺点：中间态仍有混乱

### 方案 C: 只做 infra/ 合并，不动 services/ (保守，0.5 天)
只把 `backend/infra/` + `backend/app/db/` + `backend/app/infrastructure/` 三个分散点合并成一个 `app/infrastructure/`。services/ 保持不动。
- 优点：最小改动，消除最紧迫的"基础设施散落"问题
- 缺点：services/ 仍然包含基础设施代码

## 推荐: 方案 B (两阶段)

### Phase 1: 合并基础设施 (1天)

```
1. 创建 app/infrastructure/db/
2. 搬入: app/db/database.py, app/db/repositories.py, app/db/events_repository.py
3. 搬入: backend/infra/*.py (event_bus, llm, tts, svg, tracing, resilience)
4. 搬入: app/infrastructure/crypto.py → 不动
5. 删除: app/db/ 目录
6. 更新所有 import: infra.xxx → app.infrastructure.xxx
```

### Phase 2: 迁移 services/ 中基础设施到 infrastructure/ (1-2天)

```
1. 创建 app/infrastructure/llm/
2. 搬入: services/llm/*.py
3. 创建 app/infrastructure/media/
4. 搬入: services/materials/*.py
5. 搬入: services/common/embedding_utils.py → infrastructure/embedding_utils.py
6. 更新所有 import
```
