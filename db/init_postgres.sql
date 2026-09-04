SELECT 'CREATE DATABASE iot_support_assistant'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'iot_support_assistant')\gexec

\connect iot_support_assistant

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    device_model TEXT,
    firmware_version TEXT,
    error_code TEXT,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    summary TEXT NOT NULL,
    retrieved_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    suggested_action TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    useful BOOLEAN NOT NULL,
    ticket_id TEXT,
    comment TEXT,
    retrieved_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at DESC);
