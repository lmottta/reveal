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
    type VARCHAR,
    source VARCHAR,
    relevance FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS news (
    id SERIAL PRIMARY KEY,
    search_id INTEGER REFERENCES search(id),
    title VARCHAR(500),
    url VARCHAR(1000) UNIQUE,
    source VARCHAR(200),
    author VARCHAR(200),
    snippet TEXT,
    image_url VARCHAR(500),
    published_date VARCHAR(50),
    search_term VARCHAR(200),
    state VARCHAR(2),
    city VARCHAR(100),
    correlation VARCHAR(100),
    relevance_score FLOAT,
    is_relevant BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lawsuit (
    id SERIAL PRIMARY KEY,
    cnj VARCHAR(25) UNIQUE NOT NULL,
    tribunal VARCHAR(10),
    state VARCHAR(2),
    comarca VARCHAR(100),
    court VARCHAR(100),
    judge VARCHAR(200),
    forum_address VARCHAR(300),
    class_type VARCHAR(100),
    subject VARCHAR(200),
    parties TEXT,
    status VARCHAR(100),
    distribution_date VARCHAR(20),
    last_movement_date VARCHAR(20),
    movements TEXT,
    last_update TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_url ON news(url);
CREATE INDEX IF NOT EXISTS idx_news_state ON news(state);
CREATE INDEX IF NOT EXISTS idx_news_city ON news(city);
CREATE INDEX IF NOT EXISTS idx_lawsuit_cnj ON lawsuit(cnj);
CREATE INDEX IF NOT EXISTS idx_lawsuit_state ON lawsuit(state);
CREATE INDEX IF NOT EXISTS idx_search_query ON search(query);
CREATE INDEX IF NOT EXISTS idx_search_result_search_id ON search_result(search_id);
