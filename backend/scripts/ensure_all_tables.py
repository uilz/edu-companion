#!/usr/bin/env python3
"""
确保所有数据库表存在 — 导出完整 DDL 并回放。
幂等，可安全重复执行。
"""
import os
import subprocess
import sys
import re

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "companion")
DB_NAME = os.environ.get("DB_NAME", "edu_companion")
DB_PASSWORD = os.environ.get("DB_PASSWORD")


def get_ddl() -> str:
    """导出完整 schema DDL"""
    env = os.environ.copy()
    if DB_PASSWORD:
        env["PGPASSWORD"] = DB_PASSWORD
    cmd = [
        "pg_dump",
        f"--host={DB_HOST}", f"--port={DB_PORT}",
        f"--username={DB_USER}", f"--dbname={DB_NAME}",
        "--schema-only", "--no-owner", "--no-acl",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
        return r.stdout
    except FileNotFoundError:
        print("错误: 请先安装 postgresql-client")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"错误: pg_dump 失败: {e.stderr}")
        sys.exit(1)


def extract_ddl(text: str) -> str:
    """提取 CREATE TABLE / INDEX 语句，添加 IF NOT EXISTS"""
    # 移除 pg_dump restrict 行
    text = re.sub(r'^\\\\restrict.*\n', '', text, flags=re.MULTILINE)

    stmts = []

    # 匹配完整 CREATE TABLE 语句 (从 "CREATE TABLE" 到行尾的 ");" 或 ";")
    for m in re.finditer(
        r'(CREATE\s+(UNIQUE\s+)?INDEX\s+.*?;)',
        text, re.DOTALL | re.IGNORECASE
    ):
        stmts.append(m.group(1))

    for m in re.finditer(
        r'(CREATE\s+TABLE\s+.*?\);)\s*',
        text, re.DOTALL | re.IGNORECASE
    ):
        stmts.append(m.group(1))

    # 去重 (按内容): pg_dump 可能输出同一个表多次
    seen = set()
    unique = []
    for s in stmts:
        key = re.sub(r'\s+', ' ', s.strip())
        if key not in seen:
            seen.add(key)
            unique.append(s.strip())

    # 添加 IF NOT EXISTS
    output = []
    for s in unique:
        s = re.sub(r'^CREATE\s+TABLE\b', 'CREATE TABLE IF NOT EXISTS', s, count=1)
        s = re.sub(r'^CREATE\s+(UNIQUE\s+)?INDEX\b',
                   lambda m: f'CREATE {m.group(1) or ""}INDEX IF NOT EXISTS', s, count=1)
        output.append(s)

    return '\n\n'.join(output)


def apply_ddl(ddl: str):
    """通过 psql 回放"""
    env = os.environ.copy()
    if DB_PASSWORD:
        env["PGPASSWORD"] = DB_PASSWORD

    proc = subprocess.run(
        ["psql", f"--host={DB_HOST}", f"--port={DB_PORT}",
         f"--username={DB_USER}", f"--dbname={DB_NAME}",
         "-v", "ON_ERROR_STOP=1"],
        input=ddl, capture_output=True, text=True, env=env,
    )

    if proc.returncode != 0:
        errors = [l for l in proc.stderr.split('\n')
                  if l.strip() and 'already exists' not in l and 'NOTICE:' not in l]
        if errors:
            for e in errors[:10]:
                print(f"  ! {e}")

    # 统计表数量
    cnt = subprocess.run(
        ["psql", f"--host={DB_HOST}", f"--port={DB_PORT}",
         f"--username={DB_USER}", f"--dbname={DB_NAME}",
         "-Atc", "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"],
        capture_output=True, text=True, env=env
    )
    print(f"     当前表数量: {cnt.stdout.strip()}")


def main():
    print(f"连接: {DB_HOST}:{DB_PORT}/{DB_NAME} (user={DB_USER})")
    print("导出 DDL...")
    raw = get_ddl()
    ddl = extract_ddl(raw)

    tables = ddl.count("CREATE TABLE IF NOT EXISTS")
    indexes = ddl.count("INDEX IF NOT EXISTS")
    print(f"解析到 {tables} 张表, {indexes} 个索引")
    print("回放 (幂等)...")
    apply_ddl(ddl)
    print("完成.")


if __name__ == "__main__":
    main()
