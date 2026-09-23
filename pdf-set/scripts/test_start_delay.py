import argparse
import builtins
import contextlib
import io
import os
import sys
import unittest
from unittest.mock import patch

from start_delay import parse_delay_args, wait_for_start


class DelayTests(unittest.TestCase):
    def parse(self, argv):
        parser = argparse.ArgumentParser()
        parser.add_argument('--book-name', nargs='+')
        parser.add_argument('--only', action='store_true')
        parser.add_argument('--batch', type=int)
        return parse_delay_args(parser, argv)

    def test_durations_and_existing_options(self):
        for flag, seconds in [('--30', 1800), ('--3h12m', 11520),
                              ('--3h', 10800), ('--12m', 720), ('--0', 0)]:
            with self.subTest(flag=flag):
                args = self.parse(['--book-name', 'Book A', 'Book B', flag,
                                   '--only', '--batch', '2'])
                self.assertEqual(args.start_delay_seconds, seconds)
                self.assertEqual(args.book_name, ['Book A', 'Book B'])
                self.assertTrue(args.only)
                self.assertEqual(args.batch, 2)
        self.assertEqual(self.parse([]).start_delay_seconds, 0)

    def test_reject_invalid_or_multiple_delays(self):
        for argv in [['--3x'], ['--hm'], ['--1.5'], ['--1m2h'],
                     ['--30', '--2h'], ['--0', '--0'], ['--batch', 'bad']]:
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    self.parse(argv)
                self.assertEqual(exc.exception.code, 2)

    def test_countdown_and_cancellation(self):
        output = io.StringIO()
        with patch('start_delay.time.time', side_effect=[100, 100, 101, 102]), \
                patch('start_delay.time.sleep') as sleep, contextlib.redirect_stdout(output):
            wait_for_start(2)
        self.assertEqual(sleep.call_count, 2)
        self.assertIn('00:00:02', output.getvalue())
        self.assertIn('[START]', output.getvalue())
        with patch('start_delay.time.sleep', side_effect=KeyboardInterrupt), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as exc:
                wait_for_start(60)
            self.assertEqual(exc.exception.code, 130)

    def test_both_entrypoints_wait_before_processing(self):
        # Import with a harmless in-memory config so this test runs in a clean
        # checkout without a user's private API credentials.
        real_isfile = os.path.isfile
        real_open = builtins.open
        config = 'base_url = "https://example.invalid/v1"\napi_key = "test-only"\nmodel = "test-model"\n'

        def test_isfile(path):
            return str(path).endswith('secrets_openai.txt') or real_isfile(path)

        def test_open(path, *args, **kwargs):
            if str(path).endswith('secrets_openai.txt'):
                return io.StringIO(config)
            return real_open(path, *args, **kwargs)

        with patch('os.path.isfile', side_effect=test_isfile), \
                patch('builtins.open', side_effect=test_open):
            import ocr
            import fasttrans

        for module in (ocr, fasttrans):
            with self.subTest(module=module.__name__), \
                    patch.object(sys, 'argv', [module.__file__, '--book-name', 'Test', '--3h12m']), \
                    patch.object(module, 'wait_for_start', side_effect=SystemExit(130)) as wait, \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    module.main()
                wait.assert_called_once_with(11520)


if __name__ == '__main__':
    unittest.main()
