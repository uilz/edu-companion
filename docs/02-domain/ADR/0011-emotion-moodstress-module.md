# ADR 0011: Emotion / MoodStress 模块全面重构

> 状态: Accepted
> 日期: 2026-07-04
> Task: #87

## 背景

Task #87 摸底发现 Emotion / MoodStress 模块存在**严重**问题：

1. **后端 4 个核心 .py 源文件丢失**，仅剩 .pyc 缓存：
   - `app/api/secretary/mood_stress.py`
   - `app/services/secretary/mood_stress_store.py`
   - `app/services/secretary/modules/mood_stress.py`
   - `app/infrastructure/event_bus_utils.py`

2. **前端 4 个文件缺失** 导致 build 失败：
   - `components/emotion/ManualRecordCard.tsx`
   - `components/emotion/InterventionPanel.tsx`
   - `lib/navConfig.ts`
   - `hooks/useCurrentUserId.ts`

3. **主入口 `app/main.py` 引用 5+ 个模块的源文件丢失**：
   - `app.api.project` (含 routes)
   - `app.api.planning` (含 routes)
   - `app.api.admin` (含 __init__)
   - `app.api.flashcard` (含 routes)
   - `app.api.interest` (含 routes)
   - `app.api.reading` (含 __init__)
   - `app.api.liveroom` (含 __init__)

导致：
- 后端完全无法启动 (`ImportError: cannot import name 'router'`)
- 前端 build 失败 (`Module not found`)
- /emotion 页面所有 MoodStress 功能失效

## 决策

### 1. 补桩缺失文件（必须）
对所有丢失的源文件，**优先重建 emotion 模块本身**（mood_stress.py / store / modules / event_bus_utils / ManualRecordCard / InterventionPanel / navConfig / useCurrentUserId）。这些是本任务范围。

### 2. 临时桩（其他模块）
对非 emotion 范围但阻塞启动的模块（project / planning / admin / flashcard / interest / reading / liveroom），创建**最小桩** `__init__.py` 含 `router = APIRouter(...)`。**不**实现业务逻辑，由其他 Task 负责。

理由：
- 立即可启动后端 → 可验证 emotion 模块端到端
- 避免引入"完整实现"导致本任务范围爆炸
- 临时桩有清晰标记（`tags=["...(占位)"]`）便于追溯

### 3. 数据 schema 对齐
`secretary_schema.sql` 声明 `emotion_records.id` 为 `TEXT`，但实际数据库为 `uuid` 类型。本任务以**实际数据库**为准：
- store 使用 `str(uuid.uuid4())` 生成 36 字符 UUID
- 后续可更新 schema.sql 与实际一致

### 4. 事件透明
所有写操作 (record / intervention / signal / prefs) 都发对应事件，遵循 shared/events.py 的 DomainEvent 模式。空 prefs PUT 不发事件（Task #87 B-8 决策保留）。

### 5. 测试策略
- **42 个新 E2E 测试** 覆盖 15 端点 + 4 事件 + 跨用户隔离 + 端到端流
- 使用 FastAPI TestClient + JWT Bearer 真实 HTTP
- 数据库不可用时 skip

## 后果

### 正面
- Emotion 模块完整可用
- 后端可启动，前端 build 阻塞解除（emotion 相关）
- 4 个 MoodStress 事件正式纳入全局事件流
- 42 测试可作为后续重构的安全网

### 负面
- **临时桩** 仅占位，project/planning/admin/flashcard/interest/reading/liveroom 模块仍不可用
- schema.sql 与实际数据库存在差异，需要后续迁移脚本或对齐任务
- emotion 标签在前端 EMOTION_CONFIG + 后端 VALID_EMOTION_TAGS + EMOTION_CATEGORIES 三处重复定义（建议下个任务集中）

## 关联

- ADR 0005 (Secretary 模块)
- ADR 0008 (Settings 模块)
- ADR 0009 (Secretary 扩展模块)
- Task #83 (Secretary E2E)
- Task #87 (Emotion E2E)
