CREATE TABLE processed_commands (
    command_id TEXT NOT NULL,
    command_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    expected_revision INTEGER NOT NULL
        CHECK (expected_revision >= 0),
    result_revision INTEGER NOT NULL
        CHECK (result_revision >= 1),

    PRIMARY KEY (command_id),
    UNIQUE (result_revision),
    FOREIGN KEY (result_revision)
        REFERENCES chronicle_events (revision)
);