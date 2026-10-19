import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Database URL for connecting to the PostgreSQL database using SQLAlchemy with psycopg2 driver.
DATABASE_URL = os.getenv("POSTGRES_URL")

engine = create_engine(DATABASE_URL)


class Base(DeclarativeBase):
    pass

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
