from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class SignupPolicyTests(unittest.TestCase):
    def test_anonymous_mode_allows_public_signup_when_enabled(self):
        from open_webui.routers.auths import is_signup_allowed

        self.assertTrue(
            is_signup_allowed(
                webui_auth=False,
                has_users=True,
                enable_signup=True,
                enable_login_form=True,
                enable_initial_admin_signup=False,
            )
        )

    def test_anonymous_mode_blocks_public_signup_when_disabled(self):
        from open_webui.routers.auths import is_signup_allowed

        self.assertFalse(
            is_signup_allowed(
                webui_auth=False,
                has_users=True,
                enable_signup=False,
                enable_login_form=True,
                enable_initial_admin_signup=False,
            )
        )

    def test_auth_mode_preserves_existing_signup_gate(self):
        from open_webui.routers.auths import is_signup_allowed

        self.assertFalse(
            is_signup_allowed(
                webui_auth=True,
                has_users=True,
                enable_signup=False,
                enable_login_form=True,
                enable_initial_admin_signup=False,
            )
        )

    def test_anonymous_public_signup_does_not_promote_to_admin(self):
        from open_webui.routers.auths import should_promote_signup_user_to_admin

        self.assertFalse(
            should_promote_signup_user_to_admin(
                webui_auth=False,
                user_email='buyer@example.com',
                total_users=2,
                guest_user_exists=True,
            )
        )

    def test_auth_mode_first_user_can_still_be_promoted_to_admin(self):
        from open_webui.routers.auths import should_promote_signup_user_to_admin

        self.assertTrue(
            should_promote_signup_user_to_admin(
                webui_auth=True,
                user_email='owner@example.com',
                total_users=1,
                guest_user_exists=False,
            )
        )


if __name__ == '__main__':
    unittest.main()
