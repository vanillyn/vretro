#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import flet as ft

from gui.app import VRetroApp


def main(page: ft.Page) -> None:
    VRetroApp(page)


if __name__ == "__main__":
    ft.run(main)
