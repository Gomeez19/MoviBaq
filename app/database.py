import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Obtiene la cadena de conexión de Neon desde .env o variable de entorno
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_9qW5eOvASMHn@ep-broad-brook-b5rjq3b1-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

# En SQLAlchemy 2+, postgresql:// sin driver busca 'psycopg' (v3). 
# Con psycopg2-binary instalado, debemos especificar 'postgresql+psycopg2://'
db_uri = DATABASE_URL
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_uri.startswith("postgresql://") and not db_uri.startswith("postgresql+"):
    db_uri = db_uri.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = None
SessionLocal = None
Base = declarative_base()

try:
    engine = create_engine(
        db_uri,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    print(f"[AVISO] No se pudo inicializar engine de PostgreSQL directamente: {e}")

# Dependencia para inyectar la sesión en los endpoints de FastAPI
def get_db():
    if SessionLocal is None:
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
