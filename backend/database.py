import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Sur Render : l'adresse de Postgres est donnée par la variable DATABASE_URL.
# Sur ton PC : cette variable n'existe pas, donc on garde SQLite (le fichier beauty360.db).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./beauty360.db")

# Certains hébergeurs écrivent "postgres://", mais SQLAlchemy veut "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    # Réglage spécial, seulement pour SQLite
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Postgres : pool_pre_ping vérifie que la connexion est encore vivante avant de l'utiliser
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db          # on prête la session à la route
    finally:
        db.close()        # on la ferme toujours à la fin