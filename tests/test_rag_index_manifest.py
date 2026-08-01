from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from equipdoc_agent.config import Settings
from equipdoc_agent.rag import KnowledgeRetriever
from equipdoc_agent.rag.index_manifest import (
    expected_index_manifest,
    read_index_manifest,
    write_index_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class RagIndexManifestTests(unittest.TestCase):
    def test_manifest_round_trip_binds_index_to_chunks_and_model(self):
        settings = Settings.from_env(ROOT)
        chunk_count = len(settings.rag_chunks_path.read_text(encoding="utf-8").splitlines())
        expected = expected_index_manifest(settings, chunk_count)
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            write_index_manifest(directory, expected)
            self.assertEqual(read_index_manifest(directory), expected)

    def test_existing_vector_directory_without_manifest_is_not_loaded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = replace(
                Settings.from_env(ROOT),
                rag_db_dir=Path(temp_dir).resolve(),
            )
            retriever = KnowledgeRetriever(settings)

        self.assertIsNone(retriever._dense_collection)
        self.assertIn(
            "vector DB manifest is missing or stale; dense retrieval disabled until rebuild",
            retriever.warnings,
        )


if __name__ == "__main__":
    unittest.main()
