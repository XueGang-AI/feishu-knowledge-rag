PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sync_jobs (
    job_id TEXT PRIMARY KEY,
    scope_type TEXT NOT NULL,
    scope_id TEXT,
    status TEXT NOT NULL,
    total_items INTEGER NOT NULL DEFAULT 0,
    processed_items INTEGER NOT NULL DEFAULT 0,
    failed_items INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS spaces (
    space_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    updated_time INTEGER,
    synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    node_token TEXT PRIMARY KEY,
    space_id TEXT NOT NULL,
    parent_node_token TEXT,
    obj_token TEXT,
    obj_type TEXT,
    title TEXT NOT NULL,
    source_url TEXT,
    updated_time INTEGER,
    deleted_at TEXT,
    synced_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_space_id ON nodes(space_id);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_node_token);

CREATE TABLE IF NOT EXISTS documents (
    doc_token TEXT PRIMARY KEY,
    space_id TEXT NOT NULL,
    node_token TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT,
    updated_time INTEGER,
    block_hash TEXT,
    deleted_at TEXT,
    synced_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_space_id ON documents(space_id);
CREATE INDEX IF NOT EXISTS idx_documents_node_token ON documents(node_token);

CREATE TABLE IF NOT EXISTS blocks (
    block_id TEXT PRIMARY KEY,
    doc_token TEXT NOT NULL,
    parent_block_id TEXT,
    block_type TEXT NOT NULL,
    heading_level INTEGER,
    text TEXT,
    raw_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(doc_token) REFERENCES documents(doc_token)
);

CREATE INDEX IF NOT EXISTS idx_blocks_doc_token ON blocks(doc_token);
CREATE INDEX IF NOT EXISTS idx_blocks_parent ON blocks(parent_block_id);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL,
    node_token TEXT NOT NULL,
    doc_token TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    title TEXT NOT NULL,
    section_path TEXT NOT NULL,
    source_url TEXT,
    block_ids TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    updated_time INTEGER,
    indexed_at TEXT,
    deleted_at TEXT,
    FOREIGN KEY(doc_token) REFERENCES documents(doc_token)
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_token ON chunks(doc_token);
CREATE INDEX IF NOT EXISTS idx_chunks_content_hash ON chunks(content_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_deleted_at ON chunks(deleted_at);

CREATE TABLE IF NOT EXISTS index_events (
    event_id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_index_events_chunk_id ON index_events(chunk_id);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
