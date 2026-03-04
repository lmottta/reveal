-- Initial Schema Migration for Supabase

-- Enable RLS
ALTER TABLE IF EXISTS search ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS search_result ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS news ENABLE ROW LEVEL SECURITY;

-- Create tables
CREATE TABLE IF NOT EXISTS search (
    id SERIAL PRIMARY KEY,
    query VARCHAR NOT NULL,
    tribunal VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS search_result (
    id SERIAL PRIMARY KEY,
    search_id INTEGER REFERENCES search(id),
    content JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS news (
    id SERIAL PRIMARY KEY,
    search_id INTEGER REFERENCES search(id),
    title VARCHAR,
    url VARCHAR UNIQUE,
    source VARCHAR,
    snippet VARCHAR,
    image_url VARCHAR,
    published_date VARCHAR,
    city VARCHAR,
    state VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS (again, to be sure)
ALTER TABLE search ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_result ENABLE ROW LEVEL SECURITY;
ALTER TABLE news ENABLE ROW LEVEL SECURITY;

-- Create policies for public read access
-- Drop existing policies if any to avoid errors
DROP POLICY IF EXISTS "Enable read access for all users" ON search;
DROP POLICY IF EXISTS "Enable read access for all users" ON search_result;
DROP POLICY IF EXISTS "Enable read access for all users" ON news;

CREATE POLICY "Enable read access for all users" ON search FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON search_result FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON news FOR SELECT USING (true);

-- No write policies for anon users. Only service_role can write (implicit bypass).
