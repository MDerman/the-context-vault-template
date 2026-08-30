from __future__ import annotations

import importlib.util
import io
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parents[2] / "bootstrap/offer_machine_setup.py"
SPEC = importlib.util.spec_from_file_location("offer_machine_setup", SCRIPT)
assert SPEC and SPEC.loader
offer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(offer)


class OfferMachineSetupTests(unittest.TestCase):
    def run_offer(self, answer: str, *, non_interactive: bool = False):
        output = io.StringIO()
        calls: list[list[str]] = []

        def runner(command: list[str]) -> int:
            calls.append(command)
            return 0

        result = offer.offer_machine_setup(
            vault_command="/tmp/vault",
            input_stream=io.StringIO(answer),
            output_stream=output,
            non_interactive=non_interactive,
            dry_run=False,
            runner=runner,
        )
        return result, output.getvalue(), calls

    def test_yes_launches_machine_setup(self):
        result, _, calls = self.run_offer("yes\n")
        self.assertEqual(result, 0)
        self.assertEqual(calls, [["/tmp/vault", "machine", "setup"]])

    def test_no_defers_successfully(self):
        result, output, calls = self.run_offer("n\n")
        self.assertEqual(result, 0)
        self.assertEqual(calls, [])
        self.assertIn("vault machine setup", output)

    def test_eof_defaults_to_no(self):
        result, _, calls = self.run_offer("")
        self.assertEqual(result, 0)
        self.assertEqual(calls, [])

    def test_non_interactive_never_reads_or_launches(self):
        result, output, calls = self.run_offer("yes\n", non_interactive=True)
        self.assertEqual(result, 0)
        self.assertEqual(calls, [])
        self.assertIn("non-interactive", output)


if __name__ == "__main__":
    unittest.main()
