from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "openai_hello.py"


def load_module():
    spec = importlib.util.spec_from_file_location("openai_hello", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OpenAIHelloTests(unittest.TestCase):
    def test_resolve_settings_reads_env_and_normalizes_base_url(self):
        module = load_module()
        parser = module.build_parser()
        args = parser.parse_args([])

        with patch.dict(
            "os.environ",
            {
                "OPENAI_COMPAT_BASE_URL": "https://example.com/v1/",
                "OPENAI_COMPAT_API_KEY": "test-key",
                "OPENAI_COMPAT_MODEL": "gpt-4o-mini",
            },
            clear=False,
        ):
            settings = module.resolve_settings(args)

        self.assertEqual(settings["base_url"], "https://example.com/v1")
        self.assertEqual(settings["api_key"], "test-key")
        self.assertEqual(settings["model"], "gpt-4o-mini")

    def test_pick_default_model_prefers_gpt_entries(self):
        module = load_module()

        selected = module.pick_default_model(
            ["claude-3-5-sonnet", "gpt-4o-mini", "deepseek-chat"]
        )

        self.assertEqual(selected, "gpt-4o-mini")

    def test_pick_default_model_falls_back_to_first_entry(self):
        module = load_module()

        selected = module.pick_default_model(["deepseek-chat", "claude-3-5-sonnet"])

        self.assertEqual(selected, "deepseek-chat")


if __name__ == "__main__":
    unittest.main()
