"""
Les OUTILS de l'agent Beauty360.
Ce sont des fonctions Python normales. DeepSeek ne peut pas les exécuter lui-même :
il DEMANDE à les utiliser, et c'est notre API qui les exécute puis lui renvoie le résultat.
"""
from sqlalchemy.orm import Session
import models
from products import recommander, df, TYPES   # on réutilise le catalogue déjà chargé


# ===== OUTIL 1 : le dernier scan de l'utilisatrice =====
def dernier_scan(db: Session, user_id: int) -> dict:
    scan = (db.query(models.Scan)
              .filter(models.Scan.user_id == user_id)
              .order_by(models.Scan.date_scan.desc())
              .first())
    if scan is None:
        return {"trouve": False, "message": "Aucun scan de peau pour le moment."}
    return {
        "trouve": True,
        "type_peau": scan.type_peau,
        "confiance": round(scan.confiance, 2),
        "date": scan.date_scan.strftime("%d/%m/%Y"),
    }


# ===== OUTIL 2 : chercher des produits dans le catalogue =====
def rechercher_produits(type_peau: str, sensible: bool = False,
                        categorie: str | None = None, limite: int = 3):
    try:
        produits = recommander(type_peau=type_peau, sensible=sensible,
                               categorie=categorie, limite=limite)
    except Exception:
        return {"erreur": "Type de peau inconnu."}
    for p in produits:
        p.pop("ingredients", None)   # trop long : on ne l'envoie pas à l'agent
    return produits


# ===== OUTIL 3 : la fiche détaillée d'un produit précis =====
def fiche_produit(nom: str) -> dict:
    trouves = df[df["Name"].str.contains(nom, case=False, regex=False)]
    if trouves.empty:
        return {"trouve": False, "message": "Produit introuvable dans le catalogue."}
    p = trouves.sort_values("score", ascending=False).iloc[0]   # le plus pertinent
    ingredients = [i.strip() for i in str(p["Ingredients"]).split(",") if i.strip()]
    return {
        "trouve": True,
        "nom": p["Name"],
        "marque": p["Brand"],
        "categorie": p["Label"],
        "prix_usd": int(p["Price"]),
        "note": float(p["Rank"]),
        "types_de_peau": [col for col in TYPES.values() if p[col] == 1],
        "premiers_ingredients": ingredients[:15],   # les 15 premiers = les plus concentrés
    }


# ===== LA "NOTICE" DES OUTILS POUR DEEPSEEK =====
# DeepSeek lit ces descriptions pour savoir QUAND et COMMENT utiliser chaque outil.
OUTILS = [
    {
        "type": "function",
        "function": {
            "name": "dernier_scan",
            "description": "Donne le type de peau détecté lors du dernier scan de l'utilisatrice.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rechercher_produits",
            "description": "Cherche des produits de soin adaptés dans le catalogue Beauty360.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type_peau": {
                        "type": "string",
                        "enum": ["dry", "normal", "oily", "combination", "sensitive"],
                        "description": "Type de peau en anglais.",
                    },
                    "sensible": {"type": "boolean", "description": "True si la peau est sensible."},
                    "categorie": {
                        "type": "string",
                        "enum": ["Moisturizer", "Cleanser", "Face Mask",
                                 "Treatment", "Eye cream", "Sun protect"],
                        "description": "Catégorie de produit (facultatif).",
                    },
                    "limite": {"type": "integer", "description": "Nombre de produits (3 par défaut)."},
                },
                "required": ["type_peau"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fiche_produit",
            "description": "Donne la fiche d'un produit précis du catalogue : prix, note, "
                           "types de peau et principaux ingrédients.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Nom du produit, ou une partie du nom."},
                },
                "required": ["nom"],
            },
        },
    },
]