#!/usr/bin/env python3
"""
数据库表结构同步 — export / import / prune 模式。

用法:
  # 在完整库的机器上导出 DDL
  DB_PASSWORD=xxx python3 scripts/ensure_all_tables.py --export

  # 在远端机器上导入 DDL (补全缺失表 + 缺列 + 缺索引)
  DB_PASSWORD=yyy python3 scripts/ensure_all_tables.py --import

  # 导入 + 删除远端多余的表 (使两端完全对齐)
  DB_PASSWORD=yyy python3 scripts/ensure_all_tables.py --import --prune

  # rebuild.sh 集成 (默认跳过, 加 --sync-db 触发导入)
  bash rebuild.sh --sync-db
"""
import os
import subprocess
import sys
import re
import argparse
import json

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema_ddl.sql")


def parse_args():
    parser = argparse.ArgumentParser(description="数据库表结构同步")
    parser.add_argument("--export", action="store_true",
                        help="从本地库导出 DDL 到 scripts/schema_ddl.sql")
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="从 scripts/schema_ddl.sql 导入 DDL 到本地库")
    parser.add_argument("--prune", action="store_true",
                        help="(配合 --import) 删除目标库中 schema_ddl.sql 不存在的表")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="跳过确认提示")
    return parser.parse_args()


def _db_env():
    return {
        "host": os.environ.get("DB_HOST", "127.0.0.1"),
        "port": os.environ.get("DB_PORT", "5432"),
        "user": os.environ.get("DB_USER", "companion"),
        "db": os.environ.get("DB_NAME", "edu_companion"),
        "password": os.environ.get("DB_PASSWORD", ""),
    }


def _psql_env():
    env = os.environ.copy()
    cfg = _db_env()
    if cfg["password"]:
        env["PGPASSWORD"] = cfg["password"]
    return env, cfg


def run_psql(sql: str):
    env, cfg = _psql_env()
    r = subprocess.run(
        ["psql", f"--host={cfg['host']}", f"--port={cfg['port']}",
         f"--username={cfg['user']}", f"--dbname={cfg['db']}",
         "-At", "-c", sql],
        capture_output=True, text=True, env=env,
    )
    if r.returncode != 0:
        print(f"psql 错误: {r.stderr.strip()}")
        return ""
    return r.stdout.strip()


def run_psql_file(sql: str, on_error_stop: bool = True):
    """执行多行 SQL 文件"""
    env, cfg = _psql_env()
    args = ["psql", f"--host={cfg['host']}", f"--port={cfg['port']}",
            f"--username={cfg['user']}", f"--dbname={cfg['db']}"]
    if on_error_stop:
        args.extend(["-v", "ON_ERROR_STOP=1"])
    proc = subprocess.run(
        args, input=sql, capture_output=True, text=True, env=env,
    )
    if proc.returncode != 0:
        errors = [l for l in proc.stderr.split('\n')
                  if l.strip() and 'already exists' not in l
                  and 'NOTICE:' not in l and 'must be owner' not in l]
        if errors:
            for e in errors[:10]:
                print(f"  ! {e}")


def run_pg_dump():
    """导出完整 DDL"""
    env, cfg = _psql_env()
    try:
        r = subprocess.run(
            ["pg_dump", f"--host={cfg['host']}", f"--port={cfg['port']}",
             f"--username={cfg['user']}", f"--dbname={cfg['db']}",
             "--schema-only", "--no-owner", "--no-acl"],
            capture_output=True, text=True, env=env, check=True,
        )
        return r.stdout
    except subprocess.CalledProcessError as e:
        print(f"pg_dump 失败: {e.stderr}")
        sys.exit(1)


def parse_table_names_from_ddl(text: str) -> set[str]:
    """从 DDL 文本中提取所有表名"""
    names = set()
    for m in re.finditer(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?(\w+)',
        text, re.IGNORECASE
    ):
        names.add(m.group(1))
    return names


def _table_ddl_dict(text: str) -> dict[str, str]:
    """{table_name: CREATE TABLE DDL}"""
    result = {}
    for m in re.finditer(
        r'(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?(\w+)\s*\(.*?\);)\s*',
        text, re.DOTALL | re.IGNORECASE
    ):
        stmt = m.group(1)
        tbl = m.group(2)
        result[tbl] = stmt
    return result


def _columns_from_ddl(stmt: str) -> list[str]:
    """从 CREATE TABLE DDL 提取所有列名 (排除约束)"""
    cols = []
    body = re.search(r'\((.*)\);', stmt, re.DOTALL)
    if not body:
        return cols
    for line in body.group(1).split('\n'):
        line = line.strip().rstrip(',')
        if not line or re.match(r'^\s*(PRIMARY|UNIQUE|FOREIGN|CONSTRAINT|CHECK|INDEX|KEY|UNIQUE)\s',
                                line, re.IGNORECASE):
            continue
        m = re.match(r'^\s*"?(\w+)"?\s+', line)
        if m:
            cols.append(m.group(1))
    return cols


def extract_ddl(text: str) -> str:
    """提取 CREATE TABLE / INDEX，加 IF NOT EXISTS"""
    text = re.sub(r'^\\\\restrict.*\n', '', text, flags=re.MULTILINE)
    stmts = []

    for m in re.finditer(r'(CREATE\s+(UNIQUE\s+)?INDEX\s+.*?;)', text, re.DOTALL | re.IGNORECASE):
        stmts.append(m.group(1))
    for m in re.finditer(r'(CREATE\s+TABLE\s+.*?\);)\s*', text, re.DOTALL | re.IGNORECASE):
        stmts.append(m.group(1))

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


def do_export():
    cfg = _db_env()
    print(f"导出 DDL 从 {cfg['host']}:{cfg['port']}/{cfg['db']}...")
    raw = run_pg_dump()
    ddl = extract_ddl(raw)

    tables = ddl.count("CREATE TABLE IF NOT EXISTS")
    indexes = ddl.count("INDEX IF NOT EXISTS")

    with open(SCHEMA_FILE, "w") as f:
        f.write(f"-- 导出时间: {subprocess.run(['date', '+%Y-%m-%d %H:%M:%S'], capture_output=True, text=True).stdout.strip()}\n")
        f.write(f"-- 包含 {tables} 张表, {indexes} 个索引\n\n")
        f.write(ddl)
        f.write("\n")

    print(f"已写入 {SCHEMA_FILE}")
    print(f"  {tables} 张表, {indexes} 个索引")
    print(f"  (文件大小: {os.path.getsize(SCHEMA_FILE):,} 字节)")


def _existing_columns(table: str) -> set[str]:
    """查询目标库某表已有的列名"""
    rows = run_psql(
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_schema='public' AND table_name='{table}'"
    )
    if not rows:
        return set()
    return set(rows.strip().split('\n'))


def do_import(prune: bool, yes: bool):
    if not os.path.exists(SCHEMA_FILE):
        print(f"错误: 找不到 {SCHEMA_FILE}")
        print("请先在完整库的机器上执行 --export, 然后将此文件复制到远端机器")
        sys.exit(1)

    with open(SCHEMA_FILE) as f:
        ddl = f.read()

    tables = ddl.count("CREATE TABLE IF NOT EXISTS")
    indexes = ddl.count("INDEX IF NOT EXISTS")

    print(f"从 {SCHEMA_FILE} 导入 DDL...")
    print(f"  {tables} 张表, {indexes} 个索引")
    print(f"导入到 {_db_env()['host']}:{_db_env()['port']}/{_db_env()['db']}...")

    # ── Phase 1: CREATE TABLE IF NOT EXISTS ──
    print("\n[Phase 1/3]  建表...")
    # 只提取 CREATE TABLE 语句 (不含 INDEX)
    table_stmts = '\n\n'.join(
        _table_ddl_dict(ddl).values()
    )
    run_psql_file(table_stmts)
    print("  ✓ 建表完成")

    # ── Phase 2: ALTER TABLE ADD COLUMN (缺列补充) ──
    print("\n[Phase 2/3]  补充缺失列...")
    added = 0
    table_cols = {}  # {table: [col_names]}
    for tbl, stmt in _table_ddl_dict(ddl).items():
        expected = _columns_from_ddl(stmt)
        actual = _existing_columns(tbl)
        if not actual:  # 表不存在 → Phase 1 已创建, 无需补列
            continue
        missing = [c for c in expected if c not in actual]
        if not missing:
            continue
        # 从 DDL 提取每一列完整定义
        body = re.search(r'\((.*)\);', stmt, re.DOTALL)
        if not body:
            continue
        col_defs = {}
        for line in body.group(1).split('\n'):
            line = line.strip().rstrip(',')
            if not line or re.match(r'^\s*(PRIMARY|UNIQUE|FOREIGN|CONSTRAINT|CHECK|INDEX|KEY|UNIQUE)\s',
                                    line, re.IGNORECASE):
                continue
            cm = re.match(r'^\s*"?(\w+)"?\s+(.+)$', line)
            if cm:
                col_defs[cm.group(1)] = line

        for col in missing:
            if col not in col_defs:
                continue
            sql = f'ALTER TABLE "{tbl}" ADD COLUMN {col_defs[col]};'
            # 脱敏 DEFAULT 中有函数调用的列 (如 gen_random_uuid)
            sql_safe = re.sub(r"DEFAULT\s+\w+\(.*?\)", "DEFAULT NULL", sql)
            run_psql(sql_safe)
            print(f"    ✓ {tbl}.{col}")
            added += 1

    if added == 0:
        print("  所有列已是最新, 无需补充.")

    # ── Phase 3: CREATE INDEX IF NOT EXISTS (容错) ──
    print("\n[Phase 3/3]  建索引 (容错模式)...")
    index_stmts = []
    for m in re.finditer(r'(CREATE\s+(UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+.*?;)',
                         ddl, re.DOTALL | re.IGNORECASE):
        index_stmts.append(m.group(1))
    if index_stmts:
        # 逐个执行, 失败只警告
        for stmt in index_stmts:
            env, cfg = _psql_env()
            r = subprocess.run(
                ["psql", f"--host={cfg['host']}", f"--port={cfg['port']}",
                 f"--username={cfg['user']}", f"--dbname={cfg['db']}",
                 "-c", stmt],
                capture_output=True, text=True, env=env,
            )
            if r.returncode != 0:
                err = r.stderr.strip()
                if "already exists" not in err:
                    print(f"  ! 索引跳过: {err[:120]}")
        print(f"  ✓ 索引处理完成 ({len(index_stmts)} 个)")
    else:
        print("  无索引需要处理.")

    cnt = run_psql(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
    )
    print(f"\n导入完成.  当前表数量: {cnt}")

    # ── 清理多余表 ──
    if prune:
        _prune_tables(ddl, yes)


def _prune_tables(source_ddl: str, yes: bool):
    """删除目标库中 schema 不存在的表"""
    expected = parse_table_names_from_ddl(source_ddl)

    raw = run_psql(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
    )
    if not raw:
        return
    actual = set(raw.strip().split('\n'))

    extra = actual - expected
    extra = {t for t in extra if not t.startswith('alembic_')}

    if not extra:
        print("  没有多余表需要清理.")
        return

    print(f"\n发现 {len(extra)} 张多余表:")
    for t in sorted(extra):
        print(f"    - {t}")

    if not yes:
        reply = input("\n确认删除这些表及其所有数据? (y/n): ").strip().lower()
        if reply != 'y':
            print("已取消.")
            return

    for t in sorted(extra):
        run_psql(f'DROP TABLE IF EXISTS "{t}" CASCADE')
        print(f"    ✓ 已删除 {t}")

    cnt = run_psql(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
    )
    print(f"清理完成.  当前表数量: {cnt}")


def main():
    args = parse_args()

    if args.export:
        do_export()
    elif args.do_import:
        do_import(prune=args.prune, yes=args.yes)
    else:
        print("请指定 --export 或 --import")
        print("  --export   从本地库导出 DDL 到 scripts/schema_ddl.sql")
        print("  --import   从 scripts/schema_ddl.sql 导入 DDL 到本地库")
        print("  --prune    (配合 --import) 删除多余表")
        print("  -y         跳过确认")
        sys.exit(1)


if __name__ == "__main__":
    main()
