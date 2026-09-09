import argparse
import unittest
from unittest.mock import Mock, patch

from youtube_cleanup.cli import _unsubscribe
from youtube_cleanup.models import Classification


def candidate():
    return Classification("sub-1", "Noise Channel", 10, "Drama / Ragebait", "UNSUBSCRIBE_CANDIDATE", "Repeated negative signals.")


class UnsubscribeSafetyTests(unittest.TestCase):
    def test_dry_run_never_calls_api(self):
        client = Mock()
        args = argparse.Namespace(all_candidates=True, ids=[], select=[], dry_run=True)
        self.assertEqual(_unsubscribe(client, [candidate()], args), 0)
        client.unsubscribe.assert_not_called()

    @patch("builtins.input", return_value="")
    def test_default_confirmation_is_no(self, _input):
        client = Mock()
        args = argparse.Namespace(all_candidates=True, ids=[], select=[], dry_run=False)
        self.assertEqual(_unsubscribe(client, [candidate()], args), 0)
        client.unsubscribe.assert_not_called()

    @patch("builtins.input", return_value="y")
    def test_exact_yes_executes_selected_item(self, _input):
        client = Mock()
        args = argparse.Namespace(all_candidates=False, ids=["sub-1"], select=[], dry_run=False)
        self.assertEqual(_unsubscribe(client, [candidate()], args), 0)
        client.unsubscribe.assert_called_once_with("sub-1")

    def test_displayed_row_can_be_selected(self):
        client = Mock()
        args = argparse.Namespace(all_candidates=False, ids=[], select=[1], dry_run=True)
        self.assertEqual(_unsubscribe(client, [candidate()], args), 0)
        client.unsubscribe.assert_not_called()

    def test_invalid_row_aborts_entire_operation(self):
        client = Mock()
        args = argparse.Namespace(all_candidates=False, ids=[], select=[2], dry_run=False)
        self.assertEqual(_unsubscribe(client, [candidate()], args), 2)
        client.unsubscribe.assert_not_called()

    def test_configured_ids_build_selection(self):
        client = Mock()
        args = argparse.Namespace(all_candidates=False, ids=[], select=[], from_config=True, dry_run=True)
        config = {"unsubscribe_subscription_ids": ["sub-1"]}
        self.assertEqual(_unsubscribe(client, [candidate()], args, config), 0)
        client.unsubscribe.assert_not_called()

    def test_stale_configured_id_aborts(self):
        client = Mock()
        args = argparse.Namespace(all_candidates=False, ids=[], select=[], from_config=True, dry_run=True)
        config = {"unsubscribe_subscription_ids": ["missing"]}
        self.assertEqual(_unsubscribe(client, [candidate()], args, config), 2)
        client.unsubscribe.assert_not_called()
