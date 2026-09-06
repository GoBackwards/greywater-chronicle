import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

from fastapi import Request


MIGRATIONS_DIRECTORY = Path(__file__).parents[1] / "migrations"


def connect_database(
    database_path: Path,
) -> sqlite3.Connection:
    connection = sqlite3.connect(
        database_path,
        check_same_thread=False,
    )
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path) -> None:
    with closing(connect_database(database_path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_name TEXT PRIMARY KEY
            )
            """
        )
        connection.commit()

        applied_migrations = {
            row[0]
            for row in connection.execute(
                """
                SELECT migration_name
                FROM schema_migrations
                """
            ).fetchall()
        }

        for migration_path in sorted(
            MIGRATIONS_DIRECTORY.glob("*.sql")
        ):
            if migration_path.name in applied_migrations:
                continue

            migration_sql = migration_path.read_text(
                encoding="utf-8"
            )

            try:
                connection.executescript(
                    f"BEGIN IMMEDIATE;\n{migration_sql}\n"
                )
                connection.execute(
                    """
                    INSERT INTO schema_migrations (
                        migration_name
                    )
                    VALUES (?)
                    """,
                    (migration_path.name,),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise


def get_database_connection(
    request: Request,
) -> Iterator[sqlite3.Connection]:
    connection = connect_database(
        request.app.state.database_path
    )

    try:
        yield connection
    finally:
        connection.close()