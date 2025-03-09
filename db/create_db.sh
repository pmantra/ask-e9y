#!/bin/bash
# Instructions for setting up PostgreSQL database

# 1. First, create a new database (skip if you already have one)
createdb ask_e9y_db

# 2. Run the schema SQL script
psql -d ask_e9y_db -f schema.sql

# 3. Run the sample data SQL script
psql -d ask_e9y_db -f sample_data.sql

# 4. Verify the tables were created and populated
psql -d ask_e9y_db -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'eligibility' ORDER BY table_name;"
psql -d ask_e9y_db -c "SELECT COUNT(*) FROM eligibility.member;"
psql -d ask_e9y_db -c "SELECT COUNT(*) FROM eligibility.verification;"