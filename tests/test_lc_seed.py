"""Seed execution and PNG round-trip checks without model inference."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image, PngImagePlugin

spec = importlib.util.spec_from_file_location("lc_seed_test", Path(__file__).resolve().parents[1] / "lc_seed.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.live = {"nodes": [
            {"id": 3761, "type": "LCSeed", "widgets_values": [-1, "fixed"],
             "widgets_values_named": {"base_seed": -1}},
            {"id": 9, "type": "LCSeed", "widgets_values": [-1]},
        ]}

    def test_random_seed_png_round_trip_and_repeat_queue(self):
        for actual in (2**52 + 123, 2**52 + 456):
            queued = {"workflow": copy.deepcopy(self.live)}
            prompt = {"3761": {"class_type": "LCSeed", "inputs": {"base_seed": -1}},
                      "9": {"class_type": "LCSeed", "inputs": {"base_seed": -1}}}
            with patch.object(seed.random, "randint", return_value=actual):
                result = seed.LCSeed().emit(-1, prompt, queued, "3761")
            self.assertEqual(result["result"], (actual,))
            self.assertEqual(result["ui"]["seed"], [actual])
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("prompt", json.dumps(prompt))
            metadata.add_text("workflow", json.dumps(queued["workflow"]))
            buf = io.BytesIO()
            Image.new("RGB", (1, 1)).save(buf, format="PNG", pnginfo=metadata)
            buf.seek(0)
            with Image.open(buf) as image:
                saved = json.loads(image.info["workflow"])["nodes"][0]
                self.assertEqual(saved["widgets_values"][0], actual)
                self.assertEqual(saved["widgets_values_named"]["base_seed"], actual)
                self.assertEqual(json.loads(image.info["prompt"])["3761"]["inputs"]["base_seed"], actual)
            self.assertEqual(queued["workflow"]["nodes"][1], self.live["nodes"][1])
            self.assertEqual(prompt["9"]["inputs"]["base_seed"], -1)
            self.assertEqual(self.live["nodes"][0]["widgets_values"][0], -1)

    def test_fixed_zero_and_max_seed(self):
        for value in (0, seed.JS_SAFE_MAX):
            with patch.object(seed.random, "randint", side_effect=AssertionError("fixed")):
                self.assertEqual(seed.LCSeed().emit(value)["result"], (value,))
                self.assertEqual(seed.LCSeed.IS_CHANGED(value, {}, {}, "3761"), value)

    def test_missing_optional_metadata_and_legacy_workflow(self):
        self.assertEqual(seed.LCSeed().emit(42, unique_id="missing")["result"], (42,))
        queued = {"workflow": {"nodes": [{"id": 3761, "type": "LCSeed", "widgets_values": [-1]}]}}
        seed.LCSeed().emit(42, {}, queued, 3761)
        self.assertEqual(queued["workflow"]["nodes"][0]["widgets_values"], [42])

    def test_hidden_metadata_contract(self):
        self.assertEqual(seed.LCSeed.INPUT_TYPES()["hidden"], {
            "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO", "unique_id": "UNIQUE_ID"})


if __name__ == "__main__":
    unittest.main()
