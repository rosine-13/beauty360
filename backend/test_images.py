"""
TEST : combien de nos produits ont une photo dans Open Beauty Facts ?
On teste 20 produits au hasard avant de décider d'aller plus loin.
Open Beauty Facts = base de données libre de cosmétiques (gratuite, sans clé).
"""
import json
import time
import urllib.parse
import urllib.request
import pandas as pd

df = pd.read_csv("../data/cosmetics_clean.csv")
echantillon = df.sample(20, random_state=1)   # 20 produits au hasard (toujours les mêmes)

trouves = 0
for _, p in echantillon.iterrows():
    # 1. Construire la recherche : "marque + nom du produit"
    parametres = urllib.parse.urlencode({
        "search_terms": f"{p.Brand} {p.Name}",
        "search_simple": 1, "action": "process", "json": 1, "page_size": 5,
        "fields": "product_name,brands,image_front_url",
    })
    url = "https://world.openbeautyfacts.org/cgi/search.pl?" + parametres
    requete = urllib.request.Request(url, headers={"User-Agent": "Beauty360/1.0 (projet etudiant)"})

    # 2. Interroger Open Beauty Facts
    try:
        data = json.load(urllib.request.urlopen(requete, timeout=20))
    except Exception as e:
        print("Erreur :", e)
        continue

    # 3. Garder une image seulement si la MARQUE correspond (évite les fausses photos)
    image = None
    premier_mot_marque = p.Brand.lower().split()[0]
    for resultat in data.get("products", []):
        if premier_mot_marque in (resultat.get("brands") or "").lower() and resultat.get("image_front_url"):
            image = resultat["image_front_url"]
            break

    trouves += image is not None
    print("✅" if image else "❌", p.Brand, "-", p.Name[:40], image or "")
    time.sleep(1)   # politesse : 1 demande par seconde maximum

print(f"\nImages trouvées : {trouves} / 20")