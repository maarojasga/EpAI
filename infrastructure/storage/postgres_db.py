"""
postgres_db.py - PostgreSQL connection utility using SQLAlchemy.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

# Credenciales (Configuradas vía .env)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# Configuración del Engine
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Dependency generator for FastAPI to manage DB sessions.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def execute_sql_file(file_path: str):
    """
    Executes a .sql file directly against the database using a raw connection.
    Used for schema initialization.
    """
    import psycopg2
    
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()
            # Split by ';' to execute block by block if needed, 
            # though psycopg2 can handle multiple statements if not using SSMS batch separators.
            # Since we removed GO, it should work.
            cursor.execute(sql)
            print(f"Successfully executed {file_path}")
    except Exception as e:
        print(f"Error executing {file_path}: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()
