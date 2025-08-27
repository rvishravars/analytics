CREATE TABLE arxiv_papers (
    paper_id TEXT PRIMARY KEY,
    title TEXT,
    abstract TEXT,
    abstract_vector VECTOR(768),
    category TEXT,
    updated DATE
);

ALTER TABLE arxiv_papers
ADD VECTOR INDEX abstract_vector_index(abstract_vector)
INDEX_OPTIONS '{"index_type":"IVF_PQFS", "metric_type":"DOT_PRODUCT"}';
