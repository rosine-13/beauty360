from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    mot_de_passe_hash = Column(String, nullable=False)
    date_creation = Column(DateTime, default=datetime.utcnow)

# Nouvelle table (l'ancienne table "scans" ne gardait qu'un type de peau)
class Analyse(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    problemes = Column(String, nullable=False, default="")  # ex. "acne,points_noirs" (vide = rien détecté)
    scores = Column(Text, nullable=False, default="{}")     # toutes les probabilités, en JSON
    date_analyse = Column(DateTime, default=datetime.utcnow)
