"""
v6 -> v7 数据库迁移脚本

1. 将旧表名重命名为 nonebot-plugin-orm 的默认表名格式
2. 为 InfoData 表补充 v7 新增列

用法:
    python migrate.py [数据库URL]

数据库URL示例:
    sqlite:///db.sqlite3
    postgresql://user:pass@localhost/dbname
    mysql+pymysql://user:pass@localhost/dbname

不传参数时从 .env 读取 SQLALCHEMY_DATABASE_URL，否则使用默认 sqlite:///db.sqlite3
"""

import sys

from sqlalchemy import BigInteger, Integer, inspect, text
from sqlalchemy import create_engine

RENAMES = {
    "User": "nonebot_plugin_osubot_userdata",
    "Info": "nonebot_plugin_osubot_infodata",
    "SbUser": "nonebot_plugin_osubot_sbuserdata",
    "sbuserdata": "nonebot_plugin_osubot_sbuserdata",
}

# InfoData 新增列: (列名, DDL类型)
NEW_INFO_COLUMNS = [
    ("ranked_score", BigInteger()),
    ("total_score", BigInteger()),
    ("max_combo", Integer()),
    ("count_xh", Integer()),
    ("count_x", Integer()),
    ("count_sh", Integer()),
    ("count_s", Integer()),
    ("count_a", Integer()),
    ("replays", Integer()),
    ("play_time", Integer()),
    ("badge_count", Integer()),
]


def get_db_url() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    try:
        from dotenv import dotenv_values

        for fname in (".env", ".env.prod"):
            env = dotenv_values(fname)
            if url := env.get("SQLALCHEMY_DATABASE_URL") or env.get("DATABASE_URL"):
                return url
    except ImportError:
        pass
    return "sqlite:///db.sqlite3"


def main():
    url = get_db_url()
    # 将异步驱动替换为同步驱动（migrate.py 使用同步 SQLAlchemy）
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("mysql+aiomysql://", "mysql+pymysql://")
    url = url.replace("sqlite+aiosqlite://", "sqlite://")
    print(f"连接数据库: {url}")
    engine = create_engine(url)
    dialect = engine.dialect.name

    with engine.begin() as conn:
        insp = inspect(conn)
        existing_tables = set(insp.get_table_names())

        # 1. 重命名表
        for old, new in RENAMES.items():
            if old not in existing_tables:
                print(f"跳过重命名: 表 {old!r} 不存在")
                continue
            if new in existing_tables:
                print(f"跳过重命名: 表 {new!r} 已存在")
                continue
            if dialect == "mysql":
                stmt = f"RENAME TABLE `{old}` TO `{new}`"
            else:
                stmt = f'ALTER TABLE "{old}" RENAME TO "{new}"'
            conn.execute(text(stmt))
            print(f"已重命名: {old!r} -> {new!r}")
            existing_tables.discard(old)
            existing_tables.add(new)

        # 2. 修复索引名
        # 删除旧索引
        DROP_INDEXES = {
            "nonebot_plugin_osubot_infodata": ["idx_Info_id_786c64"],
            "nonebot_plugin_osubot_userdata": ["idx_User_user_id_93024f"],
        }
        # 创建新索引: (表名, 索引名, 列名)
        ADD_INDEXES = [
            ("nonebot_plugin_osubot_userdata", "ix_nonebot_plugin_osubot_userdata_user_id", "user_id"),
            ("nonebot_plugin_osubot_sbuserdata", "ix_nonebot_plugin_osubot_sbuserdata_user_id", "user_id"),
        ]

        for table, indexes in DROP_INDEXES.items():
            if table not in existing_tables:
                continue
            existing_indexes = {idx["name"] for idx in inspect(conn).get_indexes(table)}
            for idx in indexes:
                if idx not in existing_indexes:
                    print(f"跳过删除索引: {idx!r} 不存在")
                    continue
                if dialect == "mysql":
                    conn.execute(text(f"DROP INDEX `{idx}` ON `{table}`"))
                else:
                    conn.execute(text(f'DROP INDEX "{idx}"'))
                print(f"已删除索引: {idx!r}")

        for table, idx_name, col in ADD_INDEXES:
            if table not in existing_tables:
                print(f"跳过创建索引: 表 {table!r} 不存在")
                continue
            existing_indexes = {idx["name"] for idx in inspect(conn).get_indexes(table)}
            if idx_name in existing_indexes:
                print(f"跳过创建索引: {idx_name!r} 已存在")
                continue
            if dialect == "mysql":
                conn.execute(text(f"CREATE INDEX `{idx_name}` ON `{table}` (`{col}`)"))
            else:
                conn.execute(text(f'CREATE INDEX "{idx_name}" ON "{table}" ("{col}")'))
            print(f"已创建索引: {idx_name!r}")

        # 3. 为 InfoData 补充新列
        info_table = "nonebot_plugin_osubot_infodata"
        if info_table not in existing_tables:
            print(f"跳过补列: 表 {info_table!r} 不存在")
        else:
            existing_cols = {col["name"] for col in inspect(conn).get_columns(info_table)}
            for col_name, col_type in NEW_INFO_COLUMNS:
                if col_name in existing_cols:
                    print(f"跳过补列: {col_name!r} 已存在")
                    continue
                type_str = col_type.compile(dialect=engine.dialect)
                if dialect == "mysql":
                    stmt = f"ALTER TABLE `{info_table}` ADD COLUMN `{col_name}` {type_str} NULL"
                else:
                    stmt = f'ALTER TABLE "{info_table}" ADD COLUMN "{col_name}" {type_str}'
                conn.execute(text(stmt))
                print(f"已添加列: {info_table}.{col_name}")

    print("迁移完成，请运行以下命令标记迁移版本：")
    print("  nb orm stamp 68a04ea31d05")


if __name__ == "__main__":
    main()
