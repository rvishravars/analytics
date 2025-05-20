# ArXiv Semantic Search Engine using SingleStore and Sentence Transformers

This project demonstrates a scalable semantic search system for scientific publications using the [ArXiv Metadata Snapshot](https://www.kaggle.com/datasets/Cornell-University/arxiv/data). The system indexes abstracts of research papers as high-dimensional vectors in [SingleStore Cloud](https://www.singlestore.com/) using the `VECTOR(768)` column type, enabling fast and meaningful retrieval based on natural language queries.

---

## 📦 Dataset

- **Source**: [Kaggle - ArXiv Metadata Snapshot](https://www.kaggle.com/datasets/Cornell-University/arxiv/data)
- **Size**: ~1.6 GB (uncompressed)
- **Format**: JSONL (one paper per line)
- **Fields used**: `id`, `title`, `abstract`, `categories`, `update_date`

### Big Data Characteristics:
- **Volume**: ~2.3 million papers with structured and unstructured metadata.
- **Variety**: Includes structured fields (IDs, dates), semi-structured lists (authors, tags), and unstructured text (abstracts).

---

## 🧠 Technologies Used

- **Database**: SingleStore Cloud (Free Tier)
- **Embedding Model**: `sentence-transformers/all-mpnet-base-v2`
- **Language**: Python
- **Libraries**: `singlestoredb`, `sentence-transformers`, `tqdm`, `dotenv`

---

## 📐 Schema Overview

```sql
CREATE TABLE arxiv_papers (
    paper_id TEXT PRIMARY KEY,
    title TEXT,
    abstract TEXT,
    abstract_vector VECTOR(768),
    category TEXT,
    updated DATE
);
```

An ANN index is created on `abstract_vector` using:

```sql
ALTER TABLE arxiv_papers
ADD VECTOR INDEX abstract_vector_index(abstract_vector)
INDEX_OPTIONS '{"index_type":"IVF_PQFS", "metric_type":"DOT_PRODUCT"}';
```

---

## 🚀 Running the Project

### 1. Clone the Repository

```bash
git clone git@github.com:rvishravars/analytics.git
cd analytics
```

### 2. Install Dependencies

Ensure Python 3.8+ is installed:

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install singlestoredb sentence-transformers tqdm python-dotenv
```

### 3. Configure Environment

Create a `.env` file with your SingleStore Cloud credentials:

```env
S2_HOST=your-host.svc.singlestore.com
S2_PORT=3306
S2_USER=your-user
S2_PASSWORD=your-password
S2_DATABASE=your-db
```

### 4. Load Data (ETL)

Run the ingestion script to read, embed, and insert papers:

```bash
python etl.py
```

This will:
- Parse each paper
- Embed the abstract using `all-mpnet-base-v2`
- Insert into SingleStore in batches

### 5. Perform a Semantic Search

```bash
python query.py
```

You will be prompted to enter a natural language query like:

```
🔍 Enter your paper query or abstract: deep learning in protein folding
```

---

## 🧪 Example Output

```
📚 Top matching papers:
- [2103.00020] Advances in Protein Structure Prediction Using Deep Learning (score: 0.9251)
- [1907.00376] Learning Protein Folding Patterns with Neural Nets (score: 0.8972)
...
```

---

## 🔮 Future Scope

- **Full-Text Storage**: Store full research papers as BLOB or TEXT in SingleStore, enabling richer content-based queries.
- **Hybrid Indexing**: Combine vector similarity with full-text search (`MATCH AGAINST`) for more precise results.
- **Federated Metadata Index**: Use the current table as a metadata gateway for advanced recommender systems, citation networks, or clustering engines.
- **Streaming Updates**: Ingest live updates from ArXiv feeds for real-time indexing.

---

## 📜 License

This project is for academic and research use only. Refer to the dataset license on [Kaggle](https://www.kaggle.com/datasets/Cornell-University/arxiv/data) for usage restrictions.

---

## 🙏 Acknowledgements

- [ArXiv.org](https://arxiv.org/)
- [Sentence-Transformers](https://www.sbert.net/)
- [SingleStore](https://www.singlestore.com/)
- [Kaggle Datasets](https://www.kaggle.com/datasets)
