import os
import zipfile
import json
import uuid
from functools import wraps
import filetype  # 🛡️ NOUVEAU : Pour lire l'ADN des fichiers
from werkzeug.utils import secure_filename
from flask import send_file, make_response, abort
from flask import send_from_directory, abort
from datetime import datetime, timedelta
import io
from app.models import ArchiveDocument
from app.models import Bordereau 
from app.models import LettreNotification, LettreInvitation, Contrat, LettreInformation, LogAction
from app.models import Candidat, LettreNotification, ProcesVerbal
from app.utils import generer_pdf_bordereau, generer_pdf_contrat
from app.utils import generer_pdf_pv_attribution
from io import BytesIO
from num2words import num2words
from datetime import datetime
from app.utils import generer_pdf_bordereau
import pandas as pd
from openpyxl.utils import get_column_letter
from fpdf import FPDF

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app, jsonify, session
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db, mail
from app.models import User, Candidat, Cotation, Offre, Historique, LoginAttempt, LogAction
from app.utils import clean_text, generer_lettre_agrement, num2words_fr, dessiner_entete_officiel

# Création du "Blueprint"
main = Blueprint('main', __name__)

def role_requis(*roles_autorises):
    """
    Décorateur moderne (RBAC) : Bloque l'accès si l'utilisateur n'a pas le bon rôle.
    Utilisation : @role_requis('superadmin', 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Si l'utilisateur n'est pas dans la liste des rôles autorisés
            if current_user.role not in roles_autorises:
                flash("Accès refusé : Votre niveau d'habilitation est insuffisant pour cette action.", "danger")
                # On le renvoie à l'accueil
                return redirect(url_for('main.tableau_de_bord'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator




# ==========================================================
# 🛡️ OUTILS DE SÉCURITÉ ET D'HISTORIQUE
# ==========================================================

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}

def fichier_est_autorise(filename):
    """ 1ère couche : Vérifie si l'extension est autorisée """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def contenu_fichier_est_securise(file_stream):
    """ 2ème couche : Vérifie la vraie signature (Magic Bytes) à l'intérieur du fichier """
    header = file_stream.read(2048)
    file_stream.seek(0) # IMPORTANT : remet le curseur à zéro
    
    kind = filetype.guess(header)
    if kind is None:
        return False
        
    mimes_autorises = [
        'application/pdf', 
        'image/png', 
        'image/jpeg',
        'application/msword', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]
    
    return kind.mime in mimes_autorises

def log_action(action, cible):
    """ Enregistre les actions dans la base de données (Historique) """
    try:
        user_name = current_user.username if current_user.is_authenticated else "Système"
        nouveau_log = Historique(utilisateur=user_name, action=action, cible=cible)
        db.session.add(nouveau_log)
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"ERREUR SÉCURITÉ - Impossible d'enregistrer le log ({action}) : {str(e)}")

# ==========================================================
# ==========================================================

# --- ROUTES AUTHENTIFICATION ---

@main.route('/', methods=['GET', 'POST'])
@main.route('/login', methods=['GET', 'POST'])
def login():
    # 1. Si déjà connecté, on redirige vers le bon tableau de bord
    if current_user.is_authenticated:
        if current_user.role == 'superadmin':
            return redirect(url_for('main.super_dashboard'))
        return redirect(url_for('main.tableau_de_bord'))

    # 🛡️ SÉCURITÉ : Récupère la vraie IP même si l'application est derrière un proxy
    # S'il y a plusieurs IP (séparées par des virgules), la première est la vraie IP du client.
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        user_ip = forwarded_for.split(',')[0].strip()
    else:
        user_ip = request.remote_addr 
    record = LoginAttempt.query.filter_by(ip_address=user_ip).first()
    
    # 2. VÉRIFICATION DU BLOCAGE (Applicable à TOUT LE MONDE, pas d'immunité)
    if record and record.is_blocked:
        if datetime.utcnow() - record.last_attempt > timedelta(minutes=15):
            # Déblocage auto après 15 minutes
            record.is_blocked = False
            record.attempts = 0
            db.session.commit()
        else:
            flash("Trop de tentatives échouées. Veuillez réessayer dans 15 minutes.", "danger")
            return render_template('login.html')

    if request.method == 'POST':
        # --- 3. PIÈGE POT DE MIEL (Sécurisé contre le DoS) ---
        honeypot = request.form.get('confirm_email_address')
        if honeypot:
            # C'est un bot ! On simule un échec SANS bloquer l'IP pour éviter de bannir des innocents
            log_action("ALERTE_HONEYPOT", f"Tentative de bot ignorée depuis l'IP {user_ip}")
            flash("Identifiant ou mot de passe incorrect.", "danger")
            return render_template('login.html')

        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        # --- 4. CAS : SUCCÈS DE CONNEXION ---
        if user and check_password_hash(user.password_hash, password):
            # On efface l'historique d'échecs de cette IP
            if record:
                db.session.delete(record)
                db.session.commit()
            
            login_user(user)
            
            # Active la limite de temps de session (Point 11 de l'audit)
            session.permanent = True  
            
            log_action("Connexion réussie", f"Utilisateur {user.username}")
            
            # Redirection selon le rôle
            if user.role == 'superadmin':
                return redirect(url_for('main.super_dashboard'))
            return redirect(url_for('main.tableau_de_bord'))

        # --- 5. CAS : ÉCHEC DE CONNEXION ---
        else:
            if not record:
                record = LoginAttempt(ip_address=user_ip, attempts=1, last_attempt=datetime.utcnow())
                db.session.add(record)
            else:
                record.attempts += 1
                record.last_attempt = datetime.utcnow()

            # On bloque à 5 tentatives (MÊME si c'est le compte admin !)
            if record.attempts >= 5:
                record.is_blocked = True
                log_action("ALERTE_SECURITE", f"IP {user_ip} BANNIE temporairement (Cible: {username})")
                flash("Compte temporairement bloqué suite à 5 échecs. Attendez 15 minutes.", "danger")
            else:
                flash(f"Identifiant ou mot de passe incorrect ({record.attempts}/5).", "danger")
            
            db.session.commit()
                
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/tableau_de_bord')
@login_required
def tableau_de_bord():
    liste = Candidat.query.order_by(Candidat.date_enregistrement.desc()).all()
    return render_template('dashboard.html', candidats=liste)

# --- ROUTES CANDIDATS ---

@main.route('/ajouter')
@login_required
@role_requis('superadmin', 'admin', 'agent') # 🛡️ Le Stagiaire est bloqué ici
def afficher_formulaire():
    return render_template('ajouter.html')

@main.route('/sauvegarder', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin', 'agent') # 🛡️ Le Stagiaire est bloqué ici
def sauvegarder():
    nouveau = Candidat(
        nom_entreprise=request.form.get('nom_entreprise'),
        adresse=request.form.get('adresse'),
        ville=request.form.get('ville'),
        ninea=request.form.get('ninea'),
        position=request.form.get('position'),
        nom_proprietaire=request.form.get('nom_proprietaire'),
        genre=request.form.get('genre'),
        email=request.form.get('email'),
        telephone=request.form.get('telephone')
    )
    db.session.add(nouveau)
    log_action("Ajout Nouveau Candidat", nouveau.nom_entreprise)
    db.session.commit()
    generer_lettre_agrement(nouveau, mode='vierge')
    return redirect(url_for('main.tableau_de_bord'))

@main.route('/telecharger_agrement_vierge/<int:id>')
@login_required
def telecharger_agrement_vierge(id):
    candidat = db.session.get(Candidat, id)
    # On génère le fichier (assure-toi que generer_lettre_agrement enregistre maintenant dans stockage_prive)
    nom_fichier_relatif = generer_lettre_agrement(candidat, mode='vierge')
    
    # On récupère juste le nom du fichier pour utiliser notre route sécurisée
    filename = os.path.basename(nom_fichier_relatif)
    return redirect(url_for('main.secure_download', folder='agreement', filename=filename))

@main.route('/telecharger_agrement_final/<int:id>')
@login_required
def telecharger_agrement_final(id):
    # Les flush=True sont là pour forcer l'affichage immédiat dans le terminal !
    print("\n--- 🛠️ DEBUG : TENTATIVE DE TELECHARGEMENT ---", flush=True)
    
    candidat = db.session.get(Candidat, id)
    
    # Sécurité anti-crash
    if not candidat:
        print("❌ ERREUR : Aucun candidat trouvé avec cet ID !", flush=True)
        flash("Candidat introuvable.", "danger")
        return redirect(url_for('main.tableau_de_bord'))
        
    print(f"Analyse du candidat en base -> Statut: '{candidat.statut}', Réf: '{candidat.ref_interne}'", flush=True)
    
    if candidat.statut == "Retenu" and candidat.ref_interne:
        print("✅ Conditions OK. Lancement du téléchargement.", flush=True)
        nom_fichier_relatif = generer_lettre_agrement(candidat, mode='final')
        filename = os.path.basename(nom_fichier_relatif)
        return redirect(url_for('main.secure_download', folder='agreement', filename=filename))
    else:
        print("❌ Conditions NON remplies. Pourquoi ?", flush=True)
        if candidat.statut != "Retenu":
            print(f"  -> Le statut est '{candidat.statut}' au lieu de 'Retenu'", flush=True)
        if not candidat.ref_interne:
            print(f"  -> La ref_interne est vide (None ou '')", flush=True)
        print("----------------------------------------------\n", flush=True)
        
        flash("Ce dossier n'est pas encore validé.", "danger")
        return redirect(url_for('main.tableau_de_bord'))
    
@main.route('/valider_agrement_final', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin') # 🛡️ SEULS LES CHEFS : L'Agent et le Stagiaire sont bloqués !
def valider_agrement_final():
    candidat_id = request.form.get('candidat_id')
    if not candidat_id: return redirect(url_for('main.tableau_de_bord'))
    
    candidat = db.session.get(Candidat, int(candidat_id))
    if candidat:
        # --- LA CORRECTION EST ICI ---
        # 1. On récupère les morceaux depuis le formulaire HTML
        ref_numero = request.form.get('ref_numero', '').strip()
        ref_suffixe = request.form.get('ref_suffixe', '').strip()
        
        # 2. On les assemble pour créer la référence interne
        if ref_numero:
            # Exemple: "0001" + " /SG/DAGE/ms" -> "0001 /SG/DAGE/ms"
            candidat.ref_interne = f"{ref_numero} {ref_suffixe}".strip()
            
        # 3. On récupère les autres champs de ton formulaire HTML
        candidat.titre_signataire = request.form.get('titre_signataire', 'Le Directeur')
        candidat.date_signature_agrement = request.form.get('date_signature')
        candidat.ref_lettre_candidat = request.form.get('ref_lettre_candidat')
        # -----------------------------

        # ... (début de ta fonction inchangé) ...
        candidat.statut = "Retenu"
        db.session.commit()
        
        # On génère le PDF final
        pdf_path_relatif = generer_lettre_agrement(candidat, mode='final')
        filename = os.path.basename(pdf_path_relatif)
        
        # --- NOUVEAU BLOC SANS L'EMAIL ---
        log_action("Validation Agrément", candidat.nom_entreprise)
        flash("Dossier validé et agrément généré avec succès !", "success")
            
    return redirect(url_for('main.tableau_de_bord'))

@main.route('/decision/<int:id>/<type_decision>', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin') 
def decision(id, type_decision):
    candidat = db.session.get(Candidat, id)
    if candidat and type_decision == 'refuser':
        candidat.statut = "Refusé"
        log_action("Refus Candidature", candidat.nom_entreprise)
        db.session.commit()
        flash(f"Le dossier de {candidat.nom_entreprise} a été refusé.", "warning")
    return redirect(url_for('main.tableau_de_bord'))

@main.route('/supprimer/<int:id>', methods=['POST']) # <-- AJOUTE methods=['POST']
@login_required
@role_requis('superadmin', 'admin') # 🛡️ SEULS LES CHEFS : Destruction de données interdite aux Agents/Stagiaires
def supprimer(id):
    candidat = db.session.get(Candidat, id)
    if candidat:
        log_action("Suppression Dossier", candidat.nom_entreprise)
        db.session.delete(candidat)
        db.session.commit()
    return redirect(url_for('main.tableau_de_bord'))

# --- ROUTES COTATIONS ---

@main.route('/cotations')
@login_required
def liste_cotations():
    liste = Cotation.query.order_by(Cotation.date_ouverture.desc()).all()
    return render_template('cotations_liste.html', cotations=liste)

@main.route('/nouvelle_cotation')
@login_required
@role_requis('superadmin', 'admin', 'agent') # 🛡️ Stagiaire bloqué (Lecture seule)
def nouvelle_cotation():
    candidats = Candidat.query.order_by(Candidat.nom_entreprise).all()
    return render_template('cotations_form.html', candidats=candidats, cotation=None)

@main.route('/modifier_cotation/<int:id>')
@login_required
@role_requis('superadmin', 'admin', 'agent')
def modifier_cotation(id):
    cotation = db.session.get(Cotation, id)
    # 🛡️ ROBUSTESSE : Si l'ID n'existe pas, on renvoie poliment l'utilisateur à la liste
    if not cotation:
        flash("Erreur : Ce dossier n'existe pas ou a été supprimé.", "danger")
        return redirect(url_for('main.liste_cotations'))
        
    candidats = Candidat.query.order_by(Candidat.nom_entreprise).all()
    return render_template('cotations_form.html', candidats=candidats, cotation=cotation)

@main.route('/sauvegarder_cotation', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin', 'agent')
def sauvegarder_cotation():
    cotation_id = request.form.get('cotation_id')
    def get_date(f): 
        val = request.form.get(f)
        return datetime.strptime(val, '%Y-%m-%dT%H:%M') if val else None

    if cotation_id:
        cotation = db.session.get(Cotation, int(cotation_id))
        cotation.objet = request.form.get('objet')
        cotation.lieu = request.form.get('lieu')
        cotation.president = request.form.get('president')
        cotation.membre1 = request.form.get('membre1')
        cotation.membre2 = request.form.get('membre2')
        cotation.date_limite = get_date('date_limite')
        cotation.date_ouverture = get_date('date_ouverture')
        cotation.date_attribution = get_date('date_attribution')
        for o in cotation.offres: db.session.delete(o)
    else:
        cotation = Cotation(
            objet=request.form.get('objet'), lieu=request.form.get('lieu'),
            president=request.form.get('president'), membre1=request.form.get('membre1'), membre2=request.form.get('membre2'),
            date_limite=get_date('date_limite'), date_ouverture=get_date('date_ouverture'), date_attribution=get_date('date_attribution')
        )
        db.session.add(cotation)
    
    # 🛠️ CORRECTION ICI : On utilise flush() au lieu de commit()
    # Cela simule l'enregistrement pour obtenir le cotation.id, 
    # mais garde la possibilité d'annuler si les montants sont faux !
    db.session.flush() 
    
    for i in range(1, 4):
        nom = request.form.get(f'candidat_{i}')
        mnt = request.form.get(f'montant_{i}')
        if nom and mnt:
            try:
                montant_securise = int(mnt)
                
                # 🚨 LA VÉRIFICATION SÉCURITÉ ABSOLUE
                if montant_securise >= 3000000:
                    db.session.rollback() # 🔄 Annule TOUT (même la création de la cotation)
                    flash(f"Alerte Sécurité : Le montant pour {nom} ({montant_securise} FCFA) dépasse le plafond autorisé de 3 Millions !", "danger")
                    return redirect(url_for('main.nouvelle_cotation'))
                
                db.session.add(Offre(cotation_id=cotation.id, nom_candidat=nom, montant=montant_securise))
            except ValueError:
                db.session.rollback() # 🔄 Annule tout en cas d'erreur de frappe (lettres)
                flash(f"Erreur : Le montant pour {nom} doit être un chiffre valide.", "danger")
                return redirect(request.url)
                
    action = "Modification Cotation" if cotation_id else "Création Cotation"
    log_action(action, cotation.objet)
    
    # 🛠️ TOUT EST VALIDE : On valide définitivement toute la transaction !
    db.session.commit() 
    
    return redirect(url_for('main.liste_cotations'))

@main.route('/supprimer_cotation/<int:id>', methods=['POST']) # <-- AJOUTE methods=['POST']
@login_required
@role_requis('superadmin', 'admin') # 🛡️ ACTION CRITIQUE : Seuls les chefs peuvent supprimer !
def supprimer_cotation(id):
    c = db.session.get(Cotation, id)
    if c: 
        # 👇 ON PLACE LE RADAR ICI 👇
        log_action("Suppression Cotation", c.objet)
        
        db.session.delete(c)
        db.session.commit()
        
    return redirect(url_for('main.liste_cotations'))

@main.route('/telecharger_pv/<int:id>')
@login_required
def telecharger_pv(id):
    cotation = db.session.get(Cotation, id)
    
    # 🛡️ ROBUSTESSE : On protège le téléchargement du PDF si l'ID est faux
    if not cotation:
        flash("Erreur : Ce dossier n'existe pas.", "danger")
        return redirect(url_for('main.liste_cotations'))
        
    offres = sorted(cotation.offres, key=lambda x: x.montant)
    gagnant = offres[0] if offres else None
    
    def fmt_date(dt): return dt.strftime('%d/%m/%Y à %Hh%M mn') if dt else "N/A"
    
    pdf = FPDF()
    
    def tableau_info(pdf_obj, titre_objet, date_reunion_str, is_attribution=False):
        pdf_obj.set_font("Arial", '', 10)
        
        def row(lbl, val, bold=False):
            x, y = pdf_obj.get_x(), pdf_obj.get_y()
            largeur_col2 = pdf_obj.epw - 70
            
            # 1. Dessine la colonne de gauche (largeur 70)
            pdf_obj.multi_cell(70, 8, txt=clean_text(lbl), border=1)
            h_gauche = pdf_obj.get_y() - y
            
            # 2. Se décale pour la colonne de droite
            pdf_obj.set_xy(x + 70, y)
            if bold: 
                pdf_obj.set_font("Arial", 'B', 10)
                
            # ⚠️ CORRECTION FPDF2 : On décale temporairement la marge gauche
            # pour éviter que le texte ne revienne s'écraser sur la colonne 1 !
            marge_gauche_originale = pdf_obj.l_margin
            pdf_obj.set_left_margin(x + 70)
            
            # 3. Dessine la colonne de droite
            pdf_obj.multi_cell(largeur_col2, 8, txt=clean_text(val), border=1)
            h_droite = pdf_obj.get_y() - y
            
            # 4. On restaure la marge et on se place sous la plus grande cellule
            pdf_obj.set_left_margin(marge_gauche_originale)
            pdf_obj.set_font("Arial", '', 10)
            
            hauteur_max = max(h_gauche, h_droite)
            pdf_obj.set_xy(x, y + hauteur_max)
                
        row("Désignation de l'AC", "MINISTERE DE LA CULTURE, DE L'ARTISANAT ET DU TOURISME")
        row("PRM :", "DIRECTION DE L'ADMINISTRATION GENERALE ET DE L'EQUIPEMENT")
        row("Objet de la COTATION :", clean_text(titre_objet).upper(), bold=True)
        row("Procédure :", "Demande de COTATION")
        if not is_attribution: row("Date et heure limite de dépôt :", fmt_date(cotation.date_limite), bold=True)
        row("Lieu de tenue de la séance :", clean_text(cotation.lieu), bold=True)
        row("Date et heure réunion :", date_reunion_str, bold=True)
    
    def commission(pdf_obj):
        pdf_obj.set_font("Arial", 'BU', 11); pdf_obj.cell(0, 8, "MEMBRES DE LA COMMISSION :", ln=1)
        pdf_obj.set_font("Arial", 'B', 10)
        pdf_obj.cell(50, 8, "Qualité", 1, 0, 'C')
        pdf_obj.cell(90, 8, "Noms et Prénoms", 1, 0, 'C')
        pdf_obj.cell(50, 8, "Signature", 1, 1, 'C')
        pdf_obj.set_font("Arial", '', 10)
        
        mbs = [("Président", cotation.president), ("Membre", cotation.membre1), ("Membre", cotation.membre2)]
        for q, n in mbs:
            pdf_obj.cell(50, 10, clean_text(q), 1, 0) # Ajout du 0 pour rester sur la ligne
            pdf_obj.set_font("Arial", 'B', 10)
            pdf_obj.cell(90, 10, clean_text(n), 1, 0) # pdf_obj au lieu de pdf
            pdf_obj.set_font("Arial", '', 10)
            pdf_obj.cell(50, 10, "", 1, 1) # Retour à la ligne (1)s

    pdf.add_page(); dessiner_entete_officiel(pdf, afficher_direction=True)
    pdf.set_y(55); pdf.set_font("Arial", 'BU', 12)
    titre1 = f"PROCES-VERBAL D'OUVERTURE DE LA DEMANDE DE\nCOTATION: {cotation.objet.upper()}"
    pdf.multi_cell(0, 6, clean_text(titre1), align='C'); pdf.ln(5)
    tableau_info(pdf, cotation.objet, fmt_date(cotation.date_ouverture), False)
    pdf.ln(5); commission(pdf); pdf.ln(5)
    pdf.set_font("Arial", 'BU', 11); pdf.cell(0, 8, clean_text("RESULTATS DE L'EXAMEN DES OFFRES :"), ln=1)
    
    pdf.set_font("Arial", 'B', 9); pdf.cell(15, 8, clean_text("N°"), 1, 0, 'C'); pdf.cell(100, 8, "Candidat", 1, 0, 'C'); pdf.cell(75, 8, "Montant", 1, 1, 'C'); pdf.set_font("Arial", '', 10)
    for i, off in enumerate(cotation.offres, 1):
        pdf.cell(15, 10, str(i), 1, 0, 'C'); pdf.set_font("Arial", 'B', 10)
        pdf.cell(100, 10, clean_text(off.nom_candidat), 1); pdf.set_font("Arial", '', 10)
        pdf.cell(75, 10, "{:,} F TTC".format(off.montant).replace(',', ' '), 1, 1, 'R')

    pdf.add_page(); dessiner_entete_officiel(pdf, afficher_direction=True)
    pdf.set_y(55); pdf.set_font("Arial", 'BU', 12)
    titre2 = f"PROCES-VERBAL D'ATTRIBUTION DE LA DEMANDE DE\nCOTATION: {cotation.objet.upper()}"
    pdf.multi_cell(0, 6, clean_text(titre2), align='C'); pdf.ln(5)
    tableau_info(pdf, cotation.objet, fmt_date(cotation.date_attribution), True)
    pdf.ln(5); commission(pdf); pdf.ln(5)

    pdf.set_font("Arial", 'BU', 11)
    pdf.cell(0, 8, clean_text("RÉSULTATS DE L'EXAMEN DES OFFRES"), 0, 1, 'L')
    
    pdf.set_font("Arial", 'BU', 9); pdf.cell(10, 8, clean_text("N°"), 1, 0, 'C'); pdf.cell(90, 8, "Candidat", 1, 0, 'C'); pdf.cell(60, 8, "Montant", 1, 0, 'C'); pdf.cell(30, 8, "RANG", 1, 1, 'C'); pdf.set_font("Arial", '', 10)
    for i, off in enumerate(offres, 1):
        pdf.cell(10, 10, str(i), 1, 0, 'C'); pdf.set_font("Arial", 'B', 10)
        pdf.cell(90, 10, clean_text(off.nom_candidat), 1); pdf.set_font("Arial", '', 10)
        pdf.cell(60, 10, "{:,} F TTC".format(off.montant).replace(',', ' '), 1, 0, 'R')
        pdf.cell(30, 10, f"{i}er" if i==1 else f"{i}eme", 1, 1, 'C')
    pdf.ln(5)
    
    if gagnant:
        mt_lettres = num2words(gagnant.montant, lang='fr').upper()
        mt_chiffres = "{:,}".format(gagnant.montant).replace(',', ' ')

        pdf.set_font("Arial", '', 11)
        pdf.write(6, "En conséquence, la commission propose de retenir "); pdf.set_font("Arial", 'B', 11)
        pdf.write(6, clean_text(gagnant.nom_candidat.upper())); pdf.set_font("Arial", '', 11)
        pdf.write(6, " dont l'offre est conforme et moins disante pour "); pdf.set_font("Arial", 'B', 11)
        pdf.write(6, clean_text(f"{mt_lettres} ({mt_chiffres}) F CFA TTC."))
    

    # 1. On génère le PDF en mémoire (RAM)
    try:
        pdf_bytes = bytes(pdf.output()) # Si tu utilises fpdf2
    except TypeError:
        pdf_bytes = pdf.output(dest='S').encode('latin1') # Si tu utilises l'ancien fpdf

    buffer = io.BytesIO(pdf_bytes)
    buffer.seek(0)
    
    # 2. On garde ton historique d'action
    log_action("Téléchargement PV Cotation", cotation.objet)
    db.session.commit()

    # 3. On envoie le fichier au navigateur
    return send_file(
        buffer, 
        as_attachment=True, 
        download_name=f"PV_Cotation_{cotation.id}.pdf",
        mimetype='application/pdf'
    )

# --- ADMIN ROUTES ---

@main.route('/exporter_excel')
@login_required
def exporter_excel():
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        
        candidats = Candidat.query.all()
        if candidats:
            data_candidats = [{
                'ID': c.id, 'Entreprise': c.nom_entreprise, 'NINEA': c.ninea, 'Ville': c.ville,
                'Contact': c.nom_proprietaire, 'Téléphone': c.telephone, 'Email': c.email,
                'Statut': c.statut, 'Réf Interne': c.ref_interne,
                'Date Enreg.': c.date_enregistrement.strftime('%d/%m/%Y') if c.date_enregistrement else ""
            } for c in candidats]
            pd.DataFrame(data_candidats).to_excel(writer, sheet_name='Candidats', index=False)
        
        cotations = Cotation.query.all()
        if cotations:
            data_cotations = [{
                'ID': cot.id, 'Objet': cot.objet, 'Lieu': cot.lieu,
                'Date Ouverture': cot.date_ouverture.strftime('%d/%m/%Y') if cot.date_ouverture else "",
                'Date Attribution': cot.date_attribution.strftime('%d/%m/%Y') if cot.date_attribution else "",
                'Nombre Offres': len(cot.offres)
            } for cot in cotations]
            pd.DataFrame(data_cotations).to_excel(writer, sheet_name='Cotations', index=False)

        offres = Offre.query.all()
        if offres:
            data_offres = [{
                'ID Offre': o.id, 'Marché (ID)': o.cotation_id, 'Candidat': o.nom_candidat, 'Montant (FCFA)': o.montant
            } for o in offres]
            pd.DataFrame(data_offres).to_excel(writer, sheet_name='Détails des Offres', index=False)

        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        if cell.value:
                            length = len(str(cell.value))
                            if length > max_length: max_length = length
                    except Exception as e:
                        current_app.logger.warning(f"Alerte Excel: Impossible de lire une cellule : {str(e)}")
                adjusted_width = (max_length + 2)
                if adjusted_width > 100: adjusted_width = 100
                worksheet.column_dimensions[column_letter].width = adjusted_width

    output.seek(0)
    date_jour = datetime.now().strftime('%Y-%m-%d')
    nom_fichier = f"Base_Donnees_MCAT_{date_jour}.xlsx"
    return send_file(output, download_name=nom_fichier, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@main.route('/sauvegarde_bdd')
@login_required
def sauvegarde_bdd():
    if current_user.role != 'superadmin': return redirect(url_for('main.tableau_de_bord'))
    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    return send_file(db_path, as_attachment=True)
@main.route('/telecharger_backup_complet')
@login_required
def telecharger_backup_complet():
    # Sécurité absolue : seul le superadmin passe
    if current_user.role != 'superadmin': 
        return redirect(url_for('main.tableau_de_bord'))

    

    # On prépare le fichier ZIP en mémoire
    memory_file = BytesIO()
    
    # On définit les chemins exacts d'après tes infos
    base_dir = os.path.abspath(os.path.dirname(current_app.root_path))
    db_path = os.path.join(base_dir, 'mes_marches.db')
    uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads')

    # On commence à remplir le ZIP
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. Ajout de la base de données
        if os.path.exists(db_path):
            zf.write(db_path, 'mes_marches.db')
        
        # 2. Ajout de TOUS les dossiers et fichiers PDF
        if os.path.exists(uploads_dir):
            for root, dirs, files in os.walk(uploads_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # On garde une belle structure de dossiers dans le ZIP
                    arcname = os.path.relpath(file_path, start=os.path.dirname(uploads_dir))
                    zf.write(file_path, os.path.join('uploads', arcname))
    
    memory_file.seek(0)
    
    # On génère un nom stylé avec la date et l'heure
    date_str = datetime.now().strftime('%Y-%m-%d_%Hh%M')
    zip_filename = f"MCAT_Backup_Complet_{date_str}.zip"
    
    # On enregistre l'action dans ton journal de surveillance
    log_action("Téléchargement Backup", "Base de données + Fichiers PDF")
    db.session.commit()
    
    # On envoie le fichier au Superadmin
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    )
@main.route('/admin/download-backup')
@login_required
def download_backup():
    if current_user.role != 'admin': return "Interdit", 403
    db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    return send_file(db_path, as_attachment=True, download_name='backup_mcat.db')

# N'oublie pas que tu dois avoir importé ou créé ta fonction role_requis en haut du fichier !

@main.route('/dashboard')
@login_required
@role_requis('superadmin') # 🛡️ On remplace le 'if' par le badge !
def super_dashboard():
    users = User.query.all()
    
    # 1. On récupère les logs de sécurité
    logs_securite = LogAction.query.all()
    liste_finale = []
    
    for s in logs_securite:
        liste_finale.append({
            'date_action': s.timestamp,
            'utilisateur': 'SYSTÈME / BOT',
            'action': s.action,
            'cible': s.details or 'N/A'
        })
    
    # 2. On récupère l'historique métier
    historique_metier = Historique.query.all()
    for h in historique_metier:
        liste_finale.append({
            'date_action': h.date_action,
            'utilisateur': h.utilisateur,
            'action': h.action,
            'cible': h.cible
        })
    
    # 3. On trie par date (du plus récent au plus ancien)
    liste_finale.sort(key=lambda x: x['date_action'] if x['date_action'] else datetime.min, reverse=True)
    
    ips_bloquees = LoginAttempt.query.filter_by(is_blocked=True).all()
    
    return render_template('super_dashboard.html', 
                           users=users, 
                           logs=liste_finale[:100], 
                           ips_bloquees=ips_bloquees)

@main.route('/creer_utilisateur', methods=['POST'])
@login_required
@role_requis('superadmin') # 🛡️ Seul le SuperAdmin peut créer des comptes
def creer_utilisateur():
    username = request.form.get('username')
    password = request.form.get('password')
    # 👇 NOUVEAU : On récupère le rôle depuis le formulaire HTML !
    role_choisi = request.form.get('role', 'agent') # Par défaut, on met 'agent' par sécurité
    
    # Sécurité : On s'assure que personne ne bidouille le formulaire pour créer un faux superadmin
    roles_valides = ['admin', 'agent', 'stagiaire']
    if role_choisi not in roles_valides:
        role_choisi = 'agent' 
        
    if User.query.filter_by(username=username).first():
        flash("Cet utilisateur existe déjà.", "warning")
    else:
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        # 👇 NOUVEAU : On applique le rôle choisi !
        new_user = User(username=username, password_hash=hashed_pw, role=role_choisi)
        db.session.add(new_user)
        log_action(f"Création Utilisateur ({role_choisi})", username)
        db.session.commit()
        flash(f"Utilisateur {username} créé avec succès en tant que {role_choisi.capitalize()}.", "success")
        
    return redirect(url_for('main.super_dashboard'))

@main.route('/supprimer_utilisateur/<int:id>', methods=['POST']) 
@login_required
@role_requis('superadmin') # 🛡️
def supprimer_utilisateur(id):
    user_to_delete = db.session.get(User, id)
    if user_to_delete:
        if user_to_delete.role == 'superadmin':
            flash("Impossible de supprimer le SuperAdmin !", "danger")
        else:
            log_action("Suppression Utilisateur", user_to_delete.username)
            db.session.delete(user_to_delete)
            db.session.commit()
            flash("Utilisateur supprimé.", "success")
            
    return redirect(url_for('main.super_dashboard'))

# 🛡️ SÉCURITÉ : Ajout de methods=['POST']
@main.route('/reset_password/<int:id>', methods=['POST'])
@login_required
@role_requis('superadmin') # 👈 Utilisation de ton décorateur !
def reset_password(id):
    user_to_reset = db.session.get(User, id)
    
    if user_to_reset:
        mdp_defaut = current_app.config['MOT_DE_PASSE_PAR_DEFAUT']
        user_to_reset.password_hash = generate_password_hash(mdp_defaut, method='pbkdf2:sha256')
        db.session.commit()
        log_action("Réinitialisation MDP", user_to_reset.username)
        flash(f"Mot de passe de {user_to_reset.username} réinitialisé à : {mdp_defaut}", "warning")
    else:
        flash("Utilisateur introuvable.", "danger")
        
    return redirect(url_for('main.super_dashboard'))

@main.route('/forcer-changement-mdp', methods=['GET', 'POST'])
@login_required
def forcer_changement_mdp():
    mdp_defaut = current_app.config['MOT_DE_PASSE_PAR_DEFAUT']
    if not check_password_hash(current_user.password_hash, mdp_defaut):
        return redirect(url_for('main.tableau_de_bord'))

    if request.method == 'POST':
        nouveau = request.form.get('new_password')
        confirmation = request.form.get('confirm_password')

        if nouveau != confirmation:
            flash("Les mots de passe ne correspondent pas.", "danger")
        elif nouveau == mdp_defaut:
            flash("Vous ne pouvez pas reprendre le mot de passe par défaut !", "danger")
        else:
            current_user.password_hash = generate_password_hash(nouveau)
            db.session.commit()
            flash("Mot de passe mis à jour avec succès !", "success")
            
            if current_user.role == 'superadmin':
                return redirect(url_for('main.super_dashboard'))
            else:
                return redirect(url_for('main.tableau_de_bord'))
    
    return render_template('change_password.html')

from flask import current_app, request, redirect, url_for, flash
from werkzeug.security import check_password_hash
from flask_login import current_user

@main.before_request
def verifier_mot_de_passe_temporaire():
    # On vérifie uniquement si l'utilisateur est connecté
    if current_user.is_authenticated:
        
        # Liste des pages qu'il a le droit de visiter avec le mot de passe par défaut
        # On inclut 'static' pour que le CSS et les images chargent bien
        pages_autorisees = ['main.forcer_changement_mdp', 'main.logout', 'static']
        
        # Si la page qu'il essaie de visiter n'est pas dans la liste autorisée
        if request.endpoint not in pages_autorisees:
            
           # 🛡️ SÉCURITÉ : On récupère le mot de passe par défaut directement depuis le fichier .env
            mdp_defaut = os.environ.get('MOT_DE_PASSE_PAR_DEFAUT')
            
            # On s'assure que la variable a bien été trouvée dans le .env pour éviter un crash
            if mdp_defaut:
                # On vérifie si son mot de passe actuel EST le mot de passe par défaut
                if check_password_hash(current_user.password_hash, mdp_defaut):
                    flash("Sécurité : Veuillez modifier votre mot de passe temporaire avant de continuer.", "warning")
                    # On le redirige de force !
                    return redirect(url_for('main.forcer_changement_mdp'))
            else:
                # Petit message d'alerte dans ta console de développeur si le .env est mal lu
                print("⚠️ Attention : MOT_DE_PASSE_PAR_DEFAUT est introuvable dans le fichier .env !")

# --- ROUTE POUR LA PAGE DRPS  ---
@main.route('/drps', methods=['GET', 'POST'])
@login_required
# On utilise une logique différente ici car la route fait les DEUX (affichage et génération POST)
def drps():
    if request.method == 'POST':
        # 🛡️ SÉCURITÉ : Le Stagiaire ne peut pas générer de documents via POST
        if current_user.role not in ['superadmin', 'admin', 'agent']:
            flash("Accès refusé : Vous n'avez pas l'autorisation de générer ces documents.", "danger")
            return redirect(url_for('main.drps'))

        # On récupère le type de document avec un seul nom de variable
        type_document = request.form.get('type_document')

        # ---------- LETTRE D'INFORMATION ----------
        if type_document == 'information':
            direction_name = request.form.get('direction_name')
            num_ordre = request.form.get('num_ordre', '')
            ref_service = request.form.get('ref_service', '')
            date_lettre = request.form.get('date_lettre', '')
            signataire = request.form.get('signataire', '')
            immatriculation = request.form.get('immatriculation')
            date_commission = request.form.get('date_commission')
            objet_marche = request.form.get('objet_marche')

            prestataires_ids = request.form.getlist('prestataires_ids')
            rcs_saisis = request.form.getlist('rc[]')

            prestataires = []
            from itertools import zip_longest
            for pid, rc_agent in zip_longest(prestataires_ids, rcs_saisis, fillvalue=""):
                if pid:
                    candidat = db.session.get(Candidat, int(pid))
                    if candidat:
                        adresse_db = candidat.adresse or ""
                        ville_db = candidat.ville or ""
                        ninea_db = candidat.ninea or "Néant"
                        tel_db = candidat.telephone or "Néant"
                        rc_final = rc_agent or "Non renseigné"

                        lieu = f"{adresse_db} {ville_db}".strip()
                        phrase_adresse_complete = f"{lieu}, RC : {rc_final}, NINEA : {ninea_db}, Tél : {tel_db} ;"

                        prestataires.append({
                            'nom': candidat.nom_entreprise,
                            'adresse': phrase_adresse_complete
                        })

            buffer = io.BytesIO()
            data = {
                'direction_name': direction_name,
                'num_ordre': num_ordre,
                'ref_service': ref_service,
                'date_lettre': date_lettre,
                'signataire': signataire,
                'immatriculation': immatriculation,
                'date_commission': date_commission,
                'objet_marche': objet_marche,
                'prestataires': prestataires
            }

            from app.utils import generer_pdf_lettre_information
            generer_pdf_lettre_information(buffer, data)
            buffer.seek(0)
            log_action("Génération Lettre Info", immatriculation)
            db.session.commit()
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"Lettre_Information_{immatriculation}.pdf",
                mimetype='application/pdf'
            )

        # ---------- PV D'ATTRIBUTION ----------
        elif type_document == 'pv_attribution':
            date_commission_raw = request.form.get('date_commission')
            mois_fr = ["", "janvier", "février", "mars", "avril", "mai", "juin",
                       "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
            try:
                dt = datetime.strptime(date_commission_raw, '%Y-%m-%d')
                date_commission_fr = f"{dt.day:02d} {mois_fr[dt.month]} {dt.year}"
            except Exception as e:
                current_app.logger.warning(f"Erreur de format de date ignorée : {str(e)}")
                date_commission_fr = date_commission_raw

            prestataire_id = request.form.get('prestataire_id_pv')
            entreprise_nom = "ENTREPRISE NON RENSEIGNÉE"
            if prestataire_id:
                candidat = db.session.get(Candidat, int(prestataire_id))
                if candidat:
                    entreprise_nom = candidat.nom_entreprise

            data = {
                'ref_service': request.form.get('ref_service'),
                'num_ordre': request.form.get('num_ordre', '............'),
                'date_lettre': request.form.get('date_lettre'),
                'signataire': request.form.get('signataire', 'Le Directeur,'),
                'signataire_bas': request.form.get('signataire_bas', ''),
                'direction_name': request.form.get('direction_name'),
                'adresse_direction': request.form.get('adresse_direction', 'route des Almadies, Dakar'),
                'immatriculation': request.form.get('immatriculation'),
                'objet_marche': request.form.get('objet_marche'),
                'date_commission': date_commission_fr,
                'entreprise_attributaire': entreprise_nom
            }

            buffer = io.BytesIO()
            from app.utils import generer_pdf_pv_attribution
            generer_pdf_pv_attribution(buffer, data)
            buffer.seek(0)
            return send_file(
                buffer,
                as_attachment=True,
                download_name=f"PV_Attribution_{data['immatriculation']}.pdf",
                mimetype='application/pdf'
            )

        # ---------- NOTIFICATION ---------- 
        elif type_document == 'notification':
            # déléguer à la fonction existante
            return ajouter_notification()

    # =========================================================
    # Affichage normal de la page (quand on clique sur l'onglet) -> TOUT LE MONDE PEUT VOIR
    # =========================================================
    
    candidats = Candidat.query.order_by(Candidat.nom_entreprise).all()
    lettres_db = LettreInvitation.query.order_by(LettreInvitation.id.desc()).all()
    
    print(f"\n\n==== DIAGNOSTIC ==== j'ai trouvé {len(lettres_db)} lettres d'invitation dans la base !\n\n")
    
    lettres_pour_tableau = []
    for lettre in lettres_db:
        data = json.loads(lettre.form_data) if lettre.form_data else {}
        lettres_pour_tableau.append({
            'id': lettre.id,
            'immatriculation': lettre.immatriculation,
            'objet_marche': lettre.objet_marche,
            'num_ordre': data.get('num_ordre', 'N/A'),
            'date_heure_limite': data.get('date_heure_limite', 'Non défini')
        })

    return render_template('drps.html', candidats=candidats, lettres=lettres_pour_tableau)

# ==========================================
# --- ROUTES : BORDEREAUX D'ENVOI ---
# ==========================================

@main.route('/bordereaux')
@login_required
# Pas de blocage : Tout le monde peut voir la liste
def liste_bordereaux():
    bordereaux = Bordereau.query.order_by(Bordereau.id.desc()).all()
    return render_template('liste_bordereaux.html', bordereaux=bordereaux)

@main.route('/bordereaux/ajouter', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin', 'agent') # 🛡️ Stagiaire bloqué
def ajouter_bordereau():
    import json
    from datetime import datetime
    
    direction_name = request.form.get('direction_name')
    numero = request.form.get('numero')
    service_ref = request.form.get('service_ref')
    date_str = request.form.get('date_signature')
    observations = request.form.get('observations')
    # ✅ 1. ON RÉCUPÈRE LE DESTINATAIRE ICI
    destinataire = request.form.get('destinataire')
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        date_obj = datetime.now().date()

    liste_objets = request.form.getlist('objets[]')
    liste_refs = request.form.getlist('references[]')
    
    dossiers_list = []
    for i in range(len(liste_objets)):
        dossiers_list.append({
            'objet': liste_objets[i],
            'ref': liste_refs[i]
        })
    
    nouveau_bordereau = Bordereau(
        direction_name=direction_name,
        numero=numero,
        service_ref=service_ref,
        date_signature=date_obj,
        observations=observations,
        destinataire=destinataire, # 🔥 L'OUBLI ÉTAIT ICI : on le met dans la base !
        dossiers_data=json.dumps(dossiers_list)
    )
    
    db.session.add(nouveau_bordereau)
    log_action("Ajout Bordereau", f"N° {numero}")
    db.session.commit()
    
    flash("Bordereau enregistré avec succès !", "success")
    return redirect(url_for('main.liste_bordereaux'))

@main.route('/bordereaux/pdf/<int:id>')
@login_required
# Pas de blocage : Tout le monde peut télécharger
def download_bordereau_pdf(id):
    bordereau = Bordereau.query.get_or_404(id)
    buffer = io.BytesIO()
    
    data = {
        'direction': bordereau.direction_name.upper() if bordereau.direction_name else "DIRECTION...",
        'numero': bordereau.numero,
        'service_ref': bordereau.service_ref,
        'date': bordereau.date_signature.strftime("%d/%m/%Y"),
        'dossiers': bordereau.get_dossiers(),
        # 🔥 C'EST CETTE LIGNE QUI CHANGE TOUT ! ON LIT LA BASE DE DONNÉES :
        'destinataire': bordereau.destinataire if bordereau.destinataire else 'Monsieur le Coordonnateur de la Cellule de Passation des Marchés Publics',
        'observations': bordereau.observations
    }
    
    from app.utils import generer_pdf_bordereau
    generer_pdf_bordereau(buffer, data)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Bordereau_N{bordereau.numero}.pdf",
        mimetype='application/pdf'
    )

@main.route('/bordereaux/voir_scan/<int:id>')
@login_required
# Pas de blocage : Tout le monde peut voir
def voir_scan_bordereau(id):
    bordereau = Bordereau.query.get_or_404(id)
    if bordereau.fichier_scanne:
        return redirect(url_for('main.secure_download', folder='scans', filename=bordereau.fichier_scanne))
    else:
        flash("Aucun fichier scanné n'a été uploadé pour ce bordereau.", "warning")
        return redirect(url_for('main.liste_bordereaux'))

@main.route('/bordereaux/supprimer/<int:id>', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin') # 🛡️ ACTION CRITIQUE : Seuls les chefs peuvent supprimer !
def supprimer_bordereau(id):
    bordereau = Bordereau.query.get_or_404(id)
    
    if bordereau.fichier_scanne:
        basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        chemin_fichier = os.path.join(basedir, 'stockage_prive', 'scans', bordereau.fichier_scanne)
        if os.path.exists(chemin_fichier):
            os.remove(chemin_fichier)
            
    log_action("Suppression Bordereau", f"N° {bordereau.numero}")
    db.session.delete(bordereau)
    db.session.commit()
    
    flash('Bordereau et ses fichiers associés supprimés.', 'success')
    return redirect(url_for('main.liste_bordereaux'))




# NOUVEAU : La route attend maintenant le numéro du bordereau ET l'immatriculation
@main.route('/api/get_infos_bordereau')
@login_required
def get_infos_bordereau():
    # 1. On récupère les informations envoyées par le JavaScript de manière sécurisée
    numero_bordereau = request.args.get('bordereau', '').strip()
    immatriculation = request.args.get('immat', '').strip()
    
    tous_les_bordereaux = Bordereau.query.all()
    
    for bordereau in tous_les_bordereaux:
        # 2. On compare en nettoyant les espaces superflus avec .strip()
        if str(bordereau.numero).strip() == numero_bordereau:
            dossiers = bordereau.get_dossiers() 
            
            for dossier in dossiers:
                # 3. Dans votre HTML, vous aviez appelé ça "immatriculation" et "label"
                ref_dossier = str(dossier.get('immatriculation', '') or dossier.get('ref', '')).strip()
                
                if ref_dossier == immatriculation:
                    # BINGO ! On récupère le texte ("label" ou "objet")
                    texte_objet = dossier.get('label', '') or dossier.get('objet', '')
                    
                    return jsonify({
                        "success": True,
                        "objet": texte_objet,
                        "numero_bordereau": bordereau.numero,
                        "service_ref": bordereau.service_ref, 
                        "direction_name": bordereau.direction_name 
                    })
                
    # Si on parcourt tout sans rien trouver :
    return jsonify({"success": False, "message": "Dossier non trouvé"})


@main.route('/api/get_adresse/<int:id>')
@login_required
def get_adresse(id):
    candidat = db.session.get(Candidat, id)
    if candidat:
        return jsonify({'adresse': candidat.adresse})
    return jsonify({'adresse': ''}), 404

# ==========================================
# --- ROUTES : LETTRES DE NOTIFICATION ---
# ==========================================

@main.route('/notifications')
@login_required
def liste_notifications():
    notifications = LettreNotification.query.order_by(LettreNotification.id.desc()).all()
    candidats = Candidat.query.order_by(Candidat.nom_entreprise).all()
    
    # --- NOUVEAU : On prépare la liste des Lettres d'Invitation pour le menu déroulant ---
    invitations_brutes = LettreInvitation.query.order_by(LettreInvitation.id.desc()).all()
    lettres_invitation = []
    
    for inv in invitations_brutes:
        if inv.form_data:
            try:
                data = json.loads(inv.form_data)
                # On récupère le num_ordre (Réf) depuis le JSON
                num_ordre = data.get('num_ordre', 'Sans Réf')
                lettres_invitation.append({
                    'immatriculation': inv.immatriculation,
                    'num_ordre': num_ordre,
                    'objet': inv.objet_marche
                })
            except:
                pass

    return render_template('liste_notifications.html', 
                           notifications=notifications, 
                           candidats=candidats, 
                           lettres_invitation=lettres_invitation) # On envoie la liste au HTML

@main.route('/api/get_infos_invitation')
@login_required
def get_infos_invitation():
    immatriculation = request.args.get('immat', '').strip()
    
    if not immatriculation:
        return jsonify({"success": False, "message": "Immatriculation vide."})

    lettre = LettreInvitation.query.filter_by(immatriculation=immatriculation).first()
    
    if lettre and lettre.form_data:
        try:
            data = json.loads(lettre.form_data)
            
            # --- CORRECTION : NETTOYAGE DE LA DIRECTION ---
            nom_direction = data.get('direction_nom') or data.get('direction_name') or data.get('nom_direction') or data.get('direction') or data.get('direction_beneficiaire') or data.get('direction_retrait_pv')
        
            if isinstance(nom_direction, str):
                nom_direction = nom_direction.strip() # Retire les espaces fantômes
                
            if not nom_direction:
                nom_direction = "La Direction de l'Administration Générale et de l'Equipement"
            # -----------------------------------------------
            
            # --- CORRECTION : NETTOYAGE DES PRESTATAIRES ---
            prestataires_bruts = data.get('prestataires', [])
            prestataires_propres = []
            
            for p in prestataires_bruts:
                nom = p.get('nom_entreprise') or p.get('nom')
                p_id = p.get('id') or p.get('candidat_id') or p.get('prestataire_id')
                
                # Si on n'a pas l'ID mais qu'on a le nom, on cherche l'ID dans la base de données !
                if not p_id and nom:
                    candidat_db = Candidat.query.filter(Candidat.nom_entreprise.ilike(f"%{nom}%")).first()
                    if candidat_db:
                        p_id = candidat_db.id
                
                # On n'ajoute que les prestataires qui ont bien un ID et un Nom valides
                if nom and p_id:
                    prestataires_propres.append({
                        "id": p_id,
                        "nom": nom
                    })
            # -----------------------------------------------
            
            return jsonify({
                "success": True,
                "objet": lettre.objet_marche,
                "num_ordre": data.get('num_ordre', ''), 
                "ref_service": data.get('ref_service', ''),
                "direction_name": nom_direction, 
                "prestataires": prestataires_propres 
            })
        except json.JSONDecodeError:
            return jsonify({"success": False, "message": "Erreur JSON."})
            
    return jsonify({"success": False, "message": "Aucune lettre trouvée."})

@main.route('/info_depuis_notif/<path:immatriculation>')
@login_required
def info_depuis_notif(immatriculation):
    # On cherche la lettre d'information qui correspond à cette immatriculation
    lettre_info = LettreInformation.query.filter_by(immatriculation=immatriculation).order_by(LettreInformation.id.desc()).first()
    
    if lettre_info:
        # Si on la trouve, on lance le téléchargement direct !
        return redirect(url_for('main.telecharger_lettre_information', id=lettre_info.id))
    else:
        # Sinon, on affiche le message d'erreur
        flash("Aucune lettre d'information n'a été générée pour ce marché (peut-être qu'il n'y avait pas de perdants).", "warning")
        return redirect(url_for('main.liste_notifications'))

@main.route('/notifications/ajouter', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin', 'agent') # 🛡️ SÉCURITÉ : Stagiaire bloqué
def ajouter_notification():
    immatriculation = request.form.get('immatriculation')
    prestataire_id = request.form.get('prestataire_id_notif')
    
    # --- LOGS DE DÉBUT ---
    print("\n" + "="*50)
    print(f"🛠️ DEBUG - GÉNÉRATION TRIPLE (NOTIF + INFO + PV) POUR : {immatriculation}")
    
    if not prestataire_id or prestataire_id == 'undefined':
        flash("Erreur : L'entreprise gagnante n'a pas d'ID valide.", "danger")
        return redirect(url_for('main.liste_notifications'))

    # --- 1. RÉCUPÉRATION DES DONNÉES DU GAGNANT ---
    candidat_gagnant = db.session.get(Candidat, int(prestataire_id))
    destinataire_nom = candidat_gagnant.nom_entreprise if candidat_gagnant else "Non renseigné"
    
    # Préparation des données communes
    objet_marche = request.form.get('objet_marche')
    direction_name = request.form.get('direction_name')
    date_commission = request.form.get('date_commission')
    num_ordre = request.form.get('num_ordre', '............')
    date_lettre = request.form.get('date_lettre')
    signataire = request.form.get('signataire', 'Le Directeur,')
    
    # 👇 NOUVEAU : On récupère les deux nouveaux champs du formulaire web 👇
    adresse_direction = request.form.get('adresse_direction', 'Route des Almadies, Dakar')
    signataire_bas = request.form.get('signataire_bas', "Le Directeur de l'Administration\nGénérale et de l'Equipement")

    # --- 2. CRÉATION DE LA NOTIFICATION (Gagnant) ---
    data_notif = {
        'ref_service': request.form.get('ref_service'),
        'direction_name': direction_name,
        'signataire': signataire,
        'civilite_representant': request.form.get('civilite_representant'),
        'objet_marche': objet_marche,
        'immatriculation': immatriculation,
        'date_commission': date_commission,
        'num_ordre': num_ordre,
        'date_lettre': date_lettre,
        'destinataire_nom': destinataire_nom,
        'destinataire_adresse': f"{candidat_gagnant.adresse or ''} {candidat_gagnant.ville or ''}".strip(),
        'destinataire_tel': candidat_gagnant.telephone or "Non renseigné"
    }
    nouvelle_notif = LettreNotification(
        immatriculation=immatriculation,
        objet_marche=objet_marche,
        entreprise=destinataire_nom,
        form_data=json.dumps(data_notif)
    )
    db.session.add(nouvelle_notif)

   # --- 3. CRÉATION AUTOMATIQUE DU PV D'ATTRIBUTION ---
    data_pv = {
        'direction_name': direction_name,
        'num_ordre': num_ordre,
        'ref_service': data_notif['ref_service'],
        'date_lettre': date_lettre,
        'signataire': signataire,
        'date_commission': date_commission,
        'entreprise_nom': destinataire_nom, 
        'immatriculation': immatriculation,
        'objet_marche': objet_marche,
        
        # 👇 MISE À JOUR : On utilise les variables qu'on a récupérées en haut 👇
        'adresse_direction': adresse_direction, 
        'signataire_bas': signataire_bas 
    }
    
    nouveau_pv = ProcesVerbal(
        numero_drp=immatriculation,
        objet=objet_marche,
        entreprise=destinataire_nom,
        form_data=json.dumps(data_pv)
    )
    db.session.add(nouveau_pv)
    print(f"✅ DEBUG - PV d'Attribution créé pour {destinataire_nom}")
    
    # --- 4. GESTION DES PERDANTS (LETTRE D'INFORMATION) ---
    lettre_invit = LettreInvitation.query.filter_by(immatriculation=immatriculation).first()
    candidats_perdants_pdf = []
    
    if lettre_invit and lettre_invit.form_data:
        invit_data = json.loads(lettre_invit.form_data)
        prestataires_invites = invit_data.get('prestataires', [])
        
        for p in prestataires_invites:
            # 1. On cherche l'ID du candidat
            cand_id = p.get('id') or p.get('candidat_id') or p.get('prestataire_id')
            
            # Si le JSON n'a pas gardé l'ID, on cherche par le nom en BDD
            if not cand_id:
                nom_p = p.get('nom') or p.get('nom_entreprise') or ''
                c_db = Candidat.query.filter(Candidat.nom_entreprise.ilike(f"%{nom_p}%")).first()
                if c_db:
                    cand_id = c_db.id

            # 2. Si on a trouvé un candidat valide
            if cand_id:
                cand_obj = db.session.get(Candidat, int(cand_id))
                
                if cand_obj:
                    # 🚨 LE NOUVEAU FILTRE INFAILLIBLE 🚨
                    # On compare strictement les vrais IDs en BDD !
                    if int(cand_obj.id) == int(prestataire_id):
                        print(f"⏩ {cand_obj.nom_entreprise} est le GAGNANT, on l'ignore.")
                        continue 
                    
                    # 💡 CORRECTION : On récupère en priorité les infos du JSON de l'Invitation (p)
                    # S'il n'y a rien, on retombe sur la base de données (cand_obj)
                    rc_final = p.get('rc') or cand_obj.rc or 'N/A'
                    ninea_final = p.get('ninea') or cand_obj.ninea or 'N/A'
                    adresse_final = p.get('adresse') or cand_obj.adresse or 'Non renseignée'
                    tel_final = p.get('tel') or cand_obj.telephone or 'N/A'

                    candidats_perdants_pdf.append({
                        'nom_entreprise': cand_obj.nom_entreprise,
                        'adresse': adresse_final,
                        'rc': rc_final,
                        'ninea': ninea_final,
                        'tel': tel_final
                    })

    if candidats_perdants_pdf:
        data_info = data_pv.copy() # On reprend les bases
        data_info['perdants'] = candidats_perdants_pdf
        
        # 💡 NOUVEAU : On récupère le mot "FOURNISSEURS" stocké dans l'invitation,
        # et on l'injecte dans les données de la Lettre d'Information !
        type_entreprise_choisi = invit_data.get('type_entreprise', 'PRESTATAIRES')
        data_info['type_entreprise'] = type_entreprise_choisi
        nouvelle_info = LettreInformation(
            immatriculation=immatriculation,
            objet_marche=objet_marche,
            form_data=json.dumps(data_info)
        )
        db.session.add(nouvelle_info)
        print(f"✅ DEBUG - Lettre d'Information créée ({len(candidats_perdants_pdf)} perdants)")

    # 👇 C'EST ICI QUE TU REMPLACES L'ANCIENNE FINALISATION 👇
    # --- FINALISATION ---
    try:
        db.session.commit()
        log_action("Génération Complète Marché", immatriculation)
        flash(f"Succès ! Notification, Information et PV d'Attribution générés pour {immatriculation}", "success")
    except Exception as e:
        db.session.rollback() # 🛠️ Sécurité : on annule tout en cas d'erreur
        print(f"❌ ERREUR DB lors de la génération multiple : {str(e)}")
        flash("Une erreur critique est survenue lors de l'enregistrement. Veuillez réessayer.", "danger")
        
    return redirect(url_for('main.liste_notifications'))

# --- ROUTE PDF NOTIFICATION (Gagnant) - DÉJÀ EXISTANTE ---
@main.route('/notifications/pdf/<int:id>')
@login_required
def download_notification_pdf(id):
    notif = LettreNotification.query.get_or_404(id)
    data = json.loads(notif.form_data)
    
    buffer = io.BytesIO()
    from app.utils import generer_pdf_lettre_notification
    generer_pdf_lettre_notification(buffer, data)
    buffer.seek(0)
    
    return send_file(
        buffer, 
        as_attachment=True, 
        download_name=f"Lettre_Notification_{notif.immatriculation}.pdf", 
        mimetype='application/pdf'
    )


# --- NOUVELLE ROUTE PDF INFORMATION (Perdants) ---
@main.route('/informations/pdf_by_immat/<immatriculation>')
@login_required
def download_information_pdf(immatriculation):
    info = LettreInformation.query.filter_by(immatriculation=immatriculation).order_by(LettreInformation.id.desc()).first()
    
    if not info:
        flash("Aucune lettre d'information trouvée pour ce marché.", "danger")
        return redirect(url_for('main.liste_notifications'))

    data = json.loads(info.form_data)
    
    buffer = io.BytesIO()
    # ATTENTION : Il faudra créer cette fonction generer_pdf_lettre_information plus tard !
    from app.utils import generer_pdf_lettre_information 
    generer_pdf_lettre_information(buffer, data)
    buffer.seek(0)
    
    return send_file(
        buffer, 
        as_attachment=True, 
        download_name=f"Lettre_Information_{info.immatriculation}.pdf", 
        mimetype='application/pdf'
    )

# --- NOUVEAU : ROUTE POUR VOIR LE SCAN DE LA NOTIFICATION ---
@main.route('/notifications/voir_scan/<int:id>')
@login_required
def voir_scan_notification(id):
    notif = LettreNotification.query.get_or_404(id)
    if notif.fichier_scanne:
        # On utilise la route sécurisée pour pointer vers le dossier 'scans'
        return redirect(url_for('main.secure_download', folder='scans', filename=notif.fichier_scanne))
    else:
        flash("Aucun fichier scanné n'a été uploadé pour cette notification.", "warning")
        return redirect(url_for('main.liste_notifications'))

@main.route('/notifications/supprimer/<int:id>', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin', ) # 🛡️ SÉCURITÉ : Stagiaire et Agent bloqué
def supprimer_notification(id):
    notif = LettreNotification.query.get_or_404(id)
    
    # --- NOUVEAU : SUPPRESSION DU FICHIER PHYSIQUE SI EXISTANT ---
    if notif.fichier_scanne:
        basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        chemin_fichier = os.path.join(basedir, 'stockage_prive', 'scans', notif.fichier_scanne)
        if os.path.exists(chemin_fichier):
            os.remove(chemin_fichier)
            
    log_action("Suppression Notification", notif.immatriculation)
    db.session.delete(notif)
    db.session.commit()
    
    flash("Lettre de notification et ses fichiers associés supprimés.", "success")
    return redirect(url_for('main.liste_notifications'))

# ==========================================
# --- ROUTES : PROCÈS-VERBAL D'ATTRIBUTION ---
# ==========================================

@main.route('/pv-attribution')
@login_required
def liste_pv():
    pvs = db.session.query(ProcesVerbal).order_by(ProcesVerbal.id.desc()).all()
    candidats = Candidat.query.order_by(Candidat.nom_entreprise).all()
    return render_template('liste_pv.html', pvs=pvs, candidats=candidats)

@main.route('/pv-attribution/ajouter', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin', 'agent') # 🛡️ SÉCURITÉ : Stagiaire bloqué
def ajouter_pv():
    prestataire_id = request.form.get('prestataire_id_pv')
    entreprise_nom = "Non renseignée"
    
    if prestataire_id:
        candidat = db.session.get(Candidat, int(prestataire_id))
        if candidat:
            entreprise_nom = candidat.nom_entreprise

    # Formatage de la date en français (ex: 2025-11-21 -> 21 novembre 2025)
    date_commission_raw = request.form.get('date_commission', '')
    mois_fr = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    try:
        dt = datetime.strptime(date_commission_raw, '%Y-%m-%d')
        date_commission_fr = f"{dt.day:02d} {mois_fr[dt.month]} {dt.year}"
    except:
        date_commission_fr = date_commission_raw

    data = {
        'num_ordre': request.form.get('num_ordre', ''),
        'ref_service': request.form.get('ref_service', ''),
        'date_lettre': request.form.get('date_lettre', ''),
        'direction_name': request.form.get('direction_name', ''),
        'adresse_direction': request.form.get('adresse_direction', ''),
        'signataire': request.form.get('signataire', ''),
        'signataire_bas': request.form.get('signataire_bas', ''),
        'objet_marche': request.form.get('objet_marche', ''),
        'immatriculation': request.form.get('immatriculation', ''),
        'date_commission': date_commission_fr,  # <--- On utilise la belle date formatée !
        'entreprise_nom': entreprise_nom
    }

    nouveau_pv = ProcesVerbal(
        numero_drp=data['immatriculation'],
        objet=data['objet_marche'],
        entreprise=entreprise_nom,
        form_data=json.dumps(data)
    )
    db.session.add(nouveau_pv)
    log_action("Génération PV Attribution", entreprise_nom)
    db.session.commit()
    
    flash("PV d'attribution enregistré avec succès !", "success")
    return redirect(url_for('main.liste_pv'))

@main.route('/pv-attribution/download/<int:id>')
@login_required
def download_pv_pdf(id):
    pv = db.session.get(ProcesVerbal, id)
    if not pv:
        abort(404)
    
    data = json.loads(pv.form_data)
    data['entreprise_attributaire'] = data.get('entreprise_nom', 'Entreprise non renseignée')
    
    buffer = io.BytesIO()
    from app.utils import generer_pdf_pv_attribution
    generer_pdf_pv_attribution(buffer, data)
    buffer.seek(0)
    
    nom_fichier = f"PV_Attribution_{pv.numero_drp.replace('/', '_')}.pdf"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nom_fichier,
        mimetype='application/pdf'
    )

# --- NOUVEAU : ROUTE POUR VOIR LE SCAN DU PV ---
@main.route('/pv-attribution/voir_scan/<int:id>')
@login_required
def voir_scan_pv(id):
    pv = db.session.get(ProcesVerbal, id)
    if pv and pv.fichier_scanne:
        return redirect(url_for('main.secure_download', folder='scans', filename=pv.fichier_scanne))
    else:
        flash("Aucun fichier scanné n'a été uploadé pour ce PV.", "warning")
        return redirect(url_for('main.liste_pv'))

@main.route('/pv-attribution/supprimer/<int:id>', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin') # 🛡️ SÉCURITÉ : ACTION CRITIQUE, seuls les chefs peuvent supprimer !
def supprimer_pv(id):
    pv = db.session.query(ProcesVerbal).get_or_404(id)
    
    # --- NOUVEAU : SUPPRESSION DU FICHIER PHYSIQUE SI EXISTANT ---
    if pv.fichier_scanne:
        basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        chemin_fichier = os.path.join(basedir, 'stockage_prive', 'scans', pv.fichier_scanne)
        if os.path.exists(chemin_fichier):
            os.remove(chemin_fichier)
            
    log_action("Suppression PV", pv.numero_drp)
    db.session.delete(pv)
    db.session.commit()
    
    flash("Le PV et ses fichiers associés ont été supprimés avec succès.", "success")
    return redirect(url_for('main.liste_pv'))


# ==========================================
# --- ROUTES : LETTRES D'INVITATION ---
# ==========================================

@main.route('/creer_lettre_invitation', methods=['GET', 'POST'])
@login_required
def creer_lettre_invitation():
    import json
    from datetime import datetime  # <-- NOUVEAU : On importe l'outil pour lire les dates

    if request.method == 'POST':
        # 🛡️ SÉCURITÉ : Le Stagiaire peut voir la page (GET) mais ne peut pas valider le formulaire (POST)
        if current_user.role == 'stagiaire':
            flash("Accès refusé : Les stagiaires ne sont pas autorisés à générer des lettres.", "danger")
            return redirect(url_for('main.creer_lettre_invitation'))

        # 1. On récupère les informations générales simples
        immatriculation = request.form.get('immatriculation')
        objet_marche = request.form.get('objet_marche')
        num_ordre = request.form.get('num_ordre', '')
        ref_service = request.form.get('ref_service', '')
        signataire = request.form.get('signataire', '')
        adresse_depot = request.form.get('adresse_depot')
        lieu_ouverture = request.form.get('lieu_ouverture')
        direction_nom = request.form.get('direction_nom', "Direction de l'Administration Générale et de l'Equipement")
        # 💡 NOUVEAU : On récupère le type d'entreprise depuis le formulaire HTML
        type_entreprise = request.form.get('type_entreprise', 'PRESTATAIRES')
# juste après : type_entreprise = request.form.get('type_entreprise', 'PRESTATAIRES')
        print(f"🚨 DEBUG - Le type d'entreprise reçu du HTML est : {type_entreprise}")
        # --- NOUVEAU : TRADUCTION DES DATES EN FRANÇAIS ---
        mois_fr = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        jours_fr = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

        # Traduction de la Date de la lettre (ex: 2026-03-14 -> 14 mars 2026)
        date_lettre_brute = request.form.get('date_lettre', '')
        date_lettre = date_lettre_brute
        if date_lettre_brute:
            try:
                dt_lettre = datetime.strptime(date_lettre_brute, '%Y-%m-%d')
                date_lettre = f"{dt_lettre.day} {mois_fr[dt_lettre.month - 1]} {dt_lettre.year}"
            except ValueError:
                pass

        # Traduction de la Date et heure limite (ex: 2026-03-14T10:25 -> samedi 14 mars 2026 à 10 heures 25 minutes)
        date_limite_brute = request.form.get('date_heure_limite')
        date_heure_limite = date_limite_brute
        if date_limite_brute:
            try:
                dt_limite = datetime.strptime(date_limite_brute, '%Y-%m-%dT%H:%M')
                date_heure_limite = f"{jours_fr[dt_limite.weekday()]} {dt_limite.day} {mois_fr[dt_limite.month - 1]} {dt_limite.year} à {dt_limite.hour} heures {dt_limite.minute:02d} minute{'s' if dt_limite.minute > 1 else ''}"
            except ValueError:
                pass
        # --------------------------------------------------

        # 2. On récupère la liste des prestataires cochés
        prestataires_ids = request.form.getlist('prestataires_ids')
        prestataires_selectionnes = []

        for p_id in prestataires_ids:
            candidat = db.session.get(Candidat, int(p_id))
            if candidat:
                rc_saisi = request.form.get(f'rc_{p_id}', 'Non renseigné')
                compte = request.form.get(f'compte_bancaire_{candidat.id}', '')
                
                prestataires_selectionnes.append({
                    'id': candidat.id,
                    'nom': candidat.nom_entreprise,
                    'adresse': candidat.adresse,
                    'telephone': candidat.telephone,
                    'ninea': candidat.ninea,
                    'rc': rc_saisi,
                    'compte': compte
                })

        # 3. Dictionnaire de données
        form_data_dict = {
            'immatriculation': immatriculation,
            'objet_marche': objet_marche,
            'num_ordre': num_ordre,
            'ref_service': ref_service,
            'date_lettre': date_lettre,
            'signataire': signataire,
            'date_heure_limite': date_heure_limite,
            'adresse_depot': adresse_depot,
            'lieu_ouverture': lieu_ouverture,
            'direction_nom': direction_nom,
            'type_entreprise': type_entreprise, # 💡 NOUVEAU : On l'ajoute au dictionnaire JSON
            'prestataires': prestataires_selectionnes
        }

        # 4. Sauvegarde en BDD
        nouvelle_lettre = LettreInvitation(
            immatriculation=immatriculation,
            objet_marche=objet_marche,
            form_data=json.dumps(form_data_dict)
        )
        db.session.add(nouvelle_lettre)
        # CORRECTION ICI : on log l'immatriculation pour éviter un crash si aucun candidat n'est coché
        log_action("Génération Lettre Invitation", immatriculation) 
        db.session.commit()

        # --- MODIFICATION ICI (On supprime la génération directe du PDF) ---
        flash("Lettre d'invitation générée avec succès !", "success")
        return redirect(url_for('main.creer_lettre_invitation'))

    # === DÉBUT DES MODIFICATIONS POUR LA PARTIE GET ===
    
    # 1. On récupère les données habituelles
    candidats = Candidat.query.all()
    lettres_db = LettreInvitation.query.order_by(LettreInvitation.id.desc()).all()
    lettres_pour_tableau = []
    
    for lettre in lettres_db:
        data = json.loads(lettre.form_data) if lettre.form_data else {}
        lettres_pour_tableau.append({
            'id': lettre.id,
            'immatriculation': lettre.immatriculation,
            'objet_marche': lettre.objet_marche,
            'num_ordre': data.get('num_ordre', 'N/A'),
            'date_heure_limite': data.get('date_heure_limite', 'Non défini'),
            'fichier_scanne': lettre.fichier_scanne
        })
        
    # 2. --- NOUVEAU : Préparation GROUPÉE par Bordereau ---
    lettres_db = LettreInvitation.query.all()
    tous_les_bordereaux = Bordereau.query.order_by(Bordereau.id.desc()).all()
    
    immatriculations_deja_utilisees = [lettre.immatriculation.strip() for lettre in lettres_db if lettre.immatriculation]
    
    # On va créer une liste de groupes (chaque groupe = 1 bordereau)
    groupes_bordereaux = [] 
    
    for b in tous_les_bordereaux:
        dossiers = b.get_dossiers()
        dossiers_a_afficher = [] # Les dossiers restants pour CE bordereau
        
        for d in dossiers:
            ref = d.get('ref')
            objet_marche = d.get('objet', 'Objet non précisé') # On récupère aussi le nom du marché !
            
            if ref:
                ref = ref.strip()
                if ref not in immatriculations_deja_utilisees:
                    # On crée une belle étiquette avec le N° et l'objet
                    # Exemple: "N°F_DPT_126 - Fourniture Bureaux"
                    dossiers_a_afficher.append({
                        'immatriculation': ref,
                        'label': f"N° {ref} - {objet_marche}"
                    })
                    
        # Si le bordereau contient au moins 1 dossier non traité, on ajoute le groupe entier !
        if dossiers_a_afficher:
            groupes_bordereaux.append({
                'numero_bordereau': b.numero,
                'nombre_dossiers': len(dossiers_a_afficher),
                'dossiers': dossiers_a_afficher
            })
    return render_template('creer_lettre_invitation.html', 
                           candidats=candidats, 
                           lettres=lettres_pour_tableau, # (ou juste 'lettres' selon votre ancien code)
                           groupes_bordereaux=groupes_bordereaux)

@main.route('/telecharger_lettre/<int:id>')
@login_required
def telecharger_lettre(id):
    import json
    from app.utils import generer_pdf_lettre_invitation
    
    lettre = LettreInvitation.query.get_or_404(id)
    form_data_dict = json.loads(lettre.form_data)
    
    pdf_path = generer_pdf_lettre_invitation(form_data_dict)
    return send_file(pdf_path, as_attachment=True)

# --- NOUVEAU : ROUTE POUR VOIR LE SCAN DE LA LETTRE ---
@main.route('/lettre_invitation/voir_scan/<int:id>')
@login_required
def voir_scan_lettre(id):
    lettre = LettreInvitation.query.get_or_404(id)
    if lettre.fichier_scanne:
        return redirect(url_for('main.secure_download', folder='scans', filename=lettre.fichier_scanne))
    else:
        flash("Aucun fichier scanné n'a été uploadé pour cette lettre d'invitation.", "warning")
        return redirect(url_for('main.creer_lettre_invitation'))

@main.route('/supprimer_lettre/<int:id>', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin') # 🛡️ SÉCURITÉ : Action critique
def supprimer_lettre(id):
    lettre = LettreInvitation.query.get_or_404(id)
    
    # --- NOUVEAU : SUPPRESSION DU FICHIER PHYSIQUE SI EXISTANT ---
    if lettre.fichier_scanne:
        basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        chemin_fichier = os.path.join(basedir, 'stockage_prive', 'scans', lettre.fichier_scanne)
        if os.path.exists(chemin_fichier):
            os.remove(chemin_fichier)
            
    log_action("Suppression Lettre Invitation", lettre.immatriculation)
    db.session.delete(lettre)
    db.session.commit()
    
    flash("Lettre d'invitation et fichiers associés supprimés.", "success")
    return redirect(url_for('main.creer_lettre_invitation'))

# ==========================================
# --- ROUTES : CONTRATS ---
# ==========================================

@main.route('/creer_contrat', methods=['GET', 'POST'])
@login_required
def creer_contrat():
    import json
    
    if request.method == 'POST':
        # 🛡️ SÉCURITÉ : Le Stagiaire peut voir la page (GET) mais ne peut pas générer de contrat (POST)
        if current_user.role == 'stagiaire':
            flash("Accès refusé : Les stagiaires ne sont pas autorisés à générer des contrats.", "danger")
            return redirect(url_for('main.creer_contrat'))

        candidat_id = request.form.get('candidat_id')
        candidat_gagnant = db.session.get(Candidat, int(candidat_id)) if candidat_id else None
        
        objet_marche = request.form.get('objet_marche')
        gestion_annee = request.form.get('gestion_annee', '2025')
        montant = request.form.get('montant')
        montant_lettres = request.form.get('montant_lettres', '') 
        financement = request.form.get('financement', 'Budget de Fonctionnement')
        imputation = request.form.get('imputation')
        programme = request.form.get('programme')
        comptable = request.form.get('comptable', 'Payeur Général du Trésor (PGT)')
        vocable = request.form.get('vocable', 'Prestataire')
        numero = request.form.get('numero')
        ref_service = request.form.get('ref_service')
        date_lettre = request.form.get('date_lettre')
        
        # Récupérés automatiquement via notre nouvelle API cachée dans le formulaire
        rc_final = request.form.get('rc_candidat', '........................')
        compte_final = request.form.get('compte_candidat', '...................................')

        if not candidat_gagnant:
            flash("Erreur : Impossible de retrouver le prestataire.", "danger")
            return redirect(url_for('main.creer_contrat'))

        # 1. ON SAUVEGARDE LE CONTRAT DANS LA BASE DE DONNÉES
        
        # A) On récupère le numéro d'immatriculation du marché grâce au PV
        immatriculation_marche = numero # Valeur par défaut si rien d'autre
        pv_id = request.form.get('pv_id')
        if pv_id:
            pv_lie = db.session.get(ProcesVerbal, int(pv_id))
            if pv_lie and pv_lie.numero_drp:
                immatriculation_marche = pv_lie.numero_drp

        # B) On crée le contrat avec toutes les infos + l'immatriculation !
        nouveau_contrat = Contrat(
            candidat_id=candidat_gagnant.id,
            objet_marche=objet_marche,
            gestion_annee=gestion_annee,
            montant_chiffres=montant,
            montant_lettres=montant_lettres,
            financement=financement,
            imputation=imputation,
            programme=programme,
            comptable_assignataire=comptable,
            rc_candidat=rc_final,
            compte_bancaire=compte_final,
            numero=numero,
            ref_service=ref_service,
            date_lettre=date_lettre,
            immatriculation=immatriculation_marche # 👈 LA PIÈCE MANQUANTE EST ICI !
        )
        
        db.session.add(nouveau_contrat)
        log_action("Ajout Contrat", candidat_gagnant.nom_entreprise)
        db.session.commit()

        # 2. ON PRÉPARE LES DONNÉES POUR LE PDF (Optionnel ici si téléchargé via le tableau)
        flash("Contrat généré et sauvegardé avec succès !", "success")
        return redirect(url_for('main.creer_contrat'))

    # === DÉBUT PARTIE GET ===
    # On récupère tous les PV d'attribution
    liste_pvs = ProcesVerbal.query.order_by(ProcesVerbal.id.desc()).all()
    
    contrats_bruts = Contrat.query.order_by(Contrat.id.desc()).all()
    contrats_sauvegardes = []
    for c in contrats_bruts:
        cand = db.session.get(Candidat, c.candidat_id)
        c.entreprise_nom = cand.nom_entreprise if cand else "Entreprise inconnue"
        contrats_sauvegardes.append(c)

    return render_template('formulaire_contrat.html', pvs=liste_pvs, contrats=contrats_sauvegardes)


# === PARTIE 2 : LA NOUVELLE API MAGIQUE POUR LE PV ===
@main.route('/api/get_infos_pv')
@login_required
def get_infos_pv():
    import json
    pv_id = request.args.get('pv_id')
    pv = ProcesVerbal.query.get(pv_id)
    
    if not pv:
        return jsonify({"success": False})
        
    candidat = Candidat.query.filter_by(nom_entreprise=pv.entreprise).first()
    
    # 1. On extrait les données du PV (Réf, Date, N° Ordre)
    data_pv = json.loads(pv.form_data) if pv.form_data else {}
    immatriculation = pv.numero_drp
    
    # 2. On va chercher le RC et le Compte bancaire dans la lettre d'invitation d'origine
    invit = LettreInvitation.query.filter_by(immatriculation=immatriculation).first()
    rc = "Non renseigné"
    compte = "Non renseigné"
    
    if invit and invit.form_data:
        try:
            data_invit = json.loads(invit.form_data)
            for p in data_invit.get('prestataires', []):
                if p.get('nom') == pv.entreprise:
                    rc = p.get('rc', 'Non renseigné')
                    compte = p.get('compte', 'Non renseigné')
                    break
        except:
            pass
            
    # On renvoie TOUT au formulaire HTML !
    return jsonify({
        "success": True,
        "candidat_id": candidat.id if candidat else "",
        "nom_entreprise": pv.entreprise,
        "objet_marche": pv.objet,
        "ref_service": data_pv.get('ref_service', ''),
        "date_lettre": data_pv.get('date_lettre', ''),
        "num_ordre": data_pv.get('num_ordre', ''),
        "rc": rc,
        "compte": compte
    })


@main.route('/telecharger_contrat/<int:id>')
@login_required
def telecharger_contrat(id):
    from app.utils import generer_pdf_contrat
    contrat = Contrat.query.get_or_404(id)
    candidat = db.session.get(Candidat, contrat.candidat_id)
    
    data_contrat = {
        'titulaire': candidat.nom_entreprise if candidat else 'Inconnu',
        'ninea': getattr(candidat, 'ninea', 'N/A'),
        'rc': contrat.rc_candidat,                       
        'compte_bancaire': contrat.compte_bancaire, 
        'adresse_candidat': getattr(candidat, 'adresse', 'N/A'),   
        'tel_candidat': getattr(candidat, 'telephone', 'N/A'),      
        'objet_marche': contrat.objet_marche,      
        'gestion_annee': contrat.gestion_annee,
        'montant': contrat.montant_chiffres,
        'montant_lettres': contrat.montant_lettres,
        'financement': contrat.financement,
        'imputation': contrat.imputation,
        'programme': contrat.programme,
        'comptable': contrat.comptable_assignataire,
        'vocable': 'Prestataire',
        'numero': getattr(contrat, 'numero', ''), 
        'ref_service': getattr(contrat, 'ref_service', ''), 
        'date_lettre': getattr(contrat, 'date_lettre', '') 
    }
    
    chemin_pdf = generer_pdf_contrat(data_contrat)
    nom_safe = candidat.nom_entreprise.replace(' ', '_') if candidat else 'Inconnu'
    nom_fichier = f"Contrat_{nom_safe}.pdf"
    return send_file(chemin_pdf, as_attachment=True, download_name=nom_fichier)


@main.route('/contrat/voir_scan/<int:id>')
@login_required
def voir_scan_contrat(id):
    contrat = Contrat.query.get_or_404(id)
    if contrat.fichier_scanne:
        return redirect(url_for('main.secure_download', folder='scans', filename=contrat.fichier_scanne))
    else:
        flash("Aucun fichier scanné n'a été uploadé pour ce contrat.", "warning")
        return redirect(url_for('main.creer_contrat'))


@main.route('/supprimer_contrat/<int:id>', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin') # 🛡️ SÉCURITÉ : Action critique, chefs uniquement
def supprimer_contrat(id):
    contrat = Contrat.query.get_or_404(id)
    candidat = db.session.get(Candidat, contrat.candidat_id)
    nom_entreprise = candidat.nom_entreprise if candidat else f"Entreprise ID {contrat.candidat_id}"

    if contrat.fichier_scanne:
        basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        chemin_fichier = os.path.join(basedir, 'stockage_prive', 'scans', contrat.fichier_scanne)
        if os.path.exists(chemin_fichier):
            os.remove(chemin_fichier)
            
    log_action("Suppression Contrat", nom_entreprise)
    db.session.delete(contrat)
    db.session.commit()
    flash("Le contrat et ses fichiers associés ont été supprimés avec succès.", "success")
    return redirect(url_for('main.creer_contrat'))

# ==========================================
# --- ROUTES : LETTRES D'INFORMATION ---
# ==========================================

@main.route('/creer_lettre_information', methods=['POST'])
@login_required
def creer_lettre_information():
    # 🛡️ SÉCURITÉ : Le Stagiaire ne peut pas générer de lettre d'information
    if current_user.role == 'stagiaire':
        flash("Accès refusé : Les stagiaires ne sont pas autorisés à générer des lettres d'information.", "danger")
        return redirect(url_for('main.lettres_information'))

    import io
    from datetime import datetime
    import json
    
    direction_name = request.form.get('direction_name')
    num_ordre = request.form.get('num_ordre')
    ref_service = request.form.get('ref_service')
    signataire = request.form.get('signataire')
    
    date_lettre_raw = request.form.get('date_lettre')
    try:
        dt_lettre = datetime.strptime(date_lettre_raw, '%Y-%m-%d')
        date_lettre = dt_lettre.strftime('%d/%m/%Y')
    except:
        date_lettre = date_lettre_raw or datetime.now().strftime('%d/%m/%Y')

    immatriculation = request.form.get('immatriculation')
    date_comm_raw = request.form.get('date_commission')
    try:
        dt = datetime.strptime(date_comm_raw, '%Y-%m-%d')
        date_commission = dt.strftime('%d/%m/%Y')
    except:
        date_commission = date_comm_raw

    objet_marche = request.form.get('objet_marche')
    
    prestataires_ids = request.form.getlist('prestataire_id[]')
    rcs_saisis = request.form.getlist('rc[]') 
    
    prestataires = []
    from itertools import zip_longest
    for pid, rc_agent in zip_longest(prestataires_ids, rcs_saisis, fillvalue=""):
        if pid:
            candidat = db.session.get(Candidat, int(pid))
            if candidat:
                adresse_db = candidat.adresse or ""
                ville_db = candidat.ville or ""
                ninea_db = candidat.ninea or "Néant"
                tel_db = candidat.telephone or "Néant"
                rc_final = rc_agent or "Non renseigné"
                
                lieu = f"{adresse_db} {ville_db}".strip()
                phrase_adresse_complete = f"{lieu}, RC : {rc_final}, NINEA : {ninea_db}, Tél : {tel_db} ;"
                
                prestataires.append({
                    'nom': candidat.nom_entreprise,
                    'adresse': phrase_adresse_complete
                })
    
    data = {
        'direction_name': direction_name,
        'num_ordre': num_ordre,
        'ref_service': ref_service,
        'date_lettre': date_lettre,
        'signataire': signataire,
        'immatriculation': immatriculation,
        'date_commission': date_commission,
        'objet_marche': objet_marche,
        'prestataires': prestataires
    }            

    # SAUVEGARDE DANS LA BASE DE DONNÉES
    nouvelle_lettre = LettreInformation(
        immatriculation=immatriculation,
        objet_marche=objet_marche,
        form_data=json.dumps(data)
    )
    db.session.add(nouvelle_lettre)
    log_action("Ajout Lettre Information", immatriculation)
    db.session.commit()

    # REDIRECTION VERS LE TABLEAU (Méthode Post-Redirect-Get)
    flash("Lettre d'information générée avec succès !", "success")
    return redirect(url_for('main.lettres_information'))

@main.route('/lettres_information', methods=['GET'])
@login_required
def lettres_information():
    import json
    candidats = Candidat.query.order_by(Candidat.nom_entreprise).all()
    lettres_db = LettreInformation.query.order_by(LettreInformation.id.desc()).all()
    
    lettres_pour_tableau = []
    for lettre in lettres_db:
        data = json.loads(lettre.form_data) if lettre.form_data else {}
        lettres_pour_tableau.append({
            'id': lettre.id,
            'immatriculation': lettre.immatriculation,
            'objet_marche': lettre.objet_marche,
            'num_ordre': data.get('num_ordre', 'N/A'),
            'date_commission': data.get('date_commission', 'Non défini'),
            'fichier_scanne': lettre.fichier_scanne
        })

    return render_template('lettres_information.html', candidats=candidats, lettres=lettres_pour_tableau)

@main.route('/telecharger_lettre_information/<int:id>')
@login_required
def telecharger_lettre_information(id):
    import json, io
    from app.utils import generer_pdf_lettre_information
    
    lettre = LettreInformation.query.get_or_404(id)
    data = json.loads(lettre.form_data)
    
    buffer = io.BytesIO()
    generer_pdf_lettre_information(buffer, data)
    buffer.seek(0)
    log_action("Téléchargement Lettre Info", lettre.immatriculation)
    db.session.commit()
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Lettre_Information_{lettre.immatriculation.replace('/', '_')}.pdf",
        mimetype='application/pdf'
    )

# --- NOUVEAU : ROUTE POUR VOIR LE SCAN DE LA LETTRE INFO ---
@main.route('/lettre_information/voir_scan/<int:id>')
@login_required
def voir_scan_lettre_info(id):
    lettre = LettreInformation.query.get_or_404(id)
    if lettre.fichier_scanne:
        return redirect(url_for('main.secure_download', folder='scans', filename=lettre.fichier_scanne))
    else:
        flash("Aucun fichier scanné n'a été uploadé pour cette lettre d'information.", "warning")
        return redirect(url_for('main.lettres_information'))

@main.route('/supprimer_lettre_information/<int:id>', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin') # 🛡️ SÉCURITÉ : Action critique, chefs uniquement
def supprimer_lettre_information(id):
    lettre = LettreInformation.query.get_or_404(id)
    
    # --- NOUVEAU : SUPPRESSION DU FICHIER PHYSIQUE SI EXISTANT ---
    if lettre.fichier_scanne:
        basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        chemin_fichier = os.path.join(basedir, 'stockage_prive', 'scans', lettre.fichier_scanne)
        if os.path.exists(chemin_fichier):
            os.remove(chemin_fichier)
            
    log_action("Suppression Lettre Info", lettre.immatriculation)
    db.session.delete(lettre)
    db.session.commit()
    
    flash("La lettre d'information et ses fichiers associés ont été supprimés avec succès.", "success")
    return redirect(url_for('main.lettres_information'))

# ==========================================
# --- ROUTES : GESTION DES SCANS ET UPLOADS ---
# ==========================================

@main.route('/voir_scan/<nom_fichier>')
@login_required
def voir_scan(nom_fichier):
    # Log de l'action
    log_action("Consultation Scan", nom_fichier)
    db.session.commit()
    
    # On délègue tout le travail à la route sécurisée, pas besoin de code mort en dessous !
    return redirect(url_for('main.secure_download', folder='scans', filename=nom_fichier))
    
    
@main.route('/uploader_scan', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin', 'agent') # 🛡️ SÉCURITÉ : Pas de stagiaire !
def uploader_scan():
    print("--- DÉBUT DE L'UPLOAD ---")
    
    type_doc = request.form.get('type_doc').lower()
    doc_id = request.form.get('doc_id')
    page_retour = request.form.get('page_retour', 'main.tableau_de_bord') # Sécurité : fallback par défaut
    
    if 'scan_file' not in request.files or request.files['scan_file'].filename == '':
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for(page_retour))
        
    file = request.files['scan_file']

    # 1ère couche : Vérification du nom
    if not fichier_est_autorise(file.filename):  # 👈 Utilise le nom d'origine ici !
        flash("Fichier non autorisé ! L'extension n'est pas acceptée.", "danger")
        log_action("ALERTE SÉCURITÉ", f"Upload bloqué (Mauvaise extension) : {file.filename} pour doc n°{doc_id}")
        db.session.commit()
        return redirect(url_for(page_retour))

    # 2ème couche : Vérification du contenu réel
    if not contenu_fichier_est_securise(file):
        flash("ALERTE : Fichier falsifié ou corrompu ! Le contenu ne correspond pas à l'extension.", "danger")
        # On logue la tentative de spoofing !
        log_action("ALERTE CRITIQUE", f"Tentative de Spoofing (Fausse extension) bloquée : {file.filename}")
        db.session.commit()
        return redirect(url_for(page_retour))
    
    # 1. Préparation du nom et du dossier
    # ✨ NOUVEAU CODE SÉCURISÉ (UUID) ✨
    # 1. On récupère juste l'extension du fichier original (ex: "pdf", "jpg")
    nom_propre = secure_filename(file.filename)
    extension = nom_propre.rsplit('.', 1)[1].lower() if '.' in nom_propre else 'pdf'
    
    # 2. On génère un nom totalement aléatoire et impossible à deviner
    nom_uuid = f"{uuid.uuid4().hex}.{extension}"
    
    basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    dossier_sauvegarde = os.path.join(basedir, 'stockage_prive', 'scans')
    os.makedirs(dossier_sauvegarde, exist_ok=True)

    # On importe les modèles ici pour éviter les imports circulaires
    from app.models import (LettreInvitation, Contrat, LettreInformation, 
                            LettreNotification, Bordereau, ProcesVerbal, 
                            Cotation, Candidat)
                            
    # 2. Dictionnaire de correspondance (beaucoup plus propre que les if/elif)
    modeles_map = {
        'lettre_invitation': LettreInvitation,
        'contrat': Contrat,
        'lettre_information': LettreInformation,
        'lettre_notification': LettreNotification,
        'bordereau': Bordereau,
        'pv_attribution': ProcesVerbal,
        'cotation': Cotation,
        'agrement': Candidat
    }

    if type_doc not in modeles_map:
        flash("Type de document invalide.", "danger")
        return redirect(url_for(page_retour))

    # 3. On récupère le document
    Modele = modeles_map[type_doc]
    doc = Modele.query.get(doc_id)

    if not doc:
        flash("Erreur : Le document cible n'existe pas en base de données.", "danger")
        return redirect(url_for(page_retour))

    # 4. On sauvegarde physiquement le fichier
    chemin_complet = os.path.join(dossier_sauvegarde, nom_uuid)
    file.save(chemin_complet)

    # 5. On met à jour l'objet en mémoire (SANS FAIRE DE COMMIT ICI)
    doc.fichier_scanne = nom_uuid
    
     
# =========================================================
# --- AJOUT AUTOMATIQUE AUX ARCHIVES GLOBALES ---
# =========================================================
# Correction : on utilise "or" pour forcer le plan de secours si l'attribut est None ou vide
    ref_archive = getattr(doc, 'reference', None) or getattr(doc, 'immatriculation', None) or f"{type_doc.upper().replace('_', '')}-{doc_id}"

    type_formate = type_doc.replace('_', ' ').title()

    nouvelle_archive = ArchiveDocument(
        reference=ref_archive,
        type_document=type_formate,

        nom_fichier=nom_uuid
    )
    db.session.add(nouvelle_archive)
    
    # 👇 ON PLACE LE RADAR JUSTE AVANT LE DERNIER COMMIT 👇
    log_action("Upload Scan", f"{type_formate} ({ref_archive})")
    
    # 6. UN SEUL COMMIT POUR TOUT VALIDER D'UN COUP ! 🎯
    db.session.commit() 
    
    flash("Le document scanné a été ajouté avec succès !", "success")
    return redirect(url_for(page_retour))

# ==========================================
# --- ROUTES : ARCHIVES GLOBALES ---
# ==========================================

@main.route('/archives', methods=['GET'])
@login_required
def page_archives():
    from app.models import ArchiveDocument
    toutes_les_archives = ArchiveDocument.query.order_by(ArchiveDocument.date_ajout.desc()).all()
    return render_template('archives.html', archives=toutes_les_archives)

@main.route('/upload_archive', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin', 'agent') # 🛡️ SÉCURITÉ : Stagiaires bloqués
def upload_archive():
    from app.models import ArchiveDocument
    
    if 'fichier' not in request.files or request.files['fichier'].filename == '':
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for('main.page_archives'))
        
    file = request.files['fichier']

    # ==========================================================
    # 👇 LE BOUCLIER DE SÉCURITÉ EST LÀ 👇
    if not fichier_est_autorise(file.filename):
        flash("Fichier non autorisé ! Seuls les PDF et images sont acceptés.", "danger")
        log_action("Alerte Sécurité", f"Tentative d'upload illégal : {file.filename}")
        db.session.commit()
        return redirect(url_for('main.page_archives'))
    # 👆 FIN DU BOUCLIER 👆
    # ==========================================================
    
    filename = secure_filename(file.filename)
    
    # On sauvegarde bien dans le stockage privé
    dossier_sauvegarde = os.path.abspath(os.path.join(current_app.root_path, '..', 'stockage_prive', 'archives'))
    os.makedirs(dossier_sauvegarde, exist_ok=True)
    
    chemin_complet = os.path.join(dossier_sauvegarde, filename)
    file.save(chemin_complet)
    
    reference_saisie = request.form.get('reference')
    type_doc = request.form.get('type_document')
    
    nouvelle_archive = ArchiveDocument(
        reference=reference_saisie,
        type_document=type_doc,
        nom_fichier=filename
    )
    db.session.add(nouvelle_archive)
    
    log_action("Ajout Archive", f"{type_doc} ({reference_saisie})")
    db.session.commit()
    
    flash("Document archivé avec succès !", "success")
    return redirect(url_for('main.page_archives'))

@main.route('/telecharger_archive/<nom_fichier>')
@login_required
def telecharger_archive(nom_fichier):
    import os
    from flask import send_from_directory, current_app, abort
    
    log_action("Consultation Archive", nom_fichier)
    db.session.commit()
    
    # 📁 CORRECTION : On pointe vers les NOUVEAUX dossiers privés
    basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    dossier_archives = os.path.join(basedir, 'stockage_prive', 'archives')
    dossier_scans = os.path.join(basedir, 'stockage_prive', 'scans')
    
    # 1. On regarde d'abord si le fichier a été uploadé manuellement
    if os.path.exists(os.path.join(dossier_archives, nom_fichier)):
        return send_from_directory(dossier_archives, nom_fichier)
        
    # 2. Sinon, on regarde s'il vient d'un scan automatique
    elif os.path.exists(os.path.join(dossier_scans, nom_fichier)):
        return send_from_directory(dossier_scans, nom_fichier)
        
    # 3. Introuvable
    else:
        abort(404)

# ==========================================
# --- ROUTES : SUIVI DES DOSSIERS (TIMELINE) ---
# ==========================================

@main.route('/suivi_dossiers', methods=['GET'])
@login_required
def page_suivi_dossiers():
    from app.models import LettreInvitation, ProcesVerbal, LettreNotification, LettreInformation, Contrat
    
    immatriculations = set()
    
    # On récolte toutes les immatriculations
    for lettre in LettreInvitation.query.all():
        if lettre.immatriculation:
            immatriculations.add(lettre.immatriculation)
            
    for pv in ProcesVerbal.query.all():
        if pv.numero_drp: 
            immatriculations.add(pv.numero_drp)

    dossiers_suivis = []
# Pour chaque marché, on vérifie l'état d'avancement
    for immat in immatriculations:
        doc_invitation = LettreInvitation.query.filter_by(immatriculation=immat).first()
        doc_pv = ProcesVerbal.query.filter_by(numero_drp=immat).first()
        doc_notif = LettreNotification.query.filter_by(immatriculation=immat).first()
        doc_info = LettreInformation.query.filter_by(immatriculation=immat).first()
        
        objet_du_marche = "Objet non défini"
        reference_du_pv = None 
        
        if doc_invitation and doc_invitation.objet_marche:
            objet_du_marche = doc_invitation.objet_marche
            
        if doc_pv:
            if doc_pv.objet:
                objet_du_marche = doc_pv.objet
            # On extrait la référence (ref_service) qui est cachée dans le JSON du PV
            if doc_pv.form_data:
                import json
                try:
                    data_pv = json.loads(doc_pv.form_data)
                    reference_du_pv = data_pv.get('ref_service')
                except:
                    pass

        # 👇 RECHERCHE DU CONTRAT GRÂCE AU NUMÉRO DE RÉFÉRENCE 👇
        doc_contrat = None
        
        # 1. On cherche d'abord avec le numéro de référence (Ton idée !)
        if reference_du_pv:
            doc_contrat = Contrat.query.filter_by(ref_service=reference_du_pv).first()
            
        # 2. Si on ne trouve pas (ou s'il est vide), on tente l'immatriculation
        if not doc_contrat:
            doc_contrat = Contrat.query.filter_by(immatriculation=immat).first()
            
        # 3. Plan de secours ultime : on lie par l'objet du marché
        if not doc_contrat and objet_du_marche != "Objet non défini":
            doc_contrat = Contrat.query.filter_by(objet_marche=objet_du_marche).first()
        # 👆 FIN DE LA RECHERCHE 👆

        # 👇 C'EST ICI QUE LA MAGIE OPÈRE 👇
        dossier = {
            'immatriculation': immat,
            'objet_marche': objet_du_marche,
            'etapes': {
                'etape_1_invitation': True if (doc_invitation and doc_invitation.fichier_scanne) else False,
                'etape_2_pv': True if (doc_pv and doc_pv.fichier_scanne) else False,
                'etape_3_notification': True if (doc_notif and doc_notif.fichier_scanne) else False,
                'etape_4_information': True if (doc_info and doc_info.fichier_scanne) else False,
                'etape_5_contrat': True if (doc_contrat and doc_contrat.fichier_scanne) else False
            }
        }
        dossiers_suivis.append(dossier)

    return render_template('suivi_dossiers.html', dossiers=dossiers_suivis)
        
@main.route('/supprimer_archive/<int:id>', methods=['POST'])
@login_required
@role_requis('superadmin', 'admin') # 🛡️ SÉCURITÉ : Seuls les chefs peuvent supprimer !
def supprimer_archive(id):
    from app.models import ArchiveDocument
    import os
    
    archive = db.session.get(ArchiveDocument, id)
    if archive:
        # 📁 CORRECTION : On pointe vers le bon dossier privé
        basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        dossier_archives = os.path.join(basedir, 'stockage_prive', 'archives')
        chemin_fichier = os.path.join(dossier_archives, archive.nom_fichier)
        
        # Suppression physique (Uniquement si c'est dans 'archives' manuels)
        if os.path.exists(chemin_fichier):
            try:
                os.remove(chemin_fichier)
            except Exception as e:
                print(f"Erreur lors de la suppression du fichier physique : {e}")
        
        log_action("Suppression Archive", f"{archive.type_document} ({archive.reference})")
        
        db.session.delete(archive)
        db.session.commit()
        
        flash("L'archive a été supprimée avec succès.", "success")
    else:
        flash("Archive introuvable.", "danger")
        
    return redirect(url_for('main.page_archives'))
    
# --- EXPORT EXCEL ---
@main.route('/exporter_archives_excel')
@login_required
def exporter_archives_excel():
    from app.models import ArchiveDocument
    import pandas as pd
    from io import BytesIO
    from flask import send_file
    # J'ai supprimé le 'import datetime' ici
    
    archives = ArchiveDocument.query.order_by(ArchiveDocument.date_ajout.desc()).all()
    
    donnees = []
    for doc in archives:
        donnees.append({
            "Référence du Document": doc.reference,
            "Type de Document": doc.type_document,
            "Nom du Fichier (Scan)": doc.nom_fichier,
            "Date d'Archivage": doc.date_ajout.strftime('%d/%m/%Y %H:%M') if doc.date_ajout else "N/A"
        })
        
    df = pd.DataFrame(donnees)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Registre_Archives')
        
        worksheet = writer.sheets['Registre_Archives']
        for idx, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 5
            worksheet.column_dimensions[chr(65 + idx)].width = max_len
            
    output.seek(0)
    
    # ICI : on utilise juste datetime.now()
    date_jour = datetime.now().strftime('%Y-%m-%d')
    nom_fichier_export = f"Registre_Archives_MCAT_{date_jour}.xlsx"
    
    # 👇 AJOUTE CES DEUX LIGNES 👇
    log_action("Export Excel", "Registre des Archives Documentaires")
    db.session.commit()
    
    return send_file(
        output,
        as_attachment=True,
        download_name=nom_fichier_export,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



@main.route('/debloquer_ip/<int:id>', methods=['POST'])
@login_required
def debloquer_ip(id):
    if current_user.role != 'superadmin':
        return redirect(url_for('main.tableau_de_bord'))
    
    ban_record = LoginAttempt.query.get_or_404(id)
    ip_liberee = ban_record.ip_address
    
    db.session.delete(ban_record) # On supprime carrément l'entrée
    log_action("DEBLOCAGE_IP", f"L'IP {ip_liberee} a été débloquée manuellement")
    db.session.commit()
    
    flash(f"L'adresse IP {ip_liberee} a été débloquée avec succès.", "success")
    return redirect(url_for('main.super_dashboard'))

@main.app_errorhandler(404)
def error_404(error):
    return render_template('errors/404.html'), 404

@main.app_errorhandler(500)
def error_500(error):
    db.session.rollback() # Très important : annule les bêtises en BDD si ça a planté
    return render_template('errors/500.html'), 500



@main.route('/telecharger_document/<path:filename>')
@login_required
def telecharger_protected_file(filename):
    # Au lieu de chercher uniquement dans 'archives', 
    # on utilise la logique multi-dossiers de secure_download
    return secure_download(folder='archives', filename=filename)

from pathlib import Path

@main.route('/secure_download/<folder>/<path:filename>')
@login_required
def secure_download(folder, filename):
    """Version sécurisée contre le Directory Traversal + Masquage UUID"""
    
    ALLOWED_FOLDERS = ['archives', 'cotations', 'scans', 'drps', 'agreement']
    
    if folder not in ALLOWED_FOLDERS:
        abort(403)

    # --- 1. TON CODE DE SÉCURITÉ EXISTANT (On garde tout !) ---
    root_dir = Path(current_app.root_path).parent.resolve()
    base_path = (root_dir / 'stockage_prive' / folder).resolve()

    try:
        full_path = (base_path / filename).resolve()
    except Exception:
        abort(404)

    if not full_path.is_relative_to(base_path):
        abort(403)

    if not full_path.exists():
        scans_path = (root_dir / 'stockage_prive' / 'scans').resolve()
        full_path = (scans_path / filename).resolve()
        if not full_path.is_relative_to(scans_path) or not full_path.exists():
            abort(404)
            
    # --- 2. LA NOUVEAUTÉ : TRADUCTION DE L'UUID EN JOLI NOM ---
    from app.models import ArchiveDocument
    
    # On cherche l'UUID dans la table des archives
    archive = ArchiveDocument.query.filter_by(nom_fichier=full_path.name).first()
    
    if archive:
        # Si on le trouve, on fabrique un beau nom ! 
        # Ex: "Contrat_S-DAGE-198.pdf"
        joli_nom = f"{archive.type_document}_{archive.reference}.pdf".replace(" ", "_")
    else:
        # Plan de secours si jamais le fichier n'est pas dans les archives
        joli_nom = "Document_Scan.pdf"

    # --- 3. L'ENVOI AU NAVIGATEUR ---
    return send_from_directory(
        str(full_path.parent), 
        full_path.name,
        as_attachment=False,  # Affichage direct dans le navigateur si possible
        download_name=joli_nom  # 👈 Le masque magique est appliqué ici !
    )

@main.route('/vider_logs_securite', methods=['POST'])
@login_required
def vider_logs_securite():
    # 1. Vérification de sécurité stricte
    if current_user.role != 'superadmin':
        flash("Action non autorisée.", "danger")
        return redirect(url_for('main.tableau_de_bord'))
    
    try:
        # 2. On supprime TOUTES les lignes de la table LogAction
        LogAction.query.delete()
        db.session.commit()
        
        # 3. Message de succès et redirection
        flash("Tous les logs de sécurité ont été effacés définitivement.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Une erreur est survenue lors du nettoyage : {str(e)}", "danger")
        
    return redirect(url_for('main.super_dashboard'))

@main.route('/verifier_cle_securite', methods=['POST'])
@login_required
def verifier_cle_securite():
    # Seul le superadmin a le droit de tenter sa chance
    if current_user.role != 'superadmin':
        flash("Accès interdit.", "danger")
        return redirect(url_for('main.tableau_de_bord'))
    
    # On récupère ce qui a été tapé dans le formulaire
    cle_saisie = request.form.get('cle_saisie')
    # On récupère la vraie clé stockée dans le config.py / .env
    vraie_cle = current_app.config.get('CLE_DE_VERROUILLAGE')
    
    # On compare les deux (en direct, sans hachage, car c'est une clé maître d'environnement)
    if cle_saisie == vraie_cle:
        # C'est bon ! On donne le passe-droit dans la session
        session['acces_autorise_page_secrete'] = True
        return redirect(url_for('main.page_changement_mot_de_passe'))
    else:
        # C'est faux
        flash("Clé de sécurité incorrecte.", "danger")
        # On redirige vers la page d'où il vient (le referrer)
        return redirect(request.referrer or url_for('main.super_dashboard'))
    

@main.route('/page_changement_mot_de_passe', methods=['GET', 'POST'])
@login_required
def page_changement_mot_de_passe():
    # 1. LA BARRIÈRE DE SÉCURITÉ : On vérifie le laissez-passer
    # Si la personne n'a pas tapé la bonne clé dans le `.env` juste avant, on la bloque !
    if not session.get('acces_autorise_page_secrete'):
        flash("Accès refusé. Veuillez utiliser la clé de sécurité pour accéder à cette page.", "danger")
        return redirect(url_for('main.tableau_de_bord'))
    
    # 2. TRAITEMENT DU FORMULAIRE (Quand tu cliques sur Valider)
    if request.method == 'POST':
        nouveau_mdp = request.form.get('nouveau_mot_de_passe')
        confirmation_mdp = request.form.get('confirmation_mot_de_passe')
        
        # Vérification 1 : Les champs ne sont pas vides
        if not nouveau_mdp or not confirmation_mdp:
            flash("Veuillez remplir tous les champs.", "warning")
            return redirect(url_for('main.page_changement_mot_de_passe'))
            
        # Vérification 2 : Les deux mots de passe sont identiques
        if nouveau_mdp != confirmation_mdp:
            flash("Les mots de passe ne correspondent pas. Veuillez réessayer.", "danger")
            return redirect(url_for('main.page_changement_mot_de_passe'))
            
        # Vérification 3 : Le mot de passe est assez long (8 caractères min)
        if len(nouveau_mdp) < 8:
            flash("Pour des raisons de sécurité, votre mot de passe doit faire au moins 8 caractères.", "warning")
            return redirect(url_for('main.page_changement_mot_de_passe'))
            
        # TOUT EST BON ! On hache le nouveau mot de passe et on l'enregistre
        current_user.password_hash = generate_password_hash(nouveau_mdp, method='pbkdf2:sha256')
        db.session.commit()
        
        # ON FERME LA PORTE : On détruit le laissez-passer pour que personne ne puisse réutiliser la page
        session.pop('acces_autorise_page_secrete', None)
        
        flash("Félicitations ! Votre mot de passe Super-Admin a été changé avec succès.", "success")
        return redirect(url_for('main.tableau_de_bord')) # Redirige où tu veux (ex: la page des utilisateurs)
        
    # 3. AFFICHAGE DE LA PAGE (Quand tu arrives sur la page)
    return render_template('changement_mdp.html')

@main.route('/api/convertir_montant')
def convertir_montant():
    montant_str = request.args.get('montant', '0')
    try:
        montant = int(montant_str)
        if montant <= 0:
            return jsonify({'lettres': ''})
        # Convertit en français
        lettres = num2words(montant, lang='fr')
        return jsonify({'lettres': lettres.capitalize() + ' francs CFA'})
    except ValueError:
        return jsonify({'lettres': ''})