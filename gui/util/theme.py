import subprocess
from pathlib import Path
from typing import Optional

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
            result = subprocess.run(
                [
                    "kreadconfig6",
                    "--file",
                    "kdeglobals",
                    "--group",
                    "General",
                    "--key",
                    "ColorScheme",
                ],
                capture_output=True,
                text=True,
                timeout=1,
            )

            if result.returncode == 0 and result.stdout.strip():
                scheme = result.stdout.strip().lower()
                if "dark" in scheme:
                    return ft.ThemeMode.DARK
                if "light" in scheme or "breeze" in scheme:
                    return ft.ThemeMode.LIGHT
        except Exception:
            pass

        try:
            xresources = self._read_xresources()
            bg = xresources.get("background") or xresources.get("Background")
            if bg:
                return (
                    ft.ThemeMode.LIGHT
                    if self._is_light_color(bg)
                    else ft.ThemeMode.DARK
                )
        except Exception:
            pass

        return ft.ThemeMode.DARK

    def _read_xresources(self) -> dict:
        resources = {}
        try:
            result = subprocess.run(
                ["xrdb", "-query"], capture_output=True, text=True, timeout=1
            )

            if result.returncode == 0:
                lines = result.stdout.splitlines()
            else:
                x_path = Path.home() / ".Xresources"
                lines = x_path.read_text().splitlines() if x_path.exists() else []

            for line in lines:
                line = line.strip()
                if not line or line.startswith(("!", "#")):
                    continue
                if ":" in line:
                    key, value = line.split(":", 1)
                    clean_key = key.strip().lstrip("*").lstrip(".")
                    resources[clean_key] = value.strip()
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
            import colorsys

            from PIL import Image

            img = Image.open(image_path)
            img = img.resize((150, 150))
            img = img.convert("RGB")

            pixels = list(img.getdata())

            is_light = self.get_theme_mode() == ft.ThemeMode.LIGHT

            color_counts = {}
            for pixel in pixels:
                if pixel in color_counts:
                    color_counts[pixel] += 1
                else:
                    color_counts[pixel] = 1

            sorted_colors = sorted(
                color_counts.items(), key=lambda x: x[1], reverse=True
            )

            for color, _ in sorted_colors[:20]:
                r, g, b = color

                if (r < 30 and g < 30 and b < 30) or (r > 225 and g > 225 and b > 225):
                    continue

                h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

                if s < 0.2:
                    continue

                if is_light:
                    v = max(0.3, min(0.6, v))
                    s = max(0.4, s)
                else:
                    v = max(0.5, min(0.9, v))
                    s = max(0.3, s)

                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

            if sorted_colors:
                r, g, b = sorted_colors[0][0]
                h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

                if is_light:
                    v = 0.5
                    s = 0.6
                else:
                    v = 0.7
                    s = 0.5

                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

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

        try:
            import subprocess

            result = subprocess.run(
                ["kreadconfig6", "--group", "General", "--key", "AccentColor"],
                capture_output=True,
                text=True,
                timeout=1,
            )

            if result.returncode == 0:
                color_values = result.stdout.strip().split(",")
                if len(color_values) >= 3:
                    r, g, b = [int(v) for v in color_values[:3]]
                    return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            pass

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
