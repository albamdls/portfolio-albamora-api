from functools import lru_cache

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def get_vectorstore():
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings
    from app.services.kb_loader import load_kb_documents

    documents = load_kb_documents()
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    vectorstore = FAISS.from_documents(documents, embeddings)

    return vectorstore


def retrieve_context(query: str, k: int = 4):
    vectorstore = get_vectorstore()
    return vectorstore.similarity_search(query, k=k)