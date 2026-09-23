"""Shared delayed-start CLI handling for OCR and translation."""

import math
import re
import time


DELAY_HELP = (
    "Delayed start: --30 waits 30 minutes; --3h12m waits 3 hours 12 minutes. "
    "Also accepts --3h or --12m. Use at most one delay. Ctrl+C cancels."
)


def parse_delay_args(parser, argv=None):
    """Keep ordinary argparse validation while accepting duration-only options."""
    parser.epilog = "\n".join(filter(None, (parser.epilog, DELAY_HELP)))
    args, unknown = parser.parse_known_args(argv)
    delay = None
    for token in unknown:
        match = re.fullmatch(r"--(?:(\d+)|(?:(\d+)h)?(?:(\d+)m)?)", token)
        if not match or not any(part is not None for part in match.groups()):
            parser.error(f"unrecognized argument: {token}; {DELAY_HELP}")
        if delay is not None:
            parser.error("Specify only one delayed-start argument.")
        minutes, hours, extra_minutes = match.groups()
        delay = (int(minutes) * 60 if minutes is not None else
                 int(hours or 0) * 3600 + int(extra_minutes or 0) * 60)
    args.start_delay_seconds = delay or 0
    return args


def wait_for_start(seconds):
    """Wait once before processing; elapsed wall time includes computer sleep."""
    if not seconds:
        return
    deadline = time.time() + seconds
    try:
        while True:
            remaining = max(0, math.ceil(deadline - time.time()))
            hours, tail = divmod(remaining, 3600)
            minutes, secs = divmod(tail, 60)
            print(f"\r[WAITING] Starts in {hours:02d}:{minutes:02d}:{secs:02d} "
                  "(Ctrl+C to cancel)   ", end="", flush=True)
            if remaining == 0:
                break
            time.sleep(min(1, remaining))
    except KeyboardInterrupt:
        print("\n[CANCELLED] Delayed start cancelled.", flush=True)
        raise SystemExit(130)
    print("\n[START] Countdown complete; starting now.", flush=True)
