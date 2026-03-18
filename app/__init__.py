import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta
from flask import Flask, render_template
from flask_migrate import Migrate
from config import Config
from app.extensions import db, mail, login_manager
from flask_wtf.csrf import CSRFProtect
# 👇 NOUVEAU 2 : On crée l'objet CSRF (le bouclier)
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- CONFIGURATION SÉCURITÉ SESSION ---
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    # --------------------------------------

    # Initialisation
    db.init_app(app)
    migrate = Migrate(app, db, render_as_batch=True)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = "Votre session a expiré. Veuillez vous reconnecter."
    login_manager.login_message_category = "info"

    # 👇 NOUVEAU 3 : On attache le bouclier à ton application !
    csrf.init_app(app)

    # --- ÉTAPE 1 : CONFIGURATION DU FICHIER LOG ---
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # Fichier tournant : max 100 Ko par fichier, garde les 10 derniers
        file_handler = RotatingFileHandler('logs/mcat_errors.log', maxBytes=102400, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.info('Démarrage du système MCAT - Surveillance active')

    # Blueprint
    from app.routes import main as main_bp
    app.register_blueprint(main_bp)

    # --- ÉTAPE 2 : GESTIONNAIRES D'ERREURS ---
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback() # On annule les transactions BDD en cours
        return render_template('errors/500.html'), 500
    
    # --- NOUVEAU : GESTION DE L'ERREUR DE FICHIER TROP LOURD ---
    @app.errorhandler(413)
    def file_too_large(error):
        return render_template('errors/413.html'), 413
    
    # Création BDD
    with app.app_context():
        from app import models 
        db.create_all()
        
        # Admins par défaut
        from werkzeug.security import generate_password_hash
        if not models.User.query.filter_by(username='Admin').first():
            hashed = generate_password_hash('@dmin1900', method='pbkdf2:sha256')
            db.session.add(models.User(username='Admin', password_hash=hashed, role='admin'))
        
        if not models.User.query.filter_by(username='SuperAdmin').first():
            hashed = generate_password_hash('TAWHID2021!', method='pbkdf2:sha256')
            db.session.add(models.User(username='SuperAdmin', password_hash=hashed, role='superadmin'))
        
        db.session.commit()

    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return db.session.get(User, int(user_id))