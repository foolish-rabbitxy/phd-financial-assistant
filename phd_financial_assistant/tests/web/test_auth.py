import unittest

from src.web import auth


class PasswordTest(unittest.TestCase):
    def test_hash_and_verify(self):
        h = auth.hash_password("hunter2", iterations=1000)
        self.assertTrue(h.startswith("pbkdf2_sha256$1000$"))
        self.assertTrue(auth.verify_password("hunter2", h))
        self.assertFalse(auth.verify_password("hunter3", h))
        self.assertFalse(auth.verify_password("x", "garbage"))


class SessionsTest(unittest.TestCase):
    def setUp(self):
        self.s = auth.Sessions(auth.hash_password("pw", iterations=1000), ttl=100)

    def test_login_creates_session_with_csrf(self):
        tok = self.s.login("pw", now=0)
        self.assertIsNotNone(tok)
        sess = self.s.get(tok, now=50)
        self.assertEqual(len(sess.csrf), 64)
        self.assertIsNone(self.s.get(tok, now=101))
        self.assertIsNone(self.s.get("nope", now=1))

    def test_wrong_password_and_lockout(self):
        for i in range(5):
            self.assertIsNone(self.s.login("bad", now=i))
        self.assertTrue(self.s.locked(now=10))
        self.assertIsNone(self.s.login("pw", now=10))  # locked even with right pw
        self.assertFalse(self.s.locked(now=70))
        self.assertIsNotNone(self.s.login("pw", now=70))

    def test_logout(self):
        tok = self.s.login("pw", now=0)
        self.s.logout(tok)
        self.assertIsNone(self.s.get(tok, now=1))


class PasswordChangeTest(unittest.TestCase):
    def test_set_password_keeps_only_current_session(self):
        s = auth.Sessions(auth.hash_password("old-pass1", iterations=1000))
        mine, other = s.login("old-pass1", now=0), s.login("old-pass1", now=0)
        s.set_password(auth.hash_password("new-pass1", iterations=1000), keep=mine)
        self.assertIsNotNone(s.get(mine, now=1))
        self.assertIsNone(s.get(other, now=1))
        self.assertIsNone(s.login("old-pass1", now=2))
        self.assertIsNotNone(s.login("new-pass1", now=3))

    def test_password_problem(self):
        self.assertIsNone(auth.password_problem("longenough", "longenough"))
        self.assertIn("match", auth.password_problem("longenough", "different"))
        self.assertIn("8", auth.password_problem("short", "short"))


class ResetTokensTest(unittest.TestCase):
    def test_one_time_and_expiry(self):
        r = auth.ResetTokens()
        tok = r.issue(now=0)
        self.assertTrue(r.valid(tok, now=10))
        self.assertTrue(r.consume(tok, now=10))
        self.assertFalse(r.consume(tok, now=11))  # already used
        tok2 = r.issue(now=auth.RESET_EMAIL_INTERVAL_S)
        self.assertFalse(r.consume(tok2, now=auth.RESET_EMAIL_INTERVAL_S + auth.RESET_TTL_S))  # expired
        self.assertFalse(r.valid("made-up", now=1))

    def test_rate_limit_and_new_link_voids_old(self):
        r = auth.ResetTokens()
        first = r.issue(now=0)
        self.assertIsNone(r.issue(now=60))
        second = r.issue(now=auth.RESET_EMAIL_INTERVAL_S)
        self.assertFalse(r.valid(first, now=auth.RESET_EMAIL_INTERVAL_S + 1))
        self.assertTrue(r.valid(second, now=auth.RESET_EMAIL_INTERVAL_S + 1))


if __name__ == "__main__":
    unittest.main()
