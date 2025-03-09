#!/bin/bash
# Script to set up the project structure

# Create project directory
mkdir -p ask-e9y/app/{models,services,routers,utils}
mkdir -p ask-e9y/tests

# Create necessary Python files with empty content
touch ask-e9y/app/__init__.py
touch ask-e9y/app/main.py
touch ask-e9y/app/config.py
touch ask-e9y/app/database.py

touch ask-e9y/app/models/__init__.py
touch ask-e9y/app/models/requests.py
touch ask-e9y/app/models/responses.py

touch ask-e9y/app/services/__init__.py
touch ask-e9y/app/services/llm_service.py
touch ask-e9y/app/services/openai_llm.py
touch ask-e9y/app/services/gemini_llm.py
touch ask-e9y/app/services/query_service.py

touch ask-e9y/app/routers/__init__.py
touch ask-e9y/app/routers/query.py

touch ask-e9y/app/utils/__init__.py
touch ask-e9y/app/utils/schema_loader.py

touch ask-e9y/tests/__init__.py
touch ask-e9y/README.md
touch ask-e9y/.env.example

# Create .gitignore
cat > ask-e9y/.gitignore << 'EOL'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Project specific
.coverage
htmlcov/
.pytest_cache/
EOL

echo "Project structure created successfully!"