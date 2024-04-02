# api pour gerer un sondage

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from pymongo import MongoClient
from bson import ObjectId
from typing import Optional
import secrets
import logging
import bcrypt

app = FastAPI()

uri = "mongodb+srv://maruis:maruis@quizapi.q1m3hy9.mongodb.net/?retryWrites=true&w=majority&appName=QUIZAPI"


API_KEY_NAME = "access_token"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)


# Créer une instance du client MongoDB
client = MongoClient(uri)

# Sélectionner la base de données
db = client["quizapi"]

# Créer une collection pour les sondages
surveys_collection = db["surveys"]
users_collection = db["users"]

# verifier l'api key
async def get_user(api_key_header: str = Depends(api_key_header)):
    user = users_collection.find_one({"api_key": api_key_header})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return user

# Définir le modèle de sondage
class Sondage(BaseModel):
    question: str
    oui_count: int = 0
    non_count: int = 0

class User(BaseModel):
    username: str
    email : str
    password: str



# Configurer le système de logging
logging.basicConfig(filename='api.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Créer un nouveau sondage
@app.post("/sondages/", dependencies=[Depends(get_user)])
async def creer_sondage(sondage: Sondage, user: dict = Depends(get_user)):
    logging.info(f"Utilisateur {user['username']} a créé un sondage avec la question : {sondage.question}")
    sondage_id = surveys_collection.insert_one({**sondage.dict(), "user_id": user["_id"]}).inserted_id
    return {"sondage_id": str(sondage_id)}



# Répondre à un sondage
@app.post("/sondages/{sondage_id}/repondre/")
async def repondre_sondage(sondage_id: str, reponse: str):
    logging.info(f"Réponse au sondage {sondage_id} : {reponse}")
    sondage = surveys_collection.find_one({"_id": ObjectId(sondage_id)})
    if sondage:
        if reponse.lower() == "oui":
            surveys_collection.update_one({"_id": ObjectId(sondage_id)}, {"$inc": {"oui_count": 1}})
            return {"message": "Réponse enregistrée"}
        elif reponse.lower() == "non":
            surveys_collection.update_one({"_id": ObjectId(sondage_id)}, {"$inc": {"non_count": 1}})
            return {"message": "Réponse enregistrée"}
        else:
            raise HTTPException(status_code=400, detail="Réponse invalide")
    else:
        raise HTTPException(status_code=404, detail="Sondage non trouvé")



# Obtenir les statistiques d'un sondage
@app.get("/sondages/{sondage_id}/statistiques/", dependencies=[Depends(get_user)])
async def obtenir_statistiques_sondage(sondage_id: str, user: dict = Depends(get_user)):
    logging.info(f"Utilisateur {user['username']} a consulté les statistiques du sondage {sondage_id}")
    sondage = surveys_collection.find_one({"_id": ObjectId(sondage_id)})
    if sondage and sondage["user_id"] == user["_id"]:
        total_reponses = sondage["oui_count"] + sondage["non_count"]
        if total_reponses > 0:
            pourcentage_oui = (sondage["oui_count"] / total_reponses) * 100
            pourcentage_non = (sondage["non_count"] / total_reponses) * 100
            return {"pourcentage_oui": pourcentage_oui, "pourcentage_non": pourcentage_non}
        else:
            raise HTTPException(status_code=404, detail="Pas de réponses encore")
    else:
        raise HTTPException(status_code=404, detail="Sondage non trouvé")



#supprimer le sondage
@app.delete("/sondages/{sondage_id}/", dependencies=[Depends(get_user)])
async def supprimer_sondage(sondage_id: str, user: dict = Depends(get_user)):
    logging.info(f"Utilisateur {user['username']} a supprimé le sondage {sondage_id}")
    deleted_sondage = surveys_collection.find_one_and_delete({"_id": ObjectId(sondage_id), "user_id": user["_id"]})
    if deleted_sondage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sondage not found",
        )
    return {"message": "Sondage supprimé"}



# Obtenir tous mes sondages
@app.get("/sondages/", dependencies=[Depends(get_user)])
async def obtenir_sondages(user: dict = Depends(get_user)):
    logging.info(f"Utilisateur {user['username']} a consulté la liste de ses sondages")
    sondages = []
    for sondage in surveys_collection.find({"user_id": user["_id"]}):
        sondage["_id"] = str(sondage["_id"])
        sondages.append(sondage)
    return sondages



# Obtenir un sondage par ID
@app.get("/sondages/{sondage_id}/", dependencies=[Depends(get_user)])
async def lire_sondage(sondage_id: str, user: dict = Depends(get_user)):
    logging.info(f"Utilisateur {user['username']} a consulté le sondage {sondage_id}")
    sondage = surveys_collection.find_one({"_id": ObjectId(sondage_id)})
    if sondage is None or sondage["user_id"] != user["_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sondage not found",
        )
    return sondage



# Mettre à jour un sondage
@app.put("/sondages/{sondage_id}/", dependencies=[Depends(get_user)])
async def mettre_a_jour_sondage(sondage_id: str, sondage: Sondage, user: dict = Depends(get_user)):
    logging.info(f"Utilisateur {user['username']} a mis à jour le sondage {sondage_id}")
    sondage = surveys_collection.find_one({"_id": ObjectId(sondage_id)})
    if sondage and sondage["user_id"] == user["_id"]:
        surveys_collection.update_one({"_id": ObjectId(sondage_id)}, {"$set": sondage.dict()})
        return {"message": "Sondage mis à jour"}
    else:
        raise HTTPException(status_code=404, detail="Sondage non trouvé")



# Supprimer tous mes sondages
@app.delete("/sondages/", dependencies=[Depends(get_user)])
async def supprimer_sondages(user: dict = Depends(get_user)):
    logging.info(f"Utilisateur {user['username']} a supprimé tous ses sondages")
    surveys_collection.delete_many({"user_id": user["_id"]})
    return {"message": "Tous les sondages de l'utilisateur ont été supprimés"}



# Créer un utilisateur
@app.post("/users/")
async def create_user(user: User):
    user_dict = user.dict()
    user_dict["api_key"]= secrets.token_urlsafe(16)  # Génère une clé API sécurisée
        
    # Vérifier si l'utilisateur existe déjà et l'email aussi
    if users_collection.find_one({"username": user_dict["username"]}):
        raise HTTPException(status_code=400, detail="Username déjà utilisé")
    elif users_collection.find_one({"email": user_dict["email"]}):
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    else:
        # crypter le mot de passe en utilisant bcrypt
        user_dict["password"] = bcrypt.hashpw(user_dict["password"].encode('utf-8'), bcrypt.gensalt())

        user_id = users_collection.insert_one(user_dict).inserted_id
    return {"api_key": user_dict["api_key"]}
