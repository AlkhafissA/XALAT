from flask_migrate import Migrate
from flask import Flask
from config import Config
from app.extensions import db, mail, login_manager

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialisation
    db.init_app(app)
    migrate = Migrate(app, db, render_as_batch=True)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    # Blueprint
    from app.routes import main as main_bp
    app.register_blueprint(main_bp)

    # Création BDD
    with app.app_context():
        from app import models 
        db.create_all()
        
        # Admins par défaut
        if not models.User.query.filter_by(username='Admin').first():
            from werkzeug.security import generate_password_hash
            hashed = generate_password_hash('@dmin1900', method='pbkdf2:sha256')
            db.session.add(models.User(username='Admin', password_hash=hashed, role='admin'))
        
        if not models.User.query.filter_by(username='SuperAdmin').first():
            from werkzeug.security import generate_password_hash
            hashed = generate_password_hash('TAWHID2021!', method='pbkdf2:sha256')
            db.session.add(models.User(username='SuperAdmin', password_hash=hashed, role='superadmin'))
        
        db.session.commit()

    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return db.session.get(User, int(user_id))
