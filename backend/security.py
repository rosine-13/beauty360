import os
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
import models

# Sur Render : la clé est rangée en secret dans les réglages (variable SECRET_KEY).
# Sur ton PC : on garde une clé de test.
SECRET_KEY = os.getenv("SECRET_KEY", "cle-de-test-uniquement-sur-mon-pc")
ALGORITHM = "HS256"
DUREE_TOKEN_HEURES = 24 * 14  # 14 jours

def hasher_mot_de_passe(mdp: str) -> str:
    return bcrypt.hashpw(mdp.encode(), bcrypt.gensalt()).decode()

def verifier_mot_de_passe(mdp: str, mdp_hash: str) -> bool:
    return bcrypt.checkpw(mdp.encode(), mdp_hash.encode())

def creer_token(user_id: int) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(hours=DUREE_TOKEN_HEURES)
    return jwt.encode({"sub": str(user_id), "exp": expiration}, SECRET_KEY, algorithm=ALGORITHM)

bearer = HTTPBearer()   # lit l'en-tête "Authorization: Bearer <token>"

def utilisateur_connecte(cred: HTTPAuthorizationCredentials = Depends(bearer),
                         db: Session = Depends(get_db)) -> models.User:
    try:
        donnees = jwt.decode(cred.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(donnees["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user