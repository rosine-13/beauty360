# Beauty360 — API

Application qui analyse une photo du visage, détecte les **problèmes de peau** (acné, points noirs, taches brunes…) et propose une **routine de soins vendus en Côte d'Ivoire, avec les prix en FCFA**, adaptée au climat chaud et humide.

Projet de fin de formation Développeur Data & IA — Simplon Côte d'Ivoire.

## Ce que fait l'API

| Route | Rôle |
|---|---|
| `POST /auth/register`, `POST /auth/login` | Créer un compte, se connecter (token JWT) |
| `POST /scan` | Analyser une photo : renvoie les problèmes détectés et leurs probabilités |
| `GET /scan/historique` | Les analyses de l'utilisatrice |
| `GET /scan/modele` | Les vrais résultats du modèle sur les photos de test |
| `GET /products` | Produits classés selon les problèmes, le type de peau, la catégorie, le budget |
| `GET /products/routine` | Routine en 4 étapes (nettoyant, soin ciblé, hydratant, écran solaire) + total FCFA |
| `GET /products/{id}/image` | Photo du produit (téléchargée une fois depuis Jumia, puis gardée en cache) |
| `POST /agent` | Assistante IA (DeepSeek) qui utilise les outils de l'API |

## Les données

**Photos de peau (modèle)** — dataset « skincare » sur Roboflow Universe, version 7, licence **CC BY 4.0** :
https://universe.roboflow.com/skincare-gxqjb/skincare-8dmzr
2 350 photos réelles, découpées en 1 788 train / 318 valid / 244 test. Classification **multi-label** (une photo peut avoir plusieurs problèmes) : acné, points noirs, points blancs, taches brunes, pores dilatés, rougeurs, peau grasse, peau sèche, rides, poches.

**Catalogue** — `data/catalogue_ci.csv` : 63 soins du visage vendus sur Jumia Côte d'Ivoire, prix en FCFA relevés le 11/11/2026. Chaque ligne garde le lien vers la page du produit (`url_source`). Les problèmes ciblés reprennent ce qu'annonce la marque. Les produits éclaircissants ont été exclus volontairement.

## Le modèle

`notebooks/03_modele_problemes.ipynb` (à lancer dans Google Colab, GPU) :
- transfer learning **EfficientNetB0** (ImageNet) + une sortie sigmoïde par problème ;
- augmentation (retournement, rotation, luminosité, contraste) ;
- un seuil de décision par problème, choisi sur VALID (meilleur F1) ;
- évaluation finale sur TEST (précision, rappel, F1, AUC par problème) ;
- export **TFLite** (quantification dynamique) pour un hébergement léger.

Fichiers produits dans `models/` : `skin_problems.tflite` et `skin_problems.json` (classes, seuils, résultats du test).

## Lancer en local

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

Fichier `backend/.env` (jamais sur GitHub) :
```
LLM_API_KEY=...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=...
```

## Limites (à dire honnêtement)

- L'analyse est **indicative** : ce n'est pas un diagnostic médical.
- La diversité des teintes de peau du dataset n'est pas documentée : le modèle doit être testé sur des peaux noires et métissées avant d'en tirer des conclusions.
- Les prix changent : ils sont datés et viennent d'un seul site.
- Certains problèmes (poches, rides) ont peu de produits dans le catalogue.
