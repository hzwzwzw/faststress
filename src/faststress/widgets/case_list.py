from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from ..models import RunStatus, TestCase


class CaseItem(ListItem):
    def __init__(self, case: TestCase, status: RunStatus = RunStatus.PENDING):
        super().__init__()
        self.case = case
        self.status = status

    def compose(self) -> ComposeResult:
        status_icon = {
            RunStatus.PENDING: "○",
            RunStatus.RUNNING: "◉",
            RunStatus.COMPLETED: "●",
            RunStatus.FAILED: "✗",
        }[self.status]
        status_cls = f"status-{self.status.value}"
        yield Label(f"[{status_cls}]{status_icon}[/] {self.case.name}", markup=True)


class CaseListPanel(Widget):
    selected_index: reactive[int] = reactive(0)

    class CaseSelected(Message):
        def __init__(self, index: int, case: TestCase):
            super().__init__()
            self.index = index
            self.case = case

    def __init__(self, cases: list[TestCase]):
        super().__init__()
        self.cases = cases
        self.statuses: dict[str, RunStatus] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="case-list-panel"):
            yield Label("[b]Test Cases[/b]  [dim]a:add d:del r:run R:run-all[/dim]", markup=True)
            yield ListView(*self._make_items(), id="case-listview")

    def _make_items(self) -> list[CaseItem]:
        items = []
        for case in self.cases:
            status = self.statuses.get(case.name, RunStatus.PENDING)
            items.append(CaseItem(case, status))
        return items

    def refresh_list(self):
        lv = self.query_one("#case-listview", ListView)
        lv.clear()
        for item in self._make_items():
            lv.append(item)

    def on_list_view_selected(self, event: ListView.Selected):
        idx = event.list_view.index or 0
        if idx < len(self.cases):
            self.selected_index = idx
            self.post_message(self.CaseSelected(idx, self.cases[idx]))

    def set_status(self, name: str, status: RunStatus):
        self.statuses[name] = status
        self.refresh_list()
