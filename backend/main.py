from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
import models
import auth
import scan
import products
import agent

# 1. Créer les tables de la base de données (si elles n'existent pas encore)
Base.metadata.create_all(bind=engine)

# 2. Créer l'application
app = FastAPI(title="Beauty360 API")

# 3. CORS : autoriser la version web de Flutter à appeler l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Brancher toutes les routes
app.include_router(auth.router)       # /auth/register, /auth/login, /auth/me
app.include_router(scan.router)       # /scan, /scan/historique, /scan/modele
app.include_router(products.router)   # /products, /products/routine, /products/{id}/image
app.include_router(agent.router)      # /agent


@app.get("/")
def accueil():
    return {"message": "Bienvenue sur l'API Beauty360"}