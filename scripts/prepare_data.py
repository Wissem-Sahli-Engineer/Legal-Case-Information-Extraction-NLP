"""
Préparation des données (à lancer une seule fois, ~10 min).

Lit data/raw/cour_de_cassation.jsonl.gz ligne par ligne (sans tout charger en mémoire)
et produit trois fichiers dans data/processed/ :

1. stats_all.parquet   : une ligne de statistiques par décision, pour les 553 075 décisions (EDA)
2. corpus_model.parquet: 100 000 décisions tirées au hasard, avec les textes des zones utiles (modèles)
3. eval_fulltext.parquet: 2 000 décisions avec le texte intégral (évaluation des règles d'extraction)
"""
import gzip
import json
import random
from pathlib import Path

import pandas as pd

RAW = Path("data/raw/cour_de_cassation.jsonl.gz")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

N_MODEL = 100_000      # décisions gardées pour les modèles
N_EVAL = 2_000         # décisions gardées avec texte intégral
KEEP_PROB = 0.28       # ~357 000 candidates x 0.28 ≈ 100 000 (le fichier est trié par date : on couvre toutes les années)
random.seed(42)

# Les 14 issues d'origine sont regroupées en 4 classes (les petites classes vont dans "Autre")
def group_label(solution):
    if solution in ("Rejet", "Cassation", "Irrecevabilité"):
        return solution
    return "Autre"

def zone_text(text, zones, name):
    """Recolle les morceaux d'une zone (une zone peut avoir plusieurs segments)."""
    segments = (zones or {}).get(name) or []
    return "\n".join(text[s["start"]:s["end"]] for s in segments).strip()

stats, corpus, evalset = [], [], []

with gzip.open(RAW, "rt", encoding="utf-8") as f:
    for i, line in enumerate(f):
        r = json.loads(line)
        text = r.get("text") or ""
        zones = r.get("zones") or {}
        date = r.get("decision_date") or ""

        stats.append({
            "id": r["id"],
            "date": date,
            "year": int(date[:4]) if date[:4].isdigit() else None,
            "chamber": r.get("chamber"),
            "solution": r.get("solution"),
            "label": group_label(r.get("solution")),
            "published": "Publié au Bulletin" in (r.get("publication") or []),
            "n_words": len(text.split()),
            "has_zones": bool(zones),
            **{f"zone_{z}": bool(zones.get(z)) for z in
               ["introduction", "expose", "moyens", "motivations", "dispositif", "annexes"]},
            "n_visa": len(r.get("visa") or []),
            "has_contested": bool(r.get("contested")),
            "has_summary": bool(r.get("summary")),
        })

        # Candidat pour les modèles : il faut les zones "motivations" et "dispositif"
        if zones.get("motivations") and zones.get("dispositif") and random.random() < KEEP_PROB:
            row = {
                "id": r["id"],
                "date": date,
                "chamber": r.get("chamber"),
                "solution": r.get("solution"),
                "label": group_label(r.get("solution")),
                "introduction": zone_text(text, zones, "introduction"),
                "motivations": zone_text(text, zones, "motivations"),
                "dispositif": zone_text(text, zones, "dispositif"),
            }
            if len(corpus) < N_MODEL:
                corpus.append(row)
            if len(evalset) < N_EVAL and random.random() < 0.02:
                contested = r.get("contested") or {}
                evalset.append({
                    **{k: row[k] for k in ["id", "date", "chamber", "solution", "label"]},
                    "number": r.get("number"),
                    "visa": [v.get("title") for v in (r.get("visa") or [])],
                    "contested_jurisdiction": contested.get("jurisdiction"),
                    "contested_date": contested.get("date"),
                    "text": text,
                })

        if (i + 1) % 50_000 == 0:
            print(f"{i + 1:,} décisions lues | corpus modèles : {len(corpus):,}", flush=True)

pd.DataFrame(stats).to_parquet(OUT / "stats_all.parquet", index=False)
pd.DataFrame(corpus).to_parquet(OUT / "corpus_model.parquet", index=False)
pd.DataFrame(evalset).to_parquet(OUT / "eval_fulltext.parquet", index=False)
print(f"FINI : {len(stats):,} stats | {len(corpus):,} corpus | {len(evalset):,} éval")
