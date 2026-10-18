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
            source_folder="hotro@phongdinh.info.vn",
            source_role=FolderRole.CUSTOM,
            source_delim="/",
            dest_delim=".",
            dest_canonical_map=dest_canonical,
            dest_prefix="INBOX.",
        )
        self.assertEqual(target, "INBOX.hotro@phongdinh_info_vn")

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
        mock_client.create_folder.assert_called_with("INBOX.Quan trọng")


if __name__ == "__main__":
    unittest.main()
