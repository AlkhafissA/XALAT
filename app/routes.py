import os
import zipfile
import json
from werkzeug.utils import secure_filename
from flask import send_file, make_response, abort
from flask import send_from_directory, abort
from datetime import datetime, timedelta
import io
from app.models import ArchiveDocument
from app.models import Bordereau 
from app.models import LettreNotification, LettreInvitation, Contrat, LettreInformation
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
from flask_mail import Message

from app.extensions import db, mail
from app.models import User, Candidat, Cotation, Offre, Historique, LoginAttempt, LogAction
from app.utils import clean_text, generer_lettre_agrement, num2words_fr, dessiner_entete_officiel

# Création du "Blueprint"
main = Blueprint('main', __name__)

# Seuls les PDF et les images sont acceptés !
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}

def fichier_est_autorise(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_action(action, cible):
    try:
        user_name = current_user.username if current_user.is_authenticated else "Système"
        nouveau_log = Historique(utilisateur=user_name, action=action, cible=cible)
        db.session.add(nouveau_log)
    except: pass

# --- ROUTES AUTHENTIFICATION ---

@main.route('/login', methods=['GET', 'POST'])
def login():
    # 1. On récupère l'IP du visiteur
    user_ip = request.remote_addr 
    
    # 2. TA LISTE BLANCHE (Ajoute tes IP ici entre guillemets et séparées par des virgules)
    IPS_AUTORISEES = [
        "127.0.0.1",     # Ton propre ordinateur (Localhost)
        "192.168.1.1",   # Exemple IP Bureau
        "41.82.10.25",   # Exemple IP Maison
    ]
    
    # 3. Vérification du blocage (On ignore si l'IP est dans la liste blanche)
    record = LoginAttempt.query.filter_by(ip_address=user_ip).first()
    
    if record and record.is_blocked and (user_ip not in IPS_AUTORISEES):
        # Vérification du délai de 15 minutes
        if datetime.utcnow() - record.last_attempt > timedelta(minutes=15):
            record.is_blocked = False
            record.attempts = 0
            db.session.commit()
        else:
            flash("Votre IP est temporairement restreinte pour sécurité.", "danger")
            return render_template('login.html')

    if request.method == 'POST':
        # --- PIÈGE POT DE MIEL DÉBOGAGE ---
        honeypot = request.form.get('confirm_email_address')
        if honeypot:
            # 1. On gère le record de blocage
            if not record:
                record = LoginAttempt(ip_address=user_ip, attempts=5, is_blocked=True)
                db.session.add(record)
            else:
                record.is_blocked = True
                record.attempts = 5
            
            # 2. On écrit le log SANS passer par la fonction log_action (Test direct)
            from app.models import LogAction # Import local pour être sûr
            alerte = LogAction(
                action="ALERTE_HONEYPOT", 
                details=f"IP: {user_ip} a rempli le champ invisible."
            )
            db.session.add(alerte)
            
            # 3. On force l'écriture immédiate
            try:
                db.session.commit()
                print("DEBUG: Log Honeypot enregistré avec succès en BDD")
            except Exception as e:
                db.session.rollback()
                print(f"DEBUG ERROR: Échec de l'enregistrement : {e}")
            
            return "Accès refusé. Système de sécurité activé.", 403
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        # CAS : SUCCÈS
        if user and check_password_hash(user.password_hash, password):
            session.pop('attempts', None)
            if record:
                db.session.delete(record)
                # --- AJOUT ICI ---
            session.permanent = True  # Active la limite de temps définie dans la config
            # ------------------
            
            login_user(user)
            db.session.commit()
            
            # ... (Tes redirections habituelles) ...
            return redirect(url_for('main.super_dashboard' if user.role == 'superadmin' else 'main.tableau_de_bord'))

        # CAS : ÉCHEC
        else:
            # IMMUNITÉ : Si c'est un SuperAdmin OU si l'IP est en liste blanche, on ne bloque pas
            if (user and user.role == 'superadmin') or (user_ip in IPS_AUTORISEES):
                log_action("Échec Connexion", f"Tentative sur {username} (IP Immunisée)")
                flash("Identifiant ou mot de passe incorrect.", "danger")
            
            else:
                # Blocage normal pour les autres
                if not record:
                    record = LoginAttempt(ip_address=user_ip, attempts=1)
                    db.session.add(record)
                else:
                    record.attempts += 1
                    record.last_attempt = datetime.utcnow()

                if record.attempts >= 5:
                    record.is_blocked = True
                    log_action("ALERTE_SECURITE", f"IP {user_ip} BANNIE (Cible: {username})")
                
                flash(f"Identifiant ou mot de passe incorrect ({record.attempts}/5).", "danger")
            
            db.session.commit()
                
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@main.route('/')
@login_required
def tableau_de_bord():
    liste = Candidat.query.order_by(Candidat.date_enregistrement.desc()).all()
    return render_template('dashboard.html', candidats=liste)

# --- ROUTES CANDIDATS ---

@main.route('/ajouter')
@login_required
def afficher_formulaire():
    return render_template('ajouter.html')

@main.route('/sauvegarder', methods=['POST'])
@login_required
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
    print("\n--- 🛠️ DEBUG : TENTATIVE DE TELECHARGEMENT ---")
    candidat = db.session.get(Candidat, id)
    
    print(f"Analyse du candidat en base -> Statut: '{candidat.statut}', Réf: '{candidat.ref_interne}'")
    
    if candidat.statut == "Retenu" and candidat.ref_interne:
        print("✅ Conditions OK. Lancement du téléchargement.")
        nom_fichier_relatif = generer_lettre_agrement(candidat, mode='final')
        filename = os.path.basename(nom_fichier_relatif)
        return redirect(url_for('main.secure_download', folder='agreement', filename=filename))
    else:
        print("❌ Conditions NON remplies. Pourquoi ?")
        if candidat.statut != "Retenu":
            print(f"  -> Le statut est '{candidat.statut}' au lieu de 'Retenu'")
        if not candidat.ref_interne:
            print(f"  -> La ref_interne est vide (None ou '')")
        print("----------------------------------------------\n")
        
        flash("Ce dossier n'est pas encore validé.", "danger")
        return redirect(url_for('main.tableau_de_bord'))

@main.route('/valider_agrement_final', methods=['POST'])
@login_required
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

        candidat.statut = "Retenu"
        db.session.commit()
        
        # On génère le PDF final
        pdf_path_relatif = generer_lettre_agrement(candidat, mode='final')
        filename = os.path.basename(pdf_path_relatif)
        
        # 👇 CHEMIN VERS LE COFFRE-FORT POUR LA PIÈCE JOINTE
        basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        chemin_absolu = os.path.join(basedir, 'stockage_prive', 'agreement', filename)
        
        try:
            msg = Message()
            msg.recipients = [candidat.email]
            msg.subject = "Félicitations : Votre Agrément (Validé)"
            msg.body = f"Bonjour,\n\nVotre demande a été validée.\nRef: {candidat.ref_interne}."
            
            with open(chemin_absolu, 'rb') as fp:
                msg.attach(f"Agrement_{candidat.nom_entreprise}.pdf", "application/pdf", fp.read())
            
            mail.send(msg)
            log_action("Validation Agrément & Email", candidat.nom_entreprise)
            flash("Dossier validé et agrément envoyé par email !", "success")
        except Exception as e:
            print(f"Erreur Mail: {str(e)}")
            flash("Dossier validé, mais l'envoi de l'email a échoué.", "warning")
            
    return redirect(url_for('main.tableau_de_bord'))

@main.route('/decision/<int:id>/<type_decision>')
@login_required
def decision(id, type_decision):
    candidat = db.session.get(Candidat, id)
    if candidat and type_decision == 'refuser':
        candidat.statut = "Refusé"
        log_action("Refus Candidature", candidat.nom_entreprise)
        db.session.commit()
    return redirect(url_for('main.tableau_de_bord'))

@main.route('/supprimer/<int:id>', methods=['POST']) # <-- AJOUTE methods=['POST']
@login_required
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
def nouvelle_cotation():
    candidats = Candidat.query.order_by(Candidat.nom_entreprise).all()
    return render_template('cotations_form.html', candidats=candidats, cotation=None)

@main.route('/modifier_cotation/<int:id>')
@login_required
def modifier_cotation(id):
    cotation = db.session.get(Cotation, id)
    candidats = Candidat.query.order_by(Candidat.nom_entreprise).all()
    return render_template('cotations_form.html', candidats=candidats, cotation=cotation)

@main.route('/sauvegarder_cotation', methods=['POST'])
@login_required
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
    
    db.session.commit()
    for i in range(1, 4):
        nom = request.form.get(f'candidat_{i}')
        mnt = request.form.get(f'montant_{i}')
        if nom and mnt:
           db.session.add(Offre(cotation_id=cotation.id, nom_candidat=nom, montant=int(mnt)))
    action = "Modification Cotation" if cotation_id else "Création Cotation"
    log_action(action, cotation.objet)
    db.session.commit()
    return redirect(url_for('main.liste_cotations'))

@main.route('/supprimer_cotation/<int:id>', methods=['POST']) # <-- AJOUTE methods=['POST']
@login_required
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
    offres = sorted(cotation.offres, key=lambda x: x.montant)
    gagnant = offres[0] if offres else None
    
    def fmt_date(dt): return dt.strftime('%d/%m/%Y à %Hh%M mn') if dt else "N/A"
    
    pdf = FPDF()
    
    def tableau_info(pdf_obj, titre_objet, date_reunion_str, is_attribution=False):
        pdf_obj.set_font("Arial", '', 10)
        def row(lbl, val, bold=False):
            x, y = pdf_obj.get_x(), pdf_obj.get_y()
            pdf_obj.multi_cell(70, 8, txt=clean_text(lbl), border=1)
            h = pdf_obj.get_y() - y
            pdf_obj.set_xy(x+70, y)
            if bold: pdf_obj.set_font("Arial",'B',10)
            pdf_obj.multi_cell(0, 8, txt=clean_text(val), border=1)
            pdf_obj.set_font("Arial",'',10)
            if pdf_obj.get_y() < y+h: pdf_obj.set_y(y+h)
            
        row("Désignation de l'AC", "MINISTERE DE LA CULTURE, DE L'ARTISANAT ET DU TOURISME")
        row("PRM :", "DIRECTION DE L'ADMINISTRATION GENERALE ET DE L'EQUIPEMENT")
        row("Objet de la COTATION :", clean_text(titre_objet).upper(), bold=True)
        row("Procédure :", "Demande de COTATION")
        if not is_attribution: row("Date et heure limite de dépôt :", fmt_date(cotation.date_limite), bold=True)
        row("Lieu de tenue de la séance :", clean_text(cotation.lieu), bold=True)
        row("Date et heure réunion :", date_reunion_str, bold=True)
    
    def commission(pdf_obj):
        pdf_obj.set_font("Arial", 'BU', 11); pdf_obj.cell(0, 8, "MEMBRES DE LA COMMISSION :", ln=1)
        pdf_obj.set_font("Arial", 'B', 10); pdf_obj.cell(50, 8, "Qualité", 1, 0, 'C'); pdf_obj.cell(90, 8, "Noms et Prénoms", 1, 0, 'C'); pdf_obj.cell(50, 8, "Signature", 1, 1, 'C')
        pdf_obj.set_font("Arial", '', 10)
        mbs = [("Président", cotation.president), ("Membre", cotation.membre1), ("Membre", cotation.membre2)]
        for q, n in mbs:
            pdf_obj.cell(50, 10, clean_text(q), 1)
            pdf_obj.set_font("Arial", 'B', 10)
            pdf.cell(90, 10, clean_text(n), 1)
            pdf.set_font("Arial", '', 10)
            pdf.cell(50, 10, "", 1, 1)

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
    
    dossier_pv = os.path.join(current_app.root_path, '..', 'stockage_prive', 'cotations')

    if not os.path.exists(dossier_pv):
        os.makedirs(dossier_pv)

    chemin_complet = os.path.join(dossier_pv, f"PV_{cotation.id}.pdf")
    pdf.output(chemin_complet)
    
    log_action("Téléchargement PV Cotation", cotation.objet)
    db.session.commit()

    return send_file(
        chemin_complet, 
        as_attachment=True, 
        download_name=f"PV_Cotation_{cotation.id}.pdf"
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
                    except: pass
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

@main.route('/super_dashboard')
@login_required
def super_dashboard():
    if current_user.role != 'superadmin': 
        flash("Accès réservé.", "danger")
        return redirect(url_for('main.tableau_de_bord'))
    
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
def creer_utilisateur():
    if current_user.role != 'superadmin': 
        return redirect(url_for('main.tableau_de_bord'))
    
    username = request.form.get('username')
    password = request.form.get('password')
    
    if User.query.filter_by(username=username).first():
        flash("Cet utilisateur existe déjà.", "warning")
    else:
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password_hash=hashed_pw, role='admin')
        db.session.add(new_user)
        log_action("Création Utilisateur", username)
        db.session.commit()
        flash(f"Utilisateur {username} créé avec succès.", "success")
        
    return redirect(url_for('main.super_dashboard'))

@main.route('/supprimer_utilisateur/<int:id>', methods=['POST']) # <-- AJOUTE methods=['POST']
@login_required
def supprimer_utilisateur(id):
    if current_user.role != 'superadmin': 
        return redirect(url_for('main.tableau_de_bord'))
    
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

@main.route('/reset_password/<int:id>')
@login_required
def reset_password(id):
    if current_user.role != 'superadmin':
        flash("Action non autorisée.", "danger")
        return redirect(url_for('main.tableau_de_bord'))
    
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

# --- ROUTE POUR LA PAGE DRPS  ---
@main.route('/drps', methods=['GET', 'POST'])
@login_required
def drps():
    if request.method == 'POST':
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
            except:
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
    # Affichage normal de la page (quand on clique sur l'onglet)
    # =========================================================
    
    candidats = Candidat.query.order_by(Candidat.nom_entreprise).all()
    
    # 1. On récupère les lettres depuis la base de données
    lettres_db = LettreInvitation.query.order_by(LettreInvitation.id.desc()).all()
    
    # ---> LE FAMEUX MOUCHARD EST ICI <---
    print(f"\n\n==== DIAGNOSTIC ==== j'ai trouvé {len(lettres_db)} lettres d'invitation dans la base !\n\n")
    
    # 2. On déballe le texte JSON pour que le tableau HTML puisse lire les dates et numéros
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

    # 3. On envoie TOUT au fichier HTML (les candidats ET les lettres)
    return render_template('drps.html', candidats=candidats, lettres=lettres_pour_tableau)

# ==========================================
# --- ROUTES : BORDEREAUX D'ENVOI ---
# ==========================================

@main.route('/bordereaux')
@login_required
def liste_bordereaux():
    bordereaux = Bordereau.query.order_by(Bordereau.id.desc()).all()
    return render_template('liste_bordereaux.html', bordereaux=bordereaux)

@main.route('/bordereaux/ajouter', methods=['POST'])
@login_required
def ajouter_bordereau():
    import json
    from datetime import datetime
    
    direction_name = request.form.get('direction_name')
    numero = request.form.get('numero')
    service_ref = request.form.get('service_ref')
    date_str = request.form.get('date_signature')
    observations = request.form.get('observations')
    
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
    
    # On sauvegarde dans la base de données
    nouveau_bordereau = Bordereau(
        direction_name=direction_name,
        numero=numero,
        service_ref=service_ref,
        date_signature=date_obj,
        observations=observations,
        dossiers_data=json.dumps(dossiers_list)
    )
    
    db.session.add(nouveau_bordereau)
    log_action("Ajout Bordereau", f"N° {numero}")
    db.session.commit()
    
    # --- MODIFICATION ICI ---
    flash("Bordereau enregistré avec succès !", "success")
    # On redirige vers le tableau des bordereaux au lieu du téléchargement PDF
    return redirect(url_for('main.liste_bordereaux'))

@main.route('/bordereaux/pdf/<int:id>')
@login_required
def download_bordereau_pdf(id):
    bordereau = Bordereau.query.get_or_404(id)
    buffer = io.BytesIO()
    
    data = {
        'direction': bordereau.direction_name.upper() if bordereau.direction_name else "DIRECTION...",
        'numero': bordereau.numero,
        'service_ref': bordereau.service_ref,
        'date': bordereau.date_signature.strftime("%d/%m/%Y"),
        'dossiers': bordereau.get_dossiers(),
        'observations': bordereau.observations
    }
    
    # On génère le PDF à la volée (en mémoire RAM)
    from app.utils import generer_pdf_bordereau
    generer_pdf_bordereau(buffer, data)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Bordereau_N{bordereau.numero}.pdf",
        mimetype='application/pdf'
    )

# --- NOUVEAU : ROUTE POUR VOIR LE SCAN DU BORDEREAU ---
@main.route('/bordereaux/voir_scan/<int:id>')
@login_required
def voir_scan_bordereau(id):
    bordereau = Bordereau.query.get_or_404(id)
    if bordereau.fichier_scanne:
        # On utilise notre super route sécurisée pour aller chercher le document !
        return redirect(url_for('main.secure_download', folder='scans', filename=bordereau.fichier_scanne))
    else:
        flash("Aucun fichier scanné n'a été uploadé pour ce bordereau.", "warning")
        return redirect(url_for('main.liste_bordereaux'))

@main.route('/bordereaux/supprimer/<int:id>', methods=['POST'])
@login_required
def supprimer_bordereau(id):
    bordereau = Bordereau.query.get_or_404(id)
    
    # OPTIONNEL MAIS CONSEILLÉ : Supprimer le fichier physique du scan s'il existe
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

@main.route('/bordereaux/export')
@login_required
def exporter_bordereaux():
    bordereaux = Bordereau.query.all()
    data = []
    for b in bordereaux:
        data.append({
            'Numéro': b.numero,
            'Service': b.service_ref,
            'Date Signature': b.date_signature.strftime("%d/%m/%Y"),
            'Nombre Dossiers': len(b.get_dossiers()),
            'Observations': b.observations
        })
    
    import pandas as pd
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Bordereaux')
        
    output.seek(0)
    log_action("Export Excel", "Liste des Bordereaux")
    db.session.commit()
    return send_file(output, download_name="Export_Bordereaux.xlsx", as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") 
            




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
    return render_template('liste_notifications.html', notifications=notifications, candidats=candidats)

@main.route('/notifications/ajouter', methods=['POST'])
@login_required
def ajouter_notification():
    prestataire_id = request.form.get('prestataire_id_notif')
    destinataire_nom = "Non renseignée"
    destinataire_adresse = ""
    destinataire_tel = ""
    
    if prestataire_id:
        candidat = db.session.get(Candidat, int(prestataire_id))
        if candidat:
            destinataire_nom = candidat.nom_entreprise
            lieu = f"{candidat.adresse or ''} {candidat.ville or ''}".strip()
            destinataire_adresse = lieu if lieu else "Adresse non renseignée"
            destinataire_tel = candidat.telephone or "Non renseigné"

    data = {
        'ref_service': request.form.get('ref_service'),
        'direction_name': request.form.get('direction_name'),
        'signataire': request.form.get('signataire'),
        'civilite_representant': request.form.get('civilite_representant', 'Monsieur le Directeur Général'),
        'objet_marche': request.form.get('objet_marche'),
        'immatriculation': request.form.get('immatriculation'),
        'date_commission': request.form.get('date_commission'),
        'num_ordre': request.form.get('num_ordre', '............'),
        'date_lettre': request.form.get('date_lettre'),
        'destinataire_nom': destinataire_nom,
        'destinataire_adresse': destinataire_adresse,
        'destinataire_tel': destinataire_tel
    }

    nouvelle_notif = LettreNotification(
        immatriculation=data['immatriculation'],
        objet_marche=data['objet_marche'],
        entreprise=destinataire_nom,
        form_data=json.dumps(data)
    )
    db.session.add(nouvelle_notif)
    log_action("Ajout Notification", data['immatriculation'])
    db.session.commit()
    
    # --- LA MODIFICATION EST ICI ---
    flash("Lettre de notification enregistrée avec succès !", "success")
    return redirect(url_for('main.liste_notifications'))

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
    
    if request.method == 'POST':
        # 1. On récupère les informations générales du formulaire
        immatriculation = request.form.get('immatriculation')
        objet_marche = request.form.get('objet_marche')
        num_ordre = request.form.get('num_ordre', '')
        ref_service = request.form.get('ref_service', '')
        date_lettre = request.form.get('date_lettre', '')
        signataire = request.form.get('signataire', '')
        date_heure_limite = request.form.get('date_heure_limite')
        adresse_depot = request.form.get('adresse_depot')
        lieu_ouverture = request.form.get('lieu_ouverture')
        direction_nom = request.form.get('direction_nom', "Direction de l'Administration Générale et de l'Equipement")

        # 2. On récupère la liste des prestataires cochés
        prestataires_ids = request.form.getlist('prestataires_ids')
        prestataires_selectionnes = []

        for p_id in prestataires_ids:
            candidat = db.session.get(Candidat, int(p_id))
            if candidat:
                rc_saisi = request.form.get(f'rc_{p_id}', 'Non renseigné')
                compte = request.form.get(f'compte_bancaire_{candidat.id}', '')
                
                prestataires_selectionnes.append({
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

    # === PARTIE GET (Affichage de la page) ===
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

    return render_template('creer_lettre_invitation.html', candidats=candidats, lettres=lettres_pour_tableau)

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
    candidats = Candidat.query.all()
    marches = LettreInvitation.query.all()
    
    # --- LA CORRECTION EST ICI ---
    # 1. On récupère les contrats bruts
    contrats_bruts = Contrat.query.order_by(Contrat.id.desc()).all()
    
    # 2. On attache manuellement le nom de l'entreprise à chaque contrat
    contrats_sauvegardes = []
    for c in contrats_bruts:
        cand = db.session.get(Candidat, c.candidat_id)
        # On lui invente un attribut temporaire qu'on pourra lire dans le HTML
        c.entreprise_nom = cand.nom_entreprise if cand else "Entreprise inconnue"
        contrats_sauvegardes.append(c)
    # -----------------------------
    if request.method == 'POST':
        candidat_id = request.form.get('candidat_id')
        candidat_gagnant = Candidat.query.get(candidat_id)
        
        marche_id = request.form.get('marche_id')
        marche_choisi = LettreInvitation.query.get(marche_id)
        
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

        # Extraction du RC et Compte depuis la lettre d'invitation
        lettre_data = {}
        if marche_choisi and marche_choisi.form_data:
            try:
                lettre_data = json.loads(marche_choisi.form_data)
            except:
                pass

        rc_final = '........................'
        compte_final = '...................................'

        prestataires_lettre = lettre_data.get('prestataires', [])
        for p in prestataires_lettre:
            if p.get('nom') == candidat_gagnant.nom_entreprise:
                if p.get('rc') and p.get('rc') != 'Non renseigné':
                    rc_final = p.get('rc')
                if p.get('compte'):
                    compte_final = p.get('compte')
                break

        # -------------------------------------------------------------
        # 2. ON SAUVEGARDE LE CONTRAT DANS LA BASE DE DONNÉES
        # -------------------------------------------------------------
        nouveau_contrat = Contrat(
            candidat_id=candidat_gagnant.id,
            objet_marche=marche_choisi.objet_marche,
            gestion_annee=gestion_annee,
            montant_chiffres=montant,
            montant_lettres=montant_lettres,
            financement=financement,
            imputation=imputation,
            programme=programme,
            comptable_assignataire=comptable,
            rc_candidat=rc_final,
            compte_bancaire=compte_final
        )
        db.session.add(nouveau_contrat)
        log_action("Ajout Contrat", candidat_gagnant.nom_entreprise)
        db.session.commit()

        # -------------------------------------------------------------
        # 3. ON GÉNÈRE LE PDF
        # -------------------------------------------------------------
        data_contrat = {
            'titulaire': candidat_gagnant.nom_entreprise or '........................',
            'ninea': candidat_gagnant.ninea or '........................',
            'rc': rc_final,                       
            'compte_bancaire': compte_final, 
            'adresse_candidat': getattr(candidat_gagnant, 'adresse', '........................'),   
            'tel_candidat': getattr(candidat_gagnant, 'telephone', '..........'),      
            'objet_marche': marche_choisi.objet_marche or '........................',      
            'gestion_annee': gestion_annee,
            'montant': montant,
            'montant_lettres': montant_lettres,
            'financement': financement,
            'imputation': imputation,
            'programme': programme,
            'comptable': comptable,
            'vocable': vocable,
            'numero': numero,
            'ref_service': ref_service,
            'date_lettre': date_lettre,
        }

        from app.utils import generer_pdf_contrat
        chemin_pdf = generer_pdf_contrat(data_contrat)
        nom_fichier = f"Contrat_{candidat_gagnant.nom_entreprise.replace(' ', '_')}.pdf"
        # --- NOUVEAU CODE À METTRE À LA PLACE ---
        flash("Contrat généré et sauvegardé avec succès !", "success")
        return redirect(url_for('main.creer_contrat'))

    # 4. On envoie les données au fichier HTML (Partie GET, on ne touche pas)
    return render_template('formulaire_contrat.html', candidats=candidats, marches=marches, contrats=contrats_sauvegardes)


@main.route('/telecharger_contrat/<int:id>')
@login_required
def telecharger_contrat(id):
    from app.utils import generer_pdf_contrat
    contrat = Contrat.query.get_or_404(id)
    # --- CORRECTION ICI AUSSI ---
    candidat = db.session.get(Candidat, contrat.candidat_id)
    # ----------------------------
    
    data_contrat = {
        'titulaire': candidat.nom_entreprise,
        'ninea': candidat.ninea,
        'rc': contrat.rc_candidat,                       
        'compte_bancaire': contrat.compte_bancaire, 
        'adresse_candidat': candidat.adresse,   
        'tel_candidat': candidat.telephone,      
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
   # Sécurité au cas où l'entreprise n'est pas trouvée
    nom_safe = candidat.nom_entreprise.replace(' ', '_') if candidat else 'Inconnu'
    nom_fichier = f"Contrat_{nom_safe}.pdf"
    return send_file(chemin_pdf, as_attachment=True, download_name=nom_fichier)


# --- NOUVEAU : ROUTE POUR VOIR LE SCAN DU CONTRAT ---
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
def supprimer_contrat(id):
    contrat = Contrat.query.get_or_404(id)
    
    # --- LA CORRECTION EST ICI ---
    # On va chercher le nom de l'entreprise manuellement pour le mouchard
    candidat = db.session.get(Candidat, contrat.candidat_id)
    nom_entreprise = candidat.nom_entreprise if candidat else f"Entreprise ID {contrat.candidat_id}"
    # -----------------------------

    # Suppression du fichier physique si existant
    if contrat.fichier_scanne:
        basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        chemin_fichier = os.path.join(basedir, 'stockage_prive', 'scans', contrat.fichier_scanne)
        if os.path.exists(chemin_fichier):
            os.remove(chemin_fichier)
            
    # On utilise notre variable sécurisée pour le log
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
    
    # On utilise simplement notre route sécurisée universelle
    # puisque tous les scans vont dans le dossier 'scans'
    return redirect(url_for('main.secure_download', folder='scans', filename=nom_fichier))
    
    # DEBUG : Copie ce qui s'affiche dans ton terminal pour comparer
    print(f"--- TENTATIVE DE LECTURE ---")
    print(f"Fichier cherché : {nom_fichier}")
    print(f"Chemin complet  : {chemin_complet}")
    print(f"Existe sur disque ? : {chemin_complet.exists()}")
    
    if not chemin_complet.exists():
        # Si le fichier n'est pas dans /scans, on teste dans /cotations par sécurité
        chemin_secours = base_path / 'stockage_prive' / 'cotations' / nom_fichier
        if chemin_secours.exists():
            return send_from_directory(chemin_secours.parent, nom_fichier)
        abort(404)

    return send_from_directory(dossier_scans, nom_fichier)
    
@main.route('/uploader_scan', methods=['POST'])
@login_required
def uploader_scan():
    print("--- DÉBUT DE L'UPLOAD ---")
    
    type_doc = request.form.get('type_doc')
    doc_id = request.form.get('doc_id')
    page_retour = request.form.get('page_retour')
    
    if 'scan_file' not in request.files:
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for(page_retour))
        
    file = request.files['scan_file']
    
    if file.filename == '':
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for(page_retour))

    if file:
        # ==========================================================
        # 👇 LE BOUCLIER DE SÉCURITÉ EST LÀ 👇
        if not fichier_est_autorise(file.filename):
            flash("Fichier non autorisé ! Seuls les PDF et images sont acceptés.", "danger")
            # Le mouchard enregistre la tentative et précise la cible !
            log_action("Alerte Sécurité", f"Tentative d'upload illégal : {file.filename} sur {type_doc} n°{doc_id}")
            db.session.commit()
            return redirect(url_for(page_retour))
        # 👆 FIN DU BOUCLIER 👆
        # ==========================================================
        filename = secure_filename(file.filename)
        nouveau_nom = f"{type_doc}_{doc_id}_{filename}"
        
        # 👇 ON ENREGISTRE MAINTENANT DANS LE DOSSIER PRIVÉ
        basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
        dossier_sauvegarde = os.path.join(basedir, 'stockage_prive', 'scans')
        os.makedirs(dossier_sauvegarde, exist_ok=True)
        
        
        chemin_complet = os.path.join(dossier_sauvegarde, nouveau_nom)
        file.save(chemin_complet)
        
        # --- MISE À JOUR BASE DE DONNÉES ---
        if type_doc == 'lettre_invitation':
            from app.models import LettreInvitation
            doc = LettreInvitation.query.get(doc_id)
            if doc: 
                doc.fichier_scanne = nouveau_nom
                db.session.commit()
                
        elif type_doc == 'contrat':
            from app.models import Contrat
            doc = Contrat.query.get(doc_id)
            if doc: 
                doc.fichier_scanne = nouveau_nom
                db.session.commit()
        
        elif type_doc == 'lettre_information':
            from app.models import LettreInformation
            doc = LettreInformation.query.get(doc_id)
            if doc: 
                doc.fichier_scanne = nouveau_nom
                db.session.commit()
                
        elif type_doc == 'lettre_notification':
            from app.models import LettreNotification
            doc = LettreNotification.query.get(doc_id)
            if doc: 
                doc.fichier_scanne = nouveau_nom
                db.session.commit()
                
        elif type_doc == 'bordereau':
            from app.models import Bordereau
            doc = Bordereau.query.get(doc_id)
            if doc: 
                doc.fichier_scanne = nouveau_nom
                db.session.commit()
           
        elif type_doc == 'pv_attribution':
            from app.models import ProcesVerbal
            doc = ProcesVerbal.query.get(doc_id)
            if doc:
                doc.fichier_scanne = nouveau_nom
                db.session.commit()  
                
        elif type_doc == 'cotation':
            from app.models import Cotation
            doc = Cotation.query.get(doc_id)
            if doc:
                doc.fichier_scanne = nouveau_nom
                db.session.commit()  
                      
        elif type_doc == 'agrement':
            from app.models import Candidat
            doc = Candidat.query.get(doc_id)
            if doc:
                doc.fichier_scanne = nouveau_nom
                db.session.commit()
        # =========================================================
        # --- NOUVEAU : AJOUT AUTOMATIQUE AUX ARCHIVES GLOBALES ---
        # =========================================================
        
        # 1. On récupère la référence du document s'il en a une, sinon on génère un nom par défaut
        ref_archive = getattr(doc, 'reference', f"{type_doc.upper()}-{doc_id}")
        
        # 2. On rend le type joli pour le tableau 
        type_formate = type_doc.replace('_', ' ').title()
        
        # 3. On enregistre dans la table des archives
        nouvelle_archive = ArchiveDocument(
            reference=ref_archive,
            type_document=type_formate,
            nom_fichier=nouveau_nom
        )
        db.session.add(nouvelle_archive)
        
        # 👇 ON PLACE LE RADAR JUSTE AVANT LE DERNIER COMMIT 👇
        log_action("Upload Scan", f"{type_formate} ({ref_archive})")
        
        db.session.commit() # Ce commit valide l'archive ET l'historique d'un seul coup
        
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
def upload_archive():
    from app.models import ArchiveDocument
    
    if 'fichier' not in request.files:
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for('main.page_archives'))
        
    file = request.files['fichier']
    if file.filename == '':
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for('main.page_archives'))

    if file:
    # ==========================================================
        # 👇 LE BOUCLIER DE SÉCURITÉ EST LÀ 👇
        if not fichier_est_autorise(file.filename):
            flash("Fichier non autorisé ! Seuls les PDF et images sont acceptés.", "danger")
            # Le mouchard enregistre la tentative de piratage
            log_action("Alerte Sécurité", f"Tentative d'upload illégal : {file.filename}")
            db.session.commit()
            # On renvoie le pirate d'où il vient sans sauvegarder le fichier
            return redirect(url_for('main.page_archives'))
        # 👆 FIN DU BOUCLIER 👆
        # ==========================================================
        filename = secure_filename(file.filename)
        dossier_sauvegarde = os.path.join(current_app.root_path, '..', 'stockage_prive', 'archives')
        os.makedirs(dossier_sauvegarde, exist_ok=True)
        
        chemin_complet = os.path.join(dossier_sauvegarde, filename)
        file.save(chemin_complet)
        
        # --- CORRECTION ICI : On stocke les infos dans des variables ---
        reference_saisie = request.form.get('reference')
        type_doc = request.form.get('type_document')
        
        nouvelle_archive = ArchiveDocument(
            reference=reference_saisie,
            type_document=type_doc,
            nom_fichier=filename
        )
        db.session.add(nouvelle_archive)
        
        # 👇 Maintenant le mouchard comprend les variables ! 👇
        log_action("Ajout Archive", f"{type_doc} ({reference_saisie})")
        
        db.session.commit()
        
        flash("Document archivé avec succès !", "success")
        return redirect(url_for('main.page_archives'))

@main.route('/telecharger_archive/<nom_fichier>')
@login_required
def telecharger_archive(nom_fichier):
    import os
    from flask import send_from_directory, current_app, abort
    
    # 👇 ON AJOUTE LE RADAR ICI 👇
    log_action("Consultation Archive", nom_fichier)
    db.session.commit()
    
    dossier_archives = os.path.join(current_app.root_path, 'static', 'uploads', 'archives')
    dossier_scans = os.path.join(current_app.root_path, 'static', 'uploads', 'scans')
    
    # 1. On regarde d'abord si le fichier a été uploadé manuellement (dans 'archives')
    if os.path.exists(os.path.join(dossier_archives, nom_fichier)):
        return send_from_directory(dossier_archives, nom_fichier)
        
    # 2. Sinon, on regarde s'il vient d'un scan automatique (dans 'scans')
    elif os.path.exists(os.path.join(dossier_scans, nom_fichier)):
        return send_from_directory(dossier_scans, nom_fichier)
        
    # 3. Si on ne le trouve nulle part, on affiche une erreur 404
    else:
        abort(404)
        
        
@main.route('/supprimer_archive/<int:id>', methods=['POST']) # <-- AJOUTE methods=['POST']
@login_required
def supprimer_archive(id):
    
    archive = db.session.get(ArchiveDocument, id)
    if archive:
        # 1. On cherche si le fichier physique est dans le dossier des archives manuelles
        dossier_archives = os.path.join(current_app.root_path, 'static', 'uploads', 'archives')
        chemin_fichier = os.path.join(dossier_archives, archive.nom_fichier)
        
        # S'il y est, on le supprime physiquement pour libérer de l'espace
        if os.path.exists(chemin_fichier):
            try:
                os.remove(chemin_fichier)
            except Exception as e:
                print(f"Erreur lors de la suppression du fichier physique : {e}")
        
        # (Si le fichier est dans 'scans', on ne le supprime pas physiquement pour ne pas casser l'agrément d'origine)
# 👇 AJOUTE CETTE LIGNE (avant de le supprimer) 👇
        log_action("Suppression Archive", f"{archive.type_document} ({archive.reference})")
        # 2. On supprime la ligne dans la base de données
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

@main.route('/secure_download/<folder>/<path:filename>')
@login_required
def secure_download(folder, filename):
    ALLOWED_FOLDERS = ['archives', 'cotations', 'scans', 'drps', 'agreement']
    if folder not in ALLOWED_FOLDERS:
        abort(403)
    
    root_dir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    
    # 1. On cherche d'abord dans le dossier demandé (ex: cotations)
    target_dir = os.path.join(root_dir, 'stockage_prive', folder)
    file_path = os.path.join(target_dir, filename)
    
    # 2. Si non trouvé, on cherche dans le dossier 'scans' (là où uploader_scan enregistre tout)
    if not os.path.exists(file_path):
        target_dir = os.path.join(root_dir, 'stockage_prive', 'scans')
        file_path = os.path.join(target_dir, filename)

    # 3. Si toujours rien, 404
    if not os.path.exists(file_path):
        print(f"DEBUG : Fichier introuvable nulle part -> {filename}")
        abort(404)
        
    return send_from_directory(target_dir, filename)