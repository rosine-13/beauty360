from pathlib import Path
from typing import Optional
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

# Chargement du catalogue UNE SEULE FOIS, au démarrage
CHEMIN_CSV = Path(__file__).resolve().parent.parent / "data" / "catalogue_final.csv"   # NOUVEAU catalogue (classé par l'IA)
df = pd.read_csv(CHEMIN_CSV)
df["Ingredients"] = df["Ingredients"].fillna("")   # colonne vide dans le catalogue Amazon

TYPES = {"dry": "Dry", "normal": "Normal", "oily": "Oily",
         "combination": "Combination", "sensitive": "Sensitive"}
COLONNES_TYPES = list(TYPES.values())

# Score : note du produit + bonus si le produit est ciblé (peu de types de peau)
df["nb_types"] = df[COLONNES_TYPES].sum(axis=1)
df["score"] = df["Rank"] + (5 - df["nb_types"]) * 0.2

router = APIRouter(prefix="/products", tags=["Produits"])


@router.get("")
def recommander(type_peau: Optional[str] = None,          # NOUVEAU : facultatif
                sensible: bool = False,
                categorie: Optional[str] = None,
                limite: int = Query(10, ge=1, le=50)):
    # 1. Filtrer par type de peau SEULEMENT s'il est donné
    resultat = df
    if type_peau:
        colonne = TYPES.get(type_peau.lower())
        if colonne is None:
            raise HTTPException(status_code=400,
                                detail="type_peau doit être : " + ", ".join(TYPES))
        resultat = resultat[resultat[colonne] == 1]

    # 2. Autres filtres (facultatifs)
    if sensible:
        resultat = resultat[resultat["Sensitive"] == 1]
    if categorie:
        resultat = resultat[resultat["Label"].str.lower() == categorie.lower()]

    # 3. Classer et garder les meilleurs
    resultat = resultat.sort_values("score", ascending=False).head(limite)

    # 4. Répondre
    return [{
        "id": int(r.id),                          # le numéro du produit = numéro de sa photo
        "nom": r.Name,
        "marque": r.Brand,
        "categorie": r.Label,
        "prix_usd": round(float(r.Price), 2),     # NOUVEAU : prix avec centimes (ex. 12.99)
        "note": float(r.Rank),
        "ingredients": r.Ingredients,
        "image": f"/images/{r.id}.jpg",            # NOUVEAU : adresse de la photo sur notre API
    } for r in resultat.itertuples()]


@router.get("/categories")
def categories():
    return sorted(df["Label"].unique().tolist())