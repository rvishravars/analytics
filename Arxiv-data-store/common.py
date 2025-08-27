"""Common util"""
import os
from dotenv import load_dotenv
import singlestoredb as s2
from sentence_transformers import SentenceTransformer

load_dotenv()
model = SentenceTransformer("all-mpnet-base-v2")

def get_db_connection():
    return s2.connect(
        host=os.getenv("S2_HOST"),
        port=int(os.getenv("S2_PORT")),
        user=os.getenv("S2_USER"),
        password=os.getenv("S2_PASSWORD"),
        database=os.getenv("S2_DATABASE")
    )
