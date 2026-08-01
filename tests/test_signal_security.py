from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from equipdoc_agent.config import Settings
from equipdoc_agent.tools import SignalValidationError, analyze_bearing_signal, validate_signal_path


class SignalSecurityTests(unittest.TestCase):
    def test_demo_signal_inside_sandbox_runs_without_model(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            root = Path(temp_dir)
            sample_root = root / "data/samples"
            sample_root.mkdir(parents=True)
            sample = sample_root / "test.npy"
            np.save(sample, np.arange(1024, dtype=np.float32))
            settings = Settings.from_env(root)
            settings.ensure_runtime_dirs()
            result = analyze_bearing_signal(sample, settings)
            self.assertEqual(result["mode"], "demo_fixture")
            self.assertEqual(result["signal"]["samples"], 1024)

    def test_path_outside_sandbox_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            root = Path(temp_dir)
            settings = Settings.from_env(root)
            settings.ensure_runtime_dirs()
            outside = root / "outside.npy"
            np.save(outside, np.arange(16, dtype=np.float32))
            with self.assertRaises(SignalValidationError):
                validate_signal_path(outside, settings)

    def test_multidimensional_signal_is_rejected_instead_of_flattened(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            root = Path(temp_dir)
            sample_root = root / "data/samples"
            sample_root.mkdir(parents=True)
            sample = sample_root / "matrix.npy"
            np.save(sample, np.arange(1024, dtype=np.float32).reshape(32, 32))
            settings = Settings.from_env(root)
            settings.ensure_runtime_dirs()

            with self.assertRaisesRegex(SignalValidationError, "one-dimensional"):
                analyze_bearing_signal(sample, settings)

    def test_complex_and_truncated_arrays_are_rejected_before_conversion(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True):
            root = Path(temp_dir)
            sample_root = root / "data/samples"
            sample_root.mkdir(parents=True)
            complex_sample = sample_root / "complex.npy"
            truncated_sample = sample_root / "truncated.npy"
            np.save(complex_sample, np.ones(16, dtype=np.complex64))
            np.save(truncated_sample, np.arange(16, dtype=np.float32))
            truncated_sample.write_bytes(truncated_sample.read_bytes()[:-8])
            settings = Settings.from_env(root)
            settings.ensure_runtime_dirs()

            with self.assertRaisesRegex(SignalValidationError, "real numeric"):
                analyze_bearing_signal(complex_sample, settings)
            with self.assertRaisesRegex(SignalValidationError, "valid non-pickled"):
                analyze_bearing_signal(truncated_sample, settings)


if __name__ == "__main__":
    unittest.main()
