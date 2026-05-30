# Copyright (c) 2018, Eugene Gershnik
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE.txt file or at
# https://opensource.org/licenses/BSD-3-Clause

"""Utilities for this module"""

import sys

if sys.version_info >= (3, 14):
    import _colorize  # private stdlib module; API may shift in a future release
else:
    _colorize = None

class WakeOnLanError(Exception):
    """Exception raised when something goes wrong"""
    def __init__(self, message: str):
        super().__init__(message)


def print_warning(message: str) -> None:
    """Print a warning to stderr, colorized like argparse on 3.14+."""
    if _colorize is None or not _colorize.can_colorize(file=sys.stderr):
        print(message, file=sys.stderr)
        return
    theme = _colorize.get_theme().argparse
    # `warning` / `message` keys were added in 3.15 (gh-140695, not backported
    # to 3.14). Fall back to bold red so 3.14 still gets a sensible color.
    warn = getattr(theme, 'warning', '\x1b[1;31m')
    msg = getattr(theme, 'message', '')
    print(f'{warn}warning:{theme.reset} {msg}{message}{theme.reset}',
          file=sys.stderr)
    
def print_error(message: str) -> None:
    """Print an error to stderr, colorized like argparse on 3.14+."""
    if _colorize is None or not _colorize.can_colorize(file=sys.stderr):
        print(message, file=sys.stderr)
        return
    theme = _colorize.get_theme().argparse
    # `error` / `message` keys were added in 3.15 (gh-140695, not backported
    # to 3.14). Fall back to bold magenta to match traceback's convention.
    err = getattr(theme, 'error', '\x1b[1;35m')
    msg = getattr(theme, 'message', '')
    print(f'{err}error:{theme.reset} {msg}{message}{theme.reset}',
          file=sys.stderr)
    
