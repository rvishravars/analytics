import os
import singlestoredb as s2
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# === Load environment variables ===
load_dotenv()

# === Load model once ===
model = SentenceTransformer('all-mpnet-base-v2')

# === Connect to SingleStore Cloud ===
conn = s2.connect(
    host=os.getenv("S2_HOST"),
    port=int(os.getenv("S2_PORT")),
    user=os.getenv("S2_USER"),
    password=os.getenv("S2_PASSWORD"),
    database=os.getenv("S2_DATABASE")
)
cursor = conn.cursor()

# === Prompt for user query ===
query_text = input("🔍 Enter your paper query or abstract: ").strip()

# === Embed the query ===
embedding = model.encode(query_text, normalize_embeddings=True)
vector_str = str(embedding.tolist())

# === Perform vector search ===
search_sql = """
SELECT paper_id, title, DOT_PRODUCT(abstract_vector, %s) AS score
FROM arxiv_papers
ORDER BY score DESC
LIMIT 5;
"""
cursor.execute(search_sql, (vector_str,))
results = cursor.fetchall()

print("\n📚 Top matching papers:")
for paper_id, title, score in results:
    if score < 0.1:
        break
    print(f"- [{paper_id}] {title}  (score: {score:.4f})")

# === Clean up ===
cursor.close()
conn.close()
