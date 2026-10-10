USER_VERSION = 4
APPLICATION_ID = 2060242126


PALETTE_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS palettes (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        position INTEGER NOT NULL,
        source_item_id INTEGER
          REFERENCES items (id) ON DELETE SET NULL,
        source_item_sz INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS palette_points (
        id INTEGER PRIMARY KEY,
        palette_id INTEGER NOT NULL
          REFERENCES palettes (id) ON DELETE CASCADE,
        item_id INTEGER NOT NULL
          REFERENCES items (id) ON DELETE CASCADE,
        x REAL NOT NULL,
        y REAL NOT NULL,
        position INTEGER NOT NULL,
        color TEXT NOT NULL,
        item_sz INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS palette_meta (
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
# Version 4: lasso region (JSON list of relative [x, y]) of a palette's
# last extraction
PALETTE_REGION_SCHEMA = [
    "ALTER TABLE palettes ADD COLUMN source_region TEXT",
]
SCHEMA = SCHEMA + PALETTE_SCHEMA + PALETTE_REGION_SCHEMA


MIGRATIONS = {
    2: [
        "ALTER TABLE items ADD COLUMN data JSON",
        "UPDATE items SET data = json_object('filename', filename)",
    ],
    3: PALETTE_SCHEMA,
    4: PALETTE_REGION_SCHEMA,
}
