import os
from dotenv import load_dotenv

# Charge les variables du fichier .env
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '..', '.env')) # Cherche le .env à la racine

class Config:
    # On récupère les infos depuis le .env (avec une valeur de secours au cas où)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'cle_secrete_de_secours_locale'
    
    # Base de données
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'mes_marches.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    

    # Paramètres MCAT
    MOT_DE_PASSE_PAR_DEFAUT = os.environ.get('MOT_DE_PASSE_PAR_DEFAUT') or "Mcat@Temp2025"
    # --- LA NOUVELLE CLÉ SÉCURITÉ ---
    CLE_DE_VERROUILLAGE = os.environ.get('CLE_DE_VERROUILLAGE') or "1234"
