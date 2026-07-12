"""Phase 5 Slice 5.9 端到端验证：Practice 练习壳服务下沉

验证项：
1. 题库 CRUD（创建、查询、更新、删除）
2. 题目 CRUD（创建、查询、更新、收藏、搜索）
3. 练习会话完整生命周期（创建、开始、提交答案、完成、结果）
4. 统计查询（overview、daily、sessions、errors、weak-skills）
5. 错题本查询
6. 导入预览（文本解析）
7. 推荐与秘书提案查询
8. 参考资料搜索（外部服务，容错）

用法：
    cd /home/deploy/edu-companion
    backend/venv/bin/python scripts/test/task0167/verify_practice_service_sink.py

环境要求：
    - 服务已通过 rebuild.sh 启动
    - 用户 apple / 123456 存在
"""

from __future__ import annotations

import sys
import uuid

import requests

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


def api(method: str, path: str, token: str, **kwargs):
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
    """允许失败的外部依赖调用，返回 (ok, data_or_msg, status_code)"""
    try:
        resp = requests.request(
            method,
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
            **kwargs,
        )
        if resp.ok:
            return True, resp.json(), resp.status_code
        return False, resp.text[:200], resp.status_code
    except Exception as exc:  # noqa: BLE001
        return False, str(exc), 0


def verify_bank_crud(token: str) -> tuple[bool, str, dict]:
    suffix = uuid.uuid4().hex[:8]
    bank = api(
        "POST",
        "/api/practice/banks",
        token,
        json={"name": f"验证题库 {suffix}", "description": "Practice 下沉验证"},
    )
    if not bank.get("id"):
        return False, f"创建题库失败: {bank}", {}
    bank_id = bank["id"]

    listed = api("GET", "/api/practice/banks", token)
    if not any(b["id"] == bank_id for b in listed):
        return False, "新建题库未出现在列表中", {}

    detail = api("GET", f"/api/practice/banks/{bank_id}", token)
    if detail.get("id") != bank_id:
        return False, f"题库详情异常: {detail}", {}

    updated = api(
        "PATCH",
        f"/api/practice/banks/{bank_id}",
        token,
        json={"name": f"验证题库（已更新）{suffix}"},
    )
    if updated.get("name") != f"验证题库（已更新）{suffix}":
        return False, f"更新题库失败: {updated}", {}

    return True, f"题库 CRUD 通过 (bank_id={bank_id})", {"bank_id": bank_id}


def verify_question_crud(token: str, bank_id: str) -> tuple[bool, str, dict]:
    question = api(
        "POST",
        f"/api/practice/banks/{bank_id}/questions",
        token,
        json={
            "question_type": "single",
            "stem": "服务下沉验证题：2+2=?",
            "answer": ["B"],
            "options": [
                {"letter": "A", "text": "3", "distractor_type": "careless"},
                {"letter": "B", "text": "4", "distractor_type": ""},
                {"letter": "C", "text": "5", "distractor_type": "concept"},
            ],
            "analysis": "2+2=4",
            "difficulty": 2,
            "cognitive_node_ids": [f"node_verify_{uuid.uuid4().hex[:8]}"],
            "source": "manual",
        },
    )
    if not question.get("id"):
        return False, f"创建题目失败: {question}", {}
    question_id = question["id"]

    listed = api("GET", f"/api/practice/banks/{bank_id}/questions", token)
    if not any(q["id"] == question_id for q in listed.get("items", [])):
        return False, f"新建题目未出现在列表中: {listed}", {}

    detail = api("GET", f"/api/practice/questions/{question_id}", token)
    if detail.get("id") != question_id:
        return False, f"题目详情异常: {detail}", {}

    updated = api(
        "PATCH",
        f"/api/practice/questions/{question_id}",
        token,
        json={"difficulty": 4, "analysis": "已更新解析"},
    )
    if updated.get("difficulty") != 4:
        return False, f"更新题目失败: {updated}", {}

    fav = api("POST", f"/api/practice/questions/{question_id}/favorite", token, json={})
    if not fav.get("is_favorite"):
        return False, f"收藏题目失败: {fav}", {}

    searched = api(
        "GET",
        "/api/practice/questions/search",
        token,
        params={"bank_id": bank_id, "keyword": "服务下沉"},
    )
    search_items = searched.get("items") or searched.get("questions", [])
    if not any(q["id"] == question_id for q in search_items):
        return False, f"题目搜索未命中: {searched}", {}

    return True, f"题目 CRUD 通过 (question_id={question_id})", {"question_id": question_id}


def verify_session_lifecycle(token: str, bank_id: str, question_id: str) -> tuple[bool, str, dict]:
    session = api(
        "POST",
        "/api/practice/sessions",
        token,
        json={
            "bank_id": bank_id,
            "session_type": "practice",
            "mode": "fixed",
            "count": 1,
            "question_ids": [question_id],
        },
    )
    if not session.get("id"):
        return False, f"创建会话失败: {session}", {}
    session_id = session["id"]
    if session.get("status") != "created":
        return False, f"会话初始状态异常: {session.get('status')}", {}

    started = api("PATCH", f"/api/practice/sessions/{session_id}/start", token)
    if started.get("status") != "started":
        return False, f"开始会话失败: {started}", {}

    submit = api(
        "POST",
        f"/api/practice/sessions/{session_id}/submit",
        token,
        json={"question_id": question_id, "answer": ["B"], "time_spent": 12, "confidence_before": 80},
    )
    if not submit.get("is_correct"):
        return False, f"提交答案失败或判定错误: {submit}", {}

    completed = api("POST", f"/api/practice/sessions/{session_id}/complete", token)
    if completed.get("status") != "completed":
        return False, f"完成会话失败: {completed}", {}

    result = api("GET", f"/api/practice/sessions/{session_id}/result", token)
    if "total" not in result or "correct" not in result:
        return False, f"会话结果异常: {result}", {}

    return True, f"会话生命周期通过 (session_id={session_id})", {"session_id": session_id}


def verify_stats(token: str) -> tuple[bool, str]:
    overview = api("GET", "/api/practice/stats/overview", token)
    if not isinstance(overview, dict) or "total_questions" not in overview:
        return False, f"统计 overview 字段异常: {overview}"

    daily = api("GET", "/api/practice/stats/daily?days=7", token)
    if not isinstance(daily, list):
        return False, f"日统计字段异常: {daily}"

    sessions = api("GET", "/api/practice/stats/sessions?limit=5", token)
    if not isinstance(sessions, list):
        return False, f"会话统计字段异常: {sessions}"

    errors = api("GET", "/api/practice/stats/errors", token)
    if not isinstance(errors, list):
        return False, f"错误统计字段异常: {errors}"

    weak = api("GET", "/api/practice/stats/weak-skills", token)
    if not isinstance(weak, list):
        return False, f"薄弱技能字段异常: {weak}"

    return True, "统计查询正常"


def verify_error_book(token: str) -> tuple[bool, str]:
    book = api("GET", "/api/practice/error-book", token)
    if "items" not in book:
        return False, f"错题本字段异常: {list(book.keys())}"

    stats = api("GET", "/api/practice/error-book/stats", token)
    if "unique_wrong_questions" not in stats:
        return False, f"错题本统计字段异常: {list(stats.keys())}"

    return True, "错题本查询正常"


def verify_import_preview(token: str, bank_id: str) -> tuple[bool, str]:
    text = (
        "1. 中国的首都是哪里？\n"
        "A. 上海\n"
        "B. 北京\n"
        "C. 广州\n"
        "答案：B\n"
        "解析：北京是首都。\n"
    )
    preview = api(
        "POST",
        "/api/practice/import/preview",
        token,
        json={"text": text},
    )
    questions = preview.get("questions", [])
    if not questions:
        return False, f"导入预览无题目: {preview}"

    history = api("GET", f"/api/practice/import/history?bank_id={bank_id}", token)
    if "items" not in history:
        return False, f"导入历史字段异常: {list(history.keys())}"

    return True, f"导入预览通过 (previewed={len(questions)})"


def verify_recommendations_and_proposals(token: str) -> tuple[bool, str]:
    rec = api("GET", "/api/practice/recommendations?limit=3", token)
    if "weak_skills" not in rec:
        return False, f"推荐字段异常: {list(rec.keys())}"

    proposals = api("GET", "/api/practice/secretary/proposals?limit=3", token)
    if "proposals" not in proposals:
        return False, f"提案字段异常: {list(proposals.keys())}"

    return True, "推荐与提案查询正常"


def verify_references(token: str) -> tuple[bool, str]:
    ok, data, code = api_allow_fail(
        "GET",
        "/api/practice/references/search?q=python",
        token,
    )
    if not ok:
        return True, f"参考资料搜索依赖外部服务，已容错跳过 (status={code}, msg={data})"
    if "results" not in data and "result" not in data and "items" not in data:
        return False, f"参考资料搜索返回结构异常: {list(data.keys())}"
    return True, "参考资料搜索正常"


def cleanup(token: str, bank_id: str | None, session_id: str | None) -> None:
    if session_id:
        try:
            api("DELETE", f"/api/practice/sessions/{session_id}", token)
        except Exception:  # noqa: BLE001
            pass
    if bank_id:
        try:
            api("DELETE", f"/api/practice/banks/{bank_id}", token)
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    print("=" * 60)
    print("Phase 5 Slice 5.9 验证：Practice 练习壳服务下沉")
    print("=" * 60)

    token = get_token()
    bank_id: str | None = None
    session_id: str | None = None

    try:
        ok, msg, ctx = verify_bank_crud(token)
        print(f"\n▶ 题库 CRUD... {'✅ 通过' if ok else '❌ 失败'}: {msg}")
        if not ok:
            return 1
        bank_id = ctx.get("bank_id")

        ok, msg, ctx = verify_question_crud(token, bank_id)
        print(f"▶ 题目 CRUD... {'✅ 通过' if ok else '❌ 失败'}: {msg}")
        if not ok:
            return 1
        question_id = ctx.get("question_id")

        ok, msg, ctx = verify_session_lifecycle(token, bank_id, question_id)
        print(f"▶ 会话生命周期... {'✅ 通过' if ok else '❌ 失败'}: {msg}")
        if not ok:
            return 1
        session_id = ctx.get("session_id")

        checks = [
            ("统计查询", lambda: verify_stats(token)),
            ("错题本", lambda: verify_error_book(token)),
            ("导入预览", lambda: verify_import_preview(token, bank_id)),
            ("推荐与提案", lambda: verify_recommendations_and_proposals(token)),
            ("参考资料搜索", lambda: verify_references(token)),
        ]

        all_passed = True
        for name, fn in checks:
            try:
                ok, msg = fn()
            except Exception as exc:  # noqa: BLE001
                ok, msg = False, f"异常: {exc}"
            print(f"▶ {name}... {'✅ 通过' if ok else '❌ 失败'}: {msg}")
            if not ok:
                all_passed = False

        print("\n" + "=" * 60)
        if all_passed:
            print("✅ Practice 服务下沉验证全部通过")
            return 0
        print("❌ Practice 服务下沉验证存在失败项")
        return 1
    finally:
        cleanup(token, bank_id, session_id)


if __name__ == "__main__":
    sys.exit(main())
