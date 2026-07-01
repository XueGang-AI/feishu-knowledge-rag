PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sync_jobs (
    job_id TEXT PRIMARY KEY,
    account_id TEXT,
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

CREATE INDEX IF NOT EXISTS idx_sync_jobs_account_status
ON sync_jobs(account_id, status, scope_type);

CREATE TABLE IF NOT EXISTS spaces (
    account_id TEXT NOT NULL,
    space_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    updated_time INTEGER,
    synced_at TEXT NOT NULL,
    PRIMARY KEY(account_id, space_id)
);

CREATE TABLE IF NOT EXISTS nodes (
    account_id TEXT NOT NULL,
    node_token TEXT NOT NULL,
    space_id TEXT NOT NULL,
    parent_node_token TEXT,
    obj_token TEXT,
    obj_type TEXT,
    title TEXT NOT NULL,
    source_url TEXT,
    updated_time INTEGER,
    deleted_at TEXT,
    synced_at TEXT NOT NULL,
    PRIMARY KEY(account_id, node_token),
    FOREIGN KEY(account_id, space_id) REFERENCES spaces(account_id, space_id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_account_space_id ON nodes(account_id, space_id);
CREATE INDEX IF NOT EXISTS idx_nodes_account_parent ON nodes(account_id, parent_node_token);

CREATE TABLE IF NOT EXISTS documents (
    account_id TEXT NOT NULL,
    doc_token TEXT NOT NULL,
    space_id TEXT NOT NULL,
    node_token TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT,
    updated_time INTEGER,
    block_hash TEXT,
    deleted_at TEXT,
    synced_at TEXT NOT NULL,
    PRIMARY KEY(account_id, doc_token),
    FOREIGN KEY(account_id, space_id) REFERENCES spaces(account_id, space_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_account_space_id ON documents(account_id, space_id);
CREATE INDEX IF NOT EXISTS idx_documents_account_node_token ON documents(account_id, node_token);

CREATE TABLE IF NOT EXISTS blocks (
    account_id TEXT NOT NULL,
    block_id TEXT NOT NULL,
    doc_token TEXT NOT NULL,
    parent_block_id TEXT,
    block_type TEXT NOT NULL,
    heading_level INTEGER,
    text TEXT,
    raw_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(account_id, block_id),
    FOREIGN KEY(account_id, doc_token) REFERENCES documents(account_id, doc_token)
);

CREATE INDEX IF NOT EXISTS idx_blocks_account_doc_token ON blocks(account_id, doc_token);
CREATE INDEX IF NOT EXISTS idx_blocks_account_parent ON blocks(account_id, parent_block_id);

CREATE TABLE IF NOT EXISTS chunks (
    account_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
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
    PRIMARY KEY(account_id, chunk_id),
    FOREIGN KEY(account_id, doc_token) REFERENCES documents(account_id, doc_token)
);

CREATE INDEX IF NOT EXISTS idx_chunks_account_doc_token ON chunks(account_id, doc_token);
CREATE INDEX IF NOT EXISTS idx_chunks_account_content_hash ON chunks(account_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_account_deleted_at ON chunks(account_id, deleted_at);

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
