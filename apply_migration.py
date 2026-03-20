from infrastructure.storage.postgres_db import execute_sql_file
import os
migration_path = os.path.join(os.path.dirname(__file__), "infrastructure", "storage", "nursing_migration.sql")



if os.path.exists(migration_path):
    print(f"Applying migration: {migration_path}")
    execute_sql_file(migration_path)
    print("Migration applied successfully!")
else:
    print(f"Error: Migration file not found at {migration_path}")
