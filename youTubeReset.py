
"""Compatibility entry point for the original script name.

The original script deleted every retrieved subscription immediately. This now
delegates to a safe CLI whose default behavior is read-only.
"""

from youtube_cleanup.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
