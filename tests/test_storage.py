import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

# Set dummy env vars BEFORE importing anything from src
os.environ["OPENROUTER_API_KEY"] = "dummy_key"
os.environ["DEFAULT_MODEL"] = "dummy_model"
os.environ["ENABLE_LANGSMITH_TRACING"] = "false"

sys.path.append(os.getcwd())

from src.storage.factory import get_knowledge_store, reset_knowledge_store
from src.tools import rag_tools


class TestKnowledgeStoreFactory(unittest.TestCase):
    def tearDown(self) -> None:
        reset_knowledge_store()

    def test_factory_returns_chroma_backend(self):
        with patch("src.storage.factory.cfg.VECTOR_BACKEND", "chroma"), patch(
            "src.storage.factory.ChromaKnowledgeStore", autospec=True
        ) as chroma_cls:
            instance = chroma_cls.return_value
            store = get_knowledge_store()

        chroma_cls.assert_called_once_with()
        self.assertIs(store, instance)

    def test_factory_returns_pgvector_backend(self):
        with patch("src.storage.factory.cfg.VECTOR_BACKEND", "pgvector"), patch(
            "src.storage.factory.PgVectorKnowledgeStore", autospec=True
        ) as pgvector_cls:
            instance = pgvector_cls.return_value
            store = get_knowledge_store()

        pgvector_cls.assert_called_once_with()
        self.assertIs(store, instance)


class TestRagTools(unittest.TestCase):
    def test_add_documents_delegates_to_backend(self):
        store = MagicMock()
        docs = [Document(page_content="hello", metadata={"rfc_id": "1"})]

        with patch("src.tools.rag_tools.get_knowledge_store", return_value=store):
            rag_tools.add_documents(docs)

        store.add_documents.assert_called_once_with(docs)

    def test_query_knowledge_base_delegates_to_backend(self):
        store = MagicMock()
        store.similarity_search.return_value = ["doc"]

        with patch("src.tools.rag_tools.get_knowledge_store", return_value=store):
            result = rag_tools.query_knowledge_base("ospf", n_results=3)

        store.similarity_search.assert_called_once_with("ospf", k=3)
        self.assertEqual(result, ["doc"])

    def test_check_rfc_exists_delegates_to_backend(self):
        store = MagicMock()
        store.has_rfc.return_value = True

        with patch("src.tools.rag_tools.get_knowledge_store", return_value=store):
            exists = rag_tools.check_rfc_exists("791")

        store.has_rfc.assert_called_once_with("791")
        self.assertTrue(exists)
