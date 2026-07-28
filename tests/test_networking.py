from __future__ import annotations

import socket
import unittest

from equipdoc_agent.networking import find_available_port


class PortSelectionTests(unittest.TestCase):
    def test_skips_an_occupied_port(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            occupied_port = listener.getsockname()[1]

            selected_port = find_available_port(
                "127.0.0.1", occupied_port, max_attempts=20
            )

        self.assertGreater(selected_port, occupied_port)
        self.assertLessEqual(selected_port, occupied_port + 19)

    def test_rejects_invalid_port(self) -> None:
        with self.assertRaises(ValueError):
            find_available_port("127.0.0.1", 0)


if __name__ == "__main__":
    unittest.main()
