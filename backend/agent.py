"""
L'AGENT Beauty360 : la route /agent qui discute avec DeepSeek
et exécute les outils (dernier_scan, rechercher_produits) quand il les demande.
"""
import json
import os
from typing import Literal
from dotenv import load_dotenv
from openai import OpenAI
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
import models
from security import utilisateur_connecte
from agent_tools import OUTILS, dernier_scan, rechercher_produits, fiche_produit

# ===== 1. CONNEXION À DEEPSEEK (réglages lus dans le fichier .env) =====
load_dotenv()
client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_BASE_URL"))
MODELE = os.getenv("LLM_MODEL", "deepseek-flash")

# ===== 2. LES CONSIGNES DE L'AGENT (son "rôle") =====
CONSIGNES = """Tu es l'assistante beauté de l'application Beauty360.
Règles :
- Réponds en français, de façon chaleureuse et concise (5 phrases maximum, sauf si on te demande plus).
- N'utilise pas de Markdown (pas d'astérisques ni de #). Pour une liste, commence chaque ligne par un tiret.
- Pour connaître le type de peau de l'utilisatrice, utilise l'outil dernier_scan.
- Pour conseiller des produits, utilise TOUJOURS l'outil rechercher_produits.
  Ne cite jamais un produit qui ne vient pas de cet outil. Les prix sont en dollars US.
- Pour parler d'un produit précis (sa composition, à qui il convient), utilise l'outil fiche_produit.
  Les ingrédients sont listés du plus concentré au moins concentré. Explique simplement
  le rôle des ingrédients connus, sans promettre de résultat.
- Tu ne fais aucun diagnostic médical. En cas d'irritation, de douleur, d'allergie
  ou de problème persistant, conseille de consulter un dermatologue.
- Si la question n'a rien à voir avec la beauté ou la peau, ramène poliment la conversation au sujet."""

# ===== 3. FORME DES DONNÉES ENVOYÉES PAR FLUTTER =====
class Message(BaseModel):
    role: Literal["user", "assistant"]   # qui parle : l'utilisatrice ou l'assistante
    content: str

class Conversation(BaseModel):
    messages: list[Message]               # toute la discussion, du plus ancien au plus récent

router = APIRouter(prefix="/agent", tags=["Assistant IA"])


# ===== 4. EXÉCUTER UN OUTIL DEMANDÉ PAR DEEPSEEK =====
def executer_outil(nom: str, arguments: dict, db: Session, user: models.User):
    if nom == "dernier_scan":
        return dernier_scan(db, user.id)
    if nom == "rechercher_produits":
        return rechercher_produits(**arguments)
    if nom == "fiche_produit":
        return fiche_produit(**arguments)
    return {"erreur": f"Outil inconnu : {nom}"}


# ===== 5. LA ROUTE /agent : la boucle de l'agent =====
@router.post("")
def discuter(conv: Conversation,
             user: models.User = Depends(utilisateur_connecte),
             db: Session = Depends(get_db)):
    prenom = user.nom.split()[0]
    messages = [{"role": "system", "content": CONSIGNES + f"\nL'utilisatrice s'appelle {prenom}."}]
    messages += [m.model_dump() for m in conv.messages[-10:]]   # les 10 derniers messages

    for _ in range(5):   # 5 tours maximum, pour ne jamais tourner en rond
        # a) On envoie la conversation + la notice des outils à DeepSeek
        try:
            reponse = client.chat.completions.create(model=MODELE, messages=messages, tools=OUTILS)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Assistant indisponible : {e}")
        msg = reponse.choices[0].message

        # b) Pas d'outil demandé -> c'est la réponse finale
        if not msg.tool_calls:
            return {"reponse": msg.content}

        # c) DeepSeek demande un ou plusieurs outils -> on les exécute
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [{"id": a.id, "type": "function",
                            "function": {"name": a.function.name, "arguments": a.function.arguments}}
                           for a in msg.tool_calls],
        })
        for appel in msg.tool_calls:
            arguments = json.loads(appel.function.arguments or "{}")
            resultat = executer_outil(appel.function.name, arguments, db, user)
            # d) On renvoie le résultat de l'outil à DeepSeek, qui continue de réfléchir
            messages.append({"role": "tool", "tool_call_id": appel.id,
                             "content": json.dumps(resultat, ensure_ascii=False)})

    return {"reponse": "Désolée, je n'ai pas réussi à répondre. Peux-tu reformuler ta question ?"}