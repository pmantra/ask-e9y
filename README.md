# Ask-E9Y

A chatbot system that leverages Large Language Models (LLMs) to translate natural language queries into SQL and query a PostgreSQL database.

## Features

- Natural language to SQL translation using OpenAI's GPT models
- FastAPI-based REST API
- PostgreSQL database with eligibility schema
- Modular LLM service design for easy provider switching
- Comprehensive SQL validation and security checks

## Project Structure

```
ask-e9y/
├── app/                    # Application code
├── db/                     # All database-related files
│   ├── schema.sql          # Main schema definition
│   ├── sample_data.sql     # Sample data for testing
│   ├── init-db.sh          # Database initialization script
│   └── migrations/         # Database migrations
├── Dockerfile              # Container definition
├── docker-compose.yml      # Service orchestration
├── start.sh                # App startup script
└── pyproject.toml          # Poetry configuration
```

## Setup

### Using Docker (Recommended)

1. Make sure you have Docker and Docker Compose installed
2. Set your OpenAI API key in the environment:
   ```bash
   export OPENAI_API_KEY=your_openai_api_key_here
   ```
3. Start the application:
   ```bash
   docker-compose up --build
   ```
4. Access the API at http://localhost:8000/docs

### Local Development

1. Make sure you have Python 3.12 and PostgreSQL installed
2. Create a virtual environment with Poetry:
   ```bash
   poetry install
   poetry shell
   ```
3. Set up your database:
   ```bash
   createdb ask_e9y_db
   psql -d ask_e9y_db -f db/schema.sql
   psql -d ask_e9y_db -f db/sample_data.sql
   ```
4. Create `.env` file with your configuration:
   ```
   DATABASE_URL=postgresql://your_username@localhost:5432/ask_e9y_db
   OPENAI_API_KEY=your_openai_api_key_here
   ```
5. Run the application:
   ```bash
   python run.py
   ```

## API Endpoints

- `POST /api/query`: Process natural language queries
- `POST /api/feedback`: Submit feedback on query results 
- `POST /api/schema`: Get database schema information

## Example Queries

- "Show me all members from ACME Corporation"
- "List the verification status of all members" 
- "How many members are there per organization?"

## License

This project is licensed under the MIT License.