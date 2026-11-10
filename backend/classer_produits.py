"""
CLASSER LES PRODUITS AVEC L'IA (DeepSeek)
Les mots-clés font trop d'erreurs ("cream" attrape aussi les crèmes de douche...).
On demande donc à DeepSeek de lire le nom de chaque produit et de choisir sa catégorie,
ou de l'EXCLURE si ce n'est pas un soin du visage.
À lancer UNE SEULE FOIS, depuis le dossier backend :  python classer_produits.py
"""
import json
import os
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# 1. Connexion à DeepSeek (mêmes réglages que l'agent, lus dans .env)
load_dotenv()
client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_BASE_URL"))
MODELE = os.getenv("LLM_MODEL", "deepseek-flash")

# 2. Lire le catalogue téléchargé depuis Colab
df = pd.read_csv("../data/catalogue_amazon.csv")
df.insert(0, "id", df.index)        # numéro du produit = numéro de sa photo (0.jpg, 1.jpg...)

CATEGORIES = ["Cleanser", "Moisturizer", "Treatment", "Face Mask", "Eye cream", "Sun protect"]
CONSIGNE = """Tu classes des produits cosmétiques vendus sur Amazon.
Pour chaque produit, choisis UNE seule réponse :
- Cleanser : nettoyant pour le visage, gel/mousse/eau micellaire, démaquillant, gommage visage
- Moisturizer : crème, gel ou lotion hydratante pour le visage
- Treatment : sérum, tonique, essence, soin anti-imperfections pour le visage
- Face Mask : masque pour le visage
- Eye cream : soin du contour des yeux
- Sun protect : crème ou spray de protection solaire
- EXCLURE : tout le reste (maquillage, corps, mains, cheveux, cils, accessoires, lingettes,
  appareils, coffrets de maquillage, autobronzants, produits éclaircissants ou blanchissants,
  peelings très forts, produits médicaux).
Réponds uniquement en JSON, sous la forme {"numéro": "réponse", ...}."""

# 3. Envoyer les produits par paquets de 40 (moins d'appels, donc moins cher)
reponses = {}
for debut in range(0, len(df), 40):
    paquet = df.iloc[debut:debut + 40]
    liste = "\n".join(f"{p.id}: {p.Titre}" for p in paquet.itertuples())
    resultat = client.chat.completions.create(
        model=MODELE,
        messages=[{"role": "system", "content": CONSIGNE},
                  {"role": "user", "content": liste}],
        response_format={"type": "json_object"},     # on exige du JSON
    )
    reponses.update(json.loads(resultat.choices[0].message.content))
    print(f"{min(debut + 40, len(df))} / {len(df)} produits classés")

# 4. Ranger les réponses et garder uniquement les soins du visage
df["Label"] = df["id"].astype(str).map(reponses)
final = df[df["Label"].isin(CATEGORIES)].copy()

# 5. Petits nettoyages : nom propre, caractères mal encodés, marque manquante
final["Titre"] = final["Titre"].str.replace("â€“", "-", regex=False).str.replace("â€™", "'", regex=False)
final["Name"] = final["Titre"].str.split(r"[|,]").str[0].str.strip().str[:80]
final["Brand"] = final["Brand"].fillna("Inconnue")

# 6. Enregistrer dans un NOUVEAU fichier (on garde l'ancien intact)
final.to_csv("../data/catalogue_final.csv", index=False)
print("\nProduits gardés :", len(final), "sur", len(df))
print(final["Label"].value_counts())