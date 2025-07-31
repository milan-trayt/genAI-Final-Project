-- Initialize GenAI DevOps Assistant Database
-- This script creates the necessary tables for multi-tab chat functionality

-- Chat sessions table for multi-tab support
CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    tab_id VARCHAR(255) NOT NULL,
    tab_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Chat messages table for persistent history
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    query_type VARCHAR(50) DEFAULT 'general',
    sources JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Add query_type column if it doesn't exist (for existing databases)
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS query_type VARCHAR(50) DEFAULT 'general';

-- Response cache table for Redis fallback (optional)
CREATE TABLE IF NOT EXISTS response_cache (
    cache_key VARCHAR(255) PRIMARY KEY,
    response_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp ON chat_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_tab_id ON chat_sessions(tab_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at);
CREATE INDEX IF NOT EXISTS idx_response_cache_expires_at ON response_cache(expires_at);

-- Insert some sample data for testing
INSERT INTO chat_sessions (session_id, tab_id, tab_name, metadata) VALUES 
    ('session_1', 'tab_1', 'AWS Architecture', '{"created_by": "system"}'),
    ('session_2', 'tab_2', 'Terraform Best Practices', '{"created_by": "system"}')
ON CONFLICT (session_id) DO NOTHING;