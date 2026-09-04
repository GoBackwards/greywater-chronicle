CREATE TABLE player_sessions (
    session_token TEXT NOT NULL,
    player_id TEXT NOT NULL,

    PRIMARY KEY (session_token),
    UNIQUE (player_id)
);