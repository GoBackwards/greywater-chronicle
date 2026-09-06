import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerSession:
    session_token: str
    player_id: str



def append_player_session(
    connection: sqlite3.Connection,
    session: PlayerSession,
) -> None:
    """Persist one server-issued player session."""
    connection.execute(
        """
        INSERT INTO player_sessions (
            session_token,
            player_id
        )
        VALUES (?, ?)
        """,
        (
            session.session_token,
            session.player_id,
        ),
    )


def load_player_session(
    connection: sqlite3.Connection,
    session_token: str,
) -> PlayerSession | None:
    """Load a player session by its bearer token."""
    row = connection.execute(
        """
        SELECT
            session_token,
            player_id
        FROM player_sessions
        WHERE session_token = ?
        """,
        (session_token,),
    ).fetchone()

    if row is None:
        return None

    return PlayerSession(
        session_token=row[0],
        player_id=row[1],
    )