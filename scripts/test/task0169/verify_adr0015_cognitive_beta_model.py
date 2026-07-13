"""Task #169 ADR 0015 认知概率图模型端到端验证

验证项：
  1. 通过 HTTP 创建知识树及两个节点 A、B
  2. 创建 cognitive 层级边 A→B（当前缺少 tree-edge → cognitive-edge 的 HTTP 同步入口，
     故使用 cognitive 内部便捷 API 创建）
  3. 通过 HTTP 创建题库与关联到 A 的单选题
  4. 通过 HTTP 创建并启动练习会话
  5. 提交正确答案
  6. 验证 A 节点的 cognitive_view 中 belief 已更新（proficiency > 0.5）
  7. 验证 B 节点因图传播 belief 也发生变化
  8. 清理测试数据

用法：
    cd /home/deploy/edu-companion
    backend/venv/bin/python scripts/test/task0169/verify_adr0015_cognitive_beta_model.py

环境要求：
    - 服务已通过 rebuild.sh 启动
    - 用户 apple / 123456 存在
"""

from __future__ import annotations

import sys
import time
import uuid
from typing import Any

import requests

sys.path.insert(0, "/home/deploy/edu-companion/backend")

BASE_URL = "http://127.0.0.1:8080"
USERNAME = "apple"
PASSWORD = "123456"


def get_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def api(method: str, path: str, token: str, **kwargs) -> Any:
    resp = requests.request(
        method,
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
        **kwargs,
    )
    resp.raise_for_status()
    return resp.json()


def api_allow_fail(method: str, path: str, token: str, **kwargs):
    try:
        resp = requests.request(
            method,
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
            **kwargs,
        )
        return resp.ok, resp.json() if resp.ok else resp.text[:200], resp.status_code
    except Exception as exc:  # noqa: BLE001
        return False, str(exc), 0


def ensure_knowledge_node(user_id: str, node_id: str, label: str) -> None:
    """使用 cognitive 内部便捷 API 在 knowledge_nodes 中创建节点。

    树节点与认知节点当前分属 tree_nodes / knowledge_nodes 两张表；cognitive handler
    在 belief update 时会自动 upsert atom node，但创建 knowledge_edges 前必须满足外键。
    这里显式创建，避免外键冲突。
    """
    from app.domain.cognitive.events import submit_node_created
    submit_node_created(user_id, node_id, label=label, level="atom")


def create_cognitive_edge(user_id: str, source_id: str, target_id: str, edge_type: str = "hierarchy") -> None:
    """使用 cognitive 内部便捷 API 创建 knowledge_edges 记录。

    当前系统没有暴露创建 cognitive 边的 HTTP 入口；tree edge 创建后不会自动同步到
    knowledge_edges。因此端到端验证图传播时，需要直接调用 cognitive handler 的便捷函数。
    """
    from app.domain.cognitive.events import submit_edge_created
    submit_edge_created(user_id, source_id, target_id, edge_type=edge_type, strength=0.8)


def link_tree_node_to_cognitive(user_id: str, tree_id: str, tree_node_id: str, cognitive_node_id: str) -> None:
    """创建 tree_node 与 cognitive_node 的关联。

    当前树节点与认知节点分属不同表，cognitive_view 通过 tree_node_cognitive_links
    查找关联的认知节点。验证脚本在创建双方后需要显式建立关联。
    """
    from app.services.knowledge_tree import cl_svc
    cl_svc.create_link(user_id, tree_id, tree_node_id, cognitive_node_id, link_role="primary")


def get_cognitive_view(tree_id: str, node_id: str, token: str) -> dict | None:
    data = api("GET", f"/api/trees/{tree_id}/nodes/{node_id}?include_cognitive_view=true", token)
    return data.get("node", {}).get("cognitive_view")


def run() -> tuple[bool, str]:
    token = get_token()
    suffix = uuid.uuid4().hex[:8]
    user_id = USERNAME

    # 1. 创建知识树
    tree = api("POST", "/api/trees", token, json={"name": f"ADR0015验证树{suffix}"})
    tree_id = tree["tree"]["id"]

    # 2. 创建两个节点 A、B，并获取后端真实 user_id
    node_a = api("POST", f"/api/trees/{tree_id}/nodes", token, json={"label": f"节点A-{suffix}"})
    node_b = api("POST", f"/api/trees/{tree_id}/nodes", token, json={"label": f"节点B-{suffix}"})
    node_a_id = node_a["node"]["id"]
    node_b_id = node_b["node"]["id"]
    user_id = node_a["node"]["user_id"]

    # 3. 创建 tree edge（不影响 cognitive，仅保持树结构完整）
    api(
        "POST",
        f"/api/trees/{tree_id}/edges",
        token,
        json={"source_node_id": node_a_id, "target_node_id": node_b_id, "edge_type": "parent_child", "strength": 0.8},
    )

    # 4. 确保 knowledge_nodes 中存在 A、B，建立 tree_node↔cognitive_node 关联，
    #    再创建 cognitive 边 A→B（hierarchy）
    ensure_knowledge_node(user_id, node_a_id, f"节点A-{suffix}")
    ensure_knowledge_node(user_id, node_b_id, f"节点B-{suffix}")
    link_tree_node_to_cognitive(user_id, tree_id, node_a_id, node_a_id)
    link_tree_node_to_cognitive(user_id, tree_id, node_b_id, node_b_id)
    create_cognitive_edge(user_id, node_a_id, node_b_id, edge_type="hierarchy")

    # 5. 创建题库
    bank = api("POST", "/api/practice/banks", token, json={"name": f"ADR0015验证题库{suffix}"})
    bank_id = bank["id"]

    # 6. 创建单选题，关联到节点 A
    question = api(
        "POST",
        f"/api/practice/banks/{bank_id}/questions",
        token,
        json={
            "question_type": "single",
            "stem": f"ADR0015 测试题 {suffix}",
            "options": [
                {"id": "A", "text": "正确选项"},
                {"id": "B", "text": "错误选项"},
            ],
            "answer": ["A"],
            "difficulty": 0.0,
            "cognitive_node_ids": [node_a_id],
        },
    )
    question_id = question["id"]

    # 7. 创建并启动练习会话
    session = api(
        "POST",
        "/api/practice/sessions",
        token,
        json={"bank_id": bank_id, "count": 1, "question_ids": [question_id]},
    )
    session_id = session["session_id"]
    api("PATCH", f"/api/practice/sessions/{session_id}/start", token)

    # 8. 提交正确答案
    submit_result = api(
        "POST",
        f"/api/practice/sessions/{session_id}/submit",
        token,
        json={"question_id": question_id, "answer": ["A"], "time_spent": 5, "confidence_before": 80},
    )
    if not submit_result.get("is_correct"):
        return False, f"答案提交后未判定为正确: {submit_result}"

    # 9. 等待事件异步处理完成
    time.sleep(1.0)

    # 10. 查询节点 A 的认知视图
    view_a = get_cognitive_view(tree_id, node_a_id, token)
    if view_a is None:
        return False, "节点 A 的认知视图不存在"
    if view_a.get("proficiency", 0.0) <= 0.5:
        return False, f"节点 A belief 未更新: proficiency={view_a.get('proficiency')}"

    # 11. 查询节点 B 的认知视图（图传播）
    view_b = get_cognitive_view(tree_id, node_b_id, token)
    if view_b is None:
        return False, "节点 B 的认知视图不存在"
    if view_b.get("proficiency", 0.0) <= 0.5:
        return False, f"节点 B 未收到图传播: proficiency={view_b.get('proficiency')}"

    # 12. 清理主要测试数据（tree 级联删除 tree_nodes / tree_edges；cognitive 数据可能残留）
    # 调试期间可注释掉以下清理，以便人工核查数据库状态
    api_allow_fail("DELETE", f"/api/practice/sessions/{session_id}", token)
    api_allow_fail("DELETE", f"/api/practice/questions/{question_id}", token)
    api_allow_fail("DELETE", f"/api/practice/banks/{bank_id}", token)
    # api_allow_fail("DELETE", f"/api/trees/{tree_id}", token)

    return True, (
        f"节点 A proficiency={view_a.get('proficiency'):.3f}, "
        f"节点 B proficiency={view_b.get('proficiency'):.3f}"
    )


if __name__ == "__main__":
    try:
        ok, msg = run()
    except Exception as exc:  # noqa: BLE001
        print(f"验证异常: {exc}")
        sys.exit(1)

    if ok:
        print(f"ADR 0015 端到端验证通过: {msg}")
        sys.exit(0)
    print(f"ADR 0015 端到端验证失败: {msg}")
    sys.exit(1)
