import io
from pathlib import Path
import numpy as np
from PIL import Image
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from security import utilisateur_connecte

# ===== LE MOTEUR QUI FAIT TOURNER LE MODÈLE TFLITE =====
# Sur Render (Linux) : LiteRT, un petit moteur léger (pas besoin de TensorFlow).
# Sur ton PC Windows : LiteRT n'existe pas, on utilise celui de TensorFlow.
# Les deux s'utilisent EXACTEMENT de la même façon.
try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    import tensorflow as tf
    Interpreter = tf.lite.Interpreter

# Chargement du modèle UNE SEULE FOIS, au démarrage
CHEMIN_MODELE = Path(__file__).resolve().parent.parent / "models" / "skin_model.tflite"
interpreteur = Interpreter(model_path=str(CHEMIN_MODELE))
interpreteur.allocate_tensors()                              # réserve la mémoire du modèle
ENTREE = interpreteur.get_input_details()[0]["index"]        # où on met la photo
SORTIE = interpreteur.get_output_details()[0]["index"]       # où on lit la réponse

CLASSES = ["dry", "normal", "oily"]          # même ordre qu'à l'entraînement
SEUIL_FIABLE = 0.60

router = APIRouter(prefix="/scan", tags=["Scan de peau"])


def preparer_image(contenu: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(contenu)).convert("RGB")       # couleurs RGB
    image = image.resize((224, 224), Image.BILINEAR)               # même taille qu'à l'entraînement
    tableau = np.array(image, dtype="float32")                     # image -> tableau de nombres
    return np.expand_dims(tableau, axis=0)                          # un paquet d'une seule photo


def predire(image: np.ndarray) -> np.ndarray:
    """Donne la photo au modèle et renvoie les 3 probabilités."""
    interpreteur.set_tensor(ENTREE, image)   # 1. on pose la photo à l'entrée
    interpreteur.invoke()                    # 2. le modèle calcule
    return interpreteur.get_tensor(SORTIE)[0]  # 3. on lit la réponse


@router.post("")
async def scanner(photo: UploadFile = File(...),
                  user: models.User = Depends(utilisateur_connecte),
                  db: Session = Depends(get_db)):
    # 1. Lire et préparer la photo
    contenu = await photo.read()
    try:
        image = preparer_image(contenu)
    except Exception:
        raise HTTPException(status_code=400, detail="Image illisible, envoie une photo JPG ou PNG")

    # 2. Prédiction (avec le modèle TFLite)
    probas = predire(image)
    i = int(np.argmax(probas))
    type_peau, confiance = CLASSES[i], float(probas[i])

    # 3. Enregistrer le scan
    scan = models.Scan(user_id=user.id, type_peau=type_peau, confiance=confiance)
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # 4. Répondre à Flutter
    return {
        "scan_id": scan.id,
        "type_peau": type_peau,
        "confiance": round(confiance, 3),
        "probabilites": {c: round(float(p), 3) for c, p in zip(CLASSES, probas)},
        "fiable": confiance >= SEUIL_FIABLE,
    }


@router.get("/historique")
def historique(user: models.User = Depends(utilisateur_connecte), db: Session = Depends(get_db)):
    scans = (db.query(models.Scan)
               .filter(models.Scan.user_id == user.id)
               .order_by(models.Scan.date_scan.desc())
               .all())
    return [{"id": s.id, "type_peau": s.type_peau, "confiance": round(s.confiance, 3),
             "date": s.date_scan.isoformat()} for s in scans]