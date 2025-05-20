import json
from datetime import datetime
from sentence_transformers import SentenceTransformer
import singlestoredb as s2
from tqdm import tqdm
from dotenv import load_dotenv
import os

# === Load environment variables ===
load_dotenv()

conn = s2.connect(
    host=os.getenv("S2_HOST"),
    port=int(os.getenv("S2_PORT")),
    user=os.getenv("S2_USER"),
    password=os.getenv("S2_PASSWORD"),
    database=os.getenv("S2_DATABASE")
)
cursor = conn.cursor()

# === Load embedding model ===
model = SentenceTransformer('all-mpnet-base-v2')

# === Batch settings ===
batch = []
batch_size = 50

# === Count total lines for progress bar ===
with open("arxiv-sample-500.json", "r") as f:
    total_lines = sum(1 for _ in f)

# === Process and insert ===
with open("arxiv-sample-500.json", "r") as f, tqdm(total=total_lines, desc="Processing Papers") as pbar:
    for i, line in enumerate(f):
        paper = json.loads(line)
        paper_id = paper.get("id")
        title = paper.get("title", "").strip()
        abstract = paper.get("abstract", "").replace("\n", " ").strip()
        category = paper.get("categories", "")
        date = paper.get("update_date", None)

        if not abstract or not paper_id:
            pbar.update(1)
            continue

        try:
            embedding = model.encode(abstract, normalize_embeddings=True)
            vector_str = str(embedding.tolist())
            update_date = datetime.strptime(date, "%Y-%m-%d").date() if date else None

            batch.append((paper_id, title, abstract, vector_str, category, update_date))

            if len(batch) >= batch_size:
                cursor.executemany("""
                    INSERT INTO arxiv_papers (
                        paper_id, title, abstract, abstract_vector, category, updated
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, batch)
                conn.commit()
                print(f"✅ Inserted batch of {len(batch)}")
                batch.clear()

        except Exception as e:
            print(f"⚠️ Skipping {paper_id}: {e}")

        pbar.update(1)

# Final batch
if batch:
    cursor.executemany("""
        INSERT INTO arxiv_papers (
            paper_id, title, abstract, abstract_vector, category, updated
        )
        VALUES (%s, %s, %s, %s, %s, %s)
    """, batch)
    conn.commit()
    print(f"✅ Inserted final batch of {len(batch)}")

cursor.close()
conn.close()
