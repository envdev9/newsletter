import os
import psycopg

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def connect():
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        user="demo", password="demo", dbname="demo", autocommit=True,
    )


def get_model():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODEL_NAME)


def vec_literal(v) -> str:
    return "[" + ",".join(f"{float(x):.7f}" for x in v) + "]"
