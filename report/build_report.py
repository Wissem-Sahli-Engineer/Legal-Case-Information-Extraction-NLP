"""
Génère le rapport PDF du projet (mise en page d'article scientifique sur une colonne, comme « Attention Is All You Need »).

    python report/build_report.py      ->  report/rapport_extraction_decisions_justice.pdf

Les chiffres des tableaux sont lus dans results/ (produits par les notebooks) et les figures dans figures/.
"""
import json
import os
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)
from reportlab.platypus.flowables import HRFlowable

ROOT = Path(__file__).resolve().parent.parent
RES, FIG = ROOT / "results", ROOT / "figures"
OUT = ROOT / "report" / "rapport_extraction_decisions_justice.pdf"

# ----------------------------------------------------------------------------
# Polices (Times New Roman si disponible, sinon Times intégré à ReportLab)
# ----------------------------------------------------------------------------
FONT_DIR = "/System/Library/Fonts/Supplemental/"
if os.path.exists(FONT_DIR + "Times New Roman.ttf"):
    for name, file in [("TNR", "Times New Roman.ttf"), ("TNR-B", "Times New Roman Bold.ttf"),
                       ("TNR-I", "Times New Roman Italic.ttf"), ("TNR-BI", "Times New Roman Bold Italic.ttf")]:
        pdfmetrics.registerFont(TTFont(name, FONT_DIR + file))
    addMapping("TNR", 0, 0, "TNR"); addMapping("TNR", 1, 0, "TNR-B")
    addMapping("TNR", 0, 1, "TNR-I"); addMapping("TNR", 1, 1, "TNR-BI")
    F, FB, FI = "TNR", "TNR-B", "TNR-I"
else:
    F, FB, FI = "Times-Roman", "Times-Bold", "Times-Italic"

# ----------------------------------------------------------------------------
# Mise en page : A4, une seule colonne (comme « Attention Is All You Need », format NeurIPS)
# ----------------------------------------------------------------------------
PAGE_W, PAGE_H = A4
M_LR, M_TOP, M_BOT = 2.6 * cm, 2.5 * cm, 2.5 * cm
TEXT_W = PAGE_W - 2 * M_LR          # largeur du texte (~15,8 cm)
COL_W = 12 * cm                     # largeur par défaut des tableaux (centrés)
FIG_W = 10.5 * cm                   # largeur par défaut des figures (centrées)
BODY_H = PAGE_H - M_TOP - M_BOT


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(F, 9)
    canvas.drawCentredString(PAGE_W / 2, 1.4 * cm, str(doc.page))
    canvas.restoreState()


doc = BaseDocTemplate(str(OUT), pagesize=A4, title="Extraction d'informations dans les décisions de justice",
                      author="Wissem Sahli")
doc.addPageTemplates([
    PageTemplate(id="onecol", frames=[Frame(M_LR, M_BOT, TEXT_W, BODY_H, id="one",
                                            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=footer),
])

# ----------------------------------------------------------------------------
# Styles
# ----------------------------------------------------------------------------
S = {
    "title": ParagraphStyle("title", fontName=FB, fontSize=17, leading=21, alignment=TA_CENTER, spaceBefore=6, spaceAfter=8),
    "author": ParagraphStyle("author", fontName=F, fontSize=11, leading=14, alignment=TA_CENTER),
    "affil": ParagraphStyle("affil", fontName=FI, fontSize=9.5, leading=12, alignment=TA_CENTER, spaceAfter=12),
    "abs_h": ParagraphStyle("abs_h", fontName=FB, fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=4),
    "abs": ParagraphStyle("abs", fontName=F, fontSize=10, leading=12.5, alignment=TA_JUSTIFY, leftIndent=1.2 * cm, rightIndent=1.2 * cm, spaceAfter=10),
    "body": ParagraphStyle("body", fontName=F, fontSize=10.3, leading=13, alignment=TA_JUSTIFY, spaceAfter=5.5),
    "bullet": ParagraphStyle("bullet", fontName=F, fontSize=10.3, leading=13, alignment=TA_JUSTIFY, leftIndent=14, bulletIndent=3, spaceAfter=2.5),
    "h1": ParagraphStyle("h1", fontName=FB, fontSize=12, leading=15, spaceBefore=12, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName=FB, fontSize=10.5, leading=13, spaceBefore=8, spaceAfter=4),
    "caption": ParagraphStyle("caption", fontName=F, fontSize=9, leading=11, alignment=TA_JUSTIFY, leftIndent=0.8 * cm, rightIndent=0.8 * cm, spaceBefore=3, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName=F, fontSize=8.6, leading=10.2, alignment=TA_LEFT),
    "cellb": ParagraphStyle("cellb", fontName=FB, fontSize=8.6, leading=10.2, alignment=TA_LEFT),
    "ref": ParagraphStyle("ref", fontName=F, fontSize=9, leading=11, alignment=TA_JUSTIFY, leftIndent=18, firstLineIndent=-18, spaceAfter=3),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8, leading=9.6, leftIndent=0.8 * cm, spaceAfter=0),
}

story = []
counters = {"fig": 0, "tab": 0}


def P(text, style="body"):
    story.append(Paragraph(text, S[style]))


def bullets(items):
    for it in items:
        story.append(Paragraph(it, S["bullet"], bulletText="•"))
    story.append(Spacer(1, 3))


def H1(text):
    story.append(Paragraph(text, S["h1"]))


def H2(text):
    story.append(Paragraph(text, S["h2"]))


def figure(path, caption, width=FIG_W):
    counters["fig"] += 1
    img = Image(str(path))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width, width * ratio
    story.append(KeepTogether([img, Paragraph(f"<b>Figure {counters['fig']} :</b> {caption}", S["caption"])]))
    return counters["fig"]


def table(rows, caption, col_widths=None, bold_rows=(), width=COL_W):
    """Tableau style « article » : filets en haut, sous l'en-tête et en bas (comme dans Attention Is All You Need)."""
    counters["tab"] += 1
    data = [[Paragraph(str(c), S["cellb"] if (r == 0 or r in bold_rows) else S["cell"]) for c in row] for r, row in enumerate(rows)]
    widths = col_widths or [width / len(rows[0])] * len(rows[0])
    widths = [w * width / sum(widths) for w in widths]          # le tableau occupe toujours la largeur COL_W, centré
    t = Table(data, colWidths=widths, hAlign="CENTER")
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.0, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 1.0, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.5), ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(KeepTogether([Paragraph(f"<b>Tableau {counters['tab']} :</b> {caption}", S["caption"]), t, Spacer(1, 8)]))
    return counters["tab"]


def pct(x, d=1):
    return f"{100 * x:.{d}f} %".replace(".", ",")


def num(x, d=3):
    return f"{x:.{d}f}".replace(".", ",")


# ----------------------------------------------------------------------------
# Chargement des résultats
# ----------------------------------------------------------------------------
results = pd.read_csv(RES / "model_comparison.csv", index_col=0)
rules_summary = pd.read_csv(RES / "rules_summary.csv", index_col=0)["score"]
rules_period = pd.read_csv(RES / "rules_by_period.csv", index_col=0)
prod = pd.read_csv(RES / "production_pdf_scores.csv", index_col=0)
err_period = pd.read_csv(RES / "errors_by_period.csv", index_col=0)
val_scores = json.load(open(RES / "val_scores.json"))
final = json.load(open(ROOT / "models" / "final_model.json"))
top_words = pd.read_csv(RES / "top_words_model_a.csv")

R = results.to_dict("index")
best = final["name"]
A, B, C = R["A · TF-IDF + Régression logistique"], R["B · CNN Keras (de zéro)"], R["C · CamemBERT (fine-tuné)"]
A20, B20, NB, RULES = R["A · TF-IDF + RL (20k)"], R["B · CNN Keras (20k)"], R["A0 · TF-IDF + Naive Bayes"], R["Règles (sur le dispositif)"]


# ============================================================================
# CONTENU DU RAPPORT
# ============================================================================

# ---------------- Titre et résumé (pleine largeur) ----------------
story.append(HRFlowable(width="100%", thickness=3.2, color=colors.black, spaceBefore=0, spaceAfter=10))
P("Extraction d'informations dans les décisions de justice :<br/>règles, TF-IDF, réseau convolutif et CamemBERT<br/>"
  "sur les arrêts de la Cour de cassation", "title")
story.append(HRFlowable(width="100%", thickness=0.9, color=colors.black, spaceBefore=6, spaceAfter=14))
P("Wissem Sahli", "author")
P("Projet de traitement automatique du langage naturel (NLP) — octobre 2026", "affil")
P("Résumé", "abs_h")
P(f"Les décisions de justice sont des textes longs, peu structurés et rédigés dans une langue spécialisée. "
  f"Nous proposons une chaîne de traitement qui transforme un arrêt de la Cour de cassation, fourni en PDF natif ou scanné, "
  f"en un document JSON structuré : métadonnées (chambre, date, numéro de pourvoi, président), récit (faits, moyens), "
  f"fondements juridiques (textes de loi cités, décision attaquée) et issue (verdict, ordres, motifs). "
  f"Les champs semi-structurés sont extraits par des règles (expressions régulières), évaluées sur 1 959 décisions annotées ; "
  f"la date est retrouvée dans {pct(rules_summary['Date (exact match)'], 0)} des cas grâce à une règle qui lit les dates écrites en toutes lettres. "
  f"L'issue est prédite à partir des seules <i>motivations</i> par trois modèles comparés sur les mêmes 10 000 décisions de test : "
  f"(A) prétraitement spaCy, TF-IDF et régression logistique, (B) réseau convolutif Keras entraîné de zéro, "
  f"(C) CamemBERT fine-tuné. Sur un corpus de 100 000 arrêts tirés des 553 075 décisions de Judilibre, "
  f"les F1 macro sont respectivement de {num(A['f1_macro'])}, {num(B['f1_macro'])} et {num(C['f1_macro'])} "
  f"(CamemBERT n'ayant vu que 20 000 exemples, faute de puissance de calcul). "
  f"Testée sur les arrêts réels de 2026 (95 arrêts évaluables sur 104), postérieurs aux données d'entraînement, la chaîne PDF → JSON "
  f"retrouve l'issue avec une accuracy de {pct(prod.loc['règles', 'accuracy'], 0)} par règles sur le dispositif et de "
  f"{pct(prod.loc[['A', 'B', 'C'], 'accuracy'].max(), 0)} "
  f"pour le meilleur modèle lisant les motivations.", "abs")
story.append(Spacer(1, 4))

# ---------------- 1. Introduction ----------------
H1("1&nbsp;&nbsp;Introduction et problématique")
P("Depuis la mise en place de l'open data des décisions de justice, la Cour de cassation diffuse ses arrêts sur la "
  "plateforme <b>Judilibre</b> : plus d'un demi-million de décisions pseudonymisées sont accessibles librement. "
  "Ce volume dépasse de loin ce qu'un juriste peut lire. Or l'information utile d'un arrêt tient en quelques champs : "
  "qui a jugé, quand, sur quels textes de loi, et avec quel résultat. La retrouver demande pourtant de lire un texte "
  "de plusieurs pages, écrit dans un style très codifié.")
P("<b>Choix du sujet.</b> Ce sujet réunit trois difficultés classiques du NLP : des <b>textes longs</b> (649 mots en médiane, "
  "jusqu'à 183 000), un <b>vocabulaire spécialisé</b> (« pourvoi », « dispositif », « moyen annexé ») et des "
  "<b>classes déséquilibrées</b> (54 % de rejets). Il a aussi une utilité concrète (legal tech, recherche juridique) "
  "et dispose de données ouvertes de grande taille, ce qui permet une évaluation sérieuse.")
P("<b>Problématique.</b> <i>Comment extraire automatiquement et de manière fiable les informations clés d'un arrêt, "
  "et quelle approche — règles, modèle statistique classique, réseau de neurones entraîné de zéro ou modèle de langue "
  "pré-entraîné — offre le meilleur compromis entre performance, coût de calcul et interprétabilité ?</i>")
P("<b>Extraction et non prédiction.</b> Nous ne cherchons pas à deviner l'issue d'un procès futur : nous lisons une "
  "décision déjà rendue pour en extraire l'information. Le dispositif écrivant la réponse en toutes lettres "
  "(« CASSE ET ANNULE », « REJETTE le pourvoi »), les modèles d'apprentissage reçoivent uniquement les <i>motivations</i>, "
  "c'est-à-dire le raisonnement de la Cour, afin de mesurer s'ils comprennent ce raisonnement.")
P("<b>Contributions.</b>")
bullets([
    "une chaîne complète PDF → JSON qui détecte si le PDF est natif (PyMuPDF) ou scanné (OCR Tesseract) ;",
    "des règles d'extraction évaluées sur 1 959 décisions, dont une règle qui convertit les dates écrites en toutes lettres ;",
    "une comparaison de trois modèles (TF-IDF, CNN Keras, CamemBERT) et d'une règle, à données égales et inégales ;",
    "un test de généralisation sur des arrêts réels de 2026 (95 évaluables sur 104 extraits), postérieurs à toutes les données d'entraînement.",
])

# ---------------- 2. État de l'art ----------------
H1("2&nbsp;&nbsp;État de l'art")
H2("2.1&nbsp;&nbsp;NLP juridique et analyse de décisions")
P("Zhong et al. [6] dressent un panorama de l'intelligence artificielle juridique : recherche d'information, "
  "extraction d'éléments, prédiction de jugements. Aletras et al. [7] classent les arrêts de la Cour européenne des "
  "droits de l'homme (violation ou non) avec des n-grammes et un SVM (79 % d'accuracy). Chalkidis et al. [8] "
  "reprennent cette tâche avec des réseaux de neurones et BERT. Pour le français, Şulea et al. [9] prédisent le domaine "
  "et la décision d'arrêts de la Cour de cassation avec un SVM linéaire et obtiennent des scores très élevés. "
  "Medvedeva et al. [10] soulignent cependant que la plupart de ces travaux utilisent des textes rédigés <i>après</i> "
  "la décision : ils identifient l'issue plus qu'ils ne la prédisent. Notre étude assume ce cadre d'<b>extraction</b>.")
H2("2.2&nbsp;&nbsp;Représentations et modèles de texte")
P("La pondération <b>TF-IDF</b> [12] associée à un classifieur linéaire reste une référence solide en classification de "
  "documents. Les réseaux convolutifs appliqués aux plongements de mots (Kim [11]) capturent des motifs locaux de quelques "
  "mots. L'architecture <b>Transformer</b> [1], fondée uniquement sur l'attention, a conduit aux modèles pré-entraînés "
  "comme BERT [2], puis à sa version française <b>CamemBERT</b> [3]. Dans le domaine juridique, LEGAL-BERT [4] est "
  "pré-entraîné sur des textes juridiques anglais et évalué sur le banc d'essai LexGLUE [5] ; JuriBERT [13] adapte ce "
  "principe au droit français. La limite de 512 tokens de ces modèles pose problème pour les textes longs, ce que des "
  "architectures comme Longformer [21] cherchent à résoudre.")
H2("2.3&nbsp;&nbsp;Extraction par règles et entités nommées")
P("Les métadonnées juridiques (dates, numéros, juridictions) suivent des formats stables : les expressions régulières "
  "restent efficaces et interprétables pour les extraire. La reconnaissance d'entités nommées juridiques (juges, parties, "
  "lois) par apprentissage demande en revanche un corpus annoté [14].")
P("<b>Positionnement.</b> Peu de travaux comparent, sur des arrêts français et sous contrainte de calcul, des règles, "
  "un modèle classique, un réseau entraîné de zéro et un modèle pré-entraîné, en testant la chaîne complète sur de vrais "
  "PDF postérieurs aux données d'entraînement. C'est ce que nous proposons.")

# ---------------- 3. Données ----------------
H1("3&nbsp;&nbsp;Données")
H2("3.1&nbsp;&nbsp;Choix du jeu de données")
P("Trois pistes ont été étudiées. (1) La <b>jurisprudence tunisienne</b> : la base du ministère de la Justice publie "
  "environ 12 000 arrêts de principe de la Cour de cassation, mais uniquement en arabe, sans jeu de données prêt pour le "
  "NLP ni annotations ; tout serait à construire. (2) Des corpus <b>anglophones</b> (Australie, CEDH) : bien outillés, "
  "mais hors du cadre francophone du projet. (3) <b>Judilibre</b>, l'open data de la Cour de cassation, redistribué sur "
  "Hugging Face [18] : 553 075 arrêts en français, sous Licence Ouverte Etalab 2.0, avec des champs structurés "
  "(date, chambre, issue, découpage en zones, textes visés) qui servent de <b>vérité terrain gratuite</b>. "
  "Nous retenons ce troisième choix.")
H2("3.2&nbsp;&nbsp;Description et analyse exploratoire")
P("Chaque ligne du fichier (JSONL compressé, 1 Go) contient le texte intégral et 33 champs. Le corpus totalise "
  "<b>639 millions de mots</b> ; 99 % des décisions sont postérieures à 1970 (figure 1).")
figure(FIG / "eda_per_year.png", "Nombre de décisions par année (553 075 arrêts de la Cour de cassation).")
P("Les 14 issues d'origine sont très déséquilibrées : <i>Rejet</i> (54,2 %) et <i>Cassation</i> (30,7 %) dominent. "
  "Nous les regroupons en <b>4 classes</b> : Rejet, Cassation, Irrecevabilité (4,0 %) et Autre (déchéance, non-lieu, "
  "QPC, annulation…, 11,1 %) (figure 2).")
figure(FIG / "eda_labels.png", "Issues d'origine (échelle logarithmique) et regroupement en 4 classes.")
P("Les textes sont longs : médiane de 649 mots, et <b>75,5 %</b> des décisions dépassent la limite de 512 tokens de "
  "CamemBERT (figure 3). Seules 65 % des décisions possèdent un découpage en zones ; parmi elles, les motivations et le "
  "dispositif sont presque toujours présents (99 %), alors que l'exposé des faits (34 %) et les moyens (68 %) manquent souvent. "
  "L'issue dépend aussi de la chambre : les chambres civiles cassent dans 31 à 37 % des cas, la chambre criminelle dans "
  "19 % seulement, avec 24 % d'issues « Autre ».")
figure(FIG / "eda_length.png", "Longueur des décisions en mots ; la ligne pointillée orange indique la limite approximative de CamemBERT.")
H2("3.3&nbsp;&nbsp;Construction des corpus")
P("Le script <font face='Courier' size='8'>prepare_data.py</font> lit le fichier ligne par ligne, sans le charger en "
  "mémoire, et produit : (i) une ligne de statistiques par décision (553 075, pour l'analyse exploratoire) ; "
  "(ii) un <b>corpus de modélisation de 100 000 décisions</b>, tirées au hasard (graine 42) parmi celles qui ont des "
  "motivations et un dispositif ; (iii) un <b>jeu d'évaluation des règles</b> de 1 959 décisions avec leur texte intégral. "
  "Le tableau 1 montre que le corpus de modélisation reproduit la distribution des décisions ayant des zones.")
table([["Classe", "Base complète", "Base avec zones", "Corpus 100k"],
       ["Rejet", "54,2 %", "55,4 %", "55,4 %"],
       ["Cassation", "30,7 %", "25,6 %", "25,6 %"],
       ["Irrecevabilité", "4,0 %", "4,8 %", "4,9 %"],
       ["Autre", "11,1 %", "14,2 %", "14,1 %"]],
      "Distribution des classes selon le périmètre.", [2.4 * cm, 1.95 * cm, 2.0 * cm, 1.95 * cm])
P("Dans les motivations, les mots les plus caractéristiques de chaque classe ont un sens juridique net : « violé », "
  "« texte susvisé », « cassation encourue » pour la cassation ; « manifestement », « moyens annexés » pour les rejets "
  "non spécialement motivés ; « irrecevable », « articles 606 à 608 » pour l'irrecevabilité. Les motivations sont "
  "courtes (médiane de <b>146 mots</b>), ce qui en fait une entrée adaptée aux modèles.")
H2("3.4&nbsp;&nbsp;PDF réels pour le test en production")
P("Trois numéros du <i>Bulletin</i> de la Cour de cassation (civil de mai 2026, criminel de juin et juillet 2026) "
  "servent de test final : ils contiennent <b>104 arrêts distincts</b>, tous postérieurs à la dernière décision du "
  "jeu d'entraînement (mars 2025). L'issue y est imprimée sous l'en-tête de chaque arrêt (« – Cassation – »), ce qui "
  "fournit la bonne réponse.")

# ---------------- 4. Méthodologie ----------------
H1("4&nbsp;&nbsp;Méthodologie")
H2("4.1&nbsp;&nbsp;Vue d'ensemble")
P("La chaîne de traitement comporte cinq étapes :")
bullets([
    "<b>Lecture</b> : si PyMuPDF trouve plus de 100 caractères par page sur les premières pages, le PDF est natif et son "
    "texte est lu directement ; sinon chaque page est convertie en image (300 dpi) puis reconnue par Tesseract en français [20] ;",
    "<b>Nettoyage</b> : suppression des en-têtes et numéros de page, des espaces insécables, recollage des mots coupés en fin de ligne ;",
    "<b>Découpage</b> : un Bulletin est séparé en arrêts grâce à leur en-tête (« Crim., 29 juillet 2026, n° 26-83.088 ») ; "
    "chaque arrêt est découpé en zones (introduction, exposé, moyens, motivations, dispositif) ;",
    "<b>Extraction par règles</b> des métadonnées, des textes de loi, de la décision attaquée et de l'issue ;",
    "<b>Classification</b> de l'issue à partir des motivations par un modèle d'apprentissage, puis écriture du JSON.",
])
H2("4.2&nbsp;&nbsp;Extraction par règles")
P("Deux styles de rédaction coexistent : le style ancien (« Attendu que… ; D'où il suit que le moyen n'est pas fondé ») "
  "et le <i>style direct</i> adopté depuis 2019 (« Faits et procédure », « Examen du moyen », « Réponse de la Cour »). "
  "Les marqueurs des zones couvrent les deux styles. Les principales règles sont :")
bullets([
    "<b>date</b> : on relève toutes les dates d'audience, en chiffres ou <b>en toutes lettres</b> (« du neuf janvier deux "
    "mille trois »), converties par une petite grammaire des nombres français (« quatre vingt » = 80), et l'on garde la "
    "<i>dernière</i>, qui correspond au prononcé (la première peut être celle des débats) ;",
    "<b>chambre</b> et <b>numéro de pourvoi</b> (motif « 14-27.033 ») ;",
    "<b>textes de loi</b> : « article(s) X du code Y », avec une liste de 40 codes pour reconnaître les noms complets "
    "(« code de procédure pénale » et non « code de procédure ») ;",
    "<b>issue</b> : verbes du dispositif (CASSE → Cassation, REJETTE → Rejet, IRRECEVABLE → Irrecevabilité, sinon Autre) ;",
    "<b>ordres</b> : le dispositif est découpé en injonctions (« RENVOIE… », « Condamne… aux dépens »).",
])
H2("4.3&nbsp;&nbsp;Prétraitement NLP avec spaCy")
P("Pour les modèles A et B, les motivations passent par le modèle français <font face='Courier' size='8'>fr_core_news_sm</font> "
  "de spaCy [15] : <b>tokenisation</b>, <b>lemmatisation</b> (« violé », « viole » → « violer »), suppression des mots "
  "vides, de la ponctuation et des nombres. Les <b>négations</b> (« ne », « pas », « non », « sans »…) sont "
  "volontairement conservées : « le moyen <i>n'est pas</i> fondé » (rejet) ne doit pas devenir « moyen fondé ». "
  "Exemple réel : « D'où il suit que le moyen n'est pas fondé ; qu'en statuant ainsi, la cour d'appel a violé le texte "
  "susvisé » → <i>moyen ne pas fonder statuer cour appel violer texte susviser</i>. En moyenne, une motivation passe "
  "de 207 mots à 91 lemmes.")
H2("4.4&nbsp;&nbsp;Modèles de classification")
P("<b>Modèle A — TF-IDF + régression logistique.</b> Unigrammes et bigrammes de lemmes (fréquence minimale 3, "
  "100 000 variables, TF sous-linéaire), puis régression logistique avec pondération équilibrée des classes ; la "
  "régularisation C ∈ {0,5 ; 2 ; 8} est choisie sur la validation. Un Naive Bayes multinomial sert de point de comparaison.")
P("<b>Modèle B — CNN Keras entraîné de zéro.</b> Vocabulaire de 30 000 lemmes, séquences de 300 ; plongement de "
  "dimension 128 appris ; convolution 1D (128 filtres, fenêtre de 5 mots) ; max-pooling global ; dropout 0,3 ; couche "
  "dense de 64 ; softmax à 4 sorties (≈ 3,9 M de paramètres). Optimiseur Adam (taux 10<super>-3</super>), lots de 128, "
  "arrêt précoce (patience 2, au plus 10 époques), poids de classes inversement proportionnels à leur fréquence.")
P("<b>Modèle C — CamemBERT fine-tuné.</b> <font face='Courier' size='8'>camembert-base</font> [3] (110 M de paramètres) "
  "reçoit le texte brut, découpé en sous-mots. On garde les <b>256 derniers tokens</b> des motivations "
  "(troncature à gauche), là où la Cour conclut. Une couche de classification est ajoutée ; l'ensemble est entraîné "
  "1 époque sur <b>20 000</b> décisions (taux 2·10<super>-5</super> décroissant linéairement jusqu'à 0, lots de 16, "
  "mêmes poids de classes).")

# ---------------- 5. Implémentation ----------------
H1("5&nbsp;&nbsp;Implémentation")
P("Le projet est écrit en Python 3.12 et tourne sur un MacBook à puce <b>Apple M4 (16 Go)</b>. Le GPU est utilisé "
  "via <b>TensorFlow 2.18</b> et le greffon <b>tensorflow-metal</b> ; PyTorch n'est pas utilisé. Les principales "
  "bibliothèques sont spaCy 3.8, scikit-learn 1.9 [16], tf-keras 2.18, transformers 4.57 [17] (dernière version qui "
  "fournit les classes TensorFlow), PyMuPDF et Tesseract. Toutes les versions sont figées dans "
  "<font face='Courier' size='8'>requirements.txt</font> et la graine aléatoire est fixée à 42.")
table([["Fichier", "Rôle"],
       ["scripts/prepare_data.py", "lecture du fichier brut, corpus et statistiques"],
       ["notebooks/01_EDA.ipynb", "analyse exploratoire (section 3)"],
       ["notebooks/02_NLP.ipynb", "règles, spaCy, modèles A/B/C, évaluation"],
       ["scripts/Txt_ToJSON.py", "PDF/texte → JSON (lecture, OCR, règles)"],
       ["scripts/predict.py", "JSON → issue prédite par le modèle choisi"],
       ["models/", "modèles entraînés et modèle final"]],
      "Organisation du code.", [3.5 * cm, 4.8 * cm])
P("<b>Difficultés rencontrées.</b> (1) tensorflow-metal n'est pas compatible avec TensorFlow 2.21 ni avec Python 3.14 : "
  "retour à TensorFlow 2.18 et Python 3.12. (2) Le nouvel optimiseur Adam de Keras fait planter le greffon Metal "
  "(erreur du « remapper » de graphe) : on utilise l'Adam <i>legacy</i>, recommandé par TensorFlow sur Apple Silicon. "
  "(3) CamemBERT est lent sur cette machine (≈ 4 exemples/s à l'entraînement), d'où la limite de 20 000 exemples. "
  "(4) Un Bulletin publie parfois le même arrêt sous deux thèmes : les doublons sont écartés par numéro de pourvoi.")

# ---------------- 6. Protocole expérimental ----------------
H1("6&nbsp;&nbsp;Protocole expérimental")
bullets([
    "<b>Découpage</b> stratifié du corpus de 100 000 décisions : 80 % entraînement, 10 % validation, 10 % test.",
    "<b>Choix des réglages et du modèle final</b> sur la validation uniquement ; le test n'est utilisé qu'une fois, pour le rapport.",
    "<b>Métriques</b> : accuracy, F1 par classe et surtout <b>F1 macro</b> (moyenne des F1 des 4 classes), insensible au "
    "déséquilibre ; temps d'entraînement et d'inférence par document.",
    "<b>Équité</b> : CamemBERT n'ayant vu que 20 000 exemples, A et B sont aussi ré-entraînés sur <i>les mêmes</i> 20 000 décisions.",
    "<b>Règles</b> : exact match par champ sur les 1 959 décisions du jeu d'évaluation, et rappel des textes du visa.",
    "<b>Généralisation</b> : chaîne complète (PDF → JSON → modèle) sur les arrêts des Bulletins 2026 dont l'issue est imprimée et les motivations extraites (95 sur 104).",
])

# ---------------- 7. Résultats ----------------
H1("7&nbsp;&nbsp;Résultats")
H2("7.1&nbsp;&nbsp;Extraction par règles")
table([["Champ", "Score", "Détail par période (&lt;2000 / 2000-14 / ≥2015)"],
       ["Date de la décision", pct(rules_summary["Date (exact match)"]),
        " / ".join(pct(v, 0) for v in rules_period["date_ok"])],
       ["Chambre", pct(rules_summary["Chambre (exact match)"]),
        " / ".join(pct(v, 0) for v in rules_period["chambre_ok"])],
       ["N° de pourvoi", pct(rules_summary["N° de pourvoi (exact match)"]),
        " / ".join(pct(v, 0) for v in rules_period["numero_ok"])],
       ["Cour d'appel attaquée", pct(rules_summary["Cour d'appel attaquée (exact match)"]), "décisions où elle est connue"],
       ["Textes du visa retrouvés", pct(rules_summary["Textes de loi du visa retrouvés (rappel)"]), "rappel"],
       ["Issue (dispositif), test", pct(RULES["accuracy"]), f"F1 macro {num(RULES['f1_macro'])}"],
       ["Issue (dispositif), PDF 2026", pct(prod.loc["règles", "accuracy"]), f"{int(prod.loc['règles', 'nb arrêts'])} arrêts"]],
      "Extraction par règles : exact match sur les 1 959 décisions du jeu d'évaluation "
      "(sauf les deux dernières lignes : test de 10 000 décisions et Bulletins 2026).",
      [2.9 * cm, 1.4 * cm, 4.0 * cm])
P(f"Les métadonnées sont très bien extraites quand elles sont écrites dans le texte. La règle des <b>dates en toutes "
  f"lettres</b> est décisive : sans elle, aucune date antérieure à 2015 n'était retrouvée ; avec elle, "
  f"{pct(rules_period['date_ok'].iloc[0], 0)} et {pct(rules_period['date_ok'].iloc[1], 0)} le sont. "
  f"Le numéro de pourvoi n'est retrouvé que dans {pct(rules_summary['N° de pourvoi (exact match)'], 0)} des cas, "
  f"mais ce n'est pas un défaut de la règle : il n'est <b>écrit que dans 2,8 % des textes antérieurs à 2015</b>, "
  f"alors qu'il est retrouvé dans {pct(rules_period['numero_ok'].iloc[2], 0)} des décisions récentes. "
  f"Les dates manquées après 2015 concernent surtout les ordonnances de la Première présidence, qui n'ont pas "
  f"d'en-tête daté. Enfin, la règle sur le dispositif donne l'issue avec {pct(RULES['accuracy'])} d'accuracy ; "
  f"elle est moins bonne sur « Irrecevabilité » (F1 {num(RULES['f1_Irrecevabilité'])}) et « Autre » "
  f"(F1 {num(RULES['f1_Autre'])}), classes aux formulations variées.")

H2("7.2&nbsp;&nbsp;Classification de l'issue à partir des motivations")
rows = [["Modèle", "n", "Acc.", "F1 macro", "F1 Rej.", "F1 Cass.", "F1 Irr.", "F1 Autre"]]
order = [("A0 · TF-IDF + Naive Bayes", "Naive Bayes"),
         ("A · TF-IDF + Régression logistique", "A · TF-IDF"),
         ("B · CNN Keras (de zéro)", "B · CNN"),
         ("A · TF-IDF + RL (20k)", "A · TF-IDF"),
         ("B · CNN Keras (20k)", "B · CNN"),
         ("C · CamemBERT (fine-tuné)", "C · CamemBERT")]
for key, label in order:
    r = R[key]
    rows.append([label, f"{int(r['n_train']) // 1000}k", num(r["accuracy"]), num(r["f1_macro"]),
                 num(r["f1_Rejet"]), num(r["f1_Cassation"]), num(r["f1_Irrecevabilité"]), num(r["f1_Autre"])])
table(rows, "Classification de l'issue sur le test (10 000 décisions). Les trois dernières lignes sont entraînées sur les "
      "<b>mêmes 20 000 décisions</b>. En gras : meilleur modèle à 80k et meilleur modèle à 20k.",
      [1.85 * cm, 0.6 * cm] + [0.97 * cm] * 6, bold_rows=(2, 6))
P(f"Les trois modèles dépassent largement Naive Bayes (F1 macro {num(NB['f1_macro'])}). Avec 80 000 exemples, "
  f"le modèle le plus simple, <b>TF-IDF + régression logistique, obtient le meilleur F1 macro ({num(A['f1_macro'])})</b>, "
  f"devant le CNN ({num(B['f1_macro'])}). <b>À données égales</b> (20 000 exemples), l'ordre s'inverse : CamemBERT "
  f"({num(C['f1_macro'])}) devance la régression logistique ({num(A20['f1_macro'])}) et le CNN ({num(B20['f1_macro'])}). "
  f"CamemBERT est le meilleur sur la classe Cassation (F1 {num(C['f1_Cassation'])}) mais le moins bon sur « Autre » "
  f"({num(C['f1_Autre'])}). Les écarts entre les trois modèles restent faibles (moins d'un point de F1 macro). "
  f"Le modèle final, choisi sur la <b>validation</b> (F1 macro {num(val_scores['A · TF-IDF + Régression logistique'])}), est donc A.")
figure(FIG / "model_comparison.png", "Accuracy et F1 macro sur le test pour tous les modèles (entrée : motivations).")
table([["Modèle", "Entraînement", "Inférence / doc"],
       ["Règles", "—", f"{R['Règles (sur le dispositif)']['temps_inférence_ms_par_doc']:.2f} ms".replace(".", ",")],
       ["A · TF-IDF + RL (80k)", f"{A['temps_entraînement_s']:.0f} s", f"{A['temps_inférence_ms_par_doc']:.2f} ms".replace(".", ",")],
       ["B · CNN Keras (80k)", f"{B['temps_entraînement_s']:.0f} s", f"{B['temps_inférence_ms_par_doc']:.2f} ms".replace(".", ",")],
       ["C · CamemBERT (20k)", f"{C['temps_entraînement_s'] / 60:.0f} min", f"{C['temps_inférence_ms_par_doc']:.0f} ms"]],
      "Coût de calcul sur le Mac M4. Pour A et B, il faut ajouter le prétraitement spaCy "
      "(≈ 8 ms par document sur 4 cœurs, 800 s pour 100 000 textes).", [3.3 * cm, 2.2 * cm, 2.8 * cm])

H2("7.3&nbsp;&nbsp;Test en production sur les PDF de 2026")
P(f"La chaîne complète a été appliquée aux 3 Bulletins : {int(prod.loc['A', 'nb arrêts'])} arrêts possèdent à la fois "
  f"une issue imprimée (49 cassations, 46 rejets) et des motivations exploitables.")
table([["Méthode", "Accuracy", "Erreurs"],
       ["Règles (dispositif)", pct(prod.loc["règles", "accuracy"]), "0"],
       ["A · TF-IDF + RL", pct(prod.loc["A", "accuracy"]), str(round((1 - prod.loc["A", "accuracy"]) * prod.loc["A", "nb arrêts"]))],
       ["B · CNN Keras", pct(prod.loc["B", "accuracy"]), str(round((1 - prod.loc["B", "accuracy"]) * prod.loc["B", "nb arrêts"]))],
       ["C · CamemBERT", pct(prod.loc["C", "accuracy"]), str(round((1 - prod.loc["C", "accuracy"]) * prod.loc["C", "nb arrêts"]))]],
      "Issue retrouvée sur les arrêts des Bulletins de mai à juillet 2026, postérieurs aux données d'entraînement.",
      [3.4 * cm, 2.2 * cm, 2.0 * cm])
P(f"Sur ces décisions nouvelles, <b>CamemBERT est le meilleur modèle</b> ({pct(prod.loc['C', 'accuracy'])}), "
  f"devant A ({pct(prod.loc['A', 'accuracy'])}), tandis que le CNN chute à {pct(prod.loc['B', 'accuracy'])}. "
  f"Seules deux classes sont présentes : l'accuracy est ici la bonne mesure, le F1 macro étant faussé dès qu'un "
  f"modèle prédit une classe absente. Les 4 erreurs du modèle A sont toutes des rejets prédits « Cassation ».")

# ---------------- 8. Analyse critique ----------------
H1("8&nbsp;&nbsp;Analyse critique")
P("<b>Un modèle simple suffit-il ?</b> Sur le test, oui : le TF-IDF bat les réseaux, s'entraîne en 18 secondes et "
  "prédit environ 800 fois plus vite que CamemBERT hors prétraitement (encore 9 fois plus vite en comptant spaCy). "
  f"La raison est visible dans les mots qu'il a appris (tableau {counters['tab'] + 1}) : "
  "les motivations contiennent des <b>formules quasi standardisées</b> (« violé le texte susvisé », « cassation "
  "encourue », « le moyen n'est pas fondé », « pourvoi irrecevable ») qu'un modèle de sacs de mots capte parfaitement. "
  "La tâche est donc plus proche de l'<i>identification</i> de l'issue que de sa prédiction, ce que Medvedeva et al. [10] "
  "observent aussi. Les scores très élevés ne doivent pas être lus comme une « compréhension » fine du droit.")
table([["Rejet", "Cassation", "Irrecevabilité", "Autre"]] +
      [[top_words.loc[i, c] for c in ["Rejet", "Cassation", "Irrecevabilité", "Autre"]] for i in range(8)],
      "Lemmes et bigrammes les plus influents de la régression logistique (modèle A), par classe.",
      [COL_W / 4] * 4)
P("<b>Où se situe l'avantage de CamemBERT ?</b> À données égales, il est le meilleur, et c'est lui qui généralise le "
  "mieux aux arrêts de 2026, rédigés dans le style direct récent. Son pré-entraînement sur du français général l'aide "
  "à lire des formulations nouvelles, là où le CNN, qui a appris ses plongements de zéro, se trompe davantage. "
  "Son coût reste un frein : 91 minutes d'entraînement pour 20 000 exemples et 72 ms par décision. Avec 80 000 "
  "exemples et plusieurs époques, il dépasserait probablement les autres modèles ; nous n'avons pas pu le vérifier.")
P(f"<b>Analyse des erreurs.</b> Les erreurs du modèle final se concentrent sur les décisions anciennes "
  f"(accuracy {pct(err_period.loc['avant 2000', 'accuracy'])} avant 2000 contre "
  f"{pct(err_period.loc['2019+ (style direct)', 'accuracy'])} pour le style direct). Les confusions les plus "
  "fréquentes sont « Autre » ↔ « Rejet » et « Cassation » → « Rejet » ou « Irrecevabilité ». L'examen des exemples "
  "montre trois causes : (i) des <b>négations ou tournures inhabituelles</b> : « la cour d'appel […] n'a pu violer "
  "les textes précités » devient, une fois lemmatisé, « violer texte », typique d'une cassation ; (ii) des décisions procédurales classées « Autre » (rectification d'erreur matérielle, requête en "
  "interprétation) dont le texte parle de cassation ou de rejet ; (iii) des cassations sans renvoi, dont la fin des "
  "motivations porte sur l'application de la règle de droit (« il y a lieu de mettre fin au litige ») plutôt que sur la violation.")
P("<b>Règles ou modèles ?</b> Quand le dispositif est disponible, la règle atteint 96,3 % sur le test et 100 % sur les "
  "Bulletins : elle reste la meilleure solution pour remplir le champ « verdict » du JSON. Les modèles sont utiles "
  "comme <b>contrôle de cohérence</b> (un désaccord entre la règle et le modèle signale un arrêt à vérifier) et quand le "
  "dispositif manque ou est mal extrait (OCR imparfait).")
P("<b>Raccourcis appris.</b> L'analyse exploratoire a fait apparaître le nom d'une magistrate parmi les mots "
  "caractéristiques de la classe « Autre » (ordonnances signées par la même personne). Un modèle peut ainsi apprendre "
  "<i>qui</i> signe plutôt que <i>ce qui</i> est jugé : c'est un biais à éliminer, d'autant que le droit français "
  "interdit le profilage des magistrats (section 9).")
P("<b>Validité du protocole.</b> Le modèle final a été choisi sur la validation, le test n'a servi qu'une fois, et "
  "les comparaisons à données égales neutralisent l'avantage de taille de A et B. Deux réserves : un seul tirage "
  "aléatoire (pas d'intervalle de confiance), et un test de généralisation temporelle limité à 95 arrêts.")

# Exemple de JSON pour l'annexe B : un arrêt réel du Bulletin criminel de juillet 2026 (champs longs raccourcis)
_ex = json.load(open(ROOT / "output" / "predictions" / "Bulletin_criminel_2026-7_arret_001.json", encoding="utf-8"))
for _k in ("facts", "claims"):
    _ex["narrative"][_k] = _ex["narrative"][_k][:75].replace("\n", " ") + " ..."
_ex["outcome"]["reasoning"] = _ex["outcome"]["reasoning"][:75].replace("\n", " ") + " ..."
_ex["outcome"]["orders"] = [o[:70] + " ..." for o in _ex["outcome"]["orders"][:3]]
EXAMPLE_JSON = json.dumps(_ex, ensure_ascii=False, indent=2)

# ---------------- 9. Limites et perspectives ----------------
H1("9&nbsp;&nbsp;Limites et perspectives")
H2("9.1&nbsp;&nbsp;Limites")
bullets([
    "<b>LEGAL-BERT non utilisé.</b> LEGAL-BERT [4] est pré-entraîné sur des textes juridiques <i>anglais</i>. "
    "L'appliquer à nos arrêts imposerait de les traduire d'abord en anglais : cela ajoute un second modèle lourd et lent, "
    "et la traduction déforme un vocabulaire sans équivalent exact en droit anglo-saxon (« cassation », « pourvoi », "
    "« dispositif »). La comparaison mesurerait alors « traduction + modèle » et non le modèle lui-même. Nous avons donc "
    "retenu CamemBERT, pré-entraîné sur du français.",
    "<b>Puissance de calcul.</b> CamemBERT n'a vu que 20 000 exemples, une seule époque et 256 tokens ; un entraînement "
    "complet (80 000 exemples, plusieurs époques) demanderait un GPU dédié.",
    "<b>Découpage aléatoire.</b> Le test principal mélange toutes les époques ; seul le test sur les Bulletins 2026 "
    "mesure la généralisation dans le temps, sur 95 arrêts seulement.",
    "<b>Étiquettes imparfaites.</b> Les zones et issues de Judilibre sont en partie produites automatiquement ; la classe "
    "« Autre » regroupe des issues hétérogènes.",
    "<b>Règles fragiles.</b> Elles dépendent des formats d'écriture : un nouveau modèle d'en-tête ou un OCR imparfait "
    "suffit à les mettre en défaut, et les ordonnances sans en-tête daté restent mal couvertes.",
    "<b>Une seule juridiction.</b> Rien ne garantit que les modèles fonctionnent sur les cours d'appel ou sur d'autres pays.",
])
H2("9.2&nbsp;&nbsp;Perspectives")
bullets([
    "<b>Modèles juridiques et multilingues</b> : comparer à JuriBERT [13], ou à LEGAL-BERT après traduction automatique, "
    "pour mesurer l'apport d'un pré-entraînement juridique.",
    "<b>Textes longs</b> : Longformer [21] ou découpage du texte en fenêtres pour lire la décision entière.",
    "<b>Entités nommées</b> : annoter quelques centaines d'arrêts (juges, parties, avocats, juridictions) et entraîner "
    "un modèle de NER, à la place des règles fragiles.",
    "<b>Découpage temporel</b> : entraîner sur le passé et tester sur les années récentes.",
    "<b>Extension à la Tunisie</b> : la jurisprudence tunisienne étant publiée en arabe, il faudrait construire un corpus "
    "(extraction, nettoyage, annotation) et utiliser un modèle arabe comme AraBERT [22] ou un modèle multilingue.",
    "<b>Mise en production</b> : une interface web qui reçoit un PDF et affiche le JSON.",
])
H2("9.3&nbsp;&nbsp;Éthique")
P("Les décisions sont pseudonymisées par la Cour de cassation. En France, la loi interdit d'exploiter les données "
  "d'identité des magistrats pour évaluer ou prédire leurs pratiques (article 33 de la loi n° 2019-222 du 23 mars 2019). "
  "L'apparition d'un nom de magistrat parmi les mots caractéristiques (section 8) montre qu'un système réel devrait "
  "retirer ces noms avant l'apprentissage.")

# ---------------- 10. Références ----------------
H1("10&nbsp;&nbsp;Références")
REFS = [
    "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, Ł., Polosukhin, I. (2017). Attention Is All You Need. <i>NeurIPS</i>.",
    "Devlin, J., Chang, M.-W., Lee, K., Toutanova, K. (2019). BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding. <i>NAACL-HLT</i>.",
    "Martin, L., Muller, B., Ortiz Suárez, P. J., Dupont, Y., Romary, L., de la Clergerie, É., Seddah, D., Sagot, B. (2020). CamemBERT: a Tasty French Language Model. <i>ACL</i>.",
    "Chalkidis, I., Fergadiotis, M., Malakasiotis, P., Aletras, N., Androutsopoulos, I. (2020). LEGAL-BERT: The Muppets straight out of Law School. <i>Findings of EMNLP</i>.",
    "Chalkidis, I., Jana, A., Hartung, D., Bommarito, M., Androutsopoulos, I., Katz, D. M., Aletras, N. (2022). LexGLUE: A Benchmark Dataset for Legal Language Understanding in English. <i>ACL</i>.",
    "Zhong, H., Xiao, C., Tu, C., Zhang, T., Liu, Z., Sun, M. (2020). How Does NLP Benefit Legal System: A Summary of Legal Artificial Intelligence. <i>ACL</i>.",
    "Aletras, N., Tsarapatsanis, D., Preoţiuc-Pietro, D., Lampos, V. (2016). Predicting judicial decisions of the European Court of Human Rights: an NLP perspective. <i>PeerJ Computer Science</i>.",
    "Chalkidis, I., Androutsopoulos, I., Aletras, N. (2019). Neural Legal Judgment Prediction in English. <i>ACL</i>.",
    "Şulea, O.-M., Zampieri, M., Vela, M., van Genabith, J. (2017). Predicting the Law Area and Decisions of French Supreme Court Cases. <i>RANLP</i>.",
    "Medvedeva, M., Wieling, M., Vols, M. (2023). Rethinking the field of automatic prediction of court decisions. <i>Artificial Intelligence and Law</i>, 31, 195–212.",
    "Kim, Y. (2014). Convolutional Neural Networks for Sentence Classification. <i>EMNLP</i>.",
    "Salton, G., Buckley, C. (1988). Term-weighting approaches in automatic text retrieval. <i>Information Processing &amp; Management</i>, 24(5), 513–523.",
    "Douka, S., Abdine, H., Vazirgiannis, M., El Hamdani, R., Restrepo Amariles, D. (2021). JuriBERT: A Masked-Language Model Adaptation for French Legal Text. <i>Natural Legal Language Processing Workshop</i>.",
    "Leitner, E., Rehm, G., Moreno-Schneider, J. (2019). Fine-grained Named Entity Recognition in Legal Documents. <i>SEMANTiCS</i>.",
    "Honnibal, M., Montani, I., Van Landeghem, S., Boyd, A. (2020). spaCy: Industrial-strength Natural Language Processing in Python. Zenodo.",
    "Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. <i>Journal of Machine Learning Research</i>, 12, 2825–2830.",
    "Wolf, T. et al. (2020). Transformers: State-of-the-Art Natural Language Processing. <i>EMNLP: System Demonstrations</i>.",
    "Jeannot, A. (2024). Jurisprudence : jeu de données des décisions de la Cour de cassation (Judilibre). Hugging Face, antoinejeannot/jurisprudence.",
    "Cour de cassation. Judilibre, moteur de recherche et open data des décisions de justice. courdecassation.fr.",
    "Smith, R. (2007). An Overview of the Tesseract OCR Engine. <i>ICDAR</i>.",
    "Beltagy, I., Peters, M. E., Cohan, A. (2020). Longformer: The Long-Document Transformer. arXiv:2004.05150.",
    "Antoun, W., Baly, F., Hajj, H. (2020). AraBERT: Transformer-based Model for Arabic Language Understanding. <i>OSACT Workshop</i>.",
]
for i, r in enumerate(REFS, start=1):
    story.append(Paragraph(f"[{i}]&nbsp;&nbsp;{r}", S["ref"]))

# ---------------- Annexe (pleine largeur) ----------------
story.append(PageBreak())
H1("Annexe A&nbsp;&nbsp;Figures complémentaires")
figure(FIG / "confusion_matrices.png", "Matrices de confusion normalisées par ligne (vraie classe) sur le test, pour les "
       "trois modèles. La diagonale donne le rappel de chaque classe.", width=TEXT_W)
figure(FIG / "model_b_training.png", "Courbes d'apprentissage du modèle B (CNN Keras) : perte et accuracy sur "
       "l'entraînement et la validation. L'arrêt précoce garde les poids de la meilleure époque.", width=0.75 * TEXT_W)
figure(FIG / "eda_completeness.png", "Taux de remplissage des champs du jeu de données (553 075 décisions).",
       width=0.6 * TEXT_W)
H1("Annexe B&nbsp;&nbsp;Exemple de sortie JSON (extrait)")
for line in EXAMPLE_JSON.split("\n"):
    story.append(Paragraph(line.replace(" ", "&nbsp;").replace("<", "&lt;") or "&nbsp;", S["code"]))

doc.build(story)
print("Rapport écrit :", OUT)
