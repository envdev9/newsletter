import unittest


class Ok(unittest.TestCase):
    def test_true(self):
        self.assertEqual(2 + 2, 4)


if __name__ == "__main__":
    unittest.main()
