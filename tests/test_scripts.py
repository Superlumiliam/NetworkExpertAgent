import unittest
from unittest.mock import AsyncMock, patch

from scripts import clear_rfc_db, preload_rfcs
from src.core.rfc_catalog import get_supported_rfc_ids


class TestScripts(unittest.TestCase):
    @patch("scripts.preload_rfcs.ensure_rfc_knowledge_base_schema", AsyncMock(return_value=None))
    @patch("scripts.preload_rfcs.preload_rfc_documents", AsyncMock(return_value=[{"rfc_id": "3376", "chunks": 10}]))
    def test_preload_script_runs_supported_rfc_ids(self):
        exit_code = preload_rfcs.main()

        self.assertEqual(exit_code, 0)
        preload_rfcs.ensure_rfc_knowledge_base_schema.assert_awaited_once_with()
        preload_rfcs.preload_rfc_documents.assert_awaited_once_with(get_supported_rfc_ids())

    @patch("scripts.clear_rfc_db.ensure_rfc_knowledge_base_schema", AsyncMock(return_value=None))
    @patch("scripts.clear_rfc_db.clear_rfc_knowledge_base", AsyncMock(return_value=None))
    def test_clear_script_runs_successfully(self):
        exit_code = clear_rfc_db.main()

        self.assertEqual(exit_code, 0)
        clear_rfc_db.ensure_rfc_knowledge_base_schema.assert_awaited_once_with()
        clear_rfc_db.clear_rfc_knowledge_base.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
