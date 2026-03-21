import os
from dotenv import load_dotenv

# 1. On définit le dossier de base (racine du projet)
basedir = os.path.abspath(os.path.dirname(__file__))

# 2. On charge le .env qui est au même niveau que ce fichier config.py
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    # On récupère les infos depuis le .env
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # 3. PRIORITÉ : On cherche DATABASE_URL dans le .env. 
    # Si c'est vide, ALORS on utilise SQLite.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'mes_marches.db')
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Paramètres MCAT
    MOT_DE_PASSE_PAR_DEFAUT = os.environ.get('MOT_DE_PASSE_PAR_DEFAUT') 
    CLE_DE_VERROUILLAGE = os.environ.get('CLE_DE_VERROUILLAGE')
