# Convertit le modèle Keras (lourd) en TFLite (léger) pour l'hébergement
import numpy as np
import tensorflow as tf

# 1. Charger le modèle actuel
modele = tf.keras.models.load_model("../models/skin_model.keras")

# 2. Le convertir en TFLite
convertisseur = tf.lite.TFLiteConverter.from_keras_model(modele)
modele_tflite = convertisseur.convert()
with open("../models/skin_model.tflite", "wb") as f:
    f.write(modele_tflite)
print(f"Modèle TFLite créé : {len(modele_tflite) / 1e6:.1f} Mo")

# 3. Vérifier que les deux modèles donnent la MÊME réponse
image_test = np.random.rand(1, 224, 224, 3).astype("float32") * 255
reponse_keras = modele.predict(image_test, verbose=0)[0]

interpreteur = tf.lite.Interpreter(model_content=modele_tflite)
interpreteur.allocate_tensors()
entree = interpreteur.get_input_details()[0]
sortie = interpreteur.get_output_details()[0]
interpreteur.set_tensor(entree["index"], image_test)
interpreteur.invoke()
reponse_tflite = interpreteur.get_tensor(sortie["index"])[0]

print("Keras  :", np.round(reponse_keras, 3))
print("TFLite :", np.round(reponse_tflite, 3))