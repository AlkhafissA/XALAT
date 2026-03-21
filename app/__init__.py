import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta
from flask import Flask, render_template
from flask_migrate import Migrate
from config import Config
from app.extensions import db, mail, login_manager
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- CONFIGURATION SÉCURITÉ SESSION ---
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = True  # ✅ NOUVEAU : HTTPS only (production)
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # ✅ NOUVEAU : CSRF protection
    # Désactiver en développement local si vous utilisez HTTP
    if os.environ.get('FLASK_ENV') == 'production':
        app.config['SESSION_COOKIE_SECURE'] = True
    # --------------------------------------

    # Initialisation
    db.init_app(app)
    migrate = Migrate(app, db, render_as_batch=True)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = "Votre session a expiré. Veuillez vous reconnecter."
    login_manager.login_message_category = "info"

    csrf.init_app(app)

    # --- ÉTAPE 1 : CONFIGURATION DU FICHIER LOG ---
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
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
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(413)
    def file_too_large(error):
        return render_template('errors/413.html'), 413
    
    # Création BDD
    with app.app_context():
        from app import models 
        db.create_all()
        
        from werkzeug.security import generate_password_hash
        
        # --- 🛡️ RÉCUPÉRATION OBLIGATOIRE DEPUIS LE .ENV ---
        # Les mots de passe par défaut DOIVENT être définis en variables d'environnement
        # S'ils manquent, l'application refuse de démarrer
        admin_pass = os.environ.get('ADMIN_DEFAULT_PASSWORD')
        superadmin_pass = os.environ.get('SUPERADMIN_DEFAULT_PASSWORD')
        
        # ✅ VALIDATION CRITIQUE : Forcer les variables d'environnement
        if not admin_pass or not superadmin_pass:
            raise ValueError(
                "ERREUR CRITIQUE : Les variables d'environnement ADMIN_DEFAULT_PASSWORD "
                "et SUPERADMIN_DEFAULT_PASSWORD doivent être définies dans le fichier .env"
            )

        # Création du compte Admin si absent
        if not models.User.query.filter_by(username='Admin').first():
            hashed_admin = generate_password_hash(admin_pass, method='pbkdf2:sha256')
            db.session.add(models.User(username='Admin', password_hash=hashed_admin, role='admin'))
        
        # Création du compte SuperAdmin si absent
        if not models.User.query.filter_by(username='SuperAdmin').first():
            hashed_super = generate_password_hash(superadmin_pass, method='pbkdf2:sha256')
            db.session.add(models.User(username='SuperAdmin', password_hash=hashed_super, role='superadmin'))
        
        db.session.commit()
    # -----------------------------------------------

    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return db.session.get(User, int(user_id))