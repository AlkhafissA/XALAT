from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    # On récupère une variable d'environnement, sinon on met False par défaut
    # Cela permet d'éviter d'oublier de changer le code manuellement
    production_mode = os.environ.get('FLASK_ENV') == 'production'
    
    # En production : debug=False
    # En développement : debug=True
    app.run(
        debug=not production_mode, 
        host='0.0.0.0', 
        port=5002
    )