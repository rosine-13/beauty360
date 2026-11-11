import io
import json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from security import utilisateur_connecte
from problemes import PROBLEMES, code_depuis_classe

# ===== LE MOTEUR QUI FAIT TOURNER LE MODÈLE TFLITE =====
# Sur Render (Linux) : LiteRT, un petit moteur léger (pas besoin de TensorFlow).
# Sur ton PC Windows : LiteRT n'existe pas, on utilise celui de TensorFlow.
try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    import tensorflow as tf
    Interpreter = tf.lite.Interpreter

# ===== CHARGEMENT DU MODÈLE (une seule fois, au démarrage) =====
DOSSIER_MODELES = Path(__file__).resolve().parent.parent / "models"
interpreteur = Interpreter(model_path=str(DOSSIER_MODELES / "skin_problems.tflite"))
interpreteur.allocate_tensors()
ENTREE = interpreteur.get_input_details()[0]["index"]
SORTIE = interpreteur.get_output_details()[0]["index"]

# Le fichier JSON créé par le notebook 03 : ordre des classes, seuils, résultats du test
INFOS = json.loads((DOSSIER_MODELES / "skin_problems.json").read_text(encoding="utf-8"))
TAILLE = INFOS["taille_image"]
CLASSES = INFOS["classes"]                       # ex. ["Acne", "Blackheads", ...]
CODES = [code_depuis_classe(c) for c in CLASSES]  # ex. ["acne", "points_noirs", ...]
SEUILS = [INFOS["seuils"][c] for c in CLASSES]   # un seuil par problème (choisi sur VALID)

# FIABILITÉ : un problème est "fiable" si son F1 mesuré sur TEST est d'au moins 0,55.
# Les autres sont affichés "À vérifier" dans l'appli : l'utilisatrice confirme ou non.
F1_MINIMUM = 0.55
FIABLE = {code: INFOS["test"]["par_classe"][c]["f1"] >= F1_MINIMUM
          for c, code in zip(CLASSES, CODES) if code}

# ===== DÉTECTEUR DE VISAGE (YuNet, OpenCV) =====
# Mon modèle reconnaît des problèmes de peau, mais pas "est-ce un visage humain ?".
# Sans ce contrôle, une photo de chat donnait "peau sèche". YuNet vérifie d'abord
# qu'il y a un visage (de face, de profil ou en partie) sur la photo.
DETECTEUR_VISAGE = cv2.FaceDetectorYN.create(
    str(DOSSIER_MODELES / "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.6)


def contient_un_visage(contenu: bytes) -> bool:
    image = cv2.imdecode(np.frombuffer(contenu, np.uint8), cv2.IMREAD_COLOR)  # photo en tableau BGR
    if image is None:
        return False
    h, w = image.shape[:2]
    echelle = 640 / max(h, w)                                   # même taille pour toutes les photos
    image = cv2.resize(image, (int(w * echelle), int(h * echelle)))
    DETECTEUR_VISAGE.setInputSize((image.shape[1], image.shape[0]))
    _, visages = DETECTEUR_VISAGE.detect(image)
    return visages is not None and len(visages) > 0


router = APIRouter(prefix="/scan", tags=["Analyse de peau"])


def preparer_image(contenu: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(contenu)).convert("RGB")
    image = image.resize((TAILLE, TAILLE), Image.BILINEAR)
    tableau = np.array(image, dtype="float32")      # valeurs 0-255 : le modèle normalise lui-même
    return np.expand_dims(tableau, axis=0)


def predire(image: np.ndarray) -> np.ndarray:
    """Renvoie une probabilité (0 à 1) PAR problème (multi-label)."""
    interpreteur.set_tensor(ENTREE, image)
    interpreteur.invoke()
    return interpreteur.get_tensor(SORTIE)[0]


@router.post("")
async def analyser(photo: UploadFile = File(...),
                   user: models.User = Depends(utilisateur_connecte),
                   db: Session = Depends(get_db)):
    # 1. Lire et préparer la photo
    contenu = await photo.read()
    try:
        image = preparer_image(contenu)
    except Exception:
        raise HTTPException(status_code=400, detail="Image illisible, envoie une photo JPG ou PNG")

    # 1 bis. Y a-t-il un visage humain ? Sinon on n'analyse pas.
    if not contient_un_visage(contenu):
        raise HTTPException(status_code=400, detail="Aucun visage détecté. Prenez une photo de votre "
                                                    "visage, de face, à la lumière du jour.")

    # 2. Prédiction : une probabilité par problème
    probas = predire(image)
    scores = {code: round(float(p), 3) for code, p in zip(CODES, probas) if code}

    # 3. Un problème est "détecté" si sa probabilité dépasse SON seuil
    detectes = [code for code, p, s in zip(CODES, probas, SEUILS) if code and p >= s]
    detectes.sort(key=lambda c: scores[c], reverse=True)   # le plus probable d'abord

    # 4. Enregistrer l'analyse
    analyse = models.Analyse(user_id=user.id, problemes=",".join(detectes), scores=json.dumps(scores))
    db.add(analyse)
    db.commit()
    db.refresh(analyse)

    # 5. Répondre à Flutter
    return {
        "analyse_id": analyse.id,
        "problemes": [{"code": c, "libelle": PROBLEMES[c], "score": scores[c], "fiable": FIABLE[c]}
                      for c in detectes],
        "scores": scores,
    }


@router.get("/historique")
def historique(user: models.User = Depends(utilisateur_connecte), db: Session = Depends(get_db)):
    analyses = (db.query(models.Analyse)
                  .filter(models.Analyse.user_id == user.id)
                  .order_by(models.Analyse.date_analyse.desc())
                  .all())
    return [{"id": a.id,
             "problemes": [c for c in a.problemes.split(",") if c],
             "date": a.date_analyse.isoformat()} for a in analyses]


@router.get("/modele")
def infos_modele():
    """Les VRAIS résultats du modèle sur les photos de test (pour être transparent)."""
    return {"dataset": INFOS["dataset"], "modele": INFOS.get("modele"),
            "comparaison_valid": INFOS.get("comparaison_valid"), "test": INFOS["test"],
            "problemes": {c: PROBLEMES[c] for c in CODES if c}}
