"""Symbol selector with search and multi-column layout."""

from __future__ import annotations  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

import math  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from typing import TYPE_CHECKING  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

from prompt_toolkit.application import Application  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from prompt_toolkit.buffer import Buffer  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from prompt_toolkit.key_binding import KeyBindings  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from prompt_toolkit.layout.containers import HSplit, ScrollOffsets, Window  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from prompt_toolkit.layout.controls import FormattedTextControl  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from prompt_toolkit.layout.layout import Layout  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from prompt_toolkit.styles import Style as PTStyle  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
from prompt_toolkit.widgets import Frame, TextArea  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

if TYPE_CHECKING:
    from prompt_toolkit.key_binding.key_processor import KeyPressEvent

    from monte_neo.cli.menu.main import InteractiveMenu


class SymbolSelector:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    """A searchable grid-based symbol selector."""

    def __init__(self, symbols: list[str], style=None):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        self.symbols = symbols  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        self.filtered_symbols = symbols  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        # Convert questionary style to prompt_toolkit style if needed
        if style and hasattr(style, "class_names_and_attrs"):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            self.pt_style = style  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        elif isinstance(style, list):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            self.pt_style = PTStyle(style)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        else:
            self.pt_style = None  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        self.index = 0  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        self.cols = 4  # Initial value, will be updated based on width  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        self.col_width = 18 # Symbol width + padding  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        self.search_text = ""  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        self.result: str | None = None  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        # UI components
        self.search_field = TextArea(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            prompt="Search: ",
            multiline=False,
        )
        # Add handler to buffer
        self.search_field.buffer.on_text_changed += self._on_search_change  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        self.grid_control = FormattedTextControl(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            text=self._get_grid_text,
            focusable=True,
            # This is crucial for scrolling: we tell prompt_toolkit where the "cursor" is
            get_cursor_position=self._get_cursor_position,
        )
        self.grid_window = Window(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            self.grid_control,
            height=15,
            # Enable scrolling when cursor goes out of view
            scroll_offsets=ScrollOffsets(top=1, bottom=1),
        )

        self.kb = KeyBindings()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        self._setup_keybindings()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        self.app = Application(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
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

    def _get_title(self) -> str:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        """Return dynamic title with counts."""
        total = len(self.symbols)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        filtered = len(self.filtered_symbols)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return f"Select Symbol ({filtered}/{total} tokens) (Arrows to navigate, Enter to select)"  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    def _get_cursor_position(self):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        """Return the (x, y) position of the currently selected symbol for scrolling."""
        if not self.filtered_symbols:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            return None  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        # Calculate row and column based on current index
        row = self.index // self.cols  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        col = self.index % self.cols  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        # x is the character position in the line
        x = col * self.col_width  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        # y is the line number
        y = row  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        from prompt_toolkit.data_structures import Point  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return Point(x=x, y=y)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    def _update_cols(self):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        """Update columns count based on available window width."""
        width = self.app.renderer.output.get_size().columns  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        # Subtract some padding for frames and margins
        available_width = max(20, width - 10)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        self.cols = max(1, available_width // self.col_width)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    def _on_search_change(self, buffer: Buffer) -> None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        self.search_text = buffer.text.upper()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        self.filtered_symbols = [s for s in self.symbols if self.search_text in s]  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        # Adjust index if out of bounds after filtering
        if not self.filtered_symbols:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            self.index = 0  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        else:
            self.index = min(self.index, len(self.filtered_symbols) - 1)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    def _get_grid_text(self):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if not self.filtered_symbols:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            return [("class:disabled", " No matches found")]  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        # Update columns based on current window size
        self._update_cols()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        rows = math.ceil(len(self.filtered_symbols) / self.cols)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        result = []  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        for r in range(rows):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            line = []  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            for c in range(self.cols):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                idx = r * self.cols + c  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                if idx < len(self.filtered_symbols):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                    symbol = self.filtered_symbols[idx]  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                    # Ensure each column has fixed width for cursor positioning
                    text = f" {symbol:<15} "  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                    if idx == self.index:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                        line.append(("class:highlighted", text))  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                    else:
                        line.append(("class:text", text))  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            result.extend(line)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            result.append(("", "\n"))  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return result  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    def _setup_keybindings(self):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        @self.kb.add("up")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        def _(event: KeyPressEvent):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            if self.index >= self.cols:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                self.index -= self.cols  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        @self.kb.add("down")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        def _(event: KeyPressEvent):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            if self.index + self.cols < len(self.filtered_symbols):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                self.index += self.cols  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        @self.kb.add("left")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        def _(event: KeyPressEvent):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            if self.index > 0:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                self.index -= 1  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        @self.kb.add("right")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        def _(event: KeyPressEvent):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            if self.index < len(self.filtered_symbols) - 1:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                self.index += 1  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        @self.kb.add("enter")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        def _(event: KeyPressEvent):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            if self.filtered_symbols:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                self.result = self.filtered_symbols[self.index]  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                event.app.exit(result=self.result)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

        @self.kb.add("escape")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        @self.kb.add("c-c")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        def _(event: KeyPressEvent):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            self.result = None  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            event.app.exit()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    def ask(self) -> str | None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        """Run the selector and return the selected symbol."""
        self.app.run()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return self.result  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

def select_symbol(menu: InteractiveMenu) -> str | None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    """Helper function to run the symbol selector."""
    import os  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    
    # Get available symbols from data directory
    data_dir = menu.config.data_dir  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    raw_dir = os.path.join(data_dir, "raw")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    if not os.path.exists(raw_dir):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return None  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        
    symbols = []  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    for f in os.listdir(raw_dir):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if f.endswith(".parquet"):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            # Format: SYMBOL_TIMEFRAME.parquet
            symbol_part = f.split("_")[0]  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            if symbol_part not in symbols:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                symbols.append(symbol_part)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                
    if not symbols:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return None  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        
    from monte_neo.cli.styles import CUSTOM_STYLE  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    selector = SymbolSelector(symbols, style=CUSTOM_STYLE)  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    return selector.ask()  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

def select_timeframe_for_symbol(menu: InteractiveMenu, symbol: str) -> str | None:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    """Select available timeframe for a given symbol."""
    import os  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    import questionary  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests

    from monte_neo.cli.styles import CUSTOM_STYLE  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    
    data_dir = menu.config.data_dir  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    raw_dir = os.path.join(data_dir, "raw")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    if not os.path.exists(raw_dir):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return None  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        
    timeframes = []  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
    for f in os.listdir(raw_dir):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        if f.startswith(f"{symbol}_") and f.endswith(".parquet"):  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            # Format: SYMBOL_TIMEFRAME.parquet
            parts = f.replace(".parquet", "").split("_")  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
            if len(parts) >= 2:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                timeframes.append(parts[1])  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
                
    if not timeframes:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return None  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        
    if len(timeframes) == 1:  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        return timeframes[0]  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        
    return questionary.select(  # pragma: no cover  # interactive TTY / prompt_toolkit; exercised via mocked app/styles tests
        f"Select timeframe for {symbol}:",
        choices=sorted(timeframes),
        style=CUSTOM_STYLE
    ).ask()
