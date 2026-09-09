import tempfile
import unittest
from pathlib import Path

from youtube_cleanup.classifier import classify_subscription, classify_watch_later, suggest_playlist
from youtube_cleanup.models import Subscription, Video
from youtube_cleanup.overrides import load_overrides, save_channel_override


def subscription(name, titles, channel_id="channel", description=""):
    return Subscription("sub", channel_id, name, description, tuple(titles))


class SubscriptionClassifierTests(unittest.TestCase):
    def test_cybersecurity_channel_scores_highly(self):
        result = classify_subscription(subscription("Blue Team Labs", ["Build a home SOC lab", "Linux malware analysis", "Network security CTF"] * 2))
        self.assertEqual(result.recommendation, "KEEP_HIGH_VALUE")
        self.assertGreaterEqual(result.score, 75)

    def test_anime_is_intentional_entertainment(self):
        result = classify_subscription(subscription("Anime Weekly", ["Anime season impressions", "Best manga adaptations", "New anime review"]))
        self.assertEqual(result.recommendation, "KEEP_ENTERTAINMENT")

    def test_gaming_is_not_useless(self):
        result = classify_subscription(subscription("Game Room", ["Gaming retrospective", "Video game playthrough", "Relaxing gameplay"], description="gaming"))
        self.assertEqual(result.recommendation, "KEEP_ENTERTAINMENT")

    def test_relationship_arguments_are_unsubscribe_candidate(self):
        titles = ["Men vs women dating advice", "Dating app relationship advice", "Breakup relationship podcast", "Men vs women again"]
        self.assertEqual(classify_subscription(subscription("Dating Debate", titles)).recommendation, "UNSUBSCRIBE_CANDIDATE")

    def test_drama_ragebait_is_low_value(self):
        titles = ["Celebrity drama exposed", "Influencer drama meltdown", "Outrage reaction clip"]
        self.assertIn(classify_subscription(subscription("Drama Clips", titles)).recommendation, {"LOW_VALUE", "UNSUBSCRIBE_CANDIDATE"})

    def test_teaching_beats_career_anxiety(self):
        teaching = classify_subscription(subscription("Software Skills", ["Python tutorial", "Postgres database tutorial", "Docker backend project", "SQL system design"]))
        panic = classify_subscription(subscription("Tech Panic", ["Software engineering is dead", "AI replacing developers", "Tech layoffs", "Layoff panic"] * 2))
        self.assertGreater(teaching.score, panic.score)
        self.assertEqual(panic.recommendation, "UNSUBSCRIBE_CANDIDATE")

    def test_consumerism_is_review_or_lower(self):
        result = classify_subscription(subscription("Buy More", ["Luxury haul", "Shopping haul", "Amazon finds you need this"]))
        self.assertIn(result.recommendation, {"LOW_VALUE", "UNSUBSCRIBE_CANDIDATE"})

    def test_mixed_signals_are_explained_and_reviewed(self):
        result = classify_subscription(subscription("Mixed", ["Python tutorial", "Dating advice hot take"]))
        self.assertEqual(result.recommendation, "REVIEW")
        self.assertIn("mixed", result.reason)

    def test_override_wins(self):
        item = subscription("Dating Debate", ["Men vs women dating advice"] * 6, "protected")
        self.assertEqual(classify_subscription(item, {"channels": {"protected": "always_keep"}}).recommendation, "KEEP_HIGH_VALUE")

    def test_override_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overrides.json"
            save_channel_override(path, "abc", "entertainment")
            self.assertEqual(load_overrides(path)["channels"]["abc"], "entertainment")


class WatchLaterClassifierTests(unittest.TestCase):
    def test_postgres_tutorial_moves_to_database_playlist(self):
        result = classify_watch_later(Video("v", "PostgreSQL database query planning tutorial"), ["Databases / SQL", "Fitness"])
        self.assertEqual(result.recommendation, "MOVE_TO_PLAYLIST")
        self.assertEqual(result.destination, "Databases / SQL")

    def test_fitness_tutorial_moves_to_fitness_playlist(self):
        result = classify_watch_later(Video("v", "Strength training mobility tutorial"), ["Fitness Guides"])
        self.assertEqual(result.destination, "Fitness Guides")

    def test_ragebait_is_removed(self):
        self.assertEqual(classify_watch_later(Video("v", "Celebrity drama exposed: outrage meltdown")).recommendation, "REMOVE_FROM_WATCH_LATER")

    def test_anime_and_gaming_are_watch_soon(self):
        for title in ("New anime season impressions", "Relaxing gaming gameplay"):
            self.assertEqual(classify_watch_later(Video("v", title)).recommendation, "WATCH_SOON")

    def test_playlist_override(self):
        result = suggest_playlist("Technical Learning", [], {"playlist_destinations": {"Technical Learning": "My Tech"}})
        self.assertEqual(result, "My Tech")


if __name__ == "__main__":
    unittest.main()
