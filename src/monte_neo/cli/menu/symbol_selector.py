"""Symbol selector with search and multi-column layout."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.widgets import Frame, TextArea

if TYPE_CHECKING:
    from prompt_toolkit.key_binding.key_processor import KeyPressEvent


class SymbolSelector:
    """A searchable grid-based symbol selector."""

    def __init__(self, symbols: list[str], style=None):
        self.symbols = symbols
        self.filtered_symbols = symbols
        self.style = style
        self.index = 0
        self.cols = 4
        self.search_text = ""
        
        # UI components
        self.search_field = TextArea(
            prompt="Search: ",
            multiline=False,
            change_handler=self._on_search_change,
        )
        
        self.grid_control = FormattedTextControl(
            text=self._get_grid_text,
            focusable=True,
        )
        self.grid_window = Window(self.grid_control, scrollbar=True)
        
        self.kb = KeyBindings()
        self._setup_keybindings()
        
        self.app = Application(
            layout=Layout(
                HSplit([
                    Frame(self.search_field, title="Type to Search"),
                    Frame(self.grid_window, title="Select Symbol (Arrows to navigate, Enter to select)"),
                ])
            ),
            key_bindings=self.kb,
            style=style,
            full_screen=False,
            mouse_support=True,
        )
        self.result = None

    def _on_search_change(self, buffer: Buffer) -> None:
        self.search_text = buffer.text.upper()
        self.filtered_symbols = [s for s in self.symbols if self.search_text in s]
        self.index = 0

    def _get_grid_text(self):
        if not self.filtered_symbols:
            return [("class:error", "No matches found")]
        
        rows = math.ceil(len(self.filtered_symbols) / self.cols)
        # Only show a subset if too many? No, prompt_toolkit handles scrolling if we put it in a window
        # But for simplicity, let's just render what fits or use a simple scroll
        
        # For now, let's just render the grid
        result = []
        for r in range(rows):
            for c in range(self.cols):
                idx = r * self.cols + c
                if idx < len(self.filtered_symbols):
                    symbol = self.filtered_symbols[idx]
                    if idx == self.index:
                        result.append(("class:highlighted", f" {symbol:<15} "))
                    else:
                        result.append(("", f" {symbol:<15} "))
            result.append(("", "\n"))
        return result

    def _setup_keybindings(self):
        @self.kb.add("up")
        def _(event: KeyPressEvent):
            if self.index >= self.cols:
                self.index -= self.cols

        @self.kb.add("down")
        def _(event: KeyPressEvent):
            if self.index + self.cols < len(self.filtered_symbols):
                self.index += self.cols

        @self.kb.add("left")
        def _(event: KeyPressEvent):
            if self.index > 0:
                self.index -= 1

        @self.kb.add("right")
        def _(event: KeyPressEvent):
            if self.index < len(self.filtered_symbols) - 1:
                self.index += 1

        @self.kb.add("enter")
        def _(event: KeyPressEvent):
            if self.filtered_symbols:
                self.result = self.filtered_symbols[self.index]
                event.app.exit()

        @self.kb.add("c-c")
        @self.kb.add("escape")
        def _(event: KeyPressEvent):
            self.result = None
            event.app.exit()

    def ask(self) -> str | None:
        self.app.run()
        return self.result
