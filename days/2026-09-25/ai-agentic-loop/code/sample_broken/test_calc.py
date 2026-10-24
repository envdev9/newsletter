import unittest


class CalcTests(unittest.TestCase):
    def test_add(self):
        # celowo czerwony test - agent "zapomnial" go naprawic
        self.assertEqual(2 + 2, 5)


if __name__ == "__main__":
    unittest.main()
