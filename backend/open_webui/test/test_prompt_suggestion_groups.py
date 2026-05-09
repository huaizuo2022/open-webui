from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class PromptSuggestionGroupTests(unittest.TestCase):
    def test_default_grouped_prompt_suggestions_shape(self):
        from open_webui.config import DEFAULT_PROMPT_SUGGESTION_GROUPS

        groups = DEFAULT_PROMPT_SUGGESTION_GROUPS.value

        self.assertIsInstance(groups, list)
        self.assertGreaterEqual(len(groups), 4)

        for group in groups:
            self.assertIn("id", group)
            self.assertIn("label", group)
            self.assertIn("prompts", group)
            self.assertIsInstance(group["prompts"], list)
            self.assertGreaterEqual(len(group["prompts"]), 3)

            for prompt in group["prompts"]:
                self.assertIn("content", prompt)
                self.assertIn("title", prompt)
                self.assertEqual(len(prompt["title"]), 2)


if __name__ == "__main__":
    unittest.main()
