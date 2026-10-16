"""Compatibility shim: the Step 10 story-quality checker now lives in tutor_core.quality (M6), so the web API and
Langflow can import it. Everything is re-exported unchanged, so `from vocab_adherence import ...` in the
measurement scripts and in tests/test_vocab_adherence.py works as before, and the CLI still runs:

    python scripts/vocab_adherence.py passages.txt --words "hello, water, friend"
"""
import sys

from tutor_core import quality as _quality
from tutor_core.quality import *  # noqa: F401,F403
from tutor_core.quality import main  # noqa: F401

# `import *` skips underscore names; copy every remaining module-level name so nothing that worked before is lost.
globals().update({k: v for k, v in vars(_quality).items() if not k.startswith("__") and k not in globals()})

if __name__ == "__main__":
    sys.exit(main())
