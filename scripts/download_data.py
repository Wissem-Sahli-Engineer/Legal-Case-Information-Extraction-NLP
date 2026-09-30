"""Streame cour_de_cassation.jsonl.gz (HF: antoinejeannot/jurisprudence) et ne garde que
les décisions récentes qui ont des zones (structure Judilibre) -> data/raw/cassation_sample.jsonl"""
import gzip, json, random, sys, requests

URL = "https://huggingface.co/datasets/antoinejeannot/jurisprudence/resolve/main/cour_de_cassation.jsonl.gz"
OUT = "data/raw/cassation_sample.jsonl"
MIN_DATE, MAX_DOCS, KEEP_PROB = "2015-01-01", 6000, 0.25
random.seed(42)

kept = seen = 0
with requests.get(URL, stream=True, timeout=60) as r, open(OUT, "w", encoding="utf-8") as out:
    r.raise_for_status()
    for line in gzip.GzipFile(fileobj=r.raw):
        seen += 1
        if seen % 50000 == 0:
            print(f"lu {seen} décisions, gardé {kept}", flush=True)
        rec = json.loads(line)
        if (rec.get("decision_date") or "") < MIN_DATE or not rec.get("zones") or not rec.get("text"):
            continue
        if random.random() > KEEP_PROB:
            continue
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        kept += 1
        if kept >= MAX_DOCS:
            break
print(f"FINI: lu {seen}, gardé {kept}")
