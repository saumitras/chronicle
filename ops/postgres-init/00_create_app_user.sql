-- Create the chronicle application user
-- Note: the chronicle database is already created by POSTGRES_DB env var
-- We just need to create the user and grant privileges
CREATE USER chronicle WITH PASSWORD 'chronicle';
GRANT ALL PRIVILEGES ON DATABASE chronicle TO chronicle;
\c chronicle
GRANT ALL ON SCHEMA public TO chronicle;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO chronicle;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO chronicle;
