#!/usr/bin/env python3
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
loader=unittest.TestLoader()
suite=unittest.TestSuite([
    loader.discover(str(ROOT/'tests'),top_level_dir=str(ROOT)),
    loader.discover(str(ROOT/'symulacja'),pattern='test_*.py',top_level_dir=str(ROOT)),
])
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
