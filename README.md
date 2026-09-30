# ⚖️ Legal Case Information Extraction (NLP)

Extraction automatique d'informations structurées à partir de décisions de justice françaises.

On donne un **arrêt de la Cour de cassation** (PDF ou texte) et le système renvoie un **JSON** contenant les métadonnées de l'affaire, les faits, les textes de loi cités et l'issue de la décision.

> 🚧 **Projet en cours.** L'environnement et les données sont prêts. Les notebooks, les modèles et le rapport sont en construction : voir [État d'avancement](#-état-davancement).

---

## 📑 Sommaire

1. [Le problème](#-le-problème)
2. [Les données](#-les-données)
3. [Le pipeline](#-le-pipeline)
4. [Les modèles comparés](#-les-modèles-comparés)
5. [Structure du dépôt](#-structure-du-dépôt)
6. [Installation](#-installation)
7. [Utilisation](#-utilisation)
8. [État d'avancement](#-état-davancement)
9. [Limites](#-limites)
10. [Références](#-références)

---

## 🎯 Le problème

Une décision de justice est un texte **long** (1 700 mots en médiane, parfois plus de 60 000) et **peu structuré**. Pour un juriste, retrouver « qui, quand, sur quelle loi, avec quel résultat » demande de tout lire.

Ce projet automatise cette lecture. Il extrait 4 blocs d'information :

| Bloc | Exemple |
|---|---|
| **Métadonnées** : cour, chambre, date, n° de pourvoi, président | `Troisième chambre civile`, `2016-01-28`, `14-27.033` |
| **Récit** : faits, demandes, arguments | « Mme [C] a installé une véranda sur la terrasse… » |
| **Fondements juridiques** : textes de loi, décision attaquée | `Article 4 du code de procédure civile` |
| **Issue** : décision finale et ordres | `Cassation`, « renvoie devant la cour d'appel d'Aix-en-Provence » |

### Petit lexique juridique

- **Arrêt** : décision rendue par une cour (ici la Cour de cassation).
- **Pourvoi** : recours d'une partie qui conteste une décision d'appel devant la Cour de cassation.
- **Cassation** : la Cour annule la décision attaquée. **Rejet** : le pourvoi échoue, la décision attaquée reste valable.
- **Visa** : texte de loi sur lequel la Cour fonde sa décision (« Vu l'article… »).
- **Dispositif** : la partie finale de l'arrêt, après « PAR CES MOTIFS », qui contient la décision.

### Exemple de sortie

```json
{
  "metadata": {
    "court": "Cour de cassation",
    "chamber": "Troisième chambre civile",
    "date": "2016-01-28",
    "case_number": "14-27.033",
    "presiding_judge": "M. CHAUVIN"
  },
  "facts": "Mme [C], propriétaire d'un appartement en copropriété, a installé une véranda...",
  "legal_foundations": {
    "statutes": ["Article 4 du code de procédure civile"],
    "previous_decision": {"court": "Cour d'appel d'Aix-en-Provence", "date": "2013-05-03"}
  },
  "outcome": {
    "verdict": "Cassation",
    "orders": ["Casse et annule l'arrêt du 3 mai 2013", "Condamne le syndicat aux dépens"]
  }
}
```

---

## 📊 Les données

**Source :** [antoinejeannot/jurisprudence](https://huggingface.co/datasets/antoinejeannot/jurisprudence) (Hugging Face), construit à partir de **Judilibre**, l'open data officiel de la Cour de cassation. Licence **Etalab 2.0**.

| Caractéristique | Valeur |
|---|---|
| Décisions | **553 075** arrêts de la Cour de cassation |
| Période | 1860 → 2025 (98 % après 1970) |
| Volume | 639 millions de mots |
| Format | JSONL compressé (`.jsonl.gz`), une décision par ligne, ~1 Go |
| Noms des personnes | Pseudonymisés (`Mme [C]`, `[Adresse 1]`) |

Chaque ligne contient le **texte intégral** et des **champs structurés**, qui servent de vérité terrain :

| Champ | Contenu |
|---|---|
| `text` | Texte intégral de la décision |
| `decision_date`, `chamber`, `number`, `ecli` | Métadonnées |
| `zones` | Position (début/fin) des parties : introduction, exposé, moyens, motivations, dispositif |
| `solution` | Issue : Rejet, Cassation, Irrecevabilité… |
| `visa` | Textes de loi visés |
| `contested` | Décision attaquée (cour d'appel, date, numéro) |

**Répartition des issues** (étiquettes de la classification) :

| Issue | Nombre | Part |
|---|---:|---:|
| Rejet | 299 765 | 54 % |
| Cassation | 169 592 | 31 % |
| Autre | 43 833 | 8 % |
| Irrecevabilité | 22 351 | 4 % |
| Autres classes (déchéance, non-lieu, QPC…) | 17 534 | 3 % |

Les classes sont **déséquilibrées**. C'est pourquoi on évalue avec le **F1 macro**, qui compte chaque classe à égalité, et pas seulement l'accuracy.

---

## 🔧 Le pipeline

```
                    ┌──────────────┐
   Fichier PDF ───▶ │ PDF texte ?  │
                    └──────┬───────┘
              oui ┌────────┴────────┐ non (scanné)
                  ▼                 ▼
             PyMuPDF          Tesseract OCR
       (lecture directe)   (reconnaissance d'image)
                  └────────┬────────┘
                           ▼
                      Texte brut
                           ▼
              ┌─────────────────────────┐
              │ Txt_ToJSON (règles)     │  regex : date, n° de pourvoi,
              │                         │  chambre, articles de loi ;
              │                         │  découpage en zones
              └────────────┬────────────┘
                           ▼
              ┌─────────────────────────┐
              │ Modèle NLP              │  prédit l'issue
              │ (spaCy + classifieur)   │  (Rejet, Cassation…)
              └────────────┬────────────┘
                           ▼
                     JSON final
```

**Comment on sait si un PDF est scanné ?** Si PyMuPDF trouve du texte dans les pages, le PDF est « natif » (produit par ordinateur). S'il ne trouve presque rien, les pages sont des images, et on passe par l'OCR.

---

## 🤖 Les modèles comparés

La tâche d'apprentissage est la **classification de l'issue** de la décision. Trois modèles sont entraînés et comparés avec les mêmes données et les mêmes métriques :

| | Modèle | Idée | Outils |
|---|---|---|---|
| **A** | spaCy + TF-IDF + régression logistique | Nettoyage NLP classique (tokenisation, lemmatisation, mots vides), puis les mots importants deviennent des nombres et un classifieur linéaire décide | spaCy, scikit-learn |
| **B** | Réseau de neurones entraîné de zéro | Le réseau apprend lui-même une représentation des mots (embeddings) | TensorFlow / Keras |
| **C** | CamemBERT (fine-tuné) | Modèle de langue français déjà pré-entraîné sur des milliards de mots, adapté à notre tâche | TensorFlow, transformers |

**Métriques :** accuracy, précision, rappel, **F1 macro**, matrice de confusion, temps d'entraînement et d'inférence.

Les métadonnées et les textes de loi sont extraits par **règles** (regex) et évalués par comparaison avec les champs du dataset (exact match).

---

## 📁 Structure du dépôt

```
.
├── README.md
├── requirements.txt          # dépendances avec versions exactes
├── methodologie.txt          # plan de la démarche
├── data/
│   ├── raw/                  # données brutes (ignoré par git, ~1 Go)
│   └── pdf/                  # PDF de démonstration (Bulletins de la Cour)
├── notebooks/
│   ├── 01_EDA.ipynb          # exploration des données
│   └── 02_NLP.ipynb          # prétraitement, modèles, évaluation
├── scripts/
│   ├── download_data.py      # téléchargement des données
│   ├── Txt_ToJSON.py         # PDF/texte → JSON
│   └── predict.py            # JSON → prédiction du modèle final
├── models/                   # modèles entraînés sauvegardés
└── report/                   # rapport PDF (format article scientifique)
```

---

## ⚙️ Installation

Testé sur **macOS (Apple Silicon M4)** avec **Python 3.12**.

**1. Cloner le dépôt**

```bash
git clone https://github.com/Wissem-Sahli-Engineer/Legal-Case-Information-Extraction-NLP.git
cd Legal-Case-Information-Extraction-NLP
```

**2. Installer Tesseract (pour l'OCR) avec la langue française**

```bash
brew install tesseract
curl -L -o /opt/homebrew/share/tessdata/fra.traineddata \
  https://github.com/tesseract-ocr/tessdata_fast/raw/main/fra.traineddata
```

**3. Créer l'environnement Python 3.12**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download fr_core_news_sm
```

> ⚠️ Python 3.13 ou 3.14 ne fonctionnent pas : TensorFlow 2.18 ne les supporte pas.
> Sous Linux ou Windows, retire la ligne `tensorflow-metal` de `requirements.txt`.

**4. Activer le mode Keras 2** (obligatoire pour CamemBERT en TensorFlow)

```bash
export TF_USE_LEGACY_KERAS=1
```

**5. Télécharger les données** (~1 Go)

```bash
mkdir -p data/raw
curl -L -o data/raw/cour_de_cassation.jsonl.gz \
  "https://huggingface.co/datasets/antoinejeannot/jurisprudence/resolve/main/cour_de_cassation.jsonl.gz"
```

**Vérifier que le GPU est détecté :**

```bash
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```

---

## ▶️ Utilisation

**Explorer les données et entraîner les modèles** : ouvrir les notebooks dans l'ordre.

```bash
jupyter notebook notebooks/01_EDA.ipynb
jupyter notebook notebooks/02_NLP.ipynb
```

**Transformer un PDF en JSON**

```bash
python scripts/Txt_ToJSON.py data/pdf/Bulletin_civil_2026-5.pdf -o output/
```

Le script détecte si le PDF est natif ou scanné, extrait le texte, repère chaque arrêt et produit un JSON par arrêt.

**Prédire l'issue à partir du JSON**

```bash
python scripts/predict.py output/arret_001.json
```

---

## 📌 État d'avancement

| Étape | État |
|---|---|
| Environnement (TensorFlow + GPU Metal, spaCy, Tesseract) | ✅ |
| Téléchargement des données (553 075 décisions) | ✅ |
| Notebook EDA | 🚧 |
| Script PDF → JSON | 🚧 |
| Notebook NLP (modèles A, B, C + évaluation) | 🚧 |
| Script de prédiction | 🚧 |
| Rapport PDF | 🚧 |

---

## ⚠️ Limites

- **Legal-BERT non utilisé.** Legal-BERT est pré-entraîné sur des textes juridiques **anglais**. L'utiliser demanderait de traduire les arrêts en anglais au préalable : cela ajoute un modèle de traduction lourd et lent, et la traduction déforme le vocabulaire juridique français (« cassation », « pourvoi », « dispositif » n'ont pas d'équivalent exact en droit anglo-saxon). On utilise donc **CamemBERT**, pré-entraîné sur du français.
- **Un seul pays et une seule cour.** Les modèles sont entraînés sur la Cour de cassation française ; rien ne garantit qu'ils fonctionnent sur d'autres juridictions (par exemple tunisiennes).
- **Textes longs.** CamemBERT ne lit que 512 tokens (≈ 350 à 400 mots) à la fois : les décisions sont tronquées ou découpées.
- **Étiquettes imparfaites.** Les champs du dataset (zones, solution) sont produits par la Cour de cassation et peuvent contenir des erreurs ; certaines zones sont souvent vides (exposé : 41 % remplis).
- **Fuite d'information.** Le dispositif contient souvent la réponse en toutes lettres (« CASSE ET ANNULE », « REJETTE le pourvoi »). C'est normal pour une tâche d'extraction, mais la tâche est alors facile ; une variante sans le dispositif est testée pour mesurer ce que les modèles comprennent vraiment.

---

## 📚 Références

- Martin et al. (2020). *CamemBERT: a Tasty French Language Model.* ACL.
- Chalkidis et al. (2020). *LEGAL-BERT: The Muppets straight out of Law School.* Findings of EMNLP.
- Chalkidis et al. (2022). *LexGLUE: A Benchmark Dataset for Legal Language Understanding in English.* ACL.
- Zhong et al. (2020). *How Does NLP Benefit Legal System: A Summary of Legal Artificial Intelligence.* ACL.
- Vaswani et al. (2017). *Attention Is All You Need.* NeurIPS.
- Cour de cassation, [Judilibre](https://www.courdecassation.fr/recherche-judilibre), open data des décisions de justice.
- Jeannot, A. (2024). [Jurisprudence](https://github.com/antoinejeannot/jurisprudence), dataset Hugging Face.

---

## 📄 Licence

- **Données :** Licence Ouverte Etalab 2.0 (Cour de cassation / Judilibre).
- **Code :** à définir.
