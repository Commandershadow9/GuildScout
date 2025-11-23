import unittest
from unittest.mock import Mock
from datetime import datetime, timedelta, timezone

from src.analytics.scorer import Scorer, UserScore

# Mock discord.Member object for tests
class MockMember:
    def __init__(self, id, name, discriminator, joined_at):
        self.id = id
        self.name = name
        self.discriminator = discriminator
        self.joined_at = joined_at
        self.bot = False


class TestScorer(unittest.TestCase):

    def setUp(self):
        """Set up test data for all tests."""
        self.now = datetime.now(timezone.utc)
        self.members = [
            MockMember(id=1, name="UserA", discriminator="0001", joined_at=self.now - timedelta(days=100)),
            MockMember(id=2, name="UserB", discriminator="0002", joined_at=self.now - timedelta(days=50)),
            MockMember(id=3, name="UserC", discriminator="0003", joined_at=self.now - timedelta(days=10)),
            MockMember(id=4, name="UserD", discriminator="0004", joined_at=self.now - timedelta(days=0)),
        ]
        self.message_counts = {
            1: 200,  # UserA
            2: 100,  # UserB
            3: 0,    # UserC
            4: 50,   # UserD
        }
        self.scorer = Scorer(weight_days=0.4, weight_messages=0.6)

    def test_basic_score_calculation(self):
        """Test the basic score calculation with multiple users."""
        scores = self.scorer.calculate_scores(self.members, self.message_counts)
        
        # max_days = 100, max_messages = 200
        
        # UserA:
        # days_score = (100 / 100) * 100 = 100
        # activity_score = (200 / 200) * 100 = 100
        # final_score = (100 * 0.4) + (100 * 0.6) = 40 + 60 = 100
        user_a_score = next(s for s in scores if s.user_id == 1)
        self.assertEqual(user_a_score.final_score, 100.0)
        self.assertEqual(user_a_score.days_in_server, 100)
        self.assertEqual(user_a_score.message_count, 200)

        # UserB:
        # days_score = (50 / 100) * 100 = 50
        # activity_score = (100 / 200) * 100 = 50
        # final_score = (50 * 0.4) + (50 * 0.6) = 20 + 30 = 50
        user_b_score = next(s for s in scores if s.user_id == 2)
        self.assertEqual(user_b_score.final_score, 50.0)

    def test_zero_message_user(self):
        """Test a user with zero messages."""
        scores = self.scorer.calculate_scores(self.members, self.message_counts)
        
        # UserC:
        # days_score = (10 / 100) * 100 = 10
        # activity_score = (0 / 200) * 100 = 0
        # final_score = (10 * 0.4) + (0 * 0.6) = 4.0
        user_c_score = next(s for s in scores if s.user_id == 3)
        self.assertEqual(user_c_score.final_score, 4.0)
        self.assertEqual(user_c_score.activity_score, 0)

    def test_new_user(self):
        """Test a user who just joined (0 days)."""
        scores = self.scorer.calculate_scores(self.members, self.message_counts)
        
        # UserD:
        # days_score = (0 / 100) * 100 = 0
        # activity_score = (50 / 200) * 100 = 25
        # final_score = (0 * 0.4) + (25 * 0.6) = 15.0
        user_d_score = next(s for s in scores if s.user_id == 4)
        self.assertEqual(user_d_score.final_score, 15.0)
        self.assertEqual(user_d_score.days_score, 0)

    def test_single_user_scenario(self):
        """Test with only one user to avoid division by zero."""
        single_member = [self.members[0]]
        single_counts = {1: 200}
        scores = self.scorer.calculate_scores(single_member, single_counts)
        
        # With one user, they should be max in all categories
        # days_score = (100 / 100) * 100 = 100
        # activity_score = (200 / 200) * 100 = 100
        # final_score = (100 * 0.4) + (100 * 0.6) = 100
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].final_score, 100.0)

    def test_all_zero_scenario(self):
        """Test a scenario where max days and max messages are zero."""
        member = MockMember(id=1, name="UserE", discriminator="0005", joined_at=self.now)
        counts = {1: 0}
        scores = self.scorer.calculate_scores([member], counts)
        
        # max_days and max_messages will be 0, but the scorer should handle this
        # by setting them to 1 internally to avoid division by zero.
        # days_score = (0 / 1) * 100 = 0
        # activity_score = (0 / 1) * 100 = 0
        # final_score = 0
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].final_score, 0.0)

    def test_weight_normalization(self):
        """Test that weights are normalized if they don't sum to 1.0."""
        # Weights are 1 and 1, should be normalized to 0.5 and 0.5
        scorer = Scorer(weight_days=1.0, weight_messages=1.0)
        self.assertAlmostEqual(scorer.weight_days, 0.5)
        self.assertAlmostEqual(scorer.weight_messages, 0.5)
        
        scores = scorer.calculate_scores(self.members, self.message_counts)

        # UserB with normalized weights:
        # days_score = 50
        # activity_score = 50
        # final_score = (50 * 0.5) + (50 * 0.5) = 25 + 25 = 50
        user_b_score = next(s for s in scores if s.user_id == 2)
        self.assertEqual(user_b_score.final_score, 50.0)


if __name__ == '__main__':
    unittest.main()
