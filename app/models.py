import json
from datetime import datetime
from flask_login import UserMixin
from app.extensions import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String(200))
    role = db.Column(db.String(20), default='admin')

class Historique(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    utilisateur = db.Column(db.String(100))
    action = db.Column(db.String(200))
    # On utilise db.Text pour accepter une longueur illimitée de caractères
    cible = db.Column(db.Text) 
    date_action = db.Column(db.DateTime, default=datetime.utcnow)

class Candidat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_entreprise = db.Column(db.String(100), nullable=False)
    adresse = db.Column(db.String(200))
    ville = db.Column(db.String(100))
    ninea = db.Column(db.String(50))
    position = db.Column(db.String(100))
    nom_proprietaire = db.Column(db.String(100))
    genre = db.Column(db.String(20))
    email = db.Column(db.String(120), nullable=False)
    telephone = db.Column(db.String(20))
    statut = db.Column(db.String(50), default="En attente")
    date_enregistrement = db.Column(db.DateTime, default=datetime.utcnow)
    
    ref_interne = db.Column(db.String(100))        
    date_signature_agrement = db.Column(db.String(100)) 
    ref_lettre_candidat = db.Column(db.String(100))     
    titre_signataire = db.Column(db.String(150), default="Le Directeur") 
    rc = db.Column(db.String(100))               # <-- NOUVEAU
    compte_bancaire = db.Column(db.String(200))  # <-- NOUVEAU
    fichier_scanne = db.Column(db.String(255), nullable=True) # <-- AJOUTE CECI
    contrats = db.relationship('Contrat', backref='parent_candidat', cascade="all, delete-orphan")
class Cotation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    objet = db.Column(db.Text, nullable=False)
    
    # --- NOUVEAUX CHAMPS POUR LA LETTRE D'INFORMATION ---
    num_ordre_lettre = db.Column(db.String(50))
    ref_service_lettre = db.Column(db.String(100), default="MCAT/SG/DAGE/ms")
    immatriculation = db.Column(db.String(100))
    direction_beneficiaire = db.Column(db.String(200))
    direction_retrait_pv = db.Column(db.String(200))
    date_lettre = db.Column(db.DateTime, default=datetime.utcnow)
    signataire_titre = db.Column(db.String(100), default="Le Directeur")
    # ----------------------------------------------------

    lieu = db.Column(db.String(200))
    date_limite = db.Column(db.DateTime)
    date_ouverture = db.Column(db.DateTime)
    date_attribution = db.Column(db.DateTime)
    president = db.Column(db.String(100))
    membre1 = db.Column(db.String(100))
    membre2 = db.Column(db.String(100))
    offres = db.relationship('Offre', backref='cotation', lazy=True, cascade="all, delete-orphan")
    fichier_scanne = db.Column(db.String(255), nullable=True) # <-- AJOUTE CECI

class Offre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cotation_id = db.Column(db.Integer, db.ForeignKey('cotation.id'), nullable=False)
    nom_candidat = db.Column(db.String(100))
    montant = db.Column(db.Integer)
    fichier_scanne = db.Column(db.String(255), nullable=True) # <-- AJOUTE CECI

class Bordereau(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    direction_name = db.Column(db.String(100))
    numero = db.Column(db.String(50))
    service_ref = db.Column(db.String(50))
    date_signature = db.Column(db.Date)
    observations = db.Column(db.String(200))
    # On stocke la liste des dossiers sous forme de texte (JSON)
    dossiers_data = db.Column(db.Text) 
    fichier_scanne = db.Column(db.String(255), nullable=True) # <-- AJOUTE CECI

    def get_dossiers(self):
        # Petite fonction pour récupérer la liste propre
        if self.dossiers_data:
            return json.loads(self.dossiers_data)
        return []
        

class LettreNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    immatriculation = db.Column(db.String(100))
    objet_marche = db.Column(db.Text)
    entreprise = db.Column(db.String(200)) # L'entreprise gagnante
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Ce champ va stocker TOUTES les données du formulaire sous forme de texte (JSON)
    # pour pouvoir régénérer le PDF exactement pareil plus tard.
    form_data = db.Column(db.Text)
    fichier_scanne = db.Column(db.String(255), nullable=True) # <-- AJOUTE CECI


class ProcesVerbal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_drp = db.Column(db.String(100)) # Ex: S_DAGE_373
    objet = db.Column(db.Text)
    entreprise = db.Column(db.String(200)) # L'entreprise déclarée moins disante
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    form_data = db.Column(db.Text) # Pour stocker toutes les infos du formulaire en JSON
    fichier_scanne = db.Column(db.String(255), nullable=True) # <-- AJOUTE CECI


class LettreInvitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    immatriculation = db.Column(db.String(100)) # Ex: S_DAGE_483
    objet_marche = db.Column(db.Text)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Ce champ va stocker TOUTES les données du formulaire sous forme de texte (JSON)
    # Y compris la liste des prestataires choisis, les heures de dépôt, etc.
    form_data = db.Column(db.Text)
    fichier_scanne = db.Column(db.String(255), nullable=True) # <-- AJOUTE CECI


class Contrat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # LIAISON AVEC LA TABLE CANDIDAT
    candidat_id = db.Column(db.Integer, db.ForeignKey('candidat.id'), nullable=False)
    

    # INFORMATIONS DU MARCHÉ
    objet_marche = db.Column(db.Text, nullable=False)
    gestion_annee = db.Column(db.String(10), default="2025")
    montant_chiffres = db.Column(db.String(50))
    montant_lettres = db.Column(db.Text)
    
    # INFORMATIONS BUDGÉTAIRES
    financement = db.Column(db.String(200), default="Budget de Fonctionnement")
    imputation = db.Column(db.Text)
    programme = db.Column(db.String(50))
    comptable_assignataire = db.Column(db.String(200), default="Payeur Général du Trésor (PGT)")
    
    # INFOS DE L'ENTREPRISE (au moment de la signature)
    rc_candidat = db.Column(db.String(100))
    compte_bancaire = db.Column(db.String(200))
    
    numero = db.Column(db.String(50), nullable=True)
    ref_service = db.Column(db.String(100), nullable=True)
    date_lettre = db.Column(db.String(50), nullable=True)
    
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    fichier_scanne = db.Column(db.String(255), nullable=True) # <-- AJOUTE CECI
    immatriculation = db.Column(db.String(100)) # <-- AJOUT POUR L'ARCHIVAGE


class LettreInformation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    immatriculation = db.Column(db.String(100))
    objet_marche = db.Column(db.Text)
    form_data = db.Column(db.Text) # On va y stocker tout le JSON (dates, prestataires, etc.)
    fichier_scanne = db.Column(db.String(255), nullable=True) # <-- AJOUTE CECI
    

class ArchiveDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(100), nullable=False) # Ex: S_DAGE_198
    type_document = db.Column(db.String(50), nullable=False) # Ex: 'Bordereau', 'Lettre Invitation', 'Contrat'
    nom_fichier = db.Column(db.String(255), nullable=False) # Le nom du PDF sauvegardé
    date_ajout = db.Column(db.DateTime, default=datetime.utcnow) # Date d'upload

class LoginAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, unique=True)
    attempts = db.Column(db.Integer, default=0)
    last_attempt = db.Column(db.DateTime, default=datetime.utcnow)
    is_blocked = db.Column(db.Boolean, default=False)


# journal d'audit plus fin que 'Historique' : on y enregistre
# les connexions, blocages automatiques, honeypot, etc.
class LogAction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

