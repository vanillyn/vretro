import json
import os
from pathlib import Path
from typing import Optional, Tuple

import flet as ft


class ThemeManager:
    def __init__(self) -> None:
        self.theme_mode = "system"
        self.primary_color = None
        self.dynamic_source = None

    def get_theme_mode(self) -> ft.ThemeMode:
        if self.theme_mode == "light":
            return ft.ThemeMode.LIGHT
        elif self.theme_mode == "dark":
            return ft.ThemeMode.DARK
        elif self.theme_mode == "system":
            return self._get_system_theme()
        elif self.theme_mode == "dynamic":
            return self._get_system_theme()
        return ft.ThemeMode.DARK

    def _get_system_theme(self) -> ft.ThemeMode:
        try:
            xresources = self._read_xresources()
            if xresources:
                bg = xresources.get("background", "#000000")
                if self._is_light_color(bg):
                    return ft.ThemeMode.LIGHT
                else:
                    return ft.ThemeMode.DARK
        except Exception:
            pass

        return ft.ThemeMode.DARK

    def _read_xresources(self) -> dict:
        xresources_path = Path.home() / ".Xresources"
        if not xresources_path.exists():
            return {}

        resources = {}
        try:
            with open(xresources_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("!") or line.startswith("#"):
                        continue

                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip().replace("*", "").replace(".", "")
                        value = value.strip()
                        resources[key] = value
        except Exception:
            pass

        return resources

    def _is_light_color(self, hex_color: str) -> bool:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return luminance > 0.5
        return False

    def extract_color_from_image(self, image_path: Path) -> Optional[str]:
        try:
            from PIL import Image

            img = Image.open(image_path)
            img = img.resize((150, 150))
            img = img.convert("RGB")

            pixels = list(img.getdata())

            color_counts = {}
            for pixel in pixels:
                if pixel in color_counts:
                    color_counts[pixel] += 1
                else:
                    color_counts[pixel] = 1

            sorted_colors = sorted(
                color_counts.items(), key=lambda x: x[1], reverse=True
            )

            for color, _ in sorted_colors[:10]:
                r, g, b = color
                if not (
                    (r < 30 and g < 30 and b < 30) or (r > 225 and g > 225 and b > 225)
                ):
                    return f"#{r:02x}{g:02x}{b:02x}"

            if sorted_colors:
                r, g, b = sorted_colors[0][0]
                return f"#{r:02x}{g:02x}{b:02x}"

        except Exception:
            pass

        return None

    def get_primary_color(self) -> Optional[str]:
        if self.theme_mode == "dynamic" and self.dynamic_source:
            if isinstance(self.dynamic_source, Path) and self.dynamic_source.exists():
                color = self.extract_color_from_image(self.dynamic_source)
                if color:
                    return color

        if self.primary_color:
            return self.primary_color

        xresources = self._read_xresources()
        color = xresources.get("color4", None)
        return color

    def set_theme_mode(self, mode: str) -> None:
        if mode in ["light", "dark", "system", "dynamic", "sync"]:
            self.theme_mode = mode

    def set_dynamic_source(self, source: Path) -> None:
        self.dynamic_source = source

    def set_primary_color(self, color: str) -> None:
        self.primary_color = color

    def create_theme(self) -> ft.Theme:
        primary = self.get_primary_color()

        if primary:
            theme = ft.Theme(
                color_scheme_seed=primary,
                use_material3=True,
            )
        else:
            theme = ft.Theme(use_material3=True)

        return theme
