-- PostgreSQL test database initialization
-- This script sets up test data for migration testing

-- Create test tables
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    slug VARCHAR(200) NOT NULL UNIQUE,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_name VARCHAR(100) NOT NULL,
    author_email VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'spam')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    slug VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS post_categories (
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, category_id)
);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_posts_updated_at BEFORE UPDATE ON posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert test data
INSERT INTO users (username, email, password_hash) VALUES
('admin', 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG'),
('john_doe', 'john@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG'),
('jane_smith', 'jane@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG'),
('test_user', 'test@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG');

INSERT INTO categories (name, description, slug) VALUES
('Technology', 'Posts about technology and programming', 'technology'),
('Travel', 'Travel experiences and tips', 'travel'),
('Food', 'Recipes and food reviews', 'food'),
('Lifestyle', 'General lifestyle content', 'lifestyle');

INSERT INTO posts (user_id, title, content, slug, status) VALUES
(1, 'Welcome to Our Blog', 'This is the first post on our blog. Welcome!', 'welcome-to-our-blog', 'published'),
(2, 'Getting Started with Python', 'Python is a great programming language for beginners...', 'getting-started-with-python', 'published'),
(2, 'Advanced Database Migrations', 'Database migrations can be complex, but with the right tools...', 'advanced-database-migrations', 'published'),
(3, 'My Trip to Japan', 'Japan is an amazing country with rich culture...', 'my-trip-to-japan', 'published'),
(3, 'Best Ramen in Tokyo', 'Here are my favorite ramen shops in Tokyo...', 'best-ramen-in-tokyo', 'draft'),
(4, 'Test Post', 'This is a test post for migration testing.', 'test-post', 'draft');

INSERT INTO post_categories (post_id, category_id) VALUES
(1, 4), -- Welcome post -> Lifestyle
(2, 1), -- Python post -> Technology
(3, 1), -- Database post -> Technology
(4, 2), -- Japan post -> Travel
(5, 2), -- Ramen post -> Travel
(5, 3), -- Ramen post -> Food
(6, 4); -- Test post -> Lifestyle

INSERT INTO comments (post_id, author_name, author_email, content, status) VALUES
(1, 'Reader One', 'reader1@example.com', 'Great first post! Looking forward to more content.', 'approved'),
(1, 'Reader Two', 'reader2@example.com', 'Welcome! Nice to see a new blog.', 'approved'),
(2, 'Python Fan', 'pythonfan@example.com', 'Python is indeed great for beginners. Thanks for the tips!', 'approved'),
(2, 'Beginner Coder', 'beginner@example.com', 'This helped me get started. Thank you!', 'approved'),
(3, 'DB Expert', 'dbexpert@example.com', 'Good insights on database migrations.', 'approved'),
(4, 'Travel Lover', 'traveler@example.com', 'Japan sounds amazing! I want to visit too.', 'pending'),
(4, 'Spam Bot', 'spam@spam.com', 'Buy cheap products here!', 'spam');

-- Create indexes for performance testing
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_status ON posts(status);
CREATE INDEX idx_posts_created_at ON posts(created_at);
CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_status ON comments(status);

-- Create a view for testing
CREATE VIEW published_posts AS
SELECT 
    p.id,
    p.title,
    p.content,
    p.slug,
    p.created_at,
    u.username as author,
    u.email as author_email
FROM posts p
JOIN users u ON p.user_id = u.id
WHERE p.status = 'published';

-- Create a stored function for testing
CREATE OR REPLACE FUNCTION get_user_post_count(user_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    post_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO post_count
    FROM posts
    WHERE posts.user_id = get_user_post_count.user_id;
    
    RETURN post_count;
END;
$$ LANGUAGE plpgsql;

-- Create a sequence for testing
CREATE SEQUENCE test_sequence START 1000;

-- Create an enum type for testing
CREATE TYPE post_status_enum AS ENUM ('draft', 'published', 'archived');

-- Create a custom aggregate function for testing
CREATE OR REPLACE FUNCTION array_concat_agg_sfunc(internal_state TEXT[], next_data_values TEXT)
RETURNS TEXT[] AS $$
BEGIN
    RETURN array_append(internal_state, next_data_values);
END;
$$ LANGUAGE plpgsql;

CREATE AGGREGATE array_concat_agg(TEXT) (
    SFUNC = array_concat_agg_sfunc,
    STYPE = TEXT[],
    INITCOND = '{}'
);

-- Grant permissions for test user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO testuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO testuser;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO testuser;