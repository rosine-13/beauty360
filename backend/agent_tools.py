"""
Les OUTILS de l'agent Beauty360.
DeepSeek ne peut pas les exécuter lui-même : il DEMANDE à les utiliser,
et c'est notre API qui les exécute puis lui renvoie le résultat.
"""
from sqlalchemy.orm import Session
import models
from problemes import PROBLEMES, TYPES_PEAU
from products import classer, en_json, df, routine


# ===== OUTIL 1 : la dernière analyse de l'utilisatrice =====
def derniere_analyse(db: Session, user_id: int) -> dict:
    a = (db.query(models.Analyse)
           .filter(models.Analyse.user_id == user_id)
           .order_by(models.Analyse.date_analyse.desc())
           .first())
    if a is None:
        return {"trouve": False, "message": "Aucune analyse de peau pour le moment."}
    codes = [c for c in a.problemes.split(",") if c]
    return {"trouve": True, "date": a.date_analyse.strftime("%d/%m/%Y"),
            "problemes_detectes": [{"code": c, "libelle": PROBLEMES[c]} for c in codes]}


def _court(p: dict) -> dict:
    """On garde l'essentiel pour l'agent (moins de texte = réponse plus rapide)."""
    return {k: p[k] for k in ("nom", "marque", "categorie", "prix_fcfa", "utilisation", "problemes")}


# ===== OUTIL 2 : chercher des produits =====
def rechercher_produits(problemes: list[str] | None = None, type_peau: str | None = None,
                        categorie: str | None = None, budget_max_fcfa: int | None = None,
                        limite: int = 3):
    problemes = [p for p in (problemes or []) if p in PROBLEMES]
    if type_peau not in TYPES_PEAU:
        type_peau = None
    res = classer(problemes, type_peau, categorie, budget_max_fcfa).head(limite)
    return [_court(en_json(r)) for r in res.itertuples()] or {"message": "Aucun produit trouvé."}


# ===== OUTIL 3 : une routine complète =====
def proposer_routine(problemes: list[str] | None = None, type_peau: str | None = None,
                     budget_max_fcfa: int | None = None):
    problemes = [p for p in (problemes or []) if p in PROBLEMES]
    if type_peau not in TYPES_PEAU:
        type_peau = None
    r = routine(problemes, type_peau, budget_max_fcfa)
    return {"etapes": [{"etape": e["etape"], **_court(e["produit"])} for e in r["etapes"]],
            "total_fcfa": r["total_fcfa"]}


# ===== OUTIL 4 : la fiche d'un produit précis =====
def fiche_produit(nom: str) -> dict:
    trouves = df[df["nom"].str.contains(nom, case=False, regex=False)]
    if trouves.empty:
        return {"trouve": False, "message": "Produit introuvable dans le catalogue."}
    p = en_json(next(trouves.itertuples()))
    return {"trouve": True, **{k: p[k] for k in ("nom", "marque", "categorie", "prix_fcfa", "problemes",
                                                 "types_peau", "texture_legere", "utilisation",
                                                 "vendeur", "date_releve")}}


# ===== LA "NOTICE" DES OUTILS POUR DEEPSEEK =====
_PROBLEMES = {"type": "array", "items": {"type": "string", "enum": list(PROBLEMES)},
              "description": "Problèmes de peau à traiter (codes)."}
_TYPE = {"type": "string", "enum": list(TYPES_PEAU), "description": "Type de peau (facultatif)."}
_BUDGET = {"type": "integer", "description": "Prix maximum PAR PRODUIT en FCFA (facultatif)."}

OUTILS = [
    {"type": "function", "function": {
        "name": "derniere_analyse",
        "description": "Donne les problèmes de peau détectés lors de la dernière analyse photo de l'utilisatrice.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "rechercher_produits",
        "description": "Cherche des soins du visage vendus en Côte d'Ivoire, adaptés aux problèmes de peau.",
        "parameters": {"type": "object", "properties": {
            "problemes": _PROBLEMES, "type_peau": _TYPE, "budget_max_fcfa": _BUDGET,
            "categorie": {"type": "string", "enum": ["Nettoyant", "Soin ciblé", "Hydratant",
                                                     "Protection solaire", "Masque", "Contour des yeux"]},
            "limite": {"type": "integer", "description": "Nombre de produits (3 par défaut)."}}}}},
    {"type": "function", "function": {
        "name": "proposer_routine",
        "description": "Propose une routine complète (nettoyant, soin ciblé, hydratant, écran solaire) avec son prix total en FCFA.",
        "parameters": {"type": "object", "properties": {
            "problemes": _PROBLEMES, "type_peau": _TYPE, "budget_max_fcfa": _BUDGET}}}},
    {"type": "function", "function": {
        "name": "fiche_produit",
        "description": "Donne la fiche d'un produit précis du catalogue : prix, problèmes ciblés, types de peau, utilisation.",
        "parameters": {"type": "object", "properties": {
            "nom": {"type": "string", "description": "Nom du produit, ou une partie du nom."}},
            "required": ["nom"]}}},
]
