"""
Phase 4: 模块契约层

所有 Protocol 定义在此，其他模块只依赖此抽象。
实现类位于 domain/ 和 infra/ 中。

使用时直接导入具体子模块:
    from app.shared.protocols.practice import PracticeService
    from app.shared.protocols.persistence import KnowledgeStateRepository
"""
