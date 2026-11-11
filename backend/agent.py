"""
L'AGENT Beauty360 : la route /agent qui discute avec DeepSeek
et exécute les outils (derniere_analyse, rechercher_produits, proposer_routine, fiche_produit) quand il les demande.
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
from agent_tools import OUTILS, derniere_analyse, rechercher_produits, proposer_routine, fiche_produit

# ===== 1. CONNEXION À DEEPSEEK (réglages lus dans le fichier .env) =====
load_dotenv()
client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_BASE_URL"))
MODELE = os.getenv("LLM_MODEL", "deepseek-flash")

# ===== 2. LES CONSIGNES DE L'AGENT (son "rôle") =====
CONSIGNES = """Tu es l'assistante beauté de l'application Beauty360, pour des femmes et des hommes
qui vivent en Côte d'Ivoire (Abidjan et le reste du pays).
Règles :
- Réponds en français, de façon chaleureuse et concise (5 phrases maximum, sauf si on te demande plus).
- N'utilise pas de Markdown (pas d'astérisques ni de #). Pour une liste, commence chaque ligne par un tiret.
- Pour connaître les problèmes de peau de l'utilisatrice, utilise l'outil derniere_analyse.
- Pour conseiller des produits, utilise TOUJOURS rechercher_produits ou proposer_routine.
  Ne cite jamais un produit qui ne vient pas de ces outils. Les prix sont en FCFA, relevés sur
  Jumia Côte d'Ivoire : dis que ce sont des prix indicatifs qui peuvent changer.
- Si l'utilisatrice donne un budget, passe-le dans budget_max_fcfa.
- Tes conseils tiennent compte du climat ivoirien : chaud et humide toute l'année, soleil fort,
  et l'harmattan (vent sec, environ de décembre à février) qui assèche la peau.
  Donc : textures légères et non grasses, écran solaire chaque jour (il aide aussi à éviter
  que les marques d'acné deviennent des taches brunes), nettoyer la peau après la transpiration.
  Ne parle jamais d'hiver, de neige ou de froid.
- Ne recommande jamais de produits éclaircissants ou blanchissants (hydroquinone, corticoïdes,
  mercure) : ils sont dangereux pour la peau. Si on t'en parle, explique-le avec douceur.
- Tu ne fais aucun diagnostic médical. L'analyse photo est indicative. En cas d'acné sévère
  (gros boutons douloureux, cicatrices), d'irritation, d'allergie ou de problème qui dure,
  conseille de consulter un dermatologue.
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
    try:
        if nom == "derniere_analyse":
            return derniere_analyse(db, user.id)
        if nom == "rechercher_produits":
            return rechercher_produits(**arguments)
        if nom == "proposer_routine":
            return proposer_routine(**arguments)
        if nom == "fiche_produit":
            return fiche_produit(**arguments)
    except TypeError:
        return {"erreur": "Arguments invalides pour l'outil " + nom}
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