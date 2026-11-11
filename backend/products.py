"""
LE CATALOGUE ET LES RECOMMANDATIONS
Catalogue : data/catalogue_ci.csv = 63 soins du visage vendus en Côte d'Ivoire,
prix en FCFA relevés sur Jumia CI (la colonne url_source donne la page exacte).
"""
import urllib.request
from pathlib import Path
from typing import Optional
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from problemes import PROBLEMES, TYPES_PEAU

DOSSIER = Path(__file__).resolve().parent
df = pd.read_csv(DOSSIER.parent / "data" / "catalogue_ci.csv")
df["prix_barre_fcfa"] = df["prix_barre_fcfa"].fillna(0).astype(int)
# "acne|pores" -> ["acne", "pores"] : plus simple à filtrer
df["liste_problemes"] = df["problemes"].str.split("|")
df["liste_types"] = df["types_peau"].str.split("|")
# Actifs annoncés dans le NOM du produit (vide si le nom n'en cite aucun)
df["liste_actifs"] = df["actifs"].fillna("").apply(lambda a: [x for x in a.split("|") if x])

# Ordre d'une routine simple : nettoyer -> traiter -> hydrater -> protéger
ETAPES = ["Nettoyant", "Soin ciblé", "Hydratant", "Protection solaire"]

router = APIRouter(prefix="/products", tags=["Produits"])


def en_json(r) -> dict:
    """Une ligne du catalogue -> le dictionnaire envoyé à Flutter."""
    return {
        "id": int(r.id),
        "nom": r.nom,
        "marque": r.marque,
        "categorie": r.categorie,
        "prix_fcfa": int(r.prix_fcfa),
        "prix_barre_fcfa": int(r.prix_barre_fcfa) or None,   # ancien prix si promo
        "problemes": [PROBLEMES[p] for p in r.liste_problemes],
        "types_peau": [TYPES_PEAU[t] for t in r.liste_types],
        "actifs": r.liste_actifs,
        "texture_legere": bool(r.texture_legere),
        "utilisation": r.utilisation,
        "vendeur": r.vendeur,
        "url_source": r.url_source,
        "date_releve": r.date_releve,
        "image": f"/products/{int(r.id)}/image",
    }


def classer(problemes: list[str], type_peau: Optional[str], categorie: Optional[str],
            budget_max: Optional[int]) -> pd.DataFrame:
    """Donne un score à chaque produit puis les trie du plus adapté au moins adapté."""
    res = df
    if categorie:
        res = res[res["categorie"].str.lower() == categorie.lower()]
    if budget_max:
        res = res[res["prix_fcfa"] <= budget_max]
    if type_peau:
        res = res[res["liste_types"].apply(lambda t: type_peau in t)]
    res = res.copy()

    # Score :
    #  +2 par problème de l'utilisatrice que le produit cible
    #  +0.5 si texture légère : climat chaud et humide d'Abidjan (on transpire, la peau brille)
    res["score"] = res["liste_problemes"].apply(lambda lp: 2 * len(set(lp) & set(problemes)))
    res["score"] += res["texture_legere"] * 0.5
    if problemes:
        res = res[res["score"] >= 2]          # au moins 1 problème en commun
    # à score égal : le moins cher d'abord
    return res.sort_values(["score", "prix_fcfa"], ascending=[False, True])


def verifier(problemes: list[str], type_peau: Optional[str]):
    inconnus = [p for p in problemes if p not in PROBLEMES]
    if inconnus:
        raise HTTPException(400, f"Problème inconnu : {inconnus}. Choix : {list(PROBLEMES)}")
    if type_peau and type_peau not in TYPES_PEAU:
        raise HTTPException(400, f"type_peau doit être : {list(TYPES_PEAU)}")


@router.get("")
def recommander(problemes: list[str] = Query([]),       # ex. ?problemes=acne&problemes=taches
                type_peau: Optional[str] = None,
                categorie: Optional[str] = None,
                budget_max: Optional[int] = None,
                limite: int = Query(10, ge=1, le=100)):
    verifier(problemes, type_peau)
    return [en_json(r) for r in classer(problemes, type_peau, categorie, budget_max).head(limite).itertuples()]


@router.get("/routine")
def routine(problemes: list[str] = Query([]), type_peau: Optional[str] = None,
            budget_max: Optional[int] = None):
    """Le meilleur produit pour chaque étape : nettoyant, soin ciblé, hydratant, écran solaire."""
    verifier(problemes, type_peau)
    etapes = []
    for etape in ETAPES:
        res = classer(problemes, type_peau, etape, budget_max)
        if res.empty:                                    # rien qui cible le problème :
            res = classer([], type_peau, etape, budget_max)  # on prend le meilleur de l'étape
        if not res.empty:
            etapes.append({"etape": etape, "produit": en_json(next(res.itertuples()))})
    return {"etapes": etapes, "total_fcfa": sum(e["produit"]["prix_fcfa"] for e in etapes)}


@router.get("/categories")
def categories():
    return sorted(df["categorie"].unique().tolist())


# ===== PHOTOS DES PRODUITS =====
# La 1re fois, l'API télécharge la photo depuis Jumia, puis la garde dans cache_images/.
CACHE = DOSSIER / "cache_images"
CACHE.mkdir(exist_ok=True)


@router.get("/{produit_id}/image")
def image(produit_id: int):
    fichier = CACHE / f"{produit_id}.jpg"
    if not fichier.exists():
        ligne = df[df["id"] == produit_id]
        if ligne.empty:
            raise HTTPException(404, "Produit inconnu")
        requete = urllib.request.Request(ligne.iloc[0]["image_source"],
                                         headers={"User-Agent": "Beauty360/1.0 (projet etudiant)"})
        try:
            fichier.write_bytes(urllib.request.urlopen(requete, timeout=15).read())
        except Exception:
            raise HTTPException(404, "Photo indisponible")
    return FileResponse(fichier, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800"})
