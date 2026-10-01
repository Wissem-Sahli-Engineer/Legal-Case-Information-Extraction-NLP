"""
Txt_ToJSON.py : transforme une décision de justice (PDF ou texte) en JSON structuré.

Étapes :
  1. Lire le fichier
       - PDF natif (produit par ordinateur)  -> PyMuPDF lit directement le texte
       - PDF scanné (pages = images)          -> OCR avec Tesseract
       - fichier .txt                         -> lecture simple
  2. Nettoyer le texte (en-têtes de page, espaces insécables, mots coupés en fin de ligne)
  3. Découper le document en arrêts (un Bulletin contient plusieurs arrêts)
  4. Pour chaque arrêt, extraire par règles (regex) :
       métadonnées, zones (faits, moyens, motifs, dispositif), textes de loi, issue
  5. Écrire un fichier JSON par arrêt

Utilisation :
  python scripts/Txt_ToJSON.py data/pdf/Bulletin_criminel_2026-7.pdf -o output/
  python scripts/Txt_ToJSON.py mon_arret.pdf --type scanne -o output/
"""
import argparse
import json
import re
import sys
from pathlib import Path
# pyrefly: ignore [missing-import]
import pymupdf
# pyrefly: ignore [missing-import]
import pytesseract
# pyrefly: ignore [missing-import]
from PIL import Image

# ----------------------------------------------------------------------------
# 1. LECTURE DU FICHIER
# ----------------------------------------------------------------------------

def detect_pdf_type(pdf_path, pages_to_check=5):
    """Renvoie 'natif' si le PDF contient du texte, 'scanne' sinon.
    Idée : un PDF scanné ne contient que des images, donc PyMuPDF n'y trouve presque aucun caractère."""
    # pyrefly: ignore [missing-import]

    doc = pymupdf.open(pdf_path)
    n = min(pages_to_check, len(doc))
    chars = sum(len(doc[i].get_text().strip()) for i in range(n))
    return "natif" if chars / max(n, 1) > 100 else "scanne"


def ask_pdf_type(pdf_path):
    """Demande à l'utilisateur le type du PDF, en proposant la détection automatique par défaut."""
    guess = detect_pdf_type(pdf_path)
    if not sys.stdin.isatty():          # exécution non interactive : on garde la détection
        return guess
    print(f"Détection automatique : PDF {guess}.")
    answer = input("Type du PDF ? [1] natif (PyMuPDF)  [2] scanné (OCR)  [Entrée = détection] : ").strip()
    return {"1": "natif", "2": "scanne"}.get(answer, guess)


def read_pdf_native(pdf_path):
    """PDF natif : on lit le texte de chaque page avec PyMuPDF."""

    doc = pymupdf.open(pdf_path)
    return "\n".join(page.get_text() for page in doc)


def read_pdf_ocr(pdf_path, dpi=300):
    """PDF scanné : chaque page est transformée en image, puis Tesseract reconnaît les lettres."""
    doc = pymupdf.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)                          # page -> image
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        pages.append(pytesseract.image_to_string(img, lang="fra"))
        print(f"  OCR page {i + 1}/{len(doc)}", end="\r")
    print()
    return "\n".join(pages)


def read_document(path, pdf_type=None):
    path = Path(path)
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8"), "texte"
    if pdf_type is None:
        pdf_type = ask_pdf_type(path)
    text = read_pdf_native(path) if pdf_type == "natif" else read_pdf_ocr(path)
    return text, pdf_type

# ----------------------------------------------------------------------------
# 2. NETTOYAGE
# ----------------------------------------------------------------------------

def clean_text(text):
    text = text.replace("\xa0", " ").replace(" ", " ").replace("’", "'")
    lines = []
    for line in text.split("\n"):
        s = line.strip()
        # en-têtes et pieds de page répétés des Bulletins
        if re.fullmatch(r"\d{1,4}", s):                       # numéro de page seul
            continue
        if re.match(r"^Bulletin (Chambre|Chambres|Assemblée|civil|criminel)", s):
            continue
        if s in ("Arrêts et ordonnances", "Arrêts", "■"):
            continue
        lines.append(s)
    text = "\n".join(lines)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)                  # "adminis-\ntration" -> "administration"
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

# ----------------------------------------------------------------------------
# 3. DÉCOUPAGE EN ARRÊTS
# ----------------------------------------------------------------------------

# En-tête d'un arrêt dans les Bulletins, ex. "Crim., 29 juillet 2026, n° 26-83.088, (B), FRH"
CHAMBER_ABBR = r"(Crim\.|Com\.|Soc\.|1re Civ\.|2e Civ\.|3e Civ\.|Ass\. plén\.|Ch\. mixte|Avis)"
HEADER_RE = re.compile(CHAMBER_ABBR + r",\s*(\d{1,2}(?:er)?\s+\w+\s+\d{4}),\s*n°\s*(\d{2}-\d{2}\.\d{3})[^\n.]*\n")


def split_decisions(text):
    """Découpe un Bulletin en arrêts. Les lignes d'index (suivies de pointillés '....') sont ignorées.
    Si aucun en-tête n'est trouvé, le texte entier est considéré comme un seul arrêt."""
    starts = [m.start() for m in HEADER_RE.finditer(text)]
    if not starts:
        return [text]
    starts.append(len(text))
    blocks = [text[a:b] for a, b in zip(starts, starts[1:])]
    return [b for b in blocks if "PAR CES MOTIFS" in b]         # on garde les vrais arrêts

# ----------------------------------------------------------------------------
# 4. EXTRACTION PAR RÈGLES
# ----------------------------------------------------------------------------

MONTHS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
          "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
          "décembre": 12, "decembre": 12}

CHAMBERS = {
    "Crim.": "Chambre criminelle", "Com.": "Chambre commerciale financière et économique",
    "Soc.": "Chambre sociale", "1re Civ.": "Première chambre civile",
    "2e Civ.": "Deuxième chambre civile", "3e Civ.": "Troisième chambre civile",
    "Ass. plén.": "Assemblée plénière", "Ch. mixte": "Chambre mixte",
    "CRIMINELLE": "Chambre criminelle", "COMMERCIALE": "Chambre commerciale financière et économique",
    "SOCIALE": "Chambre sociale", "PREMIÈRE CHAMBRE CIVILE": "Première chambre civile",
    "DEUXIÈME CHAMBRE CIVILE": "Deuxième chambre civile",
    "TROISIÈME CHAMBRE CIVILE": "Troisième chambre civile",
}

JUDILIBRE_CHAMBERS = {
    "CHAMBRE CRIMINELLE": "Chambre criminelle", "CHAMBRE SOCIALE": "Chambre sociale",
    "CHAMBRE COMMERCIALE": "Chambre commerciale financière et économique",
    "PREMIERE CHAMBRE CIVILE": "Première chambre civile", "DEUXIEME CHAMBRE CIVILE": "Deuxième chambre civile",
    "TROISIEME CHAMBRE CIVILE": "Troisième chambre civile", "ASSEMBLEE PLENIERE": "Assemblée plénière",
    "CHAMBRE MIXTE": "Chambre mixte",
}

DATE_RE = r"(\d{1,2})(?:er)?\s+(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+(\d{4})"


def to_iso_date(day, month, year):
    return f"{int(year):04d}-{MONTHS[month.lower()]:02d}-{int(day):02d}"


# Les décisions anciennes écrivent la date en toutes lettres :
# "audience publique du neuf janvier deux mille trois", "le dix-sept janvier mil neuf cent quatre vingt neuf"
NUMBER_WORDS = {"premier": 1, "un": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
                "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14,
                "quinze": 15, "seize": 16, "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50,
                "soixante": 60}


def words_to_number(words):
    """'mil neuf cent quatre vingt neuf' -> 1989 ; 'dix-sept' -> 17 ; 'trente et un' -> 31."""
    total, current = 0, 0
    for w in re.split(r"[\s-]+", words.lower()):
        if w in ("et", ""):
            continue
        if w in ("mil", "mille"):
            total += max(current, 1) * 1000
            current = 0
        elif w == "cent" or w == "cents":
            current = max(current, 1) * 100
        elif w in ("vingt", "vingts") and current % 100 == 4:       # "quatre vingt" = 80
            current += 76
        elif w in NUMBER_WORDS:
            current += NUMBER_WORDS[w]
        else:
            return None                                           # mot inconnu : ce n'est pas un nombre
    return total + current


MONTHS_RE = r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)"
WORD_DATE_RE = re.compile(r"audience publique[^.;]{0,80}?(?:le|du)\s+([a-z\s-]+?)\s+" + MONTHS_RE +
                          r"\s+((?:mil|deux mille)[a-z\s-]*?)\s*(?=[.,;\n]|a rendu|$)", re.IGNORECASE)


def audience_dates(text):
    """Toutes les dates d'audience du texte (en chiffres ou en lettres), avec leur position."""
    found = []
    for m in re.finditer(r"audience publique du\s+" + DATE_RE, text, re.IGNORECASE):
        found.append((m.start(), to_iso_date(*m.groups())))
    for m in WORD_DATE_RE.finditer(text):
        day, year = words_to_number(m.group(1)), words_to_number(m.group(3))
        if day and year and 1 <= day <= 31 and 1900 <= year <= 2030:
            found.append((m.start(), to_iso_date(day, m.group(2), year)))
    return sorted(found)


def first_match(pattern, text, flags=0):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def extract_metadata(text):
    meta = {"court": "Cour de cassation", "chamber": None, "date": None,
            "case_number": None, "president": None}

    header = HEADER_RE.search(text)
    if header:                                    # format Bulletin
        meta["chamber"] = CHAMBERS.get(header.group(1))
        d = re.search(DATE_RE, header.group(2))
        meta["date"] = to_iso_date(*d.groups()) if d else None
        meta["case_number"] = header.group(3)
    else:                                         # format Judilibre (texte intégral)
        # Chambre : "LA COUR DE CASSATION, TROISIÈME CHAMBRE CIVILE, a rendu..." ou "..., CHAMBRE CRIMINELLE, en son audience"
        m = re.search(r"COUR DE CASSATION,\s*(CHAMBRE CRIMINELLE|CHAMBRE SOCIALE|CHAMBRE COMMERCIALE|"
                      r"PREMI[ÈE]RE CHAMBRE CIVILE|DEUXI[ÈE]ME CHAMBRE CIVILE|TROISI[ÈE]ME CHAMBRE CIVILE|"
                      r"ASSEMBL[ÉE]E PL[ÉE]NI[ÈE]RE|CHAMBRE MIXTE)", text, re.IGNORECASE)
        if m:
            name = m.group(1).upper().replace("È", "E").replace("É", "E")      # on enlève les accents pour comparer
            meta["chamber"] = JUDILIBRE_CHAMBERS.get(name)
        # Date, dans cet ordre :
        #   1. la date de l'en-tête, seule sur sa ligne ("2 MARS 2016") ou "Audience publique du 28 janvier 2016"
        #      dans les premières lignes : c'est la date de la décision
        #   2. sinon la DERNIÈRE date d'audience du texte, en chiffres ou en lettres : en fin d'arrêt, c'est la date
        #      du prononcé ("prononcé ... en son audience publique du neuf janvier deux mille trois")
        top = re.search(r"(?:^|\n)\s*(?:Audience publique du\s+)?" + DATE_RE + r"\s*(?:\n|$)", text[:400], re.IGNORECASE)
        dates = audience_dates(text)
        if top:
            meta["date"] = to_iso_date(*top.groups())
        elif dates:
            meta["date"] = dates[-1][1]
        # Numéro : "Pourvoi n° M 13-25. 730" ou "N° B 20-85.618", sinon le premier motif "00-00.000" du texte
        n = (re.search(r"[Nn]°\s*[A-Z]?\s*(\d{2}-\d{2})\.\s?(\d{3})", text)
             or re.search(r"\b(\d{2}-\d{2})\.\s?(\d{3})\b", text))
        meta["case_number"] = f"{n.group(1)}.{n.group(2)}" if n else None

    # Président : "- Président : M. Sottet" (Bulletin) ou "M. CHAUVIN, président" (Judilibre)
    meta["president"] = (first_match(r"Président\s*:\s*((?:M\.|Mme)\s*[^\s(-]+(?:\s[A-Z][^\s(-]+)?)", text)
                         or first_match(r"\n\s*((?:M\.|Mme)\s+[A-ZÉ][A-ZÉ\-]+)\s*,\s*(?:conseiller doyen faisant fonction de )?président", text))
    return meta


# Marqueurs de début de chaque zone. Deux styles d'écriture existent :
#   - style direct (depuis 2019) : "Faits et procédure", "Examen du moyen", "Réponse de la Cour"
#   - style ancien               : "Attendu, selon l'arrêt attaqué", "Sur le moyen unique", "Vu l'article"
ZONE_MARKERS = {
    "expose": [r"\n\s*Faits et procédure", r"Attendu,? selon l'arrêt attaqué", r"Attendu qu'il résulte de l'arrêt attaqué",
               r"Selon l'arrêt attaqué"],
    "moyens": [r"\n\s*Examen d[ue]s? moyens?", r"\n\s*Enoncé d[ue]s? moyens?", r"\n\s*Sur le (?:premier |second |deuxième |troisième )?moyen"],
    "motivations": [r"\n\s*Réponse de la Cour", r"\n\s*Vu l'article", r"\n\s*Vu les articles", r"Attendu que pour"],
    "dispositif": [r"PAR CES MOTIFS"],
}


def extract_zones(text):
    """Trouve la première position de chaque marqueur, puis découpe le texte entre ces positions."""
    positions = {}
    for zone, patterns in ZONE_MARKERS.items():
        found = [m.start() for p in patterns for m in [re.search(p, text)] if m]
        if found:
            positions[zone] = min(found)
    # une zone ne peut pas commencer avant la précédente : on garde l'ordre logique
    order = ["expose", "moyens", "motivations", "dispositif"]
    ordered, last = [], -1
    for z in order:
        if z in positions and positions[z] > last:
            ordered.append((z, positions[z]))
            last = positions[z]
    zones = {"introduction": text[:ordered[0][1]].strip() if ordered else text.strip()}
    for i, (z, start) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else len(text)
        zones[z] = text[start:end].strip()
    for z in order:
        zones.setdefault(z, "")
    # on coupe la fin du dispositif (composition de la cour, avocats, textes visés)
    zones["dispositif"] = re.split(r"\nArrêt rendu en formation|\n- Président\s*:|\nTextes visés", zones["dispositif"])[0].strip()
    return zones


# Liste des codes les plus cités (les plus longs d'abord, pour que "code de procédure pénale"
# soit reconnu en entier et pas seulement "code de procédure")
CODES = sorted([
    "code civil", "code pénal", "code de procédure civile", "code de procédure pénale", "code du travail",
    "code de commerce", "code de la sécurité sociale", "code de la consommation", "code des assurances",
    "code de l'urbanisme", "code de la construction et de l'habitation", "code général des impôts",
    "code monétaire et financier", "code de la santé publique", "code de l'environnement",
    "code rural et de la pêche maritime", "code rural", "code des procédures civiles d'exécution",
    "code de l'entrée et du séjour des étrangers et du droit d'asile", "code de la route", "code des douanes",
    "code de l'organisation judiciaire", "code électoral", "code de la propriété intellectuelle",
    "code de l'action sociale et des familles", "code des transports", "code de la mutualité",
    "code général des collectivités territoriales", "code de justice administrative", "code du sport",
    "code de l'expropriation pour cause d'utilité publique", "code forestier", "code de la défense",
    "code de l'éducation", "code de l'énergie", "code pénitentiaire", "code de la justice pénale des mineurs",
    "code du tourisme", "code des postes et des communications électroniques", "code de la famille",
], key=len, reverse=True)

STATUTE_RE = re.compile(
    r"[Aa]rticles?\s+"
    r"((?:[LRD]\.?\s?)?\d+(?:[-.]\d+)*(?:,\s*[IVX]+,?)?(?:\s*(?:,|et)\s*(?:[LRD]\.?\s?)?\d+(?:[-.]\d+)*)*)"
    r"\s*(?:,\s*)?(?:du|de la|de l')\s+"
    r"(" + "|".join(re.escape(c) for c in CODES) +
    r"|loi n°\s?[\d-]+|Convention européenne des droits de l'homme|décret n°\s?[\d-]+)",
    re.IGNORECASE,
)


def extract_statutes(text):
    """Renvoie la liste (sans doublons) des textes de loi cités, ex. 'article 4 du code de procédure civile'."""
    found = []
    for numbers, source in STATUTE_RE.findall(text):
        source = re.sub(r"\s+", " ", source).strip().rstrip(" ,")
        item = f"article {numbers.strip()} du {source}" if source.startswith("code") else f"article {numbers.strip()} de la {source}"
        item = item.lower()
        if item not in found:
            found.append(item)
    return found


def extract_previous_decision(text):
    """Décision attaquée : la première cour d'appel citée, et la date qui suit."""
    m = re.search(r"cour d'appel d[e']\s?([A-ZÉ][\w\-éèàô]+(?:[- ](?:en|de|sur|la|le)[- ][\w\-éèà]+)?)", text)
    if not m:
        return {"court": None, "date": None}
    court = "Cour d'appel de " + m.group(1)
    window = text[max(0, m.start() - 150): m.end() + 150]
    d = re.search(DATE_RE, window)
    return {"court": court, "date": to_iso_date(*d.groups()) if d else None}


def verdict_from_dispositif(dispositif):
    """Issue déduite par règle à partir des verbes du dispositif."""
    d = dispositif.upper()
    if re.search(r"\bCASSE\b", d):
        return "Cassation"
    if re.search(r"\bREJETTE\b", d):
        return "Rejet"
    if "IRRECEVABLE" in d:
        return "Irrecevabilité"
    return "Autre"


def extract_orders(dispositif):
    """Découpe le dispositif en ordres ("CASSE et ANNULE...", "RENVOIE...", "Condamne...")."""
    body = re.sub(r"^PAR CES MOTIFS.*?:", "", dispositif.strip(), count=1, flags=re.DOTALL)
    parts = [re.sub(r"\s+", " ", p).strip() for p in re.split(r";\s*\n|\n\s*\n|;\s(?=[A-ZÉ]{3,})", body)]
    return [p for p in parts if len(p) > 15]


def verdict_from_header(text):
    """Dans les Bulletins, l'issue est écrite sous l'en-tête : '– Cassation –'."""
    m = re.search(r"\n\s*[–-]\s*(Cassation[^–\n]*|Rejet|Irrecevabilité|Non-lieu à statuer|Déchéance)\s*[–-]", text[:600])
    return m.group(1).strip() if m else None


def decision_to_json(text, source="", index=1):
    zones = extract_zones(text)
    return {
        "source_file": source,
        "decision_index": index,
        "metadata": extract_metadata(text),
        "narrative": {
            "facts": zones["expose"],
            "claims": zones["moyens"],
        },
        "legal_foundations": {
            "statutes": extract_statutes(text),
            "previous_decision": extract_previous_decision(text),
        },
        "outcome": {
            "verdict_rules": verdict_from_dispositif(zones["dispositif"]),
            "verdict_header": verdict_from_header(text),
            "orders": extract_orders(zones["dispositif"]),
            "reasoning": zones["motivations"],
        },
    }

# ----------------------------------------------------------------------------
# 5. PROGRAMME PRINCIPAL
# ----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Décision de justice (PDF/texte) -> JSON")
    parser.add_argument("input", help="fichier .pdf ou .txt")
    parser.add_argument("-o", "--output", default="output", help="dossier de sortie")
    parser.add_argument("--type", choices=["natif", "scanne"], help="type du PDF (sinon : question + détection)")
    args = parser.parse_args()

    text, mode = read_document(args.input, args.type)
    print(f"Lecture : mode {mode}, {len(text):,} caractères")
    text = clean_text(text)
    decisions = split_decisions(text)
    print(f"{len(decisions)} arrêt(s) trouvé(s)")

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.input).stem
    seen = set()                     # un Bulletin peut publier le même arrêt sous deux thèmes
    for i, dec in enumerate(decisions, start=1):
        result = decision_to_json(dec, source=Path(args.input).name, index=i)
        number = result["metadata"]["case_number"]
        if number and number in seen:
            print(f"  arrêt n° {number} déjà traité (publié deux fois dans le Bulletin) : ignoré")
            continue
        seen.add(number)
        out = out_dir / f"{stem}_arret_{i:03d}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        m = result["metadata"]
        print(f"  {out.name} : {m['chamber']} | {m['date']} | n° {m['case_number']} | "
              f"issue (règles) = {result['outcome']['verdict_rules']}")


if __name__ == "__main__":
    main()
