from infrastructure.storage.postgres_db import execute_sql_file
import os

fix_path = r"c:\Users\maaro\OneDrive\Documentos\EpAI\infrastructure\storage\staging_fix.sql"

if os.path.exists(fix_path):
    print(f"Applying staging fix: {fix_path}")
    execute_sql_file(fix_path)
    print("Staging fix applied successfully!")
else:
    print(f"Error: Fix file not found at {fix_path}")
