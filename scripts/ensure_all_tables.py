#!/usr/bin/env python3
"""
确保数据库表完整 — 从源库导出 DDL 并回放到目标库。

用法:
  # 自检模式 (rebuild.sh 集成)
  DB_PASSWORD=xxx python3 scripts/ensure_all_tables.py -y

  # 推送模式 — 交互式询问目标地址
  DB_PASSWORD=local_pw python3 scripts/ensure_all_tables.py

  # 推送模式 — 全参数指定 (非交互)
  DB_PASSWORD=local_pw python3 scripts/ensure_all_tables.py \
    --to-host=192.168.x.x --to-password=yyy -y
"""
import os
import subprocess
import sys
import re
import argparse

# ── 源库 (ddl 从哪里导出) ──
SRC_HOST = os.environ.get("DB_HOST", "127.0.0.1")
SRC_PORT = os.environ.get("DB_PORT", "5432")
SRC_USER = os.environ.get("DB_USER", "companion")
SRC_DB = os.environ.get("DB_NAME", "edu_companion")
SRC_PASSWORD = os.environ.get("DB_PASSWORD")


def parse_args():
    parser = argparse.ArgumentParser(description="确保数据库表完整")
    parser.add_argument("--to-host", help="目标库地址（不指定则交互式询问）")
    parser.add_argument("--to-port", default="5432")
    parser.add_argument("--to-user", default="companion")
    parser.add_argument("--to-password", default="")
    parser.add_argument("--to-db", default="edu_companion")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="跳过确认提示（非交互模式）")
    return parser.parse_args()


def get_ddl(host, port, user, db, password) -> str:
    """从指定库导出完整 schema DDL"""
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    try:
        r = subprocess.run(
            ["pg_dump", f"--host={host}", f"--port={port}",
             f"--username={user}", f"--dbname={db}",
             "--schema-only", "--no-owner", "--no-acl"],
            capture_output=True, text=True, env=env, check=True,
        )
        return r.stdout
    except FileNotFoundError:
        print("错误: 请先安装 postgresql-client")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"错误: pg_dump 失败: {e.stderr}")
        sys.exit(1)


def extract_ddl(text: str) -> str:
    """提取 CREATE TABLE / INDEX，加 IF NOT EXISTS"""
    text = re.sub(r'^\\\\restrict.*\n', '', text, flags=re.MULTILINE)
    stmts = []

    for m in re.finditer(r'(CREATE\s+(UNIQUE\s+)?INDEX\s+.*?;)', text, re.DOTALL | re.IGNORECASE):
        stmts.append(m.group(1))
    for m in re.finditer(r'(CREATE\s+TABLE\s+.*?\);)\s*', text, re.DOTALL | re.IGNORECASE):
        stmts.append(m.group(1))

    # 去重
    seen = set()
    unique = []
    for s in stmts:
        key = re.sub(r'\s+', ' ', s.strip())
        if key not in seen:
            seen.add(key)
            unique.append(s.strip())

    output = []
    for s in unique:
        s = re.sub(r'^CREATE\s+TABLE\b', 'CREATE TABLE IF NOT EXISTS', s, count=1)
        s = re.sub(r'^CREATE\s+(UNIQUE\s+)?INDEX\b',
                   lambda m: f'CREATE {m.group(1) or ""}INDEX IF NOT EXISTS', s, count=1)
        output.append(s)

    return '\n\n'.join(output)


def apply_ddl(ddl: str, host, port, user, db, password):
    """回放 DDL 到指定库"""
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    proc = subprocess.run(
        ["psql", f"--host={host}", f"--port={port}",
         f"--username={user}", f"--dbname={db}",
         "-v", "ON_ERROR_STOP=1"],
        input=ddl, capture_output=True, text=True, env=env,
    )

    if proc.returncode != 0:
        errors = [l for l in proc.stderr.split('\n')
                  if l.strip() and 'already exists' not in l and 'NOTICE:' not in l and 'must be owner' not in l]
        if errors:
            for e in errors[:10]:
                print(f"  ! {e}")

    cnt = subprocess.run(
        ["psql", f"--host={host}", f"--port={port}",
         f"--username={user}", f"--dbname={db}",
         "-Atc", "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"],
        capture_output=True, text=True, env=env,
    )
    print(f"     目标表数量: {cnt.stdout.strip()}")


def main():
    args = parse_args()

    # ── 确定目标库参数 ──
    dst_host = args.to_host
    dst_port = args.to_port
    dst_user = args.to_user
    dst_db = args.to_db
    dst_password = args.to_password

    # 没有 --to-host → 自检模式
    self_check = not dst_host

    if self_check:
        dst_host = SRC_HOST
        dst_port = SRC_PORT
        dst_user = SRC_USER
        dst_db = SRC_DB
        dst_password = SRC_PASSWORD or ""
    else:
        # 推送模式：没有 -y 时交互式确认或补充信息
        if not args.yes:
            print(f"\n目标库: {dst_host}:{dst_port}/{dst_db} (user={dst_user})")
            if not dst_password:
                dst_password = input("目标数据库密码: ").strip()
            reply = input("确认应用 DDL 到上述目标库? (y/n): ").strip().lower()
            if reply != 'y':
                print("已取消.")
                sys.exit(0)

    print(f"源库: {SRC_HOST}:{SRC_PORT}/{SRC_DB}  (user={SRC_USER})")
    print(f"目标: {dst_host}:{dst_port}/{dst_db}" +
          ("  ← 自检模式" if self_check else "  ← 推送模式"))

    print("导出 DDL...")
    raw = get_ddl(SRC_HOST, SRC_PORT, SRC_USER, SRC_DB, SRC_PASSWORD)
    ddl = extract_ddl(raw)

    tables = ddl.count("CREATE TABLE IF NOT EXISTS")
    indexes = ddl.count("INDEX IF NOT EXISTS")
    print(f"解析到 {tables} 张表, {indexes} 个索引")

    print("回放 (幂等)...")
    apply_ddl(ddl, dst_host, dst_port, dst_user, dst_db, dst_password)
    print("完成.")


if __name__ == "__main__":
    main()
