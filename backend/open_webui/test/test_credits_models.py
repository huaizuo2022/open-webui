from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class CreditModelsTests(unittest.TestCase):
    def test_credit_account_defaults(self):
        from open_webui.models.credits import CreditAccountForm

        form = CreditAccountForm(user_id='u1')

        self.assertEqual(form.balance, 0)
        self.assertEqual(form.total_recharged, 0)
        self.assertEqual(form.total_consumed, 0)

    def test_redeem_batch_requires_positive_quantity(self):
        from open_webui.models.credits import RedeemCodeBatchForm

        with self.assertRaises(ValueError):
            RedeemCodeBatchForm(batch_name='tb-001', credit_amount=100, quantity=0)

    def test_usage_quota_subject_enum_values(self):
        from open_webui.models.credits import UsageQuotaSubject

        self.assertEqual(UsageQuotaSubject.USER.value, 'user')
        self.assertEqual(UsageQuotaSubject.DEVICE.value, 'device')

    def test_table_names(self):
        from open_webui.models.credits import CreditAccount, RedeemCode, UsageQuota

        self.assertEqual(CreditAccount.__tablename__, 'credit_account')
        self.assertEqual(RedeemCode.__tablename__, 'redeem_code')
        self.assertEqual(UsageQuota.__tablename__, 'usage_quota')


if __name__ == '__main__':
    unittest.main()
