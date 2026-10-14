from pathlib import Path
import tempfile
import unittest

from things_cloud.credentials import read_credentials
from things_cloud.errors import ThingsError


class CredentialTests(unittest.TestCase):
    def file(self, directory, content, mode=0o600):
        path = Path(directory) / ".env"
        path.write_text(content)
        path.chmod(mode)
        return path

    def test_explicit_file_supports_username_password_and_quotes_without_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.file(directory, "USERNAME=\"user@example.com\"\nPASSWORD='literal$(echo bad)#part'\n")
            username, password = read_credentials(path)
            self.assertEqual(username, "user@example.com")
            self.assertEqual(password, "literal$(echo bad)#part")

    def test_things_prefixed_names_and_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.file(directory, "# comment\nexport THINGS_USERNAME=user@example.com\nTHINGS_PASSWORD=secret # ignored\n")
            self.assertEqual(read_credentials(path), ("user@example.com", "secret"))

    def test_invalid_files_fail_without_exposing_values(self):
        for content in (
            "PASSWORD=sensitive\n",
            'USERNAME=x\nPASSWORD="sensitive\n',
            "USERNAME=x\nPASSWORD=sensitive\nPASSWORD=sensitive\n",
        ):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ThingsError) as error:
                    read_credentials(self.file(directory, content))
                self.assertNotIn("sensitive", str(error.exception))

    def test_file_permissions_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.file(directory, "USERNAME=x\nPASSWORD=sensitive\n", 0o644)
            with self.assertRaises(ThingsError):
                read_credentials(path)
            path.chmod(0o600)
            link = Path(directory) / "link.env"
            link.symlink_to(path)
            with self.assertRaises(ThingsError):
                read_credentials(link)


if __name__ == "__main__":
    unittest.main()
