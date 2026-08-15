CREATE TABLE chronicle_events (
    revision INTEGER NOT NULL CHECK (revision >= 1),
    event_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
    payload_json TEXT NOT NULL,

    PRIMARY KEY (revision)
);
