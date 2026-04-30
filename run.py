from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    # 🛡️ RAPPEL SÉCURITÉ : Ce fichier est parfait pour un ordinateur en local.
    # Mais en production (sur un vrai serveur), on n'utilise JAMAIS app.run().
    # On utilisera un vrai serveur industriel comme Gunicorn.
    
    # On regarde si on a activé le mode debug dans le fichier .env
    # (On gère les cas où on écrit "True", "true", ou "1")
    est_en_debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    
    # Lancement du serveur d'entraînement local
    app.run(
        debug=est_en_debug, 
        host='0.0.0.0', 
        port=5002
    )