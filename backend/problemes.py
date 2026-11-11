"""
LES PROBLÈMES DE PEAU que Beauty360 sait reconnaître.
Un seul endroit pour les noms : le scan, le catalogue et l'agent utilisent tous ce fichier.
"""
import re

# code interne -> texte affiché en français
PROBLEMES = {
    "acne": "Acné (boutons)",
    "points_noirs": "Points noirs",
    "points_blancs": "Points blancs",
    "taches": "Taches brunes",
    "pores": "Pores dilatés",
    "rougeurs": "Rougeurs",
    "peau_grasse": "Peau grasse / brillance",
    "peau_seche": "Peau sèche",
    "rides": "Rides",
    "poches": "Poches / cernes",
}

# Types de peau (choisis par l'utilisatrice dans le questionnaire)
TYPES_PEAU = {
    "grasse": "Grasse",
    "mixte": "Mixte",
    "normale": "Normale",
    "seche": "Sèche",
    "sensible": "Sensible",
}

# Nom de la classe dans le dataset Roboflow -> notre code
# (on enlève majuscules, tirets et espaces : "Dark-Spots" -> "darkspots")
_CLASSES_DATASET = {
    "acne": "acne",
    "blackheads": "points_noirs",
    "whiteheads": "points_blancs",
    "darkspots": "taches",
    "englargedpores": "pores",   # faute de frappe d'origine dans le dataset
    "enlargedpores": "pores",
    "pores": "pores",
    "skinredness": "rougeurs",
    "oilyskin": "peau_grasse",
    "dryskin": "peau_seche",
    "wrinkles": "rides",
    "eyebags": "poches",
}


def code_depuis_classe(nom_classe: str) -> str | None:
    """'Dark-Spots' -> 'taches'. Renvoie None si la classe est inconnue."""
    cle = re.sub(r"[^a-z]", "", nom_classe.lower())
    return _CLASSES_DATASET.get(cle)
