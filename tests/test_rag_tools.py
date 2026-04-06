import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

# Set dummy env vars BEFORE importing src modules
os.environ["OPENROUTER_API_KEY"] = "dummy_key"
os.environ["DEFAULT_MODEL"] = "dummy_model"
os.environ["ENABLE_LANGSMITH_TRACING"] = "false"
os.environ["SUPABASE_DB_URL"] = "postgresql://example"
os.environ["SUPABASE_VECTOR_TABLE"] = "rfc_knowledge_base"
os.environ["SUPABASE_VECTOR_DIM"] = "3"
os.environ["SUPABASE_VECTOR_DISTANCE"] = "cosine"

sys.path.append(os.getcwd())

from src.tools import rag_tools


class FakeCursor:
    def __init__(self, fetchone_result=None, fetchall_result=None):
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result or []
        self.executed = []
        self.executemany_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def executemany(self, query, seq_of_params):
        self.executemany_calls.append((query, list(seq_of_params)))

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self._cursor


class TestRagTools(unittest.TestCase):
    def setUp(self):
        rag_tools.cfg.SUPABASE_VECTOR_DIM = 3
        rag_tools.cfg.SUPABASE_VECTOR_TABLE = "rfc_knowledge_base"
        rag_tools.cfg.SUPABASE_VECTOR_DISTANCE = "cosine"

    @patch("src.tools.rag_tools.get_embeddings")
    @patch("src.tools.rag_tools._get_db_connection")
    @patch("src.tools.rag_tools._json_value", side_effect=lambda payload: payload)
    @patch("src.tools.rag_tools._vector_value", side_effect=lambda payload: payload)
    def test_add_documents_replaces_existing_rfc_rows(
        self,
        _mock_vector,
        _mock_json,
        mock_get_connection,
        mock_get_embeddings,
    ):
        cursor = FakeCursor()
        mock_get_connection.return_value = FakeConnection(cursor)
        mock_embeddings = MagicMock()
        mock_embeddings.embed_documents.return_value = [
            [0.1, 0.2, 0.3],
            [0.3, 0.2, 0.1],
        ]
        mock_get_embeddings.return_value = mock_embeddings

        documents = [
            Document(page_content="chunk a", metadata={"rfc_id": "7540", "source": "RFC 7540"}),
            Document(page_content="chunk b", metadata={"rfc_id": "7540", "source": "RFC 7540"}),
        ]

        rag_tools.add_documents(documents)

        self.assertEqual(len(cursor.executed), 1)
        delete_query, delete_params = cursor.executed[0]
        self.assertIn("DELETE FROM public.rfc_knowledge_base", delete_query)
        self.assertEqual(delete_params, (["7540"],))

        self.assertEqual(len(cursor.executemany_calls), 1)
        insert_query, insert_params = cursor.executemany_calls[0]
        self.assertIn("INSERT INTO public.rfc_knowledge_base", insert_query)
        self.assertEqual(len(insert_params), 2)

    @patch("src.tools.rag_tools.get_embeddings")
    @patch("src.tools.rag_tools._get_db_connection")
    @patch("src.tools.rag_tools._vector_value", side_effect=lambda payload: payload)
    def test_query_knowledge_base_returns_documents(
        self,
        _mock_vector,
        mock_get_connection,
        mock_get_embeddings,
    ):
        cursor = FakeCursor(
            fetchall_result=[
                {
                    "id": "1",
                    "content": "RFC snippet",
                    "metadata": {"rfc_id": "7540", "source": "RFC 7540"},
                    "similarity": 0.99,
                }
            ]
        )
        mock_get_connection.return_value = FakeConnection(cursor)
        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_get_embeddings.return_value = mock_embeddings

        results = rag_tools.query_knowledge_base("igmp query interval", n_results=3, rfc_ids=["3376"])

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], Document)
        self.assertEqual(results[0].metadata["rfc_id"], "7540")
        self.assertIn("FROM public.rfc_knowledge_base", cursor.executed[0][0])
        self.assertIn("ORDER BY embedding <=>", cursor.executed[0][0])
        self.assertIn("::extensions.vector", cursor.executed[0][0])
        self.assertIn("::integer", cursor.executed[0][0])
        self.assertIn("::text[]", cursor.executed[0][0])
        self.assertEqual(
            cursor.executed[0][1],
            [[0.1, 0.2, 0.3], ["3376"], [0.1, 0.2, 0.3], 3],
        )

    @patch("src.tools.rag_tools._get_db_connection")
    def test_find_missing_rfcs_returns_only_absent_ids(self, mock_get_connection):
        cursor = FakeCursor(
            fetchall_result=[
                {"rfc_id": "3376"},
                {"rfc_id": "7761"},
            ]
        )
        mock_get_connection.return_value = FakeConnection(cursor)

        missing = rag_tools.find_missing_rfcs(["3376", "3810", "7761"])

        self.assertEqual(missing, ["3810"])
        self.assertIn("SELECT DISTINCT rfc_id", cursor.executed[0][0])

    @patch("src.tools.rag_tools._get_db_connection")
    def test_clear_knowledge_base_truncates_table(self, mock_get_connection):
        cursor = FakeCursor()
        mock_get_connection.return_value = FakeConnection(cursor)

        rag_tools.clear_knowledge_base()

        self.assertEqual(
            cursor.executed[0],
            ("TRUNCATE TABLE public.rfc_knowledge_base", None),
        )

    @patch("src.tools.rag_tools._get_db_connection")
    def test_check_rfc_exists_false_when_empty(self, mock_get_connection):
        cursor = FakeCursor(fetchone_result=None)
        mock_get_connection.return_value = FakeConnection(cursor)

        self.assertFalse(rag_tools.check_rfc_exists("7540"))

    @patch("src.tools.rag_tools._get_db_connection")
    def test_check_rfc_exists_true_when_present(self, mock_get_connection):
        cursor = FakeCursor(fetchone_result={"?column?": 1})
        mock_get_connection.return_value = FakeConnection(cursor)

        self.assertTrue(rag_tools.check_rfc_exists("7540"))

    def test_normalize_postgres_url_encodes_raw_password_characters(self):
        url = (
            "postgresql://postgres.abcd:EME8F%e,BrE3LZ*@db.example.supabase.co:6543/"
            "postgres?sslmode=require"
        )

        normalized = rag_tools._normalize_postgres_url(url)

        self.assertIn("EME8F%25e%2CBrE3LZ%2A", normalized)
        self.assertTrue(normalized.startswith("postgresql://postgres.abcd:"))

    def test_normalize_postgres_url_keeps_non_url_conninfo_unchanged(self):
        conninfo = "host=db.example user=postgres password=abc%def dbname=postgres"

        normalized = rag_tools._normalize_postgres_url(conninfo)

        self.assertEqual(normalized, conninfo)

    def test_validate_supabase_connection_string_rejects_direct_host_with_pooler_port(self):
        with self.assertRaises(RuntimeError) as ctx:
            rag_tools._validate_supabase_connection_string(
                "postgresql://postgres.abcd:secret@db.abcd.supabase.co:6543/postgres?sslmode=require"
            )

        self.assertIn("copy the exact pooler connection string", str(ctx.exception))

    def test_format_connection_error_guides_user_on_dns_failure(self):
        message = rag_tools._format_connection_error(
            "postgresql://postgres.abcd:secret@db.abcd.supabase.co:6543/postgres?sslmode=require",
            RuntimeError("failed to resolve host 'db.abcd.supabase.co': [Errno 8] nodename nor servname provided, or not known"),
        )

        self.assertIn("Failed to resolve the Supabase database host", message)
        self.assertIn("pooler connection string", message)

    def test_prepare_connection_for_pgvector_sets_search_path_first(self):
        cursor = FakeCursor()
        conn = FakeConnection(cursor)
        register_vector = MagicMock()

        rag_tools._prepare_connection_for_pgvector(conn, register_vector)

        self.assertEqual(
            cursor.executed[0],
            ("SET search_path TO public, extensions", None),
        )
        register_vector.assert_called_once_with(conn)

    def test_format_connection_error_explains_missing_vector_type(self):
        message = rag_tools._format_connection_error(
            "postgresql://postgres.abcd:secret@aws-0-test.pooler.supabase.com:6543/postgres?sslmode=require",
            RuntimeError("vector type not found in the database"),
        )

        self.assertIn("pgvector extension could not be found", message)
        self.assertIn("create extension if not exists vector", message)


if __name__ == "__main__":
    unittest.main()
