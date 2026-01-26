"""Symbol selector with search and multi-column layout."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window, ScrollOffsets
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.styles import Style as PTStyle

if TYPE_CHECKING:
    from prompt_toolkit.key_binding.key_processor import KeyPressEvent


class SymbolSelector:
    """A searchable grid-based symbol selector."""

    def __init__(self, symbols: list[str], style=None):
        self.symbols = symbols
        self.filtered_symbols = symbols
        # Convert questionary style to prompt_toolkit style if needed
        if style and hasattr(style, "class_names_and_attrs"):
            self.pt_style = style
        elif isinstance(style, list):
            self.pt_style = PTStyle(style)
        else:
            self.pt_style = None

        self.index = 0
        self.cols = 4  # Initial value, will be updated based on width
        self.col_width = 18 # Symbol width + padding
        self.search_text = ""
        
        # UI components
        self.search_field = TextArea(
            prompt="Search: ",
            multiline=False,
        )
        # Add handler to buffer
        self.search_field.buffer.on_text_changed += self._on_search_change
        
        self.grid_control = FormattedTextControl(
            text=self._get_grid_text,
            focusable=True,
            # This is crucial for scrolling: we tell prompt_toolkit where the "cursor" is
            get_cursor_position=self._get_cursor_position,
        )
        self.grid_window = Window(
            self.grid_control, 
            height=15,
            # Enable scrolling when cursor goes out of view
            scroll_offsets=ScrollOffsets(top=1, bottom=1),
        )
        
        self.kb = KeyBindings()
        self._setup_keybindings()
        
        self.app = Application(
            layout=Layout(
                HSplit([
                    Frame(self.search_field, title="Type to Search"),
                    Frame(self.grid_window, title=self._get_title),
                ]),
                focused_element=self.search_field,
            ),
            key_bindings=self.kb,
            style=self.pt_style,
            full_screen=False,
            mouse_support=True,
        )
        self.result = None

    def _get_title(self) -> str:
        """Return dynamic title with counts."""
        total = len(self.symbols)
        filtered = len(self.filtered_symbols)
        return f"Select Symbol ({filtered}/{total} tokens) (Arrows to navigate, Enter to select)"

    def _get_cursor_position(self):
        """Return the (x, y) position of the currently selected symbol for scrolling."""
        if not self.filtered_symbols:
            return None
        
        # Calculate row and column based on current index
        row = self.index // self.cols
        col = self.index % self.cols
        
        # x is the character position in the line
        x = col * self.col_width
        # y is the line number
        y = row
        
        from prompt_toolkit.data_structures import Point
        return Point(x=x, y=y)

    def _update_cols(self):
        """Update columns count based on available window width."""
        width = self.app.renderer.output.get_size().columns
        # Subtract some padding for frames and margins
        available_width = max(20, width - 10)
        self.cols = max(1, available_width // self.col_width)

    def _on_search_change(self, buffer: Buffer) -> None:
        self.search_text = buffer.text.upper()
        self.filtered_symbols = [s for s in self.symbols if self.search_text in s]
        # Adjust index if out of bounds after filtering
        if not self.filtered_symbols:
            self.index = 0
        else:
            self.index = min(self.index, len(self.filtered_symbols) - 1)

    def _get_grid_text(self):
        if not self.filtered_symbols:
            return [("class:disabled", " No matches found")]
        
        # Update columns based on current window size
        self._update_cols()
        
        rows = math.ceil(len(self.filtered_symbols) / self.cols)
        result = []
        for r in range(rows):
            line = []
            for c in range(self.cols):
                idx = r * self.cols + c
                if idx < len(self.filtered_symbols):
                    symbol = self.filtered_symbols[idx]
                    # Ensure each column has fixed width for cursor positioning
                    text = f" {symbol:<15} "
                    if idx == self.index:
                        line.append(("class:highlighted", text))
                    else:
                        line.append(("class:text", text))
            result.extend(line)
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
                event.app.exit(result=self.result)

        @self.kb.add("escape")
        @self.kb.add("c-c")
        def _(event: KeyPressEvent):
            self.result = None
            event.app.exit()

    def ask(self) -> str | None:
        """Run the selector and return the selected symbol."""
        return self.app.run()
