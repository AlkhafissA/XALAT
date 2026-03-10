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
    
    # Email
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = 'alkhafissa98@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  # <--- SÉCURISÉ ICI !
    MAIL_DEFAULT_SENDER = MAIL_USERNAME

    # Paramètres MCAT
    MOT_DE_PASSE_PAR_DEFAUT = os.environ.get('MOT_DE_PASSE_PAR_DEFAUT') or "Mcat@Temp2025"
