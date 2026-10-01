"""
predict.py : prend un JSON produit par Txt_ToJSON.py et prédit l'issue de la décision avec le modèle NLP.

Le modèle lit la partie "outcome.reasoning" (les motivations de la Cour) et prédit :
    Rejet | Cassation | Irrecevabilité | Autre

Utilisation :
  python scripts/predict.py output/json/Bulletin_criminel_2026-7_arret_001.json
  python scripts/predict.py output/json/*.json --model A        # choisir le modèle (A, B ou C)
  python scripts/predict.py output/json/ -o output/predictions   # tout un dossier

Par défaut, le modèle utilisé est le modèle final choisi dans le notebook 02_NLP (models/final_model.json).
Le résultat est ajouté au JSON dans un bloc "prediction" et écrit dans le dossier de sortie.
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ["TF_USE_LEGACY_KERAS"] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
import setuptools  # noqa: F401  (fournit "distutils", importé par TensorFlow 2.18 sous Python 3.12)

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
CONFIG = json.loads((MODELS / "final_model.json").read_text(encoding="utf-8"))
LABELS = CONFIG["labels"]
NEGATIONS = CONFIG["negations"]


# ----------------------------------------------------------------------------
# Prétraitement spaCy (identique au notebook 02_NLP), utilisé par les modèles A et B
# ----------------------------------------------------------------------------

def load_spacy():
    import spacy
    nlp = spacy.load("fr_core_news_sm", disable=["parser", "ner"])
    for w in NEGATIONS:
        nlp.vocab[w].is_stop = False
    return nlp


def preprocess(doc):
    words = []
    for t in doc:
        if t.lower_ in NEGATIONS:
            words.append("ne" if t.lower_ in ("n'", "n’") else t.lower_)
        elif t.is_alpha and not t.is_stop and len(t) > 1:
            words.append(t.lemma_.lower())
    return " ".join(words)


# ----------------------------------------------------------------------------
# Les trois modèles : chacun renvoie une liste de probabilités (une par classe)
# ----------------------------------------------------------------------------

def predict_a(texts):
    """Modèle A : spaCy + TF-IDF + régression logistique."""
    import joblib
    nlp = load_spacy()
    model = joblib.load(MODELS / "model_a_tfidf_logreg.joblib")
    lemmas = [preprocess(d) for d in nlp.pipe(t[-6000:] for t in texts)]
    return model.predict_proba(lemmas)


def predict_b(texts):
    """Modèle B : réseau de neurones Keras (CNN) entraîné de zéro."""
    import numpy as np
    import tf_keras as keras
    nlp = load_spacy()
    vocab = json.loads((MODELS / "model_b_vocabulary.json").read_text(encoding="utf-8"))
    vectorizer = keras.layers.TextVectorization(output_sequence_length=CONFIG["seq_len_b"], vocabulary=vocab[2:])
    model = keras.models.load_model(MODELS / "model_b_cnn.keras")
    lemmas = [preprocess(d) for d in nlp.pipe(t[-6000:] for t in texts)]
    ids = vectorizer(np.array(lemmas, dtype=object)).numpy()
    return model.predict(ids, verbose=0)


def predict_c(texts):
    """Modèle C : CamemBERT fine-tuné (lit le texte brut, garde la fin des motivations)."""
    import tensorflow as tf
    from transformers import AutoTokenizer, TFAutoModelForSequenceClassification
    path = MODELS / "camembert_finetuned"
    tokenizer = AutoTokenizer.from_pretrained(path)
    tokenizer.truncation_side = "left"
    model = TFAutoModelForSequenceClassification.from_pretrained(path)
    enc = dict(tokenizer(list(texts), truncation=True, max_length=CONFIG["max_len_c"],
                         padding="max_length", return_tensors="np"))
    logits = model.predict(enc, batch_size=16, verbose=0).logits
    return tf.nn.softmax(logits, axis=-1).numpy()


PREDICTORS = {"A": predict_a, "B": predict_b, "C": predict_c}
MODEL_NAMES = {"A": "spaCy + TF-IDF + régression logistique", "B": "CNN Keras (de zéro)",
               "C": "CamemBERT fine-tuné"}


def main():
    parser = argparse.ArgumentParser(description="JSON (Txt_ToJSON) -> prédiction de l'issue")
    parser.add_argument("inputs", nargs="+", help="fichiers JSON ou dossier")
    parser.add_argument("--model", choices=["A", "B", "C"], default=CONFIG["final_model"],
                        help=f"modèle à utiliser (défaut : {CONFIG['final_model']}, le modèle final)")
    parser.add_argument("-o", "--output", default="output/predictions", help="dossier de sortie")
    args = parser.parse_args()

    files = []
    for item in args.inputs:
        p = Path(item)
        files += sorted(p.glob("*.json")) if p.is_dir() else [p]
    docs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    keep = [i for i, d in enumerate(docs) if d["outcome"]["reasoning"].strip()]
    if not keep:
        sys.exit("Aucun JSON avec des motivations (outcome.reasoning) à analyser.")

    print(f"Modèle {args.model} : {MODEL_NAMES[args.model]} | {len(keep)} décision(s)")
    probas = PREDICTORS[args.model]([docs[i]["outcome"]["reasoning"] for i in keep])

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, p in zip(keep, probas):
        doc = docs[i]
        best = int(p.argmax())
        doc["prediction"] = {
            "model": f"{args.model} · {MODEL_NAMES[args.model]}",
            "verdict": LABELS[best],
            "confidence": round(float(p[best]), 4),
            "probabilities": {l: round(float(v), 4) for l, v in zip(LABELS, p)},
        }
        (out_dir / files[i].name).write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        truth = doc["outcome"].get("verdict_header") or doc["outcome"].get("verdict_rules")
        print(f"  {files[i].name:45s} prédit = {LABELS[best]:15s} ({p[best]:.0%})   | attendu : {truth}")


if __name__ == "__main__":
    main()
