from reportlab.lib.units import cm
import os
import io
from flask import send_file
from fpdf import FPDF
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Rect, Polygon
from reportlab.graphics import renderPDF
from reportlab.lib.colors import black

import datetime

try:
    from num2words import num2words
except ImportError:
    def num2words(number, lang='fr'): return str(number)

def clean_text(text):
    if not text: return ""
    text = str(text)
    replacements = {
        '\u2019': "'", '\u2018': "'", 'â€™': "'", '`': "'",
        '\u201c': '"', '\u201d': '"', '\u2013': '-', '\u2014': '-',
        '\u2026': '...', '\u00A0': ' ', 'Å“': 'oe', 'Å’': 'OE', 'â‚¬': 'Euros', 'Â°': 'o' 
    }
    for k, v in replacements.items(): text = text.replace(k, v)
    return text

def formater_date_fr(date_str):
    """Transforme '2025-02-06' ou '06/02/2025' en '06 février 2025'"""
    if not date_str or date_str == '...':
        return "..."
    
    mois_fr = {
        "01": "janvier", "02": "février", "03": "mars", "04": "avril",
        "05": "mai", "06": "juin", "07": "juillet", "08": "août",
        "09": "septembre", "10": "octobre", "11": "novembre", "12": "décembre"
    }
    
    try:
        # Si la date vient d'un calendrier HTML (format YYYY-MM-DD)
        if "-" in date_str:
            annee, mois_num, jour = date_str.split("-")
        # Si la date est tapée à la main (format DD/MM/YYYY)
        elif "/" in date_str:
            jour, mois_num, annee = date_str.split("/")
        else:
            return date_str # Si format inconnu, on laisse tel quel
            
        nom_mois = mois_fr.get(mois_num, mois_num)
        return f"{jour} {nom_mois} {annee}"
    except Exception:
        return date_str

def num2words_fr(number):
    try:
        return num2words(number, lang='fr')
    except:
        return str(number)

def dessiner_entete_officiel(pdf, afficher_direction=False):
    pdf.set_y(10)
    pdf.set_font("Times", 'B', 14)
    pdf.cell(0, 6, txt=clean_text("République du Sénégal"), ln=1, align='C')
    pdf.set_font("Times", 'I', 11)
    pdf.cell(0, 6, txt="Un Peuple - Un But - Une Foi", ln=1, align='C')
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 11)
    pdf.multi_cell(0, 5, txt=clean_text("MINISTÈRE DE LA CULTURE, DE\nL'ARTISANAT ET DU TOURISME"), align='C')
    if afficher_direction:
        pdf.ln(1)
        pdf.set_font("Arial", 'B', 10)
        pdf.multi_cell(0, 5, txt=clean_text("DIRECTION DE L'ADMINISTRATION\nGENERALE ET DE L'EQUIPEMENT"), align='C')
    pdf.set_xy(80, pdf.get_y()+2)
    pdf.cell(50, 0, "", "T")
    pdf.ln(5)

def generer_lettre_agrement(candidat, mode='vierge'):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=5)

    genre = candidat.genre if candidat.genre else "Homme"
    nom_entreprise = clean_text(candidat.nom_entreprise if candidat.nom_entreprise else "")
    telephone = clean_text(candidat.telephone if candidat.telephone else "")
    adresse_ent = clean_text(candidat.adresse if candidat.adresse else "")
    ville_ent = clean_text(candidat.ville if candidat.ville else "Dakar")

    if mode == 'final':
        val_ref_interne = f"N° {clean_text(candidat.ref_interne)}" 
        val_titre_signataire = clean_text(candidat.titre_signataire if candidat.titre_signataire else "Le Directeur")
        val_date_sign = clean_text(candidat.date_signature_agrement)
        val_ref_sr = clean_text(candidat.ref_lettre_candidat)
        nom_fichier = f"Agrement_FINAL_{candidat.id}_{candidat.nom_entreprise}.pdf"
    else:
        val_ref_interne = "N° ............ ...................................."
        val_titre_signataire = "Le Directeur" 
        val_date_sign = "........................"
        val_ref_sr = ".....-.....-........"
        nom_fichier = f"Agrement_VIERGE_{candidat.id}_{candidat.nom_entreprise}.pdf"

    if genre.lower() == 'femme':
        civilite = "Madame la Directrice"
        titre_destinataire = "Madame la Directrice"
    else:
        civilite = "Monsieur le Directeur"
        titre_destinataire = "Monsieur le Directeur"

  # --- DESSIN GRAPHIQUE ---
    x_flag_top = 43; y_flag_top = 10; w_band_top = 8; h_flag_top = 14 
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_flag_top, y_flag_top, w_band_top, h_flag_top, 'F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_flag_top + w_band_top, y_flag_top, w_band_top, h_flag_top, 'F')
    
    # 🌟 CENTRAGE PARFAIT - GRAND DRAPEAU
    # Ajuste ce chiffre : si l'étoile est trop basse, mets 4.0 ou 3.5. Si elle est trop haute, mets 5.0.
    decalage_y = 4.5 
    pdf.set_xy(x_flag_top + w_band_top, y_flag_top + decalage_y); 
    pdf.set_text_color(0, 140, 60); pdf.set_font("ZapfDingbats", '', 11) 
    pdf.cell(w_band_top, 5, chr(72), align='C') # Hauteur de cellule fixée à 5 pour mieux contrôler
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_flag_top + (w_band_top*2), y_flag_top, w_band_top, h_flag_top, 'F')

    y_start_text = y_flag_top + h_flag_top + 5 
    pdf.set_y(y_start_text); pdf.set_text_color(0, 0, 0); pdf.set_font("Times", 'B', 14)
    pdf.cell(90, 6, txt=clean_text("République du Sénégal"), ln=1, align='C')
    pdf.set_font("Times", 'I', 11); pdf.cell(90, 6, txt="Un Peuple - Un But - Une Foi", ln=1, align='C')
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(0, 100, 0)
    pdf.multi_cell(90, 4, txt=clean_text("MINISTÈRE DE LA CULTURE, DE\nL'ARTISANAT ET DU TOURISME"), align='C')
    
    y_barre = pdf.get_y() + 1; w_barre_total = 44; x_barre_start = 33; w_segment = w_barre_total / 3; h_barre = 1.5
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_barre_start, y_barre, w_segment, h_barre, 'F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_barre_start + w_segment, y_barre, w_segment, h_barre, 'F')
    
    # 🌟 CENTRAGE PARFAIT - PETITE BARRE TRICOLORE
    # Pareil ici : on ajuste précisément le décalage (en négatif car on remonte par rapport à la barre)
    decalage_y_barre = -1.2 
    pdf.set_xy(x_barre_start + w_segment, y_barre + decalage_y_barre); 
    pdf.set_font("ZapfDingbats", '', 5.5); pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, chr(72), align='C'); 
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, 'F')
    pdf.set_xy(10, y_barre + 3); pdf.set_font("Arial", 'B', 30); pdf.set_text_color(0, 100, 0)
    pdf.cell(90, 12, txt="MCAT", ln=1, align='C')
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 9)
    
    pdf.set_xy(105, y_start_text + 5); pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, txt=val_ref_interne, ln=1, align='C')
    pdf.ln(8); pdf.set_x(105); pdf.cell(0, 5, txt=f"Dakar, le {val_date_sign}", ln=1, align='C')
    pdf.ln(15); pdf.set_x(105); pdf.set_font("Arial", 'B', 16); pdf.multi_cell(0, 6, txt=val_titre_signataire, align='C')

    pdf.set_left_margin(20); pdf.set_y(95); pdf.set_font("Arial", 'B', 11); pdf.cell(20, 6, txt="Objet :", align='L')
    pdf.set_font("Arial", '', 11); pdf.cell(0, 6, txt=clean_text("Votre demande d'agrément"), ln=1)
    pdf.set_font("Arial", 'B', 11); pdf.cell(25, 6, txt=clean_text("Référence :"), align='L')
    pdf.set_font("Arial", '', 11); pdf.cell(0, 6, txt=f"Votre lettre SR/{val_ref_sr}", ln=1); pdf.ln(6)
    pdf.cell(0, 6, txt=f"{civilite},", ln=1); pdf.ln(4)

    texte_corps = f"""J'accuse réception de votre lettre, citée en référence, par laquelle vous sollicitez un agrément pour les services que vous proposez.
En retour, je vous informe que votre entreprise est agréée et enregistrée dans la base de données de la Direction de l'Administration Générale et de l'Equipement.

Je vous prie de croire, {civilite}, à l'assurance de ma considération distinguée."""

    pdf.multi_cell(0, 6, txt=clean_text(texte_corps)); pdf.ln(5) 
    y_actuel = pdf.get_y(); pdf.set_xy(20, y_actuel); pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 5, txt="A", ln=1, align='L'); pdf.cell(0, 5, txt=f"{titre_destinataire} de", ln=1, align='L')
    pdf.cell(0, 5, txt=nom_entreprise.upper(), ln=1, align='L')
    if adresse_ent:
        pdf.set_font("Arial", '', 11); pdf.cell(0, 5, txt=adresse_ent, ln=1, align='L')
    pdf.set_font("Arial", 'B', 11); pdf.cell(0, 5, txt=f"{ville_ent} - SENEGAL", ln=1, align='L')
    pdf.set_font("Arial", '', 11)
    if telephone: pdf.cell(0, 5, txt=f"Tel: {telephone}", ln=1, align='L')

    pdf.ln(5)
    
    # 1. On écrit le titre "Ampliation"
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 5, txt="Ampliation :", ln=1, align='L')

    # 2. Le réglage pour "- CPM"
    pdf.ln(7)      # <--- AJOUTE ÇA : Petit saut vertical de 2mm pour détacher
    pdf.set_x(35)  # <--- AJOUTE ÇA : On décale le curseur à 30mm du bord gauche (au lieu de 10)

    # 3. On écrit "- CPM" (qui sera donc décalé)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 5, txt="- CPM", ln=1, align='L')

    # CHANGE LE -22 EN -30 (ou -35 pour monter encore plus haut)
    pdf.set_y(-25)  
    
    # Le reste ne change pas, la ligne va suivre automatiquement
    pdf.set_draw_color(0, 0, 0)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(1)
    
    pdf.set_font("Arial", 'I', 8)
    texte_pied = "Ministère de la Culture, de l'Artisanat et du Tourisme\nRoute des Almadies - BP : 4049 Dakar- Sénégal\nTél. : 33 869 15 51 - Fax : 33 826 07 77 - Email: ministere@tourisme.gouv.sn"
    
    pdf.multi_cell(0, 4, txt=clean_text(texte_pied), align='C')

   # --- ENREGISTREMENT SÉCURISÉ ---
    # On remonte à la racine du projet pour atteindre 'stockage_prive'
    basedir = os.path.abspath(os.path.join(current_app.root_path, '..'))
    dossier_cible = os.path.join(basedir, 'stockage_prive', 'agreement')
    
    # Création du dossier s'il n'existe pas
    if not os.path.exists(dossier_cible):
        os.makedirs(dossier_cible)

    chemin_complet = os.path.join(dossier_cible, nom_fichier)
    
    # Génération du PDF
    pdf.output(chemin_complet)

    # On retourne uniquement le nom du fichier
    # (Tes routes s'occuperont de construire le chemin complet)
    return nom_fichier

# ... (Tout ton code existant reste au dessus) ...

import math
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, Polygon

# ==========================================
# 1. FONCTIONS DE DESSIN POUR LES DRAPEAUX ET ÉTOILES
# ==========================================

def dessiner_etoile(cx, cy, rayon, couleur):
    """Dessine une étoile parfaite à 5 branches"""
    points = []
    r_in = rayon * 0.382 
    for i in range(10):
        angle = i * (math.pi / 5) - (math.pi / 2)
        r = rayon if i % 2 == 0 else r_in
        points.extend([cx + r * math.cos(angle), cy - r * math.sin(angle)])
    return Polygon(points, fillColor=colors.HexColor(couleur), strokeColor=None)

def dessiner_drapeau():
    width = 1.6 * cm; height = 1.1 * cm; w_band = width / 3
    d = Drawing(width, height)
    d.add(Rect(0, 0, w_band, height, fillColor=colors.HexColor('#00853F'), strokeColor=None))
    d.add(Rect(w_band, 0, w_band, height, fillColor=colors.HexColor('#FDEF42'), strokeColor=None))
    d.add(Rect(w_band * 2, 0, w_band, height, fillColor=colors.HexColor('#E31B23'), strokeColor=None))
    d.add(dessiner_etoile(w_band * 1.5, height / 2, w_band * 0.35, '#00853F'))
    return d

def dessiner_petite_barre():
    width = 4.4 * cm; height = 0.15 * cm; w_band = width / 3
    d = Drawing(width, height)
    d.add(Rect(0, 0, w_band, height, fillColor=colors.HexColor('#00853F'), strokeColor=None))
    d.add(Rect(w_band, 0, w_band, height, fillColor=colors.HexColor('#FDEF42'), strokeColor=None))
    d.add(Rect(w_band * 2, 0, w_band, height, fillColor=colors.HexColor('#E31B23'), strokeColor=None))
    d.add(dessiner_etoile(width / 2, height / 2, height * 0.45, '#00853F'))
    return d

def generer_pdf_bordereau(buffer, data):
    # Initialisation du document
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1*cm, leftMargin=1.5*cm,
                            topMargin=0.5*cm, bottomMargin=1*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # =========================================================================
    # METS TOUS LES STYLES EXACTEMENT ICI (AVANT DE COMMENCER À CRÉER DU TEXTE)
    # =========================================================================
    
    # 1. Tes anciens styles (nécessaires pour éviter l'erreur Pylance ligne 368)
    style_normal = ParagraphStyle(name='Times', parent=styles['Normal'], fontName='Times-Roman', fontSize=10, leading=12)
    style_center_bold = ParagraphStyle(name='CenterBold', parent=style_normal, alignment=TA_CENTER, fontName='Times-Bold')
    style_center_italic = ParagraphStyle(name='CenterItalic', parent=style_normal, alignment=TA_CENTER, fontName='Times-Italic', fontSize=9)
    style_red_bold = ParagraphStyle(name='RedBold', parent=style_center_bold, textColor=colors.black)
    style_num_right = ParagraphStyle(name='NumRight', parent=style_normal, alignment=TA_RIGHT, fontName='Times-Bold', textColor=colors.black, fontSize=11)
    style_date_right = ParagraphStyle(name='DateRight', parent=style_normal, alignment=TA_RIGHT, fontName='Times-Bold')
    
    # 2. Les nouveaux styles sur-mesure pour le super en-tête MCAT
    style_rep = ParagraphStyle(name='Rep', fontName='Times-Bold', fontSize=15, alignment=TA_CENTER, textColor=colors.black)
    style_devise = ParagraphStyle(name='Dev', fontName='Times-Italic', fontSize=12, alignment=TA_CENTER, textColor=colors.HexColor('#000033'))
    style_min = ParagraphStyle(name='Min', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#006400'), alignment=TA_CENTER, leading=11)
    style_mcat = ParagraphStyle(name='MCAT', fontName='Helvetica-Bold', fontSize=28, textColor=colors.HexColor('#006400'), alignment=TA_CENTER, leading=30)
    style_dir = ParagraphStyle(name='Dir', fontName='Helvetica-Bold', fontSize=9, textColor=colors.black, alignment=TA_CENTER, leading=13)
    
    # =========================================================================
    # FIN DES STYLES, ON COMMENCE À CONSTRUIRE LE DOCUMENT
    # =========================================================================
    # --- COLONNE GAUCHE (Le design exact) ---
    drapeau = dessiner_drapeau()
    txt_republique = Paragraph("République du Sénégal", style_rep)
    txt_devise = Paragraph("Un Peuple - Un But - Une Foi", style_devise)
    txt_ministere = Paragraph("MINISTÈRE DE LA CULTURE, DE<br/>L'ARTISANAT ET DU TOURISME", style_min)
    petite_barre = dessiner_petite_barre()
    txt_mcat = Paragraph("MCAT", style_mcat)
    
    # On force le retour à la ligne après "GENERALE ET" pour correspondre exactement à l'image
    direction_texte = data.get('direction', "DIRECTION DE L'ADMINISTRATION GENERALE ET DE L'EQUIPEMENT")
    direction_texte = direction_texte.replace(" GENERALE ET DE ", " GENERALE ET<br/>DE ")
    txt_direction = Paragraph(direction_texte, style_dir)

    # Empilement avec les espacements précis
    col_gauche = [
        drapeau, Spacer(1, 0.2*cm),
        txt_republique, Spacer(1, 0.1*cm),
        txt_devise, Spacer(1, 0.10*cm),
        txt_ministere, Spacer(1, 0.1*cm),
        petite_barre, Spacer(1, 0.1*cm),
        txt_mcat, Spacer(1, 0.1*cm),
        txt_direction
    ]
    
    # --- COLONNE DROITE (Numéro et Date) ---
    style_droite = ParagraphStyle(
        name='StyleDroite', 
        fontName='Helvetica-Bold', 
        fontSize=11, 
        textColor=colors.black, 
        alignment=TA_LEFT,
        leftIndent=3*cm  # ---> AJOUTE CECI : ça pousse le texte de 2 cm vers la droite
    )
    
    ref_complete = f"N° {data.get('numero', '')} {data.get('service_ref', '')}"
    
    txt_numero = Paragraph(ref_complete, style_droite)
    txt_date = Paragraph(f"Dakar, le {data.get('date', '')}", style_droite)

    col_droite = [
        Spacer(1, 1.7*cm),
        txt_numero,
        Spacer(1, 1.5*cm),
        txt_date
    ]
    
    # --- ASSEMBLAGE ---
    # On gère l'alignement des éléments de gauche
    table_gauche = Table([[item] for item in col_gauche], colWidths=[9.5*cm])
    table_gauche.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'), 
        ('VALIGN', (0,0), (-1,-1), 'TOP'), 
        ('LEFTPADDING', (0,0), (-1,-1), 0), 
        ('BOTTOMPADDING', (0,0), (-1,-1), 0.5) # Espacement réduit entre les éléments du tableau
    ]))

    # L'en-tête global
    header_table = Table([[table_gauche, col_droite]], colWidths=[9.5*cm, 9.5*cm])
    
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'), 
        ('ALIGN', (1,0), (1,-1), 'RIGHT'), 
        
        # ---> C'EST CETTE LIGNE QUI FAIT TOUT LE TRAVAIL <---
        # On applique un padding négatif sur la colonne 0 (celle de gauche)
        ('LEFTPADDING', (0,0), (0,-1), -1.4*cm), 
        
        ('LEFTPADDING', (1,0), (1,-1), 0),
        ('RIGHTPADDING', (1,0), (1,-1), 0.5*cm) 
    ]))

    elements.append(header_table)

    # La suite de ton document...
    # doc.build(elements)
    # --- TITRE ET DESTINATAIRE ---
    
    # On récupère le destinataire (avec une valeur de sécurité au cas où)
   # Dans utils.py, remplace la ligne par ça :
    destinataire_texte = data.get('destinataire', 'TOTO LE TESTEUR')

    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph("<b>BORDEREAU D’ENVOI</b>", ParagraphStyle('TitreGros', parent=style_center_bold, fontSize=16)))
    elements.append(Paragraph("-----------------------------------", style_center_bold))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph("<b>A</b>", style_center_bold))
    
    # ✅ ICI on utilise la variable destinataire_texte
    elements.append(Paragraph(destinataire_texte, ParagraphStyle('Dest', parent=style_center_bold, fontSize=11)))
    
    elements.append(Spacer(1, 0.5*cm))

    # --- LE TABLEAU ---
    h_ordre = Paragraph("<b>N°<br/>d’ordre</b>", style_center_bold)
    h_design = Paragraph("<b>Désignation</b>", style_center_bold)
    h_nombre = Paragraph("<b>Nombre</b>", style_center_bold)
    h_obs = Paragraph("<b>Observations</b>", style_center_bold)
    
    table_data = [[h_ordre, h_design, h_nombre, h_obs]]
    
    dossiers = data['dossiers']
    total_count = len(dossiers)
    
    style_cell_left = ParagraphStyle('CellLeft', parent=style_normal, alignment=TA_LEFT, leading=14)
    
    # MODIFICATION 3 : Le style pour le nombre total devient noir
    style_red_count = ParagraphStyle('RedCount', parent=style_center_bold, textColor=colors.black, fontSize=12)
    style_obs = ParagraphStyle('Obs', parent=style_normal, alignment=TA_CENTER, fontSize=12)

    for index, dossier in enumerate(dossiers):
        num_ordre = str(index + 1)
        
        # --- C'EST ICI QUE TU APPRENDS LA TECHNIQUE ---
        # 1. On récupère ce que l'utilisateur a tapé (ex: T_DAGE_208)
        ref_saisie = dossier['ref']
        
        # 2. On fabrique la phrase finale en collant les morceaux (f-string)
        # f"N°{ref_saisie} ;"  -> Cela va donner : N°T_DAGE_208 ;
        reference_finale = f"N°{ref_saisie} ;"

        # 3. On insère ça dans le texte du tableau
        texte_designation = f"""-Demande de Renseignements et de Prix Restreinte ayant pour objet : 
        « {dossier['objet']} »<br/>
        {reference_finale}"""
        
        p_designation = Paragraph(texte_designation, style_cell_left)
        # ... la suite du code reste pareille ...
        
        if index == 0:
            str_total = f"{total_count:02d}"
            p_nombre = Paragraph(str_total, style_red_count)
            p_obs = Paragraph(data['observations'], style_obs)
            row = [num_ordre, p_designation, p_nombre, p_obs]
        else:
            row = [num_ordre, p_designation, '', '']
            
        table_data.append(row)

    # Ligne TOTAL
    p_total_txt = Paragraph("<b>TOTAL</b>", ParagraphStyle('Total', parent=style_normal, fontName='Times-Bold', fontSize=11))
    str_total_final = f"{total_count:02d}"
    p_total_val = Paragraph(str_total_final, style_red_count)
    
    table_data.append([p_total_txt, '', p_total_val, ''])

    # --- STYLE DU TABLEAU ---
    col_widths = [2*cm, 10.5*cm, 2*cm, 4*cm]
    t = Table(table_data, colWidths=col_widths)
    
    orange_header = colors.HexColor('#F4B084') 
    
    style_cmds = [
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), orange_header),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,1), (1,-2), 'LEFT'),
        ('LEFTPADDING', (1,1), (1,-2), 10),
        ('RIGHTPADDING', (1,1), (1,-2), 10),
        ('TOPPADDING', (1,1), (1,-2), 10),
        ('BOTTOMPADDING', (1,1), (1,-2), 10),
        ('SPAN', (0,-1), (1,-1)),
        ('ALIGN', (0,-1), (0,-1), 'LEFT'),
        ('LEFTPADDING', (0,-1), (0,-1), 10),
        ('FONTNAME', (0,-1), (-1,-1), 'Times-Bold'),
    ]

    if total_count > 0:
        style_cmds.append(('SPAN', (2, 1), (2, total_count))) 
        style_cmds.append(('SPAN', (3, 1), (3, total_count)))
        style_cmds.append(('VALIGN', (2, 1), (2, total_count), 'MIDDLE'))
        style_cmds.append(('VALIGN', (3, 1), (3, total_count), 'MIDDLE'))

    t.setStyle(TableStyle(style_cmds))
    
    elements.append(t)
    doc.build(elements)

from fpdf import FPDF
import os
import io

def generer_pdf_lettre_information(buffer, data):
    """
    Génère la Lettre d'Information au format PDF avec FPDF2
    Syntaxe 100% modernisée (new_x, new_y, style='F')
    """
    # ==========================================
    # 🛠️ 1. CLASSE POUR LE PIED DE PAGE AUTOMATIQUE
    # ==========================================
    class PDFInformation(FPDF):
        def footer(self):
            # Positionnement à 25 mm du bas
            self.set_y(-25)
            # Ligne verte
            self.set_draw_color(145, 190, 100)  
            self.set_line_width(1.5)            
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(3)
            # Textes
            self.set_text_color(0, 0, 0)
            self.set_font("Times", '', 11) 
            # (On n'a pas besoin de clean_text ici car on maîtrise ces chaînes en dur)
            self.cell(0, 5, txt="Ministère de la Culture, de l'Artisanat et du Tourisme,", align='C', new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 5, txt="Route des Almadies, Dakar Sénégal", align='C', new_x="LMARGIN", new_y="NEXT")

    # On utilise notre nouvelle classe au lieu de FPDF() classique
    pdf = PDFInformation()
    pdf.add_page()
    # ⚠️ TRÈS IMPORTANT : On dit au PDF de sauter de page s'il arrive à 30mm du bas !
    pdf.set_auto_page_break(auto=True, margin=30)
    pdf.set_left_margin(10)

    # Variables dynamiques
    date_commission = formater_date_fr(data.get('date_commission', '...'))
    direction_nom = data.get('direction_name', "Direction de l'Administration générale et de l'Equipement")
    num_ordre = data.get('num_ordre', '............')
    ref_service = data.get('ref_service', 'MCAT/SG/DAGE/ms')
    date_lettre = data.get('date_lettre', '')
    signataire = data.get('signataire', 'Le Directeur')

    # --- 1. DESSIN GRAPHIQUE GAUCHE ---
    x_flag_top = 43; y_flag_top = 10; w_band_top = 8; h_flag_top = 14 
    
    # Bande Verte
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_flag_top, y_flag_top, w_band_top, h_flag_top, style='F')
    
    # Bande Jaune
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_flag_top + w_band_top, y_flag_top, w_band_top, h_flag_top, style='F')
    
    # --- L'ÉTOILE (Vraie étoile avec ZapfDingbats) ---
    # Ajuste à 4.0 ou 5.0 si tu veux la monter ou la descendre un poil
    decalage_y_etoile = 4.5 
    pdf.set_xy(x_flag_top + w_band_top, y_flag_top + decalage_y_etoile) 
    pdf.set_text_color(0, 140, 60)
    pdf.set_font("ZapfDingbats", '', 11) # Police magique et taille ajustée
    pdf.cell(w_band_top, 5, txt=chr(72), align='C') # chr(72) dessine l'étoile
    
    # Bande Rouge
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_flag_top + (w_band_top*2), y_flag_top, w_band_top, h_flag_top, style='F')
    
    y_start_text = y_flag_top + h_flag_top + 5 
    pdf.set_y(y_start_text); pdf.set_text_color(0, 0, 0); pdf.set_font("Times", 'B', 14)
    pdf.cell(90, 6, txt=clean_text("République du Sénégal"), new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_font("Times", 'I', 11)
    pdf.cell(90, 6, txt="Un Peuple - Un But - Une Foi", new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(0, 100, 0)
    pdf.multi_cell(90, 4, txt=clean_text("MINISTÈRE DE LA CULTURE, DE\nL'ARTISANAT ET DU TOURISME"), align='C')
    
    y_barre = pdf.get_y() + 1; w_barre_total = 44; x_barre_start = 33; w_segment = w_barre_total / 3; h_barre = 1.5
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_barre_start, y_barre, w_segment, h_barre, style='F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_barre_start + w_segment, y_barre, w_segment, h_barre, style='F')
    
    # --- Étoile de la petite barre tricolore ---
    decalage_y_barre = -1.2 # On remonte un peu par rapport au Y de la barre
    pdf.set_xy(x_barre_start + w_segment, y_barre + decalage_y_barre)
    pdf.set_font("ZapfDingbats", '', 5.5); pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, txt=chr(72), align='C')
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, style='F')                                                                                                     
    
    pdf.set_xy(10, y_barre + 3); pdf.set_font("Arial", 'B', 30); pdf.set_text_color(0, 100, 0)
    pdf.cell(90, 12, txt="MCAT", new_x="LMARGIN", new_y="NEXT", align='C')
    
    # --- CORRECTION 1 : Direction sur 2 lignes centrée ---
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 9) 
    direction_affichee = clean_text(direction_nom)
    direction_affichee = direction_affichee.replace("Administration g", "Administration\ng").replace("Administration G", "Administration\nG")
    
    pdf.set_x(15) 
    pdf.multi_cell(80, 5, txt=direction_affichee, align='C')

   # --- 2. RÉFÉRENCES, DATE ET SIGNATAIRE (Alignés à droite) ---
    X_DROITE = 140  
    
    # 1. Le Numéro et la Réf Service sur la même ligne
    pdf.set_xy(X_DROITE, y_start_text) 
    pdf.set_font("Arial", 'B', 11) 
    pdf.set_text_color(0, 0, 0)
    texte_ref_complet = clean_text(f"N° {num_ordre} {ref_service}")
    pdf.cell(0, 5, txt=texte_ref_complet, new_x="LMARGIN", new_y="NEXT")
    
    # ==========================================
    # CORRECTION DU FORMAT DE LA DATE
    # ==========================================
    date_brute = str(date_lettre).strip()
    
    if len(date_brute) >= 10 and date_brute[4] == '-' and date_brute[7] == '-':
        annee = date_brute[0:4]
        mois = date_brute[5:7]
        jour = date_brute[8:10]
        date_formatee = f"{jour}/{mois}/{annee}"
    elif date_brute == "" or date_brute == "None":
        date_formatee = "---------------------------------"
    else:
        date_formatee = date_brute

    # 2. La Date (On utilise notre date_formatee)
    pdf.set_xy(X_DROITE, pdf.get_y() + 15) 
    pdf.cell(0, 5, txt=clean_text(f"Dakar, le {date_formatee}"), new_x="LMARGIN", new_y="NEXT")
    
    # 3. Le Signataire
    pdf.set_xy(X_DROITE, pdf.get_y() + 30) 
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 6, txt=clean_text(f"{signataire}"), new_x="LMARGIN", new_y="NEXT")

    # --- 3. OBJET & CORPS DE LA LETTRE (ÉQUILIBRÉ) ---
    marge_gauche_texte = 15 
    pdf.set_left_margin(marge_gauche_texte)
    pdf.set_right_margin(marge_gauche_texte)
    
    # On redonne un tout petit peu d'air en haut
    hauteur_corps_lettre = max(pdf.get_y(), 90) + 5 
    pdf.set_xy(marge_gauche_texte, hauteur_corps_lettre) 

    # Hauteur de ligne plus confortable (6 au lieu de 5)
    h_ligne = 6 
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 11) # On repasse en police 11 pour le texte
    
    objet_propre = clean_text(data.get('objet_marche', '...'))
    immat_propre = clean_text(data.get('immatriculation', '...'))
    date_comm_propre = clean_text(date_commission)
    direction_propre = clean_text(direction_nom)
    
    # ==========================================
    # ✍️ 2. Rédaction
    # ==========================================
    pdf.set_font("Arial", 'BU', 11)
    pdf.write(h_ligne, txt="Objet")
    
    pdf.set_font("Arial", 'B', 11)
    pdf.write(h_ligne, txt=" : Lettre d'information")
    pdf.ln(8) # Espace normal

    pdf.set_font("Arial", '', 11) 
    pdf.multi_cell(0, h_ligne, txt="**Messieurs,**", markdown=True)
    pdf.ln(5) # Espace aéré

    texte_p1 = f"Suite à l'évaluation et à l'attribution par la commission des marchés, des offres relatives à la Demande de Renseignements et de Prix restreinte ayant pour objet : « **{objet_propre}** » immatriculée **{immat_propre}** en date du **{date_comm_propre}**, pour le compte de la **{direction_propre}**, je vous informe que votre entreprise n'a pas été retenue comme attributaire de ladite demande de renseignements et de prix."
    pdf.multi_cell(0, h_ligne, txt=texte_p1, align='J', markdown=True)
    pdf.ln(5) # Espace aéré

    texte_p2 = f"A ce titre, je vous prie de bien vouloir passer à la **{direction_propre}** pour récupérer le procès-verbal d'ouverture et d'évaluation des offres."
    pdf.multi_cell(0, h_ligne, txt=texte_p2, align='J', markdown=True)
    pdf.ln(5) # Espace aéré

    texte_p3 = "Je vous prie d'agréer, **Monsieur le Directeur**, l'assurance de ma considération distinguée."
    pdf.multi_cell(0, h_ligne, txt=texte_p3, align='J', markdown=True)
    pdf.ln(8) # Bon espace avant le tableau

    # --- 4. TABLEAU DES PRESTATAIRES (AÉRÉ MAIS BLOQUÉ SUR 1 PAGE) ---
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    
    largeur_col1 = 65 
    largeur_col2 = 110 
    
    # 💡 NOUVEAU : On récupère le mot envoyé par routes.py, tout en majuscules
    titre_colonne_1 = data.get('type_entreprise', 'PRESTATAIRES').upper()
    
    # En-tête de tableau un peu plus haut (10 au lieu de 8)
    pdf.cell(largeur_col1, 10, txt=titre_colonne_1, border=1, align='C') # ✅ CORRIGÉ
    pdf.cell(largeur_col2, 10, txt="ADRESSES", border=1, align='C', new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Arial", '', 10) # On repasse en police 10 (plus lisible que 9)

    prestataires_liste = data.get('perdants', [])

    if not prestataires_liste:
        pdf.cell(largeur_col1 + largeur_col2, 7, txt="Aucun prestataire trouvé", border=1, align='C', new_x="LMARGIN", new_y="NEXT")
    else:
        # 🚨 ON VERROUILLE LE SAUT DE PAGE DÉFINITIVEMENT 🚨
        pdf.set_auto_page_break(auto=False) 

        for candidat in prestataires_liste:
            nom_entreprise = candidat.get('nom_entreprise', 'Nom non renseigné')
            adresse_base = candidat.get('adresse', 'Adresse non renseignée')
            rc = candidat.get('rc', 'Non renseigné')
            ninea = candidat.get('ninea', 'Non renseigné')
            tel = candidat.get('tel', 'Non renseigné')
            
            chaine_adresse = f"{adresse_base}, RC: {rc}, NINEA: {ninea}, Tél: {tel};"
            
            x_depart = marge_gauche_texte 
            y_depart = pdf.get_y()
            
            # On remonte la hauteur des lignes internes à 5.5 pour décoller le texte des bordures
            pdf.set_xy(x_depart, y_depart)
            pdf.multi_cell(largeur_col1, 5.5, txt=clean_text(nom_entreprise), border=0, align='L')
            y_col1 = pdf.get_y()
            
            pdf.set_xy(x_depart + largeur_col1, y_depart)
            pdf.multi_cell(largeur_col2, 5.5, txt=clean_text(chaine_adresse), border=0, align='L')
            y_col2 = pdf.get_y()
            
            # Dessin de la case
            y_max = max(y_col1, y_col2)
            hauteur_ligne = y_max - y_depart
            
            pdf.rect(x_depart, y_depart, largeur_col1 + largeur_col2, hauteur_ligne)
            pdf.line(x_depart + largeur_col1, y_depart, x_depart + largeur_col1, y_max)
            
            pdf.set_xy(x_depart, y_max)
    
            
            # --- On réactive l'auto-break normal pour la suite ---
            pdf.set_auto_page_break(auto=True, margin=30)
            
    # 5. Sauvegarde en mémoire
    pdf_bytes = pdf.output()
    buffer.write(pdf_bytes)

from fpdf import FPDF
import os

def generer_pdf_lettre_notification(buffer, data):
    """
    Génère la Lettre de Notification au format PDF avec FPDF2.
    Basé sur le modèle pour l'entreprise attributaire (gagnante).
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_left_margin(10)

    # Variables dynamiques
    date_commission = formater_date_fr(data.get('date_commission', '...'))
    direction_nom = data.get('direction_name', "Direction de l'Administration\nGénérale et de l'Equipement")
    num_ordre = data.get('num_ordre', '............')
    ref_service = data.get('ref_service', 'MCAT/SG/DAGE/ms')
    date_lettre = data.get('date_lettre', '')
    signataire = data.get('signataire', 'Le Directeur')

    # --- 1. DESSIN GRAPHIQUE GAUCHE ---
    x_flag_top = 43; y_flag_top = 10; w_band_top = 8; h_flag_top = 14 
    
    # Drapeau
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_flag_top, y_flag_top, w_band_top, h_flag_top, style='F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_flag_top + w_band_top, y_flag_top, w_band_top, h_flag_top, style='F')
    
    # --- L'Étoile du drapeau ---
    decalage_y_etoile = 4.5 # Modifie cette valeur si besoin (ex: 4.0 pour monter, 5.0 pour descendre)
    pdf.set_xy(x_flag_top + w_band_top, y_flag_top + decalage_y_etoile) 
    pdf.set_text_color(0, 140, 60)
    pdf.set_font("ZapfDingbats", '', 11) # Police magique
    pdf.cell(w_band_top, 5, txt=chr(72), align='C') # chr(72) génère l'étoile
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_flag_top + (w_band_top*2), y_flag_top, w_band_top, h_flag_top, style='F')
    
    # République et Ministère
    y_start_text = y_flag_top + h_flag_top + 5 
    pdf.set_y(y_start_text); pdf.set_text_color(0, 0, 0); pdf.set_font("Times", 'B', 14)
    pdf.cell(90, 6, txt=clean_text("République du Sénégal"), new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_font("Times", 'I', 11)
    pdf.cell(90, 6, txt="Un Peuple - Un But - Une Foi", new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(0, 100, 0)
    pdf.multi_cell(90, 4, txt=clean_text("MINISTÈRE DE LA CULTURE, DE\nL'ARTISANAT ET DU TOURISME"), align='C')
    
    # Barre tricolore
    y_barre = pdf.get_y() + 1; w_barre_total = 44; x_barre_start = 33; w_segment = w_barre_total / 3; h_barre = 1.5
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_barre_start, y_barre, w_segment, h_barre, style='F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_barre_start + w_segment, y_barre, w_segment, h_barre, style='F')
    
    # --- Étoile de la petite barre ---
    decalage_y_barre = -1.0 # On remonte légèrement l'étoile par rapport à la barre
    pdf.set_xy(x_barre_start + w_segment, y_barre + decalage_y_barre)
    pdf.set_font("ZapfDingbats", '', 5.5)
    pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, txt=chr(72), align='C')
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, style='F')                                                                                                     
    
    # MCAT Logo texte
    pdf.set_xy(10, y_barre + 3); pdf.set_font("Arial", 'B', 30); pdf.set_text_color(0, 100, 0)
    pdf.cell(90, 12, txt="MCAT", new_x="LMARGIN", new_y="NEXT", align='C')
    
    # Direction sous le MCAT
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 9) 
    direction_affichee = clean_text(direction_nom).replace("Administration g", "Administration\ng").replace("Administration G", "Administration\nG")
    pdf.set_x(15) 
    pdf.multi_cell(80, 5, txt=direction_affichee, align='C')

    # --- 2. RÉFÉRENCES ET DATE ---
    X_DROITE = 135 
    pdf.set_xy(X_DROITE, y_start_text) 
    
    pdf.set_font("Arial", 'B', 11) 
    pdf.set_text_color(0, 0, 0)
    texte_ref_complet = clean_text(f"N° {num_ordre} {ref_service}")
    pdf.cell(0, 5, txt=texte_ref_complet, new_x="LMARGIN", new_y="NEXT")
    
    # ==========================================
    # CORRECTION DU FORMAT DE LA DATE
    # ==========================================
    date_brute = str(date_lettre).strip()
    
    if len(date_brute) >= 10 and date_brute[4] == '-' and date_brute[7] == '-':
        annee = date_brute[0:4]
        mois = date_brute[5:7]
        jour = date_brute[8:10]
        date_formatee = f"{jour}/{mois}/{annee}"
    elif date_brute == "" or date_brute == "None":
        date_formatee = "---------------------------------"
    else:
        date_formatee = date_brute

    # On utilise date_formatee ici 👇
    pdf.set_xy(X_DROITE, pdf.get_y() + 15) 
    pdf.cell(0, 5, txt=clean_text(f"Dakar, le {date_formatee}"), new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_xy(X_DROITE, pdf.get_y() + 30) 
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 6, txt=clean_text(f"{signataire}"), new_x="LMARGIN", new_y="NEXT")

    # --- 3. OBJET ET CORPS DE LA LETTRE ---
    marge_gauche_texte = 15 
    pdf.set_left_margin(marge_gauche_texte)
    pdf.set_right_margin(marge_gauche_texte) 
    
    hauteur_corps_lettre = 95 
    pdf.set_xy(marge_gauche_texte, hauteur_corps_lettre)

    h_ligne = 7
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 11)

    objet_propre = clean_text(data.get('objet_marche', '...'))
    immat_propre = clean_text(data.get('immatriculation', '...'))
    date_comm_propre = clean_text(date_commission)
    direction_propre = clean_text(data.get('direction_name', "Direction de l'Administration Générale et de l'Equipement"))
    
    civilite_propre = clean_text(data.get('civilite_representant', 'Monsieur le Directeur Général,'))
    civilite_cloture = civilite_propre.replace(",", "") 

    texte_objet = "**Objet :** Lettre de notification"
    pdf.multi_cell(0, h_ligne, txt=texte_objet, markdown=True)
    pdf.ln(8)

    pdf.multi_cell(0, h_ligne, txt=f"**{civilite_propre}**", markdown=True)
    pdf.ln(8)

    texte_p1 = f"Suite à l'évaluation et à l'attribution par la commission des marchés, des offres relatives à la Demande de Renseignements et de Prix restreinte ayant pour objet : « **{objet_propre}** » immatriculée **{immat_propre}** en date du **{date_comm_propre}**, pour le compte de la **{direction_propre}**, je vous informe que votre entreprise a été retenue comme attributaire de ladite demande de renseignements et de prix."
    pdf.multi_cell(0, h_ligne, txt=texte_p1, align='J', markdown=True)
    pdf.ln(6)

    texte_p2 = f"A ce titre, je vous prie de bien vouloir passer à la **{direction_propre}** pour récupérer le procès-verbal d'ouverture et d'évaluation des offres et de signer le contrat."
    pdf.multi_cell(0, h_ligne, txt=texte_p2, align='J', markdown=True)
    pdf.ln(6) 

    texte_p3 = f"Je vous prie d'agréer, **{civilite_cloture}**, l'assurance de ma considération distinguée."
    pdf.multi_cell(0, h_ligne, txt=texte_p3, align='J', markdown=True)
    
    # ==========================================
    # 🎯 BLOC DESTINATAIRE (BLOC INVISIBLE) 🎯
    # ==========================================
    Y_ACTUEL = 210  # Hauteur de départ en mm
    X_GAUCHE = 15   # Position fixe depuis le bord gauche
    
    # 👈 C'est ce chiffre (80) qui crée le "mur invisible" ! 
    # Le texte ne dépassera jamais 80mm de largeur, il ira à la ligne.
    LARGEUR_BLOC = 70
    
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    
    civilite = data.get('civilite_representant', 'Monsieur le Directeur Général')
    entreprise = data.get('destinataire_nom', 'ENTREPRISE NON RENSEIGNÉE')
    adresse = data.get('destinataire_adresse', '')
    tel = data.get('destinataire_tel', '')
    
    civilite_propre = civilite.replace(',', '')
    texte_nom = f"{civilite_propre} de {entreprise}".upper()

    # 1. Le "À"
    pdf.set_xy(X_GAUCHE + 15, Y_ACTUEL)
    pdf.cell(LARGEUR_BLOC, 6, txt="À", align='L')
    # 2. Le nom (restera bloqué à 80mm de large grâce à multi_cell)
    Y_ACTUEL += 6
    pdf.set_xy(X_GAUCHE, Y_ACTUEL)
    pdf.multi_cell(LARGEUR_BLOC, 6, txt=texte_nom, align='L')
    
    # 3. L'adresse (pareil, elle ira à la ligne si elle est trop longue)
    if adresse:
        Y_ACTUEL = pdf.get_y() # On récupère la position après le nom (qu'il prenne 1, 2 ou 3 lignes)
        pdf.set_xy(X_GAUCHE, Y_ACTUEL)
        pdf.multi_cell(LARGEUR_BLOC, 5, txt=adresse, align='L')
        
    # 4. Le téléphone
    if tel and tel != "Non renseigné":
        Y_ACTUEL = pdf.get_y()
        pdf.set_xy(X_GAUCHE, Y_ACTUEL)
        pdf.multi_cell(LARGEUR_BLOC, 5, txt=f"Tél: {tel}", align='L')

    # --- 4. PIED DE PAGE ---
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-25)
    
    # Ligne verte
    pdf.set_draw_color(145, 190, 100)  
    pdf.set_line_width(1.5)            
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Times", '', 11) 
    pdf.cell(0, 5, txt=clean_text("Ministère de la Culture, de l'Artisanat et du Tourisme,"), new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.cell(0, 5, txt=clean_text("Route des Almadies, Dakar Sénégal"), new_x="LMARGIN", new_y="NEXT", align='C')
        
    # Sauvegarde en mémoire
    pdf_bytes = pdf.output()
    buffer.write(pdf_bytes)

def generer_pdf_pv_attribution(buffer, data):
    from fpdf import FPDF
    from app.utils import clean_text
    
    pdf = FPDF()
    pdf.add_page()
    
    # Récupération des variables du formulaire
    direction_nom = data.get('direction_name', "La Direction de l'Administration Générale et de l'Equipement")
    num_ordre = data.get('num_ordre', '............')
    ref_service = data.get('ref_service', '')
    date_lettre = data.get('date_lettre', '')
    signataire = data.get('signataire', 'Le Directeur,')
    
    # ==========================================
    # --- 1. DESSIN GRAPHIQUE GAUCHE ---
    # ==========================================
    x_flag_top = 43; y_flag_top = 10; w_band_top = 8; h_flag_top = 14 
    
    # Drapeau
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_flag_top, y_flag_top, w_band_top, h_flag_top, style='F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_flag_top + w_band_top, y_flag_top, w_band_top, h_flag_top, style='F')
    
    # --- L'Étoile du grand drapeau ---
    decalage_y_etoile = 4.5 # Ajuste cette valeur si besoin
    pdf.set_xy(x_flag_top + w_band_top, y_flag_top + decalage_y_etoile) 
    pdf.set_text_color(0, 140, 60)
    pdf.set_font("ZapfDingbats", '', 11) # La police magique
    pdf.cell(w_band_top, 5, txt=chr(72), align='C') # chr(72) dessine l'étoile
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_flag_top + (w_band_top*2), y_flag_top, w_band_top, h_flag_top, style='F')
    
    # République et Ministère
    y_start_text = y_flag_top + h_flag_top + 5 
    pdf.set_y(y_start_text); pdf.set_text_color(0, 0, 0); pdf.set_font("Times", 'B', 14)
    pdf.cell(90, 6, txt=clean_text("République du Sénégal"), new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_font("Times", 'I', 11)
    pdf.cell(90, 6, txt="Un Peuple - Un But - Une Foi", new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(0, 100, 0)
    pdf.multi_cell(90, 4, txt=clean_text("MINISTÈRE DE LA CULTURE, DE\nL'ARTISANAT ET DU TOURISME"), align='C')
    
    # Barre tricolore
    y_barre = pdf.get_y() + 1; w_barre_total = 44; x_barre_start = 33; w_segment = w_barre_total / 3; h_barre = 1.5
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_barre_start, y_barre, w_segment, h_barre, style='F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_barre_start + w_segment, y_barre, w_segment, h_barre, style='F')
    
    # --- Étoile de la petite barre tricolore ---
    decalage_y_barre = -1.2 # On remonte légèrement
    pdf.set_xy(x_barre_start + w_segment, y_barre + decalage_y_barre)
    pdf.set_font("ZapfDingbats", '', 5.5)
    pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, txt=chr(72), align='C')
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, style='F')                                                                                
    
    # MCAT Logo texte
    pdf.set_xy(10, y_barre + 3); pdf.set_font("Arial", 'B', 30); pdf.set_text_color(0, 100, 0)
    pdf.cell(90, 12, txt="MCAT", new_x="LMARGIN", new_y="NEXT", align='C')
    
    # Direction sous le MCAT 
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 9) 
    direction_affichee = clean_text(direction_nom).replace("Administration g", "Administration\ng").replace("Administration G", "Administration\nG")
    pdf.set_x(15) 
    pdf.multi_cell(80, 5, txt=direction_affichee, align='C')

    # ==========================================
    # --- 2. RÉFÉRENCES, DATE ET SIGNATAIRE ---
    # ==========================================
    X_DROITE = 135  # Toujours notre variable magique pour l'alignement
    
    # Numéro et Réf Service sur la même ligne
    pdf.set_xy(X_DROITE, y_start_text) 
    pdf.set_font("Arial", 'B', 11) 
    pdf.set_text_color(0, 0, 0)
    texte_ref_complet = clean_text(f"N° {num_ordre} {ref_service}")
    pdf.cell(0, 5, txt=texte_ref_complet, new_x="LMARGIN", new_y="NEXT")
    
    # ==========================================
    # CORRECTION DU FORMAT DE LA DATE
    # ==========================================
    date_brute = str(date_lettre).strip()
    
    if len(date_brute) >= 10 and date_brute[4] == '-' and date_brute[7] == '-':
        annee = date_brute[0:4]
        mois = date_brute[5:7]
        jour = date_brute[8:10]
        date_formatee = f"{jour}/{mois}/{annee}"
    elif date_brute == "" or date_brute == "None":
        date_formatee = "---------------------------------"
    else:
        date_formatee = date_brute

    # Date (On utilise date_formatee maintenant !)
    pdf.set_xy(X_DROITE, pdf.get_y() + 15) 
    pdf.cell(0, 5, txt=clean_text(f"Dakar, le {date_formatee}"), new_x="LMARGIN", new_y="NEXT")
    
    # Signataire (Le Directeur)
    pdf.set_xy(X_DROITE, pdf.get_y() + 30) 
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 6, txt=clean_text(f"{signataire}"), new_x="LMARGIN", new_y="NEXT")

    # ==========================================
    # --- 3. TITRE DU DOCUMENT ---
    # ==========================================
    pdf.ln(15)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'BU', 14)
    pdf.cell(0, 8, txt="PROCES - VERBAL D'ATTRIBUTION", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(12)

    # === FONCTION DE FORMATAGE DE LA DATE ===
    def formater_date_en_francais(date_str):
        if not date_str or len(date_str.split('-')) != 3:
            return date_str
        try:
            y, m, d = date_str.split('-')
            mois = ["janvier", "février", "mars", "avril", "mai", "juin", 
                    "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
            jour = int(d)
            jour_str = "1er" if jour == 1 else str(jour)
            return f"{jour_str} {mois[int(m)-1]} {y}"
        except (ValueError, IndexError):
            return date_str

    # ==========================================
    # --- 4. CORPS DU TEXTE DU PV ---
    # ==========================================
    # 🧹 Nettoyage et préparation des variables
    date_commission_brute = data.get('date_commission', '')
    date_commission = formater_date_en_francais(date_commission_brute)
    
    entreprise_propre = clean_text(data.get('entreprise_attributaire', "l'entreprise non renseignée"))
    adresse_propre = clean_text(data.get('adresse_direction', 'Route des Almadies, Dakar'))
    immat_propre = clean_text(data.get('immatriculation', ''))
    objet_propre = clean_text(data.get('objet_marche', ''))
    direction_propre = clean_text(direction_nom)

    # 📏 Réglage des marges symétriques à 15mm comme pour les autres courriers
    marge = 15
    pdf.set_left_margin(marge)
    pdf.set_right_margin(marge)
    pdf.set_x(marge)
    
    hauteur_ligne = 7
    pdf.set_font("Arial", '', 12) # Taille 12 pour le PV, c'est très bien !
    pdf.set_text_color(0, 0, 0) 
    
   # --- PARAGRAPHE 1 ---
    # 1. On formate le texte pour avoir "Direction de l'Administration..." au lieu de tout en majuscules
    direction_pv = direction_propre.title().replace(" De ", " de ").replace(" Et ", " et ")
    
    # 2. On l'intègre sans les ** pour éviter le gras
    texte_p1 = f"La {direction_pv} du Ministère de la Culture, de l'Artisanat et du Tourisme, **{adresse_propre}**, a procédé à l'attribution des offres reçues dans le cadre de la demande de renseignements et de prix restreinte N° **{immat_propre}** ayant pour objet : « **{objet_propre}** »."
    
    pdf.multi_cell(0, hauteur_ligne, txt=texte_p1, align='J', markdown=True)
    pdf.ln(5)

    # --- PARAGRAPHE 2 ---
    texte_p2 = f"Après avoir procédé à la vérification et au constat de la conformité des offres reçues (voir PV d'analyse, d'évaluation et d'attribution des offres de la commission des marchés en date du **{date_commission}**), l'entreprise « **{entreprise_propre}** » a été déclarée moins disante."
    
    pdf.multi_cell(0, hauteur_ligne, txt=texte_p2, align='J', markdown=True)
    pdf.ln(5)
    
    # --- PARAGRAPHE 3 ---
    texte_p3 = "En conséquence le présent procès-verbal d'attribution est établi pour servir et valoir ce que de droit."
    
    pdf.multi_cell(0, hauteur_ligne, txt=texte_p3, align='J', markdown=True)

    # ==========================================
    # --- 5. SECONDE SIGNATURE (BAS À DROITE) ---
    # ==========================================
    pdf.ln(25) # On laisse un bon espace pour la signature
    
    # On pousse le bloc vers la droite (tu peux ajuster ce chiffre : 120, 130...)
    X_SIGNATURE_DROITE = 125 
    pdf.set_x(X_SIGNATURE_DROITE) 
    
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(0, 0, 0)
    
    texte_signature_bas = data.get('signataire_bas', "Le signataire")
    
    # multi_cell(0) va prendre tout l'espace restant entre X=125 et la marge droite
    # align='C' va centrer le nom du signataire proprement dans cet espace
    pdf.multi_cell(0, 6, txt=clean_text(texte_signature_bas), align='C')

    # ==========================================
    # --- 6. PIED DE PAGE ---
    # ==========================================
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-25)
    
    # Ligne verte
    pdf.set_draw_color(145, 190, 100)  
    pdf.set_line_width(1.5)            
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Times", '', 11) 
    pdf.cell(0, 5, txt=clean_text("Ministère de la Culture, de l'Artisanat et du Tourisme,"), new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.cell(0, 5, txt=clean_text("Route des Almadies, Dakar Sénégal"), new_x="LMARGIN", new_y="NEXT", align='C')
        
    # ==========================================
    # --- 7. FIN DU DOCUMENT ---
    # ==========================================
    pdf_bytes = pdf.output()
    buffer.write(pdf_bytes)

import os
from flask import current_app
from fpdf import FPDF

def clean_text(text):
    if text is None:
        return ""
    return str(text).replace('’', "'")

def dessiner_en_tete(pdf, data):
    # Variables dynamiques
    direction_nom = data.get('direction_nom', "Direction de l'Administration Générale et de l'Equipement")
    num_ordre = data.get('num_ordre', '')
    ref_service = data.get('ref_service', 'MCAT/SG/DAGE/ms')
    date_lettre = data.get('date_lettre', '15 mars 2015')
    signataire = data.get('signataire', 'Le Directeur')

    # =========================================================
    # 🛠️ RÉGLAGES MANUELS DES POSITIONS
    # =========================================================
    POS_X_DRAPEAU = 36        
    POS_X_TEXTES_GAUCHE = 4  
    POS_X_NUMERO = 120        
    POS_X_DATE = 125          
    POS_X_SIGNATAIRE = 110    
    # =========================================================

    # --- 1. DESSIN GRAPHIQUE GAUCHE ---
    y_flag_top = 10; w_band_top = 8; h_flag_top = 14 
    
    # Drapeau (Ajout de style='F' pour FPDF2)
    pdf.set_fill_color(0, 140, 60); pdf.rect(POS_X_DRAPEAU, y_flag_top, w_band_top, h_flag_top, style='F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(POS_X_DRAPEAU + w_band_top, y_flag_top, w_band_top, h_flag_top, style='F')
    
    # --- L'Étoile du grand drapeau ---
    decalage_y_etoile = 4.5 # Ajuste à 4.0 ou 5.0 selon le rendu visuel
    pdf.set_xy(POS_X_DRAPEAU + w_band_top, y_flag_top + decalage_y_etoile) 
    pdf.set_text_color(0, 140, 60)
    pdf.set_font("ZapfDingbats", '', 11) # La police magique
    pdf.cell(w_band_top, 5, txt=chr(72), align='C') # L'étoile parfaite
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(POS_X_DRAPEAU + (w_band_top*2), y_flag_top, w_band_top, h_flag_top, style='F')
    
    # République et Ministère
    y_start_text = y_flag_top + h_flag_top + 5 
    
    pdf.set_xy(POS_X_TEXTES_GAUCHE, y_start_text)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Times", 'B', 14)
    # Remplacement de ln=1 par la norme FPDF2
    pdf.cell(90, 6, txt=clean_text("République du Sénégal"), new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.set_x(POS_X_TEXTES_GAUCHE)
    pdf.set_font("Times", 'I', 11)
    pdf.cell(90, 6, txt="Un Peuple - Un But - Une Foi", new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.ln(2)
    pdf.set_x(POS_X_TEXTES_GAUCHE)
    pdf.set_font("Arial", 'B', 8); pdf.set_text_color(0, 100, 0)
    pdf.multi_cell(90, 4, txt=clean_text("MINISTÈRE DE LA CULTURE, DE\nL'ARTISANAT ET DU TOURISME"), align='C')
    
    # Barre tricolore
    y_barre = pdf.get_y() + 1; w_barre_total = 44; w_segment = w_barre_total / 3; h_barre = 1.5
    x_barre_start = POS_X_TEXTES_GAUCHE + 23 
    
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_barre_start, y_barre, w_segment, h_barre, style='F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_barre_start + w_segment, y_barre, w_segment, h_barre, style='F')
    
    # --- Étoile de la petite barre tricolore ---
    decalage_y_barre = -1.2 # On la remonte pour la centrer
    pdf.set_xy(x_barre_start + w_segment, y_barre + decalage_y_barre)
    pdf.set_font("ZapfDingbats", '', 5.5)
    pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, txt=chr(72), align='C')
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, style='F')                                                                              
    
    # MCAT Logo texte
    pdf.set_xy(POS_X_TEXTES_GAUCHE, y_barre + 3)
    pdf.set_font("Arial", 'B', 30); pdf.set_text_color(0, 100, 0)
    pdf.cell(90, 12, txt="MCAT", new_x="LMARGIN", new_y="NEXT", align='C')
    
    # Direction sous le MCAT
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 9) 
    direction_affichee = clean_text(direction_nom).replace("Administration g", "Administration\ng").replace("Administration G", "Administration\nG")
    pdf.set_x(POS_X_TEXTES_GAUCHE + 5) 
    pdf.multi_cell(80, 5, txt=direction_affichee, align='C')
    
    # 📌 On mémorise la fin du bloc de gauche
    fin_bloc_gauche = pdf.get_y()

    # On définit une nouvelle position X pour décaler tout le bloc vers la droite.
    # (+15 millimètres par rapport à avant, tu peux changer ce nombre si besoin)
    X_DROITE = POS_X_NUMERO + 15

    # --- 2. RÉFÉRENCES ET DATE ---
    # On remonte le bloc en enlevant le "+ 5" qu'il y avait avant
    pdf.set_xy(X_DROITE, y_start_text) 
    
    # 1. Le Numéro et la Réf Service 
    pdf.set_font("Arial", 'B', 11) 
    pdf.set_text_color(0, 0, 0)
    texte_ref_complet = clean_text(f"N° {num_ordre} {ref_service}")
    pdf.cell(0, 5, txt=texte_ref_complet, new_x="LMARGIN", new_y="NEXT")
    
    # ==========================================
    # CORRECTION DU FORMAT DE LA DATE
    # ==========================================
    date_brute = str(date_lettre).strip()
    
    # On vérifie si c'est au format YYYY-MM-DD
    if len(date_brute) >= 10 and date_brute[4] == '-' and date_brute[7] == '-':
        annee = date_brute[0:4]
        mois = date_brute[5:7]
        jour = date_brute[8:10]
        date_formatee = f"{jour}/{mois}/{annee}"
    elif date_brute == "" or date_brute == "None":
        date_formatee = "---------------------------------"
    else:
        date_formatee = date_brute # On garde la valeur d'origine si le format n'est pas reconnu

    # 2. La Date 
    # On aère un peu plus en descendant de 8mm (au lieu de 5mm)
    pdf.set_xy(X_DROITE, pdf.get_y() + 15) 
    
    # 👇 On utilise la 'date_formatee' ici 👇
    pdf.cell(0, 5, txt=clean_text(f"Dakar, le {date_formatee}"), new_x="LMARGIN", new_y="NEXT")

    # --- 3. LE SIGNATAIRE ---
    # On descend pour laisser la place à la signature
    pdf.set_xy(X_DROITE, pdf.get_y() + 25) 
    pdf.set_font("Arial", 'B', 16)
    
    # On utilise exactement la même configuration de cellule pour que ça soit 100% aligné à gauche.
    # (Et j'ai enlevé la virgule qui causait le "Le Directeur,,")
    pdf.cell(0, 6, txt=clean_text(f"{signataire}"), new_x="LMARGIN", new_y="NEXT")

    # 📌 On mémorise la fin du bloc de droite
    fin_bloc_droite = pdf.get_y()

    # =========================================================
    # 🎯 FIX FINAL FPDF2 : On force le curseur sous le plus grand bloc
    # =========================================================
    position_la_plus_basse = max(fin_bloc_gauche, fin_bloc_droite)
    pdf.set_y(position_la_plus_basse + 10) # On ajoute 10mm d'espace propre avant de commencer la lettre

def generer_pdf_lettre_invitation(data):
    pdf = FPDF()
    
    immatriculation = data.get('immatriculation', '')
    objet_marche = data.get('objet_marche', '')
    date_heure = data.get('date_heure_limite', '')
    adresse_depot = data.get('adresse_depot', '')
    lieu_ouverture = data.get('lieu_ouverture', '')
    prestataires = data.get('prestataires', [])

    # =========================================================
    # SECTION 1 : LA LETTRE D'INVITATION
    # =========================================================
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    
    dessiner_en_tete(pdf, data) 
    
    # Titre
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 8, txt=clean_text("Lettre d'invitation"), ln=True, align='C')
    pdf.ln(5)
    
   # =========================================================
    # Objet
    # =========================================================
    y_start = pdf.get_y()          
    x_start = pdf.get_x()          
    
    # 1. On écrit "Objet :"
    pdf.set_font("Arial", 'BU', 11)
    pdf.cell(16, 6, txt="Objet : ") # On repasse à 6 pour la hauteur
    
    # 2. On décale la marge gauche (notre mur invisible)
    pdf.set_left_margin(x_start + 16)
    pdf.set_xy(x_start + 16, y_start) # Alignement vertical naturel, plus besoin de tricher !
    
    # 3. 🪄 L'ASTUCE : On utilise multi_cell avec markdown=True
    pdf.set_font("Arial", '', 11)
    objet_propre = clean_text(objet_marche)
    
    # Le '6' de multi_cell gère l'espace entre les lignes. 
    # Les '**' autour de la variable la mettent en gras !
    texte_objet = f"Demande de renseignements et de prix (DRP) ayant pour objet : **{objet_propre}**"
    pdf.multi_cell(0, 6, txt=texte_objet, markdown=True)
    
    # 4. On remet la marge de la page à la normale
    pdf.set_left_margin(x_start)
    pdf.ln(8)

    # Salutations
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 6, txt="Messieurs,", ln=True)
    pdf.ln(3)
    
    # =========================================================
    # Corps de la lettre
    # =========================================================
    pdf.set_font("Arial", '', 11)
    
    # On nettoie toutes les variables
    objet_propre = clean_text(objet_marche)
    date_propre = clean_text(date_heure)
    adresse_propre = clean_text(adresse_depot)
    
   # 🤖 Le petit robot expert en Marchés Publics
    objet_test = objet_propre.lower().strip()

    # 1. Famille des TRAVAUX (BTP, infrastructures)
    if objet_test.startswith(("travaux", "aménagement", "réhabilitation", "construction", "réfection", "extension")):
        pont_francais = "la réalisation des "

    # 2. Famille des FOURNITURES (Biens matériels, équipements)
    elif objet_test.startswith(("fourniture", "équipement", "matériel", "dotation")):
        pont_francais = "l'acquisition de "
        
    # 3. Mots d'ACTION directs (Si l'utilisateur a déjà écrit l'action)
    elif objet_test.startswith(("acquisition", "achat", "livraison", "abonnement", "édition")):
        pont_francais = "l'"

    # 4. Famille des SERVICES et PRESTATIONS INTELLECTUELLES
    elif objet_test.startswith(("prestation", "service", "mission")):
        pont_francais = "l'exécution des "

    # 5. FILET DE SÉCURITÉ INFAILLIBLE (Études, gardiennage, nettoyage, ou mots inconnus)
    else:
        # Les deux-points ":" sauvent la grammaire à 100% car on n'a plus besoin de deviner "le" ou "la"
        pont_francais = "la commande relative à l'objet suivant : "

    # Insertion dans le paragraphe (J'ai mis la direction en variable pour que ce soit dynamique partout)
    texte_intro = f"Il est prévu dans le cadre du marché cité en objet de procéder à {pont_francais}**{objet_propre}** pour le compte de la Direction de l'Administration Générale et de l'Equipement."

    pdf.multi_cell(0, 6, txt=texte_intro, align='J', markdown=True)
    pdf.ln(4) # Espace entre les deux paragraphes
    
    # 2. Deuxième paragraphe
    texte_paragraphe_2 = f"A cet effet, vous trouverez, ci-joint, le bordereau descriptif quantitatif des prestations que je vous demande de bien vouloir chiffrer et me le retourner au plus tard le **{date_propre}** sous enveloppe cachetée adressée à {adresse_propre}, avec les mentions suivantes :"
    
    pdf.multi_cell(0, 6, txt=texte_paragraphe_2, align='J', markdown=True)
    pdf.ln(2)
    
    # Mentions (On laisse tes write() ici car ce sont des phrases courtes avec alinéa, pas besoin de justifier)
    pdf.set_font("Arial", '', 11)
    pdf.set_x(pdf.l_margin + 15) 
    pdf.write(6, clean_text("« Demande de Renseignements et de Prix n° "))
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(6, clean_text(f"{immatriculation}"))
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(6, clean_text(" »\n"))
    
    pdf.set_x(pdf.l_margin + 15) 
    pdf.cell(0, 6, txt=clean_text("« A n'ouvrir qu'en séance d'ouverture de plis »."), ln=True)
    pdf.ln(4)
    
    # 3. Troisième paragraphe (On remplace write_html par multi_cell pour bien l'aérer)
    lieu_propre = clean_text(lieu_ouverture)
    
    # On utilise les doubles étoiles ** pour mettre en gras
    texte_paragraphe_3 = f"Les offres seront ouvertes en présence des représentants des candidats présents à l'adresse ci-après : **{lieu_propre}**. Les offres remises en retard ne seront pas acceptées."
    
    pdf.multi_cell(0, 6, txt=texte_paragraphe_3, align='J', markdown=True)
    pdf.ln(4)
    
    # 4. Les derniers paragraphes simples (qui étaient déjà bons !)
    pdf.set_font("Arial", '', 11)
    
    texte_4 = "Votre offre devra être chiffrée en toutes taxes comprises (TTC) et accompagnée des formulaires joints en annexe à la DRP. Les fournitures devront être livrées à compter de la réception du bon de commande."
    pdf.multi_cell(0, 6, txt=clean_text(texte_4), align='J')
    pdf.ln(4)
    
    texte_5 = "Les offres sont valables pour une période de trente (30) jours."
    pdf.multi_cell(0, 6, txt=clean_text(texte_5), align='J')
    pdf.ln(4)
    
    texte_6 = "La présente lettre a été adressée aux candidats présélectionnés, dont les noms figurent ci-après :"
    pdf.multi_cell(0, 6, txt=clean_text(texte_6), align='J')
    pdf.ln(4)

  # =========================================================
    # TABLEAU PAGE 1 (Ajusté pour 170mm de large)
    # =========================================================
    pdf.set_font("Arial", 'B', 10)
    col1_w = 55; col2_w = 115; x_start = pdf.get_x()
    
    # 💡 NOUVEAU : On récupère le mot dynamique depuis les données
    titre_colonne_1 = data.get('type_entreprise', 'PRESTATAIRES').upper()
    
    if pdf.get_y() > 240:
        pdf.add_page()
        
    # 1er REMPLACEMENT 👇
    pdf.cell(col1_w, 8, txt=titre_colonne_1, border=1, align='C')
    pdf.cell(col2_w, 8, txt="ADRESSES", border=1, align='C', ln=True)
    
    for p in prestataires:
        if pdf.get_y() > 250:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 10)
            # 2ème REMPLACEMENT (Si ça saute de page) 👇
            pdf.cell(col1_w, 8, txt=titre_colonne_1, border=1, align='C')
            pdf.cell(col2_w, 8, txt="ADRESSES", border=1, align='C', ln=True)

        y_start_row = pdf.get_y()
        pdf.set_auto_page_break(False)
        
        # --- Colonne 1 : Nom du prestataire ---
        pdf.set_font("Arial", 'B', 9)
        pdf.set_text_color(0, 0, 0) # Rouge
        pdf.set_xy(x_start, y_start_row)
        pdf.multi_cell(col1_w, 6, txt=clean_text(p['nom'].upper()), border=0, align='L')
        y_end1 = pdf.get_y()
        
        # --- Colonne 2 : Adresses et Infos ---
        pdf.set_font("Arial", '', 9)
        pdf.set_text_color(0, 0, 0) # Rouge
        pdf.set_xy(x_start + col1_w, y_start_row)
        
        compte = p.get('compte', '').strip()
        texte_compte = f" - CB : {compte}" if compte else ""
        texte_adresse = f"{p['adresse']} - Tel : {p['telephone']}{texte_compte}\nRC : {p['rc']} - NINEA : {p['ninea']}"
        
        pdf.multi_cell(col2_w, 5, txt=clean_text(texte_adresse), border=0, align='L')
        y_end2 = pdf.get_y()
        
        # --- Tracé des bordures ---
        hauteur_ligne = max(y_end1, y_end2) - y_start_row
        
        pdf.set_text_color(0, 0, 0) 
        pdf.rect(x_start, y_start_row, col1_w, hauteur_ligne)
        pdf.rect(x_start + col1_w, y_start_row, col2_w, hauteur_ligne)
        
        pdf.set_auto_page_break(True, margin=20)
        pdf.set_y(y_start_row + hauteur_ligne)

    pdf.ln(6)
    
   # Fin de lettre
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, txt=clean_text("Cette invitation ne peut être transférée à une autre société."), align='J')
    pdf.ln(2)
    pdf.multi_cell(0, 6, txt=clean_text("La passation de marché sera effectuée selon les dispositions du Code des Marchés publics."), align='J')
    pdf.ln(2)
    pdf.multi_cell(0, 6, txt=clean_text("La présente DRP comprend les sections suivantes :"), align='J')
    pdf.ln(2) # Petit espacement visuel propre avant la liste
    
    # 🛠️ CORRECTION 3 FPDF2 : Affichage de la liste ligne par ligne (100% Sûr et propre)
    sections = [
        "Section I : Lettre d'invitation",
        "Section II - Instructions aux Candidats",
        "Section III - Nature des services",
        "Section IV : Projet de Marché",
        "Annexes."
    ]
    
    for ligne in sections:
        pdf.set_x(pdf.l_margin + 10)  # Retrait manuel de 10mm (au lieu de la méthode set_left_margin)
        pdf.cell(0, 6, txt=clean_text(ligne), ln=True)
        
    pdf.ln(4)
   # Remplacement du write_html par multi_cell pour garder un bel interligne :
    texte_fin = "Ces prestations sont à effectuer pour le compte de la Direction de l'Administration générale et de l'Equipement (DAGE) sise aux Almadies en face de la TFM - Dakar, dès **la notification du marché.**"
    
    pdf.multi_cell(0, 6, txt=texte_fin, align='J', markdown=True)
    pdf.ln(6)
    
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, txt=clean_text("Veuillez agréer, Madame, Monsieur, l'expression de ma considération distinguée."), align='J')

    # =========================================================
    # SECTION 2 : FICHE DE TRANSMISSION
    # =========================================================
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    
    dessiner_en_tete(pdf, data) 

        
   # =========================================================
    # Objet
    # =========================================================
    y_start = pdf.get_y()          
    x_start = pdf.get_x()          
    
    # 1. On écrit "Objet :"
    pdf.set_font("Arial", 'BU', 11)
    pdf.cell(16, 6, txt="Objet : ") # On repasse à 6 pour la hauteur
    
    # 2. On décale la marge gauche (notre mur invisible)
    pdf.set_left_margin(x_start + 16)
    pdf.set_xy(x_start + 16, y_start) # Alignement vertical naturel, plus besoin de tricher !
    
    # 3. 🪄 L'ASTUCE : On utilise multi_cell avec markdown=True
    pdf.set_font("Arial", '', 11)
    objet_propre = clean_text(objet_marche)
    
    # Le '6' de multi_cell gère l'espace entre les lignes. 
    # Les '**' autour de la variable la mettent en gras !
    texte_objet = f"Demande de renseignements et de prix (DRP) relative à **{objet_propre}**"
    pdf.multi_cell(0, 6, txt=texte_objet, markdown=True)
    
    # 4. On remet la marge de la page à la normale
    pdf.set_left_margin(x_start)
    pdf.ln(8)

    x_line = pdf.get_x(); y_line = pdf.get_y()
    pdf.line(x_line, y_line, 190, y_line) 
    pdf.ln(8)

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt=clean_text("FICHE DE TRANSMISSION - LETTRE D'INVITATION"), ln=True, align='C')
    pdf.ln(8)

    col_cand = 40; col_adr = 60; col_date = 35; col_sign = 35; x_start = pdf.get_x()
    pdf.set_font("Arial", 'B', 9); y_start_head = pdf.get_y()
    
    pdf.rect(x_start, y_start_head, col_cand, 10); pdf.set_xy(x_start, y_start_head); pdf.cell(col_cand, 10, "CANDIDAT", align='C')
    pdf.rect(x_start + col_cand, y_start_head, col_adr, 10); pdf.set_xy(x_start + col_cand, y_start_head); pdf.cell(col_adr, 10, "ADRESSE", align='C')
    pdf.rect(x_start + col_cand + col_adr, y_start_head, col_date, 10); pdf.set_xy(x_start + col_cand + col_adr, y_start_head); pdf.cell(col_date, 10, clean_text("Date de réception"), align='C')
    pdf.rect(x_start + col_cand + col_adr + col_date, y_start_head, col_sign, 10); pdf.set_xy(x_start + col_cand + col_adr + col_date, y_start_head + 2); pdf.multi_cell(col_sign, 4, "EMARGEMENT &\nCACHET", align='C')
    pdf.set_y(y_start_head + 10)

    for p in prestataires:
        if pdf.get_y() > 240:
            pdf.add_page()
            y_start_head = pdf.get_y()
            pdf.rect(x_start, y_start_head, col_cand, 10); pdf.set_xy(x_start, y_start_head); pdf.cell(col_cand, 10, "CANDIDAT", align='C')
            pdf.rect(x_start + col_cand, y_start_head, col_adr, 10); pdf.set_xy(x_start + col_cand, y_start_head); pdf.cell(col_adr, 10, "ADRESSE", align='C')
            pdf.rect(x_start + col_cand + col_adr, y_start_head, col_date, 10); pdf.set_xy(x_start + col_cand + col_adr, y_start_head); pdf.cell(col_date, 10, clean_text("Date de réception"), align='C')
            pdf.rect(x_start + col_cand + col_adr + col_date, y_start_head, col_sign, 10); pdf.set_xy(x_start + col_cand + col_adr + col_date, y_start_head + 2); pdf.multi_cell(col_sign, 4, "EMARGEMENT &\nCACHET", align='C')
            pdf.set_y(y_start_head + 10)

        y_start_row = pdf.get_y()
        pdf.set_auto_page_break(False)
        
        pdf.set_font("Arial", 'B', 9); pdf.set_text_color(0, 0, 0); pdf.set_xy(x_start, y_start_row + 2)
        pdf.multi_cell(col_cand, 5, txt=clean_text(p['nom'].upper()), align='C')
        y_end1 = pdf.get_y()
        
        pdf.set_font("Arial", '', 8); pdf.set_text_color(0, 0, 0); pdf.set_xy(x_start + col_cand, y_start_row + 2)
        texte_adr = f"{p['adresse']}\nTél : {p['telephone']}"
        pdf.multi_cell(col_adr, 5, txt=clean_text(texte_adr), align='L')
        y_end2 = pdf.get_y()
        
        h = max(y_end1, y_end2) - y_start_row + 4
        if h < 20: h = 20
        
        pdf.rect(x_start, y_start_row, col_cand, h); pdf.rect(x_start + col_cand, y_start_row, col_adr, h)
        pdf.rect(x_start + col_cand + col_adr, y_start_row, col_date, h); pdf.rect(x_start + col_cand + col_adr + col_date, y_start_row, col_sign, h)
        
        pdf.set_auto_page_break(True, margin=20)
        pdf.set_y(y_start_row + h)

    # --- SAUVEGARDE ---
    dossier_pdf = os.path.join(current_app.root_path, 'static', 'pdfs')
    if not os.path.exists(dossier_pdf):
        os.makedirs(dossier_pdf)
        
    immatriculation_propre = clean_text(immatriculation).replace(" ", "_").replace("/", "_")
    nom_fichier = f"Lettre_Invitation_{immatriculation_propre}.pdf"
    chemin_complet = os.path.join(dossier_pdf, nom_fichier)
    
    pdf.output(chemin_complet)
    return chemin_complet

from fpdf import FPDF
import os

def clean_text(text):
    if not text: return ""
    text = str(text)
    replacements = {
        '\u2019': "'", '\u2018': "'", 'â€™': "'", '`': "'",
        '\u201c': '"', '\u201d': '"', '\u2013': '-', '\u2014': '-',
        '\u2026': '...', '\u00A0': ' ', 'Å“': 'oe', 'Å’': 'OE', 'â‚¬': 'Euros', 'Â°': 'o' 
    }
    for k, v in replacements.items(): text = text.replace(k, v)
    return text

def generer_pdf_contrat(data):
    # =======================================================
    # 1. LA MACHINE À LAVER MAGIQUE POUR LES DONNÉES
    # =======================================================
    for k, v in data.items():
        if v is not None:
            data[k] = clean_text(str(v))
            
    def ct(texte):
        return clean_text(texte)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Chemin du fichier
    dossier_app = os.path.abspath(os.path.dirname(__file__))
    chemin_pdf = os.path.join(dossier_app, "Projet_Contrat_MCAT.pdf")

    # ==========================================
    # PAGE 1 : PAGE DE GARDE 
    # ==========================================
    pdf.add_page()

    # Récupération de la direction (avec valeur par défaut si non fournie)
    direction_nom = data.get('direction_name', "DIRECTION DE L'ADMINISTRATION GÉNÉRALE ET DE L'ÉQUIPEMENT")
# ==========================================
    # --- NOUVEL EN-TÊTE CENTRÉ (Drapeau + Textes) ---
    # ==========================================
    
    # 1. Le Drapeau (Centré)
    # Largeur page = 210mm. Centre = 105mm. Drapeau complet = 24mm (8x3). Position X = 105 - 12 = 93.
    x_flag_top = 93 
    y_flag_top = 10 
    w_band_top = 8 
    h_flag_top = 14 
    
    # Bande Verte
    pdf.set_fill_color(0, 140, 60)
    pdf.rect(x_flag_top, y_flag_top, w_band_top, h_flag_top, style='F')
    
    # Bande Jaune
    pdf.set_fill_color(255, 215, 0)
    pdf.rect(x_flag_top + w_band_top, y_flag_top, w_band_top, h_flag_top, style='F')
    
    # --- L'Étoile au centre de la bande jaune ---
    decalage_y_etoile = 4.5 # Ajuste cette valeur si l'étoile est trop haute ou trop basse
    pdf.set_xy(x_flag_top + w_band_top, y_flag_top + decalage_y_etoile) 
    pdf.set_text_color(0, 140, 60)
    pdf.set_font("ZapfDingbats", '', 11) # La police magique
    pdf.cell(w_band_top, 5, txt=chr(72), align='C') # L'étoile parfaite
    
    # Bande Rouge
    pdf.set_fill_color(230, 30, 30)
    pdf.rect(x_flag_top + (w_band_top*2), y_flag_top, w_band_top, h_flag_top, style='F')
    
    # 2. Textes : République et Ministère (Centrés avec w=0)
    y_start_text = y_flag_top + h_flag_top + 5 
    pdf.set_y(y_start_text)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 14) 
    pdf.cell(0, 6, txt=ct("République du Sénégal"), new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.set_font("Arial", 'I', 11)
    pdf.cell(0, 6, txt="Un Peuple - Un But - Une Foi", new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 8)
    pdf.set_text_color(0, 100, 0)
    pdf.multi_cell(0, 4, txt=ct("MINISTÈRE DE LA CULTURE, DE\nL'ARTISANAT ET DU TOURISME"), align='C')
    
    # 3. La petite barre tricolore (Centrée)
    y_barre = pdf.get_y() + 1
    w_barre_total = 44
    w_segment = w_barre_total / 3
    h_barre = 1.5
    # Centre = 105. Position X = 105 - (44/2) = 83.
    x_barre_start = 83 
    
    pdf.set_fill_color(0, 140, 60)
    pdf.rect(x_barre_start, y_barre, w_segment, h_barre, style='F') # Vert
    
    pdf.set_fill_color(255, 215, 0)
    pdf.rect(x_barre_start + w_segment, y_barre, w_segment, h_barre, style='F') # Jaune
    
    # --- Petite étoile magique ---
    decalage_y_barre = -1.2 # On remonte l'étoile pour la centrer
    pdf.set_xy(x_barre_start + w_segment, y_barre + decalage_y_barre)
    pdf.set_font("ZapfDingbats", '', 5.5)
    pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, txt=chr(72), align='C') # Petite étoile
    
    pdf.set_fill_color(230, 30, 30)
    pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, style='F') # Rouge                                                                              
    
    # 4. Le Logo MCAT et la Direction (Centrés proprement)
    pdf.set_xy(10, y_barre + 3)
    pdf.set_font("Arial", 'B', 30)
    pdf.set_text_color(0, 100, 0)
    pdf.cell(0, 12, txt="MCAT", new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 9) 
    
    # --- LA MAGIE EST ICI ---
    largeur_boite = 80 # Largeur de la zone de texte en mm
    x_centre = (210 - largeur_boite) / 2 # Calcul pour centrer la boîte
    pdf.set_x(x_centre) # On place le curseur au bon endroit
    
    # Ton texte avec le retour à la ligne forcé pour que ce soit joli
    direction_affichee = ct(direction_nom).replace("Administration g", "Administration\ng").replace("Administration G", "Administration\nG")
    
    # On utilise largeur_boite au lieu de 0
    pdf.multi_cell(largeur_boite, 5, txt=direction_affichee, align='C')
    
    pdf.ln(15)# On laisse respirer sous l'en-tête

    # ==========================================
    # TITRE PRINCIPAL (EN HAUT)
    # ==========================================
    pdf.set_font("Arial", "BU", 12)
    pdf.set_fill_color(225, 225, 225) 
    largeur_cellule = 25
    x_centre = (pdf.w - largeur_cellule) / 2
    pdf.set_x(x_centre) 
    pdf.cell(largeur_cellule, 6, "CONTRAT", new_x="LMARGIN", new_y="NEXT", align="C", fill=True)
    
    pdf.ln(15) # Espace avant de commencer les infos du titulaire

    # ==========================================
    # Bloc 1 : Titulaire
    # ==========================================
    pdf.set_font("Arial", "", 11)
    pdf.cell(18, 6, "Titulaire : ", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, data.get('titulaire', '').upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # NINEA / RC
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, ct(f"NINEA : {data.get('ninea', '')}, RC : {data.get('rc', '')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Compte bancaire
    pdf.set_font("Arial", "", 11)
    pdf.cell(35, 6, "Compte bancaire : ", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, data.get('compte_bancaire', ''), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(12)

    # ==========================================
    # Bloc 2 : OBJET DU MARCHÉ (Encadré par double ligne)
    # ==========================================
    y_line = pdf.get_y()
    pdf.line(10, y_line, 200, y_line)
    pdf.line(10, y_line + 1, 200, y_line + 1)
    
    pdf.ln(4)
    
    # Texte Objet
    pdf.set_font("Arial", "B", 11)
    pdf.multi_cell(0, 6, data.get('objet_marche', ''), align="C")
    
    pdf.ln(1)
    
    # Double ligne inférieure
    y_line2 = pdf.get_y()
    pdf.line(10, y_line2, 200, y_line2)
    pdf.line(10, y_line2 + 1, 200, y_line2 + 1)

    pdf.ln(12)

    # ==========================================
    # Bloc 3 : Finances
    # ==========================================
    # Montant
    pdf.set_font("Arial", "U", 11)
    pdf.cell(18, 6, "Montant", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "", 11)
    pdf.cell(3, 6, " : ", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, ct(f"{data.get('montant', '')} CFA TTC"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Financement
    pdf.set_font("Arial", "U", 11)
    pdf.cell(26, 6, "Financement", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "", 11)
    pdf.cell(3, 6, ": ", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, data.get('financement', ''), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Imputation budgétaire
    pdf.set_font("Arial", "U", 11)
    pdf.cell(42, 6, ct("Imputation budgétaire"), new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "", 11)
    pdf.cell(3, 6, " : ", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "B", 11)
    pdf.multi_cell(0, 6, ct(f"{data.get('imputation', '')}, Programme : {data.get('programme', '')}"))
    pdf.ln(3)

    # Comptable assignataire
    pdf.set_font("Arial", "U", 11)
    pdf.cell(46, 6, "Comptable assignataire", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "", 11)
    pdf.cell(3, 6, " : ", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, data.get('comptable', ''), new_x="LMARGIN", new_y="NEXT")

    # ==========================================
    # MENTION GESTION (EN BAS DE PAGE)
    # ==========================================
    # On force la position à 40 mm du bas de la page (tu peux ajuster ce chiffre : -30, -50...)
    pdf.set_y(-40) 
    
    pdf.set_font("Arial", "BU", 11)
    # ct() est ta fonction pour nettoyer le texte (clean_text)
    texte_gestion = ct(f"GESTION {data.get('gestion_annee', '2025')}")
    pdf.cell(0, 6, texte_gestion, new_x="LMARGIN", new_y="NEXT", align="C")


    # ==========================================
    # PAGE 2 : CORPS DU CONTRAT JURIDIQUE
    # ==========================================
    pdf.add_page()

    # Récupération de la direction (avec valeur par défaut si non fournie)
    direction_nom = data.get('direction_name', "DIRECTION DE L'ADMINISTRATION GÉNÉRALE ET DE L'ÉQUIPEMENT")

   # ==========================================
    # --- NOUVEL EN-TÊTE CENTRÉ (Drapeau + Textes) ---
    # ==========================================
    
    # 1. Le Drapeau (Centré)
    # Largeur page = 210mm. Centre = 105mm. Drapeau complet = 24mm (8x3). Position X = 105 - 12 = 93.
    x_flag_top = 93 
    y_flag_top = 10 
    w_band_top = 8 
    h_flag_top = 14 
    
    # Bande Verte
    pdf.set_fill_color(0, 140, 60)
    pdf.rect(x_flag_top, y_flag_top, w_band_top, h_flag_top, style='F')
    
    # Bande Jaune
    pdf.set_fill_color(255, 215, 0)
    pdf.rect(x_flag_top + w_band_top, y_flag_top, w_band_top, h_flag_top, style='F')
    
    # --- L'Étoile au centre de la bande jaune ---
    decalage_y_etoile = 4.5 # Ajuste cette valeur si l'étoile est trop haute ou trop basse
    pdf.set_xy(x_flag_top + w_band_top, y_flag_top + decalage_y_etoile) 
    pdf.set_text_color(0, 140, 60)
    pdf.set_font("ZapfDingbats", '', 11) # La police magique
    pdf.cell(w_band_top, 5, txt=chr(72), align='C') # L'étoile parfaite
    
    # Bande Rouge
    pdf.set_fill_color(230, 30, 30)
    pdf.rect(x_flag_top + (w_band_top*2), y_flag_top, w_band_top, h_flag_top, style='F')
    
    # 2. Textes : République et Ministère (Centrés avec w=0)
    y_start_text = y_flag_top + h_flag_top + 5 
    pdf.set_y(y_start_text)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 14) 
    pdf.cell(0, 6, txt=ct("République du Sénégal"), new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.set_font("Arial", 'I', 11)
    pdf.cell(0, 6, txt="Un Peuple - Un But - Une Foi", new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 8)
    pdf.set_text_color(0, 100, 0)
    pdf.multi_cell(0, 4, txt=ct("MINISTÈRE DE LA CULTURE, DE\nL'ARTISANAT ET DU TOURISME"), align='C')
    
    # 3. La petite barre tricolore (Centrée)
    y_barre = pdf.get_y() + 1
    w_barre_total = 44
    w_segment = w_barre_total / 3
    h_barre = 1.5
    # Centre = 105. Position X = 105 - (44/2) = 83.
    x_barre_start = 83 
    
    pdf.set_fill_color(0, 140, 60)
    pdf.rect(x_barre_start, y_barre, w_segment, h_barre, style='F') # Vert
    
    pdf.set_fill_color(255, 215, 0)
    pdf.rect(x_barre_start + w_segment, y_barre, w_segment, h_barre, style='F') # Jaune
    
    # --- Petite étoile magique ---
    decalage_y_barre = -1.2 # On remonte l'étoile pour la centrer
    pdf.set_xy(x_barre_start + w_segment, y_barre + decalage_y_barre)
    pdf.set_font("ZapfDingbats", '', 5.5)
    pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, txt=chr(72), align='C') # Petite étoile
    
    pdf.set_fill_color(230, 30, 30)
    pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, style='F') # Rouge                                                                              
    
    # 4. Le Logo MCAT et la Direction (Centrés proprement)
    pdf.set_xy(10, y_barre + 3)
    pdf.set_font("Arial", 'B', 30)
    pdf.set_text_color(0, 100, 0)
    pdf.cell(0, 12, txt="MCAT", new_x="LMARGIN", new_y="NEXT", align='C')
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 9) 
    
    # --- LA MAGIE EST ICI ---
    largeur_boite = 80 # Largeur de la zone de texte en mm
    x_centre = (210 - largeur_boite) / 2 # Calcul pour centrer la boîte
    pdf.set_x(x_centre) # On place le curseur au bon endroit
    
    # Ton texte avec le retour à la ligne forcé pour que ce soit joli
    direction_affichee = ct(direction_nom).replace("Administration g", "Administration\ng").replace("Administration G", "Administration\nG")
    
    # On utilise largeur_boite au lieu de 0
    pdf.multi_cell(largeur_boite, 5, txt=direction_affichee, align='C')
    
    pdf.ln(8) # On laisse respirer sous l'en-têten-tête

   # ==========================================
    # RÉFÉRENCE ET DATE (Dynamiques)
    # ==========================================
    numero = data.get('numero', '..........................')
    ref_service = data.get('ref_service', 'MTA/SG/DAGE/ges') 
    
    # 1. On force la valeur en texte et on enlève les espaces invisibles
    date_brute = str(data.get('date_lettre', '')).strip()

    # 2. Méthode blindée : Si le texte fait au moins 10 caractères et a des tirets au bon endroit (YYYY-MM-DD)
    if len(date_brute) >= 10 and date_brute[4] == '-' and date_brute[7] == '-':
        annee = date_brute[0:4]
        mois = date_brute[5:7]
        jour = date_brute[8:10]
        date_signature = f"{jour}/{mois}/{annee}"
    elif date_brute == "" or date_brute == "None":
        date_signature = "---------------------------------"
    else:
        date_signature = date_brute # Sécurité : on affiche ce qui vient si on ne reconnaît pas le format

    pdf.set_font("Arial", "B", 10)
    
    pdf.set_x(150) 
    pdf.cell(0, 5, ct(f"N° {numero} {ref_service}"), new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(6) 
    
    pdf.set_x(150) 
    pdf.cell(0, 5, ct(f"Dakar, le {date_signature}"), new_x="LMARGIN", new_y="NEXT")

    # On réduit un peu l'espace ici (de 10 à 6) pour remonter le texte
    pdf.ln(6)

    # Titre du contrat
    pdf.set_font("Arial", "BU", 12)
    pdf.cell(0, 6, "CONTRAT DE PRESTATION", new_x="LMARGIN", new_y="NEXT", align="C")
    
    # On réduit ici aussi (de 8 à 5)
    pdf.ln(5)
    
    # Soussignés
    pdf.set_font("Arial", "BU", 10)
    pdf.cell(0, 6, ct("Entre les soussignés :"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, ct("Le Ministère du Tourisme et de l'Artisanat, sis aux Almadies en face de la TFM, Dakar, désigné dans la suite du contrat sous le vocable « partie contractante » d'une part"))
    
    pdf.ln(2)
    pdf.set_font("Arial", "BU", 10)
    pdf.cell(0, 6, "ET :", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 10)
    
    nom_entreprise = data.get('titulaire', '')
    adresse = data.get('adresse_candidat', '.........................')
    tel = data.get('tel_candidat', '..........')
    compte = data.get('compte_bancaire', '................................')
    vocable = data.get('vocable', 'Prestataire')

    texte_prestataire = f"La société, « {nom_entreprise} », {adresse}, Tél : {tel} ;\n"
    texte_prestataire += f"Compte bancaire : {compte}\n"
    texte_prestataire += f"Désigné sous le vocable « {vocable} » d'autre part"
    pdf.multi_cell(0, 5, ct(texte_prestataire))

    pdf.ln(3)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, ct("Il a été convenu et arrêté ce qui suit :"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # ================= ARTICLES =================
    pdf.set_font("Arial", "BU", 10)
    pdf.cell(16, 5, "Article 1", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Arial", "", 10)
    pdf.cell(5, 5, " :", new_x="LMARGIN", new_y="NEXT")
    
    objet = data.get('objet_marche', '')
    montant_lettres = data.get('montant_lettres', '.......................')
    montant_chiffres = data.get('montant', '')
    annee = data.get('gestion_annee', '2025')

    # 🤖 Le petit robot expert en Marchés Publics (Adapté pour l'Article 1)
    # On s'assure d'utiliser ta variable "objet"
    objet_test = str(objet).lower().strip()

    # 1. Famille des TRAVAUX (BTP, infrastructures)
    if objet_test.startswith(("travaux", "aménagement", "réhabilitation", "construction", "réfection", "extension")):
        pont_francais = "la réalisation des "

    # 2. Famille des FOURNITURES (Biens matériels, équipements)
    elif objet_test.startswith(("fourniture", "équipement", "matériel", "dotation")):
        pont_francais = "l'acquisition de "
        
    # 3. Mots d'ACTION directs (Si l'utilisateur a déjà écrit l'action)
    elif objet_test.startswith(("acquisition", "achat", "livraison", "abonnement", "édition")):
        pont_francais = "l'"

    # 4. Famille des SERVICES et PRESTATIONS INTELLECTUELLES
    elif objet_test.startswith(("prestation", "service", "mission")):
        pont_francais = "l'exécution des "

    # 5. FILET DE SÉCURITÉ INFAILLIBLE
    else:
        pont_francais = "la commande relative à l'objet suivant : "

    # 🎯 Insertion dans le paragraphe de l'Article 1
    texte_art1 = f"Le présent marché a pour objet {pont_francais}{objet} pour le compte de la DAGE du Ministère du Tourisme et de l'Artisanat pour un montant de {montant_lettres} ({montant_chiffres}) francs CFA toutes taxes comprises durant la gestion {annee}."
# --- VOICI LA LIGNE QUI MANQUAIT POUR AFFICHER LE TEXTE 👇 ---
    pdf.multi_cell(0, 5, ct(texte_art1))

    pdf.ln(3)
    pdf.set_font("Arial", "BU", 10)
    pdf.cell(60, 5, ct("Article 2 : Modalités de paiement"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 10)
    
    imputation = data.get('imputation', '')
    programme = data.get('programme', '')
    
    texte_art2 = f"Le paiement sera effectué selon l'imputation suivante :\n- DAGE : {imputation}, Programme : {programme}"
    pdf.multi_cell(0, 5, ct(texte_art2))

    pdf.ln(3)
    pdf.set_font("Arial", "BU", 10)
    pdf.cell(40, 5, ct("Article 3 : Règlement"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, ct("Les règlements seront effectués selon la procédure actuelle après traitement des dossiers de liquidation par la partie contractante sur présentation d'une facture définitive en quatre (04) exemplaires."))

    pdf.ln(3)
    pdf.set_font("Arial", "BU", 10)
    pdf.cell(40, 5, ct("Article 4 : Pénalités"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, ct("En cas de non-exécution des prestations dans les conditions annoncées dans le bordereau descriptif et quantitatif, la partie contractante se réserve le droit de s'approvisionner sur le marché, après mise en demeure infructueuse aux risques et périls du prestataire."))

    pdf.ln(3)
    pdf.set_font("Arial", "BU", 10)
    pdf.cell(60, 5, ct("Article 5 : Dispositions générales"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, ct("Les dispositions relatives au code des marchés sont applicables au présent contrat qui prend effet à compter de sa signature."))

    # 1. On vérifie s'il reste assez de place en bas de page (pour éviter la séparation)
    if pdf.get_y() > 260:
        pdf.add_page()
    else:
        pdf.ln(3) # Petit espace AVANT le titre de l'article 6

    # 2. Le Titre
    pdf.set_font("Arial", "BU", 10)
    pdf.cell(60, 5, ct("Article 6 : Enregistrement et timbre"), new_x="LMARGIN", new_y="NEXT")
    
    # 3. Le texte, collé juste en dessous (grâce au new_y="NEXT" ci-dessus, et sans pdf.ln() au milieu)
    pdf.set_font("Arial", "", 10)
    
    # On récupère le vocable en minuscules (ex: fournisseur, prestataire...)
    vocable_min = str(data.get('vocable', 'prestataire')).lower()
    
    pdf.multi_cell(0, 5, ct(f"Les frais d'enregistrement et de timbre sont à la charge du {vocable_min}."))

    pdf.ln(3)

    # Article 7
    pdf.set_font("Arial", "BU", 10)
    pdf.cell(40, 5, ct("Article 7 : Litiges"), new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(1) 
    
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, ct("Les litiges survenus au cours de l'exécution des prestations seront traités à l'amiable ou à défaut par un tribunal compétent en la matière."))

    # Signatures
    pdf.ln(10) # Réduit de 15 à 10 pour que ça tienne bien en bas de la page 2
    pdf.set_font("Arial", "B", 10) 
    pdf.cell(0, 5, ct("Lu et accepté"), new_x="LMARGIN", new_y="NEXT", align="C") 

    pdf.ln(8) # Réduit de 10 à 8
    pdf.set_font("Arial", "B", 10)
    pdf.cell(90, 5, "Le Prestataire", new_x="RIGHT", new_y="TOP", align="L")
    pdf.cell(0, 5, "Le Directeur de l'Administration", new_x="LMARGIN", new_y="NEXT", align="R")
    pdf.cell(0, 5, ct("Générale et de l'Équipement"), new_x="LMARGIN", new_y="NEXT", align="R")

    # On génère le fichier
    pdf.output(chemin_pdf)
    
    return chemin_pdf
