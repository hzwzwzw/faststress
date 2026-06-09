from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, RichLog, Static


class RunPanel(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        yield Label("[b]Output[/b]", markup=True)
        yield RichLog(id="output-log", wrap=True, highlight=True)
        yield Static("", id="result-summary")

    def append_output(self, line: str):
        log = self.query_one("#output-log", RichLog)
        log.write(line)

    def clear_output(self):
        log = self.query_one("#output-log", RichLog)
        log.clear()
        self.query_one("#result-summary", Static).update("")

    def show_result(self, text: str):
        self.query_one("#result-summary", Static).update(f"[green]{text}[/green]")

    def show_error(self, text: str):
        self.query_one("#result-summary", Static).update(f"[red]{text}[/red]")
