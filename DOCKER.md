# Docker Setup for Ask-E9Y

This document explains how to run the Ask-E9Y application using Docker, which eliminates environment inconsistencies and simplifies setup.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Setup Instructions

1. **Create the init-scripts directory and copy SQL files**

```bash
mkdir -p init-scripts
cp schema.sql init-scripts/
cp sample_data.sql init-scripts/
chmod +x init-scripts/init-db.sh
```

2. **Export your OpenAI API key**

```bash
export OPENAI_API_KEY=your_openai_api_key_here
```

3. **Start the application with Docker Compose**

```bash
docker-compose up --build
```

This will:
- Build the application container
- Start a PostgreSQL database container
- Create the eligibility schema and load sample data
- Start the API service on port 8000

4. **Access the application**

Once the containers are running, you can access:
- API documentation: http://localhost:8000/docs
- Debug endpoint: http://localhost:8000/debug/database

## Troubleshooting

If you encounter any issues:

1. **Check container logs**

```bash
docker-compose logs app  # Application logs
docker-compose logs db   # Database logs
```

2. **Connect to the database directly**

```bash
docker-compose exec db psql -U postgres -d ask_e9y_db
```

Then verify the schema exists:
```sql
\dn  -- List schemas
\dt eligibility.*  -- List tables in eligibility schema
SELECT COUNT(*) FROM eligibility.member;  -- Check for records
```

3. **Rebuild containers**

If you make changes to the code or configuration:

```bash
docker-compose down
docker-compose up --build
```

## Stopping the Application

```bash
docker-compose down
```

Add `-v` to remove volumes (this will delete the database data):
```bash
docker-compose down -v
```