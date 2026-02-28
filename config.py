import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = 'votre_cle_secrete_pro'
    
    # Base de données (stockée dans le dossier 'instance' à la racine)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'mes_marches.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = 'alkhafissa98@gmail.com'
    MAIL_PASSWORD = 'qpav frnh adxx djsl' 
    MAIL_DEFAULT_SENDER = MAIL_USERNAME

    # Paramètres MCAT
    MOT_DE_PASSE_PAR_DEFAUT = "Mcat@Temp2025"
