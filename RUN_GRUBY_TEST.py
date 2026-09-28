#!/usr/bin/env python3
"""Uruchom BARDZO GRUBY TEST REFRESHERA V3.86.7"""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent / "zip_content"
sys.path.insert(0, str(ROOT))
# Load fake tkinter if needed
try:
    import tkinter
except ModuleNotFoundError:
    sys.path.insert(0, str(ROOT))
    import fake_tk

import unittest
loader = unittest.TestLoader()
suite = unittest.TestSuite([
    loader.discover(str(ROOT/'tests'), top_level_dir=str(ROOT)),
    loader.discover(str(ROOT/'symulacja'), pattern='test_*.py', top_level_dir=str(ROOT)),
])
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
print(f"\n=== GRUBY TEST SUMMARY ===")
print(f"Tests: {result.testsRun}, Failures: {len(result.failures)}, Errors: {len(result.errors)}, Skipped: {len(result.skipped)}")
sys.exit(0 if result.wasSuccessful() else 1)
