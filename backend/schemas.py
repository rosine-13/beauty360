from pydantic import BaseModel, EmailStr, Field

# Ce que Flutter envoie pour s'inscrire
class Inscription(BaseModel):
    nom: str = Field(min_length=2)
    email: EmailStr
    mot_de_passe: str = Field(min_length=6, max_length=64)

# Ce que Flutter envoie pour se connecter
class Connexion(BaseModel):
    email: EmailStr
    mot_de_passe: str

# Ce que l'API renvoie sur un utilisateur (jamais le mot de passe)
class UtilisateurSortie(BaseModel):
    id: int
    nom: str
    email: EmailStr
    model_config = {"from_attributes": True}   # permet de lire un objet SQLAlchemy

# Ce que l'API renvoie après inscription ou connexion
class TokenSortie(BaseModel):
    access_token: str
    token_type: str = "bearer"
    utilisateur: UtilisateurSortie