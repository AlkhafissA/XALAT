import os
import zipfile
from datetime import datetime
import shutil

# --- CONFIGURATION (À vérifier selon le PC/Serveur) ---
# Chemin absolu vers le projet (là où se trouve run.py)
CHEMIN_PROJET = os.path.dirname(os.path.abspath(__file__))

# Les éléments précieux à sauvegarder
CHEMIN_BDD = os.path.join(CHEMIN_PROJET, 'mes_marches.db')
CHEMIN_UPLOADS = os.path.join(CHEMIN_PROJET, 'app', 'static', 'uploads')

# Le dossier où le robot va ranger les fichiers ZIP (en dehors de l'app si possible, mais ici on le met dans un dossier 'backups_automatiques')
DOSSIER_BACKUPS = os.path.join(CHEMIN_PROJET, 'backups_automatiques')

# Nombre de backups à conserver (pour ne pas remplir le disque dur)
MAX_BACKUPS_A_GARDER = 7 

def faire_le_backup():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Démarrage du robot de sauvegarde...")
    
    # 1. Créations du dossier des backups s'il n'existe pas
    if not os.path.exists(DOSSIER_BACKUPS):
        os.makedirs(DOSSIER_BACKUPS)
        
    # 2. Préparation du nom du fichier ZIP
    date_str = datetime.now().strftime('%Y-%m-%d_%Hh%M')
    nom_zip = f"AUTO_MCAT_Backup_{date_str}.zip"
    chemin_zip = os.path.join(DOSSIER_BACKUPS, nom_zip)
    
    # 3. Création du fichier ZIP
    try:
        with zipfile.ZipFile(chemin_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            # On Ajouter la base de données
            if os.path.exists(CHEMIN_BDD):
                zf.write(CHEMIN_BDD, os.path.basename(CHEMIN_BDD))
                print(" -> Base de données ajoutée.")
            else:
                print(" /!\\ AVERTISSEMENT : Base de données introuvable !")
                
            # On Ajouter les PDF (dossier uploads)
            if os.path.exists(CHEMIN_UPLOADS):
                for root, dirs, files in os.walk(CHEMIN_UPLOADS):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, start=os.path.dirname(CHEMIN_UPLOADS))
                        zf.write(file_path, os.path.join('uploads', arcname))
                print(" -> Dossier uploads ajouté.")
            else:
                print(" /!\\ AVERTISSEMENT : Dossier uploads introuvable !")
                
        print(f" -> Succès ! Backup créé : {nom_zip}")
        
    except Exception as e:
        print(f" [ERREUR CRITIQUE] Le backup a échoué : {e}")
        return

    # 4. Nettoyage : suppression des vieux backups pour faire de la place
    nettoyer_vieux_backups()

def nettoyer_vieux_backups():
    # Liste tous les fichiers zip dans le dossier, triés par date de modification (du plus vieux au plus récent)
    fichiers = [os.path.join(DOSSIER_BACKUPS, f) for f in os.listdir(DOSSIER_BACKUPS) if f.endswith('.zip')]
    fichiers.sort(key=os.path.getmtime)
    
    # Si on a plus de fichiers que notre limite (ex: 7)
    while len(fichiers) > MAX_BACKUPS_A_GARDER:
        vieux_fichier = fichiers.pop(0) # Prend le plus vieux
        os.remove(vieux_fichier)
        print(f" -> Ancien backup supprimé (Nettoyage) : {os.path.basename(vieux_fichier)}")
        
if __name__ == "__main__":
    faire_le_backup()
