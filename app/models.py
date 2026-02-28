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
    cible = db.Column(db.String(100))
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

class Offre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cotation_id = db.Column(db.Integer, db.ForeignKey('cotation.id'), nullable=False)
    nom_candidat = db.Column(db.String(100))
    montant = db.Column(db.Integer)

class Bordereau(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    direction_name = db.Column(db.String(100))
    numero = db.Column(db.String(50))
    service_ref = db.Column(db.String(50))
    date_signature = db.Column(db.Date)
    observations = db.Column(db.String(200))
    # On stocke la liste des dossiers sous forme de texte (JSON)
    dossiers_data = db.Column(db.Text) 

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


class ProcesVerbal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_drp = db.Column(db.String(100)) # Ex: S_DAGE_373
    objet = db.Column(db.Text)
    entreprise = db.Column(db.String(200)) # L'entreprise déclarée moins disante
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    form_data = db.Column(db.Text) # Pour stocker toutes les infos du formulaire en JSON
