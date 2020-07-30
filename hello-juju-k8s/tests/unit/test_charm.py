import unittest

import setuppath  # noqa:F401
from operator_fixtures import OperatorTestCase


class TestCharm(OperatorTestCase):
    def test_create_charm(self):
        """Verify fixtures and create a charm."""
        self.assertEqual(self.charm.state.installed, False)

    def test_install(self):
        """Test emitting an install hook."""
        self.emit("install")
        self.assertEqual(self.charm.state.installed, True)


if __name__ == "__main__":
    unittest.main()
