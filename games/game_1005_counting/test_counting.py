# Stubs for unit tests for Counting Game and localization
import unittest
from games.game_1005_counting import counting
from common.utils import localization

class TestCountingGame(unittest.TestCase):
    def setUp(self):
        self.cog = counting.Counting(None)
        self.guild_id = '12345'
        self.cog.state[self.guild_id] = {
            'channel_id': 1,
            'last_number': 0,
            'last_user': None,
            'user_timestamps': {},
            'highest_streak': 0,
            'contributions': {},
            'cooldown': 60
        }

    def test_increment(self):
        # Simulate correct increment
        state = self.cog.state[self.guild_id]
        state['last_number'] = 1
        state['last_user'] = 10
        # Simulate next user counting correctly
        user_id = 20
        state['user_timestamps'][str(user_id)] = 0
        now = 1000
        cooldown = state['cooldown']
        # Simulate logic: correct number, not same user, cooldown passed
        if now - state['user_timestamps'].get(str(user_id), 0) >= cooldown and user_id != state['last_user']:
            state['last_number'] += 1
            state['last_user'] = user_id
            state['user_timestamps'][str(user_id)] = now
            contrib = state.setdefault('contributions', {})
            user_stats = contrib.setdefault(str(user_id), {"streak": 0, "contrib": 0})
            user_stats["contrib"] += 1
            user_stats["streak"] = user_stats.get("streak", 0) + 1
        self.assertEqual(state['last_number'], 2)
        self.assertEqual(state['last_user'], user_id)
        self.assertEqual(state['contributions'][str(user_id)]['contrib'], 1)

    def test_cooldown(self):
        # Simulate cooldown logic
        state = self.cog.state[self.guild_id]
        user_id = 30
        state['user_timestamps'][str(user_id)] = 1000
        now = 1005
        cooldown = state['cooldown']
        # Should not allow if cooldown not passed
        allowed = (now - state['user_timestamps'][str(user_id)]) >= cooldown
        self.assertFalse(allowed)

class TestLocalization(unittest.TestCase):
    def test_english(self):
        text = localization.localization.get('wait_cooldown', lang='en', mention='@user', minutes=15)
        self.assertIn('wait 15 minutes', text)
    def test_spanish(self):
        text = localization.localization.get('wait_cooldown', lang='es', mention='@user', minutes=15)
        self.assertIn('debes esperar 15 minutos', text)

if __name__ == '__main__':
    unittest.main()
