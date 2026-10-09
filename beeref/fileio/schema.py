USER_VERSION = 3
APPLICATION_ID = 2060242126


PALETTE_SCHEMA = [
    """
    CREATE TABLE palettes (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        position INTEGER NOT NULL,
        source_item_id INTEGER
          REFERENCES items (id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE palette_points (
        id INTEGER PRIMARY KEY,
        palette_id INTEGER NOT NULL
          REFERENCES palettes (id) ON DELETE CASCADE,
        item_id INTEGER NOT NULL
          REFERENCES items (id) ON DELETE CASCADE,
        x REAL NOT NULL,
        y REAL NOT NULL,
        position INTEGER NOT NULL,
        color TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE palette_meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """,
]


SCHEMA = [
    """
    CREATE TABLE items (
        id INTEGER PRIMARY KEY,
        type TEXT NOT NULL,
        x REAL DEFAULT 0,
        y REAL DEFAULT 0,
        z REAL DEFAULT 0,
        scale REAL DEFAULT 1,
        rotation REAL DEFAULT 0,
        flip INTEGER DEFAULT 1,
        data JSON
    )
    """,
    """
    CREATE TABLE sqlar (
        name TEXT PRIMARY KEY,
        item_id INTEGER NOT NULL UNIQUE,
        mode INT,
        mtime INT default current_timestamp,
        sz INT,
        data BLOB,
        FOREIGN KEY (item_id)
          REFERENCES items (id)
             ON DELETE CASCADE
             ON UPDATE NO ACTION
    )
    """,
]
SCHEMA = SCHEMA + PALETTE_SCHEMA


MIGRATIONS = {
    2: [
        "ALTER TABLE items ADD COLUMN data JSON",
        "UPDATE items SET data = json_object('filename', filename)",
    ],
    3: PALETTE_SCHEMA,
}
