import os
import io
from fpdf import FPDF
from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Rect, Polygon
from reportlab.graphics import renderPDF
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
    return text.encode('latin-1', 'replace').decode('latin-1')

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
# --- DESSIN GRAPHIQUE ---
    x_flag_top = 43; y_flag_top = 10; w_band_top = 8; h_flag_top = 14 
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_flag_top, y_flag_top, w_band_top, h_flag_top, 'F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_flag_top + w_band_top, y_flag_top, w_band_top, h_flag_top, 'F')
    pdf.set_xy(x_flag_top + w_band_top, y_flag_top + 5); pdf.set_text_color(0, 140, 60); pdf.set_font("Arial", '', 20) 
    pdf.cell(w_band_top, h_flag_top - 4, "*", align='C')
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
    pdf.set_xy(x_barre_start + w_segment, y_barre - 0.5); pdf.set_font("Arial", '', 10); pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, "*", align='C'); pdf.set_fill_color(230, 30, 30); pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, 'F')
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

    # ENREGISTREMENT
    dossier_cible = os.path.join(current_app.root_path, 'static', 'documents_generes')
    if not os.path.exists(dossier_cible):
        os.makedirs(dossier_cible)

    chemin_complet = os.path.join(dossier_cible, nom_fichier)
    pdf.output(chemin_complet)

    return os.path.join('documents_generes', nom_fichier)


# ... (Tout ton code existant reste au dessus) ...

def dessiner_drapeau():
    # Dimensions du drapeau
    width = 1.5 * cm
    height = 1.0 * cm
    d = Drawing(width, height)
    
    # Largeur d'une bande
    w_band = width / 3
    
    # Bande Verte
    d.add(Rect(0, 0, w_band, height, fillColor=colors.HexColor('#00853F'), strokeColor=None))
    # Bande Jaune
    d.add(Rect(w_band, 0, w_band, height, fillColor=colors.HexColor('#FDEF42'), strokeColor=None))
    # Bande Rouge
    d.add(Rect(w_band * 2, 0, w_band, height, fillColor=colors.HexColor('#E31B23'), strokeColor=None))
    
    # Étoile Verte (approximative) au centre
    cx, cy = width / 2, height / 2
    r = w_band * 0.35 # Rayon de l'étoile
    # Points de l'étoile
    points = [
        cx, cy + r,
        cx + r * 0.22, cy + r * 0.3,
        cx + r * 0.95, cy + r * 0.3,
        cx + r * 0.36, cy - r * 0.11,
        cx + r * 0.58, cy - r * 0.8,
        cx, cy - r * 0.38,
        cx - r * 0.58, cy - r * 0.8,
        cx - r * 0.36, cy - r * 0.11,
        cx - r * 0.95, cy + r * 0.3,
        cx - r * 0.22, cy + r * 0.3,
    ]
    d.add(Polygon(points, fillColor=colors.HexColor('#00853F'), strokeColor=None))
    return d

def generer_pdf_bordereau(buffer, data):
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1*cm, leftMargin=1.5*cm,
                            topMargin=0.5*cm, bottomMargin=1*cm)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # --- STYLES ---
    style_normal = ParagraphStyle(name='Times', parent=styles['Normal'], fontName='Times-Roman', fontSize=10, leading=12)
    style_center_bold = ParagraphStyle(name='CenterBold', parent=style_normal, alignment=TA_CENTER, fontName='Times-Bold')
    style_center_italic = ParagraphStyle(name='CenterItalic', parent=style_normal, alignment=TA_CENTER, fontName='Times-Italic', fontSize=9)
    
    # MODIFICATION 1 : On met textColor=colors.black (au lieu de colors.red)
    style_red_bold = ParagraphStyle(name='RedBold', parent=style_center_bold, textColor=colors.black)
    
    # MODIFICATION 2 : Le numéro en haut à droite en noir
    style_num_right = ParagraphStyle(name='NumRight', parent=style_normal, alignment=TA_RIGHT, fontName='Times-Bold', textColor=colors.black, fontSize=11)
    
    style_date_right = ParagraphStyle(name='DateRight', parent=style_normal, alignment=TA_RIGHT, fontName='Times-Bold')
    
    # --- EN-TÊTE ---
    drapeau = dessiner_drapeau()
    txt_republique = Paragraph("<b>REPUBLIQUE DU SENEGAL</b>", style_center_bold)
    txt_devise = Paragraph("<i>Un Peuple – Un But – Une Foi</i>", style_center_italic)
    separateur = Paragraph("--------------------", style_center_bold)
    txt_ministere = Paragraph("<b>MINISTERE DU TOURISME<br/>ET DE L’ARTISANAT</b>", style_center_bold)
    
    # Utilisation du style noir défini plus haut
    txt_direction = Paragraph(f"<b>{data['direction']}</b>", style_red_bold)

    col_gauche = [drapeau, txt_republique, txt_devise, separateur, txt_ministere, separateur, txt_direction, separateur]
    
    ref_complete = f"N°  {data['numero']}  {data['service_ref']}"
    txt_numero = Paragraph(f"<b>{ref_complete}</b>", style_num_right)
    txt_date = Paragraph(f"<b>Dakar, le {data['date']}</b>", style_date_right)
    
    col_droite = [Spacer(1, 1*cm), txt_numero, Spacer(1, 1.5*cm), txt_date]

    table_gauche = Table([[item] for item in col_gauche], colWidths=[9*cm])
    table_gauche.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))

    header_table = Table([[table_gauche, col_droite]], colWidths=[10*cm, 8*cm])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (1,0), (1,-1), 'RIGHT')]))
    elements.append(header_table)
    
    # --- TITRE ET DESTINATAIRE ---
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph("<b>BORDEREAU D’ENVOI</b>", ParagraphStyle('TitreGros', parent=style_center_bold, fontSize=16)))
    elements.append(Paragraph("-----------------------------------", style_center_bold))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph("<b>A</b>", style_center_bold))
    elements.append(Paragraph("Monsieur le Coordonnateur de la Cellule de Passation des Marchés Publics", ParagraphStyle('Dest', parent=style_center_bold, fontSize=11)))
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
        texte_designation = f"""- Demande de Renseignements et de Prix Restreinte relative aux 
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

def generer_pdf_lettre_information(buffer, data):
    """
    Génère la Lettre d'Information au format PDF avec FPDF
    Correction de la Direction (retour à la ligne) et du N° (alignement horizontal)
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
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
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_flag_top, y_flag_top, w_band_top, h_flag_top, 'F')
    
    # Bande Jaune
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_flag_top + w_band_top, y_flag_top, w_band_top, h_flag_top, 'F')
    
    # --- L'ÉTOILE (Astérisque) ---
    decalage_y_etoile = 6
    pdf.set_xy(x_flag_top + w_band_top, y_flag_top + decalage_y_etoile) 
    pdf.set_text_color(0, 140, 60)
    pdf.set_font("Arial", '', 22) 
    
    pdf.cell(w_band_top, 5, "*", align='C') 
    
    # Bande Rouge
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
    pdf.set_xy(x_barre_start + w_segment, y_barre - 0.5); pdf.set_font("Arial", '', 10); pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, "*", align='C'); pdf.set_fill_color(230, 30, 30); pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, 'F')                                                                                                     
    
    pdf.set_xy(10, y_barre + 3); pdf.set_font("Arial", 'B', 30); pdf.set_text_color(0, 100, 0)
    pdf.cell(90, 12, txt="MCAT", ln=1, align='C')
    
    # --- CORRECTION 1 : Direction sur 2 lignes centrée ---
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 9) 
    direction_affichee = clean_text(direction_nom)
    direction_affichee = direction_affichee.replace("Administration g", "Administration\ng").replace("Administration G", "Administration\nG")
    
    pdf.set_x(15) 
    pdf.multi_cell(80, 5, txt=direction_affichee, align='C')

    # --- CORRECTION 2 : N° et Réf sur la MEME LIGNE ---
    pdf.set_xy(110, y_start_text + 5)
    texte_num = clean_text(f"N° {num_ordre}  ")
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    largeur_num = pdf.get_string_width(texte_num) 
    pdf.cell(largeur_num, 5, txt=texte_num)
    
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, txt=clean_text(ref_service), ln=1)
    
    pdf.ln(15); pdf.set_x(125)
    pdf.set_text_color(0, 0, 0) 
    pdf.cell(0, 5, txt=clean_text(f"Dakar, le {date_lettre}"), ln=1)
    
    pdf.ln(30); pdf.set_x(95); pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(0, 0, 0) 
    pdf.multi_cell(0, 6, txt=clean_text(f"{signataire},"))

    # --- 3. OBJET & CORPS DE LA LETTRE ---
    marge_gauche_texte = 25 
    pdf.set_left_margin(marge_gauche_texte)
    pdf.set_xy(marge_gauche_texte, max(pdf.get_y(), 95) + 5) 

    h_ligne = 7
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font("Arial", 'BU', 11)
    pdf.write(h_ligne, "* Objet")
    pdf.set_font("Arial", 'B', 11)
    pdf.write(h_ligne, " : Lettre d'information")
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 11)
    pdf.write(5, "Messieurs,")
    pdf.ln(10)

    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text("Suite à l'évaluation et à l'attribution par la commission des marchés, des offres relatives à la Demande de Renseignements et de Prix restreinte portant sur « "))
    
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(data.get('objet_marche', '...')))
    
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, " » immatriculée ")
    
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(data.get('immatriculation', '...')))
    
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, " en date du ")
    
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(date_commission))
    
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, ", pour le compte de la ")
    
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(direction_nom))
    
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(", je vous informe que votre entreprise n'a pas été retenue comme attributaire de ladite demande de renseignements et de prix."))
    
    pdf.ln(10)

    # Paragraphe 2
    pdf.write(h_ligne, clean_text("A ce titre, je vous prie de bien vouloir passer à la "))
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0) 
    pdf.write(h_ligne, clean_text(direction_nom))
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(" pour récupérer le procès-verbal d'ouverture et d'évaluation des offres."))
    
    pdf.ln(10) 

    # Paragraphe 3
    pdf.write(h_ligne, clean_text("Je vous prie d'agréer, Monsieur le Directeur, l'assurance de ma considération distinguée."))
    
    pdf.ln(15)

    # --- 4. TABLEAU DES PRESTATAIRES ---
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    
    # On harmonise les tailles de l'entête et du contenu pour que ça reste dans les marges
    largeur_col1 = 65 
    largeur_col2 = 110 
    
    pdf.cell(largeur_col1, 15, "PRESTATAIRES", border=1, align='C')
    pdf.cell(largeur_col2, 15, "ADRESSES", border=1, align='C', ln=1)

    pdf.set_font("Arial", '', 10)

    prestataires_liste = data.get('prestataires', [])

    if not prestataires_liste:
        pdf.cell(largeur_col1 + largeur_col2, 7, "Aucun prestataire sélectionné", border=1, align='C', ln=1)
    else:
        for candidat in prestataires_liste:
            nom_entreprise = candidat.get('nom', 'Nom non renseigné')
            chaine_adresse = candidat.get('adresse', 'Adresse non renseignée')
            
            x_depart = pdf.get_x()
            y_depart = pdf.get_y()
            
            # --- 1. ON ÉCRIT LE TEXTE SANS BORDURES (border=0) ---
            # Colonne 1
            pdf.multi_cell(largeur_col1, 6, clean_text(nom_entreprise), border=0, align='L')
            y_col1 = pdf.get_y()
            
            # On se décale pour la colonne 2
            pdf.set_xy(x_depart + largeur_col1, y_depart)
            
            # Colonne 2
            pdf.multi_cell(largeur_col2, 6, clean_text(chaine_adresse), border=0, align='L')
            y_col2 = pdf.get_y()
            
            # --- 2. ON MESURE QUELLE COLONNE EST LA PLUS GRANDE ---
            y_max = max(y_col1, y_col2)
            hauteur_ligne = y_max - y_depart
            
            # --- 3. ON DESSINE LES BORDURES MANUELLEMENT PAR-DESSUS ---
            # On dessine le grand rectangle extérieur qui englobe toute la ligne
            pdf.rect(x_depart, y_depart, largeur_col1 + largeur_col2, hauteur_ligne)
            # On trace la ligne verticale au milieu pour séparer les deux colonnes
            pdf.line(x_depart + largeur_col1, y_depart, x_depart + largeur_col1, y_max)
            
            # Reset au point le plus bas pour le candidat suivant
            pdf.set_xy(x_depart, y_max)

    # --- 5. PIED DE PAGE ---
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-25)
    pdf.set_draw_color(145, 190, 100)  
    pdf.set_line_width(1.5)            
    
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Times", '', 11) 
    
    pdf.cell(0, 5, clean_text("Ministère de la Culture, de l'Artisanat et du Tourisme,"), align='C', ln=1)
    pdf.cell(0, 5, clean_text("Route des Almadies, Dakar Sénégal"), align='C', ln=1)
        
    # 5. Sauvegarde en mémoire
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    buffer.write(pdf_bytes)

def generer_pdf_lettre_notification(buffer, data):
    """
    Génère la Lettre de Notification au format PDF avec FPDF.
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
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_flag_top, y_flag_top, w_band_top, h_flag_top, 'F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_flag_top + w_band_top, y_flag_top, w_band_top, h_flag_top, 'F')
    
    # L'Étoile
    decalage_y_etoile = 6
    pdf.set_xy(x_flag_top + w_band_top, y_flag_top + decalage_y_etoile) 
    pdf.set_text_color(0, 140, 60)
    pdf.set_font("Arial", '', 22) 
    pdf.cell(w_band_top, 5, "*", align='C') 
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_flag_top + (w_band_top*2), y_flag_top, w_band_top, h_flag_top, 'F')
    
    # République et Ministère
    y_start_text = y_flag_top + h_flag_top + 5 
    pdf.set_y(y_start_text); pdf.set_text_color(0, 0, 0); pdf.set_font("Times", 'B', 14)
    pdf.cell(90, 6, txt=clean_text("République du Sénégal"), ln=1, align='C')
    pdf.set_font("Times", 'I', 11); pdf.cell(90, 6, txt="Un Peuple - Un But - Une Foi", ln=1, align='C')
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(0, 100, 0)
    pdf.multi_cell(90, 4, txt=clean_text("MINISTÈRE DE LA CULTURE, DE\nL'ARTISANAT ET DU TOURISME"), align='C')
    
    # Barre tricolore
    y_barre = pdf.get_y() + 1; w_barre_total = 44; x_barre_start = 33; w_segment = w_barre_total / 3; h_barre = 1.5
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_barre_start, y_barre, w_segment, h_barre, 'F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_barre_start + w_segment, y_barre, w_segment, h_barre, 'F')
    pdf.set_xy(x_barre_start + w_segment, y_barre - 0.5); pdf.set_font("Arial", '', 10); pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, "*", align='C'); pdf.set_fill_color(230, 30, 30); pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, 'F')                                                                                                     
    
    # MCAT Logo texte
    pdf.set_xy(10, y_barre + 3); pdf.set_font("Arial", 'B', 30); pdf.set_text_color(0, 100, 0)
    pdf.cell(90, 12, txt="MCAT", ln=1, align='C')
    
    # Direction sous le MCAT (en rouge)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 9) 
    direction_affichee = clean_text(direction_nom).replace("Administration g", "Administration\ng").replace("Administration G", "Administration\nG")
    pdf.set_x(15) 
    pdf.multi_cell(80, 5, txt=direction_affichee, align='C')

    # --- 2. RÉFÉRENCES ET DATE ---
    pdf.set_xy(110, y_start_text + 5)
    texte_num = clean_text(f"N° {num_ordre}  ")
    pdf.set_font("Arial", '', 11)
    pdf.set_text_color(0, 0, 0)
    largeur_num = pdf.get_string_width(texte_num) 
    pdf.cell(largeur_num, 5, txt=texte_num)
    
    # Réf Service en rouge
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 5, txt=clean_text(ref_service), ln=1)
    
    # Date
    pdf.ln(15); pdf.set_x(125)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 5, txt=clean_text(f"Dakar, le {date_lettre}"), ln=1)
    
    # Signataire (en rouge)
    pdf.ln(30); pdf.set_x(40); pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(0, 0, 0) 
    pdf.multi_cell(0, 6, txt=clean_text(f"{signataire},"), align='C')

    # --- 3. OBJET ET CORPS DE LA LETTRE ---
    marge_gauche_texte = 25 
    pdf.set_left_margin(marge_gauche_texte)
    
    # --- POUR MONTER OU DESCENDRE LE CORPS DE LA LETTRE ---
    # Diminue ce chiffre (ex: 75, 80) pour le MONTER
    # Augmente ce chiffre (ex: 100, 110) pour le DESCENDRE
    hauteur_corps_lettre = 100 
    
    pdf.set_xy(marge_gauche_texte, hauteur_corps_lettre)

    h_ligne = 7
    
    # Objet
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'BU', 11)
    pdf.write(h_ligne, "Objet")
    pdf.set_font("Arial", 'B', 11)
    pdf.write(h_ligne, " : Lettre de notification")
    pdf.ln(12)

    # Civilité (en rouge)
    civilite = data.get('civilite_representant', 'Monsieur le Directeur Général,')
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.write(5, clean_text(civilite))
    pdf.ln(10)

    # --- PARAGRAPHE 1 ---
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text("Suite à l'évaluation et à l'attribution par la commission des marchés, des offres relatives à la Demande de Renseignements et de Prix restreinte portant sur « "))
    
    # Objet marché en rouge gras
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(data.get('objet_marche', '...')))
    
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, " » immatriculée ")
    
    # Immatriculation en rouge gras
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(data.get('immatriculation', '...')))
    
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, " en date du ")
    
    # Date commission en rouge gras
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(date_commission))
    
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, ", pour le compte de la ")
    
    # Direction en rouge normal
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0)
    direction_inline = clean_text(data.get('direction_name', "Direction de l'Administration Générale et de l'Equipement"))
    pdf.write(h_ligne, direction_inline)
    
    # Fin de phrase en noir normal
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(", je vous informe que votre entreprise a été retenue comme attributaire de ladite demande de renseignements et de prix."))
    
    pdf.ln(10)

    # --- PARAGRAPHE 2 ---
    pdf.write(h_ligne, clean_text("A ce titre, je vous prie de bien vouloir passer à la "))
    
    # Direction en rouge normal
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0) 
    pdf.write(h_ligne, direction_inline)
    
    # Fin de phrase en noir
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(" pour récupérer le procès-verbal d'ouverture et d'évaluation des offres et de signer le contrat."))
    
    pdf.ln(10) 

    # --- PARAGRAPHE 3 ---
    pdf.write(h_ligne, clean_text("Je vous prie d'agréer, "))
    
    # Civilité clôture en rouge gras
    pdf.set_font("Arial", 'B', 11); pdf.set_text_color(0, 0, 0)
    civilite_cloture = civilite.replace(",", "") # On enlève la virgule s'il y en a une pour l'insérer proprement
    pdf.write(h_ligne, clean_text(civilite_cloture))
    
    # Fin de politesse en noir
    pdf.set_font("Arial", '', 11); pdf.set_text_color(0, 0, 0)
    pdf.write(h_ligne, clean_text(", l'assurance de ma considération distinguée."))
    
    pdf.ln(15)


    # === BLOC DESTINATAIRE ===
    # 1. POUR LE MONTER PLUS HAUT : on augmente le chiffre négatif 
    # (-75 veut dire qu'on se place à 75 mm en partant du bas de la page, au lieu de 50)
    pdf.set_y(-75) 
    
    # 2. POUR LE METTRE À GAUCHE : on diminue la marge
    # (25 mm permet de l'aligner parfaitement avec le reste de ton texte. Mets 10 si tu le veux tout au bord)
    marge_gauche = 25 
    
    # On met la couleur du texte en ROUGE (RGB: 255, 0, 0)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 11)

    # Récupération des données
    civilite = data.get('civilite_representant', 'Monsieur le Directeur Général')
    entreprise = data.get('destinataire_nom', 'ENTREPRISE NON RENSEIGNÉE')
    adresse = data.get('destinataire_adresse', '')
    tel = data.get('destinataire_tel', '')

    # Écriture ligne par ligne
    pdf.set_x(marge_gauche)
    pdf.cell(0, 6, "A", ln=1)
    
    pdf.set_x(marge_gauche)
    # Petite astuce : on enlève la virgule de la civilité si elle a été tapée dans le formulaire
    civilite_propre = civilite.replace(',', '')
    pdf.cell(0, 6, f"{civilite_propre} de {entreprise}".upper(), ln=1)
    
    pdf.set_x(marge_gauche)
    pdf.cell(0, 6, adresse, ln=1)
    
    pdf.set_x(marge_gauche)
    if tel and tel != "Non renseigné":
        pdf.cell(0, 6, f"Tél: {tel}", ln=1)

    # On remet le texte en NOIR par sécurité pour la suite
    pdf.set_text_color(0, 0, 0)
    
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
    pdf.cell(0, 5, clean_text("Ministère de la Culture, de l'Artisanat et du Tourisme,"), align='C', ln=1)
    pdf.cell(0, 5, clean_text("Route des Almadies, Dakar Sénégal"), align='C', ln=1)
        
    # Sauvegarde en mémoire
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
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
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_flag_top, y_flag_top, w_band_top, h_flag_top, 'F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_flag_top + w_band_top, y_flag_top, w_band_top, h_flag_top, 'F')
    
    # L'Étoile
    decalage_y_etoile = 6
    pdf.set_xy(x_flag_top + w_band_top, y_flag_top + decalage_y_etoile) 
    pdf.set_text_color(0, 140, 60)
    pdf.set_font("Arial", '', 22) 
    pdf.cell(w_band_top, 5, "*", align='C') 
    
    pdf.set_fill_color(230, 30, 30); pdf.rect(x_flag_top + (w_band_top*2), y_flag_top, w_band_top, h_flag_top, 'F')
    
    # République et Ministère
    y_start_text = y_flag_top + h_flag_top + 5 
    pdf.set_y(y_start_text); pdf.set_text_color(0, 0, 0); pdf.set_font("Times", 'B', 14)
    pdf.cell(90, 6, txt=clean_text("République du Sénégal"), ln=1, align='C')
    pdf.set_font("Times", 'I', 11); pdf.cell(90, 6, txt="Un Peuple - Un But - Une Foi", ln=1, align='C')
    pdf.ln(2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(0, 100, 0)
    pdf.multi_cell(90, 4, txt=clean_text("MINISTÈRE DE LA CULTURE, DE\nL'ARTISANAT ET DU TOURISME"), align='C')
    
    # Barre tricolore
    y_barre = pdf.get_y() + 1; w_barre_total = 44; x_barre_start = 33; w_segment = w_barre_total / 3; h_barre = 1.5
    pdf.set_fill_color(0, 140, 60); pdf.rect(x_barre_start, y_barre, w_segment, h_barre, 'F')
    pdf.set_fill_color(255, 215, 0); pdf.rect(x_barre_start + w_segment, y_barre, w_segment, h_barre, 'F')
    pdf.set_xy(x_barre_start + w_segment, y_barre - 0.5); pdf.set_font("Arial", '', 10); pdf.set_text_color(0, 140, 60) 
    pdf.cell(w_segment, 4, "*", align='C'); pdf.set_fill_color(230, 30, 30); pdf.rect(x_barre_start + (w_segment*2), y_barre, w_segment, h_barre, 'F')                                                                                
    
    # MCAT Logo texte
    pdf.set_xy(10, y_barre + 3); pdf.set_font("Arial", 'B', 30); pdf.set_text_color(0, 100, 0)
    pdf.cell(90, 12, txt="MCAT", ln=1, align='C')
    
    # Direction sous le MCAT 
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 9) 
    direction_affichee = clean_text(direction_nom).replace("Administration g", "Administration\ng").replace("Administration G", "Administration\nG")
    pdf.set_x(15) 
    pdf.multi_cell(80, 5, txt=direction_affichee, align='C')

    # ==========================================
    # --- 2. RÉFÉRENCES ET DATE ---
    # ==========================================
    pdf.set_xy(110, y_start_text + 5)
    texte_num = clean_text(f"N° {num_ordre}  ")
    pdf.set_font("Arial", '', 11)
    pdf.set_text_color(0, 0, 0)
    largeur_num = pdf.get_string_width(texte_num) 
    pdf.cell(largeur_num, 5, txt=texte_num)
    
    # Réf Service 
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 5, txt=clean_text(ref_service), ln=1)
    
    # Date
    pdf.ln(15); pdf.set_x(125)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 5, txt=clean_text(f"Dakar, le {date_lettre}"), ln=1)
    
    # Signataire
    pdf.ln(30); pdf.set_x(40); pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(0, 0, 0) 
    pdf.multi_cell(0, 6, txt=clean_text(f"{signataire},"), align='C')

    # ==========================================
    # --- 3. TITRE DU DOCUMENT ---
    # ==========================================
    pdf.ln(15)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'BU', 14)
    pdf.cell(0, 8, "PROCES - VERBAL D'ATTRIBUTION", align='C', ln=1)
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
    # On récupère les textes et on formate la date de commission
    date_commission_brute = data.get('date_commission', '')
    date_commission = formater_date_en_francais(date_commission_brute)
    
    entreprise = data.get('entreprise_attributaire', "l'entreprise non renseignée")
    adresse = data.get('adresse_direction', 'route des Almadies, Dakar')
    immatriculation = data.get('immatriculation', '')
    objet_marche = data.get('objet_marche', '')

    # Réglage des marges et de la police
    marge = 20
    pdf.set_left_margin(marge)
    pdf.set_right_margin(marge)
    pdf.set_x(marge)
    
    hauteur_ligne = 7
    pdf.set_font("Arial", '', 12)
    pdf.set_text_color(0, 0, 0) 
    
    # --- PARAGRAPHE 1 ---
    paragraphe_1 = (
        f"{direction_nom} du Ministère de la Culture, de l'Artisanat et du Tourisme, "
        f"{adresse} a procédé à l'attribution "
        f"des offres reçues dans le cadre de la demande de renseignements et de prix restreinte "
        f"N° {immatriculation} portant sur « {objet_marche} »."
    )
    pdf.multi_cell(0, hauteur_ligne, txt=paragraphe_1.encode('latin-1', 'replace').decode('latin-1'), align='J')
    pdf.ln(5)

    # --- PARAGRAPHE 2 ---
    paragraphe_2 = (
        f"Après avoir procédé à la vérification et au constat de la conformité des offres reçues (voir PV d'analyse, "
        f"d'évaluation et d'attribution des offres de la commission des marchés en date du "
        f"{date_commission}), l'entreprise « {entreprise} » a été déclarée moins disante."
    )
    pdf.multi_cell(0, hauteur_ligne, txt=paragraphe_2.encode('latin-1', 'replace').decode('latin-1'), align='J')
    pdf.ln(5)
    
    # --- PARAGRAPHE 3 ---
    paragraphe_3 = "En conséquence le procès-verbal d'attribution est établi pour servir et valoir ce que de droit."
    pdf.multi_cell(0, hauteur_ligne, txt=paragraphe_3.encode('latin-1', 'replace').decode('latin-1'), align='J')

    # ==========================================
    # --- 5. SECONDE SIGNATURE (BAS À GAUCHE) ---
    # ==========================================
    pdf.ln(25) # On saute quelques lignes après le texte final
    pdf.set_x(20) # On se cale sur la marge de gauche
    
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(0, 0, 0)
    
    # On récupère le texte tapé dans le textarea
    texte_signature_bas = data.get('signataire_bas', '')
    pdf.multi_cell(90, 6, txt=clean_text(texte_signature_bas), align='L')

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
    pdf.cell(0, 5, clean_text("Ministère de la Culture, de l'Artisanat et du Tourisme,"), align='C', ln=1)
    pdf.cell(0, 5, clean_text("Route des Almadies, Dakar Sénégal"), align='C', ln=1)
        
    # ==========================================
    # --- 7. FIN DU DOCUMENT ---
    # ==========================================
    # C'est ICI et seulement ICI qu'on génère la sortie
    pdf_val = pdf.output(dest='S')
    
    if isinstance(pdf_val, str):
        buffer.write(pdf_val.encode('latin-1'))
    else:
        buffer.write(pdf_val)
