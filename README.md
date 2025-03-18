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
- "Show me all overeligible members"
- "Is John Smith overeligible?"
- "Check if member with ID 12345 is overeligible"

# How Ask E9Y Works

## User Input to Database Results Flow

1. **Input Reception**:  
   System receives natural language query through `/api/query` endpoint.

2. **Cache Check**:  
   Checks for identical or semantically similar queries in PostgreSQL and ChromaDB.

3. **LLM Translation**:  
   If no cache hit, sends query with database schema to OpenAI to generate SQL.

4. **SQL Validation**:  
   Validates generated SQL for safety, syntax, and schema correctness.

5. **Execution**:  
   Runs validated SQL against PostgreSQL database using SQLAlchemy.

6. **Explanation**:  
   Optionally generates natural language explanation of the results.

7. **Caching**:  
   Stores query, SQL, and results for future use.

8. **Response**:  
   Returns results, SQL, execution statistics, and explanation to the user.

The system combines traditional caching, vector similarity search, and LLM capabilities to efficiently translate natural language to SQL while preventing harmful operations.


## License

This project is licensed under the MIT License.