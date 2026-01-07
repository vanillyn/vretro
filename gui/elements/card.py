from pathlib import Path
from typing import Callable, Optional

import flet as ft


class GameCard:
    def __init__(
        self,
        game,
        on_click: Callable,
        show_console: bool = False,
    ):
        self.game = game
        self.on_click = on_click
        self.show_console = show_console
        self.is_hovered = False

    def create(self) -> ft.Container:
        graphics_dir = self.game.path / "graphics"
        grid_path = graphics_dir / "grid.png"

        if not grid_path.exists():
            grid_path = self.game.path / "assets" / "grid.png"

        if grid_path.exists():
            image = ft.Image(
                src=str(grid_path),
                fit=ft.BoxFit.COVER,
                border_radius=12,
            )
            overlay_needed = False
        else:
            thumb_path = self.game.get_thumbnail_path()
            if thumb_path and thumb_path.exists():
                image = ft.Image(
                    src=str(thumb_path),
                    fit=ft.BoxFit.COVER,
                    border_radius=12,
                )
                overlay_needed = True
            else:
                image = ft.Container(
                    content=ft.Icon(
                        ft.Icons.VIDEOGAME_ASSET,
                        size=64,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=12,
                    alignment=ft.Alignment.CENTER,
                )
                overlay_needed = False

        title_text = ft.Text(
            self.game.metadata.get_title(),
            size=14,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.WHITE if overlay_needed else None,
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        info_widgets = []

        if self.show_console:
            info_widgets.append(
                ft.Text(
                    self.game.metadata.console,
                    size=11,
                    color=ft.Colors.WHITE
                    if overlay_needed
                    else ft.Colors.ON_SURFACE_VARIANT,
                )
            )

        if self.game.metadata.year:
            info_widgets.append(
                ft.Text(
                    str(self.game.metadata.year),
                    size=11,
                    color=ft.Colors.WHITE
                    if overlay_needed
                    else ft.Colors.ON_SURFACE_VARIANT,
                )
            )

        info_row = (
            ft.Row(
                info_widgets,
                spacing=8,
            )
            if info_widgets
            else None
        )

        overlay = ft.Container(
            content=ft.Column(
                [
                    ft.Container(expand=True),
                    title_text,
                    info_row if info_row else ft.Container(),
                ],
                spacing=4,
            ),
            padding=15,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_CENTER,
                end=ft.Alignment.BOTTOM_CENTER,
                colors=["#00000000", "#000000DD"],
            )
            if overlay_needed
            else None,
            border_radius=12,
        )

        card_content = (
            ft.Stack(
                [
                    image,
                    overlay,
                ]
            )
            if overlay_needed
            else ft.Column(
                [
                    image,
                    ft.Container(
                        content=ft.Column(
                            [
                                title_text,
                                info_row if info_row else ft.Container(),
                            ],
                            spacing=4,
                        ),
                        padding=10,
                    ),
                ],
                spacing=0,
            )
        )

        return ft.Container(
            content=card_content,
            border_radius=12,
            ink=True,
            on_click=lambda _: self.on_click(self.game),
            on_hover=self._on_hover,
            animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    def _on_hover(self, e) -> None:
        if e.data == "true":
            e.control.scale = 1.05
            e.control.shadow = ft.BoxShadow(
                spread_radius=4,
                blur_radius=16,
                color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
            )
        else:
            e.control.scale = 1.0
            e.control.shadow = None
        e.control.update()


class ConsoleCard:
    def __init__(
        self,
        console_code: str,
        console_meta,
        game_count: int,
        on_click: Callable,
        icon_path: Optional[Path] = None,
    ):
        self.console_code = console_code
        self.console_meta = console_meta
        self.game_count = game_count
        self.on_click = on_click
        self.icon_path = icon_path

    def create(self) -> ft.Container:
        name = self.console_meta.name if self.console_meta else self.console_code

        if self.icon_path and self.icon_path.exists():
            icon_widget = ft.Image(
                src=str(self.icon_path),
                width=64,
                height=64,
                fit=ft.BoxFit.CONTAIN,
            )
        else:
            icon_widget = ft.Icon(
                ft.Icons.VIDEOGAME_ASSET,
                size=64,
                color=ft.Colors.PRIMARY,
            )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=icon_widget,
                        alignment=ft.Alignment.CENTER,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    name,
                                    size=14,
                                    weight=ft.FontWeight.W_500,
                                    text_align=ft.TextAlign.CENTER,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    f"{self.game_count} {'game' if self.game_count == 1 else 'games'}",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                            spacing=2,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=15,
                    ),
                ],
                spacing=0,
            ),
            border_radius=12,
            ink=True,
            on_click=lambda _: self.on_click(self.console_code),
            on_hover=self._on_hover,
            animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    def _on_hover(self, e) -> None:
        if e.data == "true":
            e.control.scale = 1.05
            e.control.shadow = ft.BoxShadow(
                spread_radius=4,
                blur_radius=16,
                color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
            )
        else:
            e.control.scale = 1.0
            e.control.shadow = None
        e.control.update()


class LoadingOverlay:
    def __init__(self, message: str = "loading"):
        self.message = message

    def create(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(),
                    ft.Text(
                        self.message,
                        size=16,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20,
            ),
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.SURFACE),
            border_radius=12,
            padding=40,
            animate_opacity=ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
        )


class EmptyState:
    def __init__(
        self,
        icon: str,
        title: str,
        subtitle: str,
        action_text: Optional[str] = None,
        on_action: Optional[Callable] = None,
    ):
        self.icon = icon
        self.title = title
        self.subtitle = subtitle
        self.action_text = action_text
        self.on_action = on_action

    def create(self) -> ft.Container:
        controls = [
            ft.Icon(
                self.icon,
                size=64,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Text(
                self.title,
                size=20,
                weight=ft.FontWeight.W_500,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            ft.Text(
                self.subtitle,
                size=14,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
            ),
        ]

        if self.action_text and self.on_action:
            controls.append(ft.Container(height=20))
            controls.append(
                ft.FilledButton(
                    self.action_text,
                    on_click=lambda _: self.on_action(),
                )
            )

        return ft.Container(
            content=ft.Column(
                controls,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15,
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
            animate_opacity=ft.Animation(300, ft.AnimationCurve.EASE_IN),
        )
