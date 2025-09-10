# database.py
import os
from contextlib import contextmanager
from sqlmodel import SQLModel, create_engine, Session

# Ex.: postgresql+psycopg://user:pass@host:5432/dbname?sslmode=require
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")

# Render pede ssl; se vier SQLite, não usa pool agressivo.
connect_args = {}
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@contextmanager
def get_session():
    with Session(engine) as session:
        yield session
