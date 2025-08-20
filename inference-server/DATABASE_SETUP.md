# Database Setup Guide

## 🐳 Docker Setup (Recommended)

The easiest way to get PostgreSQL and Weaviate running:

### 1. Quick Start
```bash
# 1. Run the unified setup script
./setup_local_dev.sh

# 2. Edit .env file with your OpenAI API key
nano .env

# 3. Start server
python start_server.py
```

### 2. Manual Docker Commands
```bash
# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs

# Stop services
docker-compose down
```

## 💻 Manual Setup (Alternative)

If you prefer installing PostgreSQL and Weaviate manually:

### 1. PostgreSQL Setup
```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql -c "CREATE DATABASE inference_db;"
sudo -u postgres psql -c "CREATE USER inference_user WITH PASSWORD 'your_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE inference_db TO inference_user;"
```

### 2. Weaviate Setup
```bash
# Run Weaviate with Docker
docker run -p 8080:8080 -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true -e PERSISTENCE_DATA_PATH=/var/lib/weaviate semitechnologies/weaviate:latest
```

### 3. Environment Variables
```bash
# Copy example file
cp .env.example .env

# Edit with your settings
nano .env
```

## 🚀 Server Startup

The server automatically:
- ✅ Connects to PostgreSQL
- ✅ Creates tables and indexes
- ✅ Connects to Weaviate
- ✅ Initializes hybrid storage

```bash
# Start the server
python start_server.py
```

## 🔧 Database Management

When you need to modify the database schema:

### Add a column:
```sql
ALTER TABLE documents ADD COLUMN new_field VARCHAR(100);
```

### Modify a column:
```sql
ALTER TABLE documents ALTER COLUMN title TYPE VARCHAR(500);
```

### Add an index:
```sql
CREATE INDEX idx_documents_new_field ON documents(new_field);
```

### Drop a table (careful!):
```sql
DROP TABLE IF EXISTS old_table CASCADE;
```

## 🔍 Quick Commands

```bash
# Connect to your database
psql $DATABASE_URL

# Or connect via Docker
docker-compose exec postgres psql -U inference_user -d inference_db

# List tables
\dt

# Describe a table
\d documents

# Show all data
SELECT * FROM documents LIMIT 10;

# Check document count
SELECT COUNT(*) FROM documents;
SELECT COUNT(*) FROM chunks;
```

## 🩺 Troubleshooting

### Docker Issues
```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs postgres
docker-compose logs weaviate

# Restart services
docker-compose restart

# Clean restart
docker-compose down && docker-compose up -d
```

### Connection Issues
```bash
# Test PostgreSQL connection
pg_isready -h localhost -p 5432 -U inference_user

# Test Weaviate connection
curl http://localhost:8080/v1/.well-known/live
```

### Common Problems

#### Docker Permission Issues
If you get "permission denied" when running Docker commands:

```bash
# Add your user to the docker group
sudo usermod -aG docker $USER

# Apply the group change immediately
newgrp docker

# Or logout/login to apply changes
# Then retry the setup
./setup_local_dev.sh
```

#### Other Issues
- **Port already in use**: Check if PostgreSQL/Weaviate are already running
- **Docker daemon not running**: Start with `sudo systemctl start docker`
- **API key missing**: Set `OPENAI_API_KEY` in `.env` file

That's it! No complex migration tools needed.