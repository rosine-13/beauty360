from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
from security import hasher_mot_de_passe, verifier_mot_de_passe, creer_token, utilisateur_connecte

router = APIRouter(prefix="/auth", tags=["Authentification"])

@router.post("/register", response_model=schemas.TokenSortie, status_code=201)
def inscription(data: schemas.Inscription, db: Session = Depends(get_db)):
    # 1. L'email existe-t-il déjà ?
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    # 2. Créer l'utilisateur avec le mot de passe hashé
    user = models.User(nom=data.nom, email=data.email,
                       mot_de_passe_hash=hasher_mot_de_passe(data.mot_de_passe))
    db.add(user)
    db.commit()
    db.refresh(user)
    # 3. Renvoyer le token
    return {"access_token": creer_token(user.id), "utilisateur": user}

@router.post("/login", response_model=schemas.TokenSortie)
def connexion(data: schemas.Connexion, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if user is None or not verifier_mot_de_passe(data.mot_de_passe, user.mot_de_passe_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    return {"access_token": creer_token(user.id), "utilisateur": user}

@router.get("/me", response_model=schemas.UtilisateurSortie)
def mon_profil(user: models.User = Depends(utilisateur_connecte)):
    return user