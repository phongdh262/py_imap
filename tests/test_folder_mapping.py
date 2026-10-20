import unittest
from unittest.mock import MagicMock
from src.core.folder_mapper import FolderMapper
from src.core.models import FolderRole
from src.core.migrator import EmailMigrator


class TestFolderMappingAndNamespace(unittest.TestCase):
    def setUp(self):
        self.mapper = FolderMapper()

    def test_gmail_important_mapping_with_inbox_prefix(self):
        dest_canonical = {FolderRole.SENT: "INBOX.Sent"}
        target = self.mapper.map_folder_name(
            source_folder="[Gmail]/Quan trọng",
            source_role=FolderRole.CUSTOM,
            source_delim="/",
            dest_delim=".",
            dest_canonical_map=dest_canonical,
            dest_prefix="INBOX.",
        )
        self.assertEqual(target, "INBOX.Quan trọng")

    def test_custom_email_folder_dots_escape(self):
        dest_canonical = {FolderRole.SENT: "INBOX.Sent"}
        target = self.mapper.map_folder_name(
            source_folder="hotro@company.com",
            source_role=FolderRole.CUSTOM,
            source_delim="/",
            dest_delim=".",
            dest_canonical_map=dest_canonical,
            dest_prefix="INBOX.",
        )
        self.assertEqual(target, "INBOX.hotro@company_com")

    def test_canonical_role_mapping(self):
        dest_canonical = {FolderRole.SENT: "INBOX.Sent"}
        target = self.mapper.map_folder_name(
            source_folder="[Gmail]/Thư đã gửi",
            source_role=FolderRole.SENT,
            source_delim="/",
            dest_delim=".",
            dest_canonical_map=dest_canonical,
            dest_prefix="INBOX.",
        )
        self.assertEqual(target, "INBOX.Sent")

    def test_migrator_ensure_dest_folder_self_healing(self):
        migrator = EmailMigrator()
        mock_client = MagicMock()

        # Simulate Dovecot failure when folder lacks INBOX. prefix
        def side_effect_create(folder_name):
            if not folder_name.startswith("INBOX."):
                raise Exception("Client tried to access nonexistent namespace. (Mailbox name should probably be prefixed with: INBOX.)")
            return True

        mock_client.folder_exists.return_value = False
        mock_client.create_folder.side_effect = side_effect_create

        res_folder = migrator._ensure_dest_folder(mock_client, "Quan trọng")
        self.assertEqual(res_folder, "INBOX.Quan trọng")
    def test_provider_detection_and_exclusion(self):
        from src.core.provider_rules import ProviderRulesManager

        rules_mgr = ProviderRulesManager()
        self.assertEqual(rules_mgr.detect_provider("imap.gmail.com", "user@gmail.com"), "gmail")
        self.assertEqual(rules_mgr.detect_provider("outlook.office365.com", "user@company.com"), "outlook")
        self.assertEqual(rules_mgr.detect_provider("mail.domain.vn", "contact@domain.vn"), "cpanel")
        self.assertEqual(rules_mgr.detect_provider("imap.yandex.com", "user@yandex.com"), "yandex")

        gmail_mapper = FolderMapper(source_provider="gmail", rules_manager=rules_mgr)
        self.assertTrue(gmail_mapper.is_excluded("[Gmail]/All Mail", FolderRole.ARCHIVE))
        self.assertTrue(gmail_mapper.is_excluded("[Gmail]/Tất cả thư", FolderRole.ARCHIVE))
        self.assertTrue(gmail_mapper.is_excluded("[Gmail]/Spam", FolderRole.JUNK))
        self.assertFalse(gmail_mapper.is_excluded("INBOX", FolderRole.INBOX))
        self.assertFalse(gmail_mapper.is_excluded("[Gmail]/Quan trọng", FolderRole.CUSTOM))


if __name__ == "__main__":
    unittest.main()
