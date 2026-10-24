import unittest


class Red(unittest.TestCase):
    def test_false(self):
        self.assertEqual(2 + 2, 5)


if __name__ == "__main__":
    unittest.main()
