from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from .models import BenchResult, Preset, RunStatus, TestCase, TestGroup
from .runner import BenchRunner
from .storage import (
    export_cases,
    import_cases,
    list_presets,
    load_group,
    load_preset,
    save_group,
    save_preset,
    save_result_csv,
)
from .widgets.case_editor import CaseEditor
from .widgets.case_list import CaseListPanel
from .widgets.optimizer_ui import OptimizerScreen
from .widgets.run_panel import RunPanel


def _fmt(val: float | None, suffix: str = "") -> str:
    return f"{val:.1f}{suffix}" if val is not None else "N/A"


# --- Modals ---


class BatchUpdateModal(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Cancel")]

    def __init__(self, cases: list[TestCase]):
        super().__init__()
        self._cases = cases

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("[b]Batch Update[/b]", markup=True)
            yield Label("Field: host / port / base_url / rate / concurrency / num_prompts")
            yield Input(id="batch-field", placeholder="e.g. base_url")
            yield Label("New Value")
            yield Input(id="batch-value", placeholder="e.g. http://10.0.0.1:8000")
            yield Label("[dim]Enter to apply, Esc to cancel[/dim]", markup=True)

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "batch-value":
            field = self.query_one("#batch-field", Input).value.strip()
            value = self.query_one("#batch-value", Input).value.strip()
            if field:
                self._apply(field, value)
            self.dismiss()

    def _apply(self, field: str, value: str):
        for case in self._cases:
            if field == "host":
                case.server.host = value
            elif field == "port":
                case.server.port = int(value) if value.isdigit() else case.server.port
            elif field == "base_url":
                case.server.base_url = value or None
            elif field == "rate":
                case.load.request_rate = float("inf") if value.lower() == "inf" else float(value)
            elif field == "concurrency":
                case.load.max_concurrency = int(value) if value.isdigit() else None
            elif field == "num_prompts":
                case.load.num_prompts = int(value) if value.isdigit() else case.load.num_prompts


class PresetSelectModal(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, presets: list[str]):
        super().__init__()
        self._presets = presets

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("[b]Select Preset[/b]", markup=True)
            items = [ListItem(Label(name)) for name in self._presets]
            yield ListView(*items, id="preset-listview")
            yield Label("[dim]Enter:select  Esc:cancel[/dim]", markup=True)

    def on_list_view_selected(self, event: ListView.Selected):
        idx = event.list_view.index if event.list_view.index is not None else 0
        if idx < len(self._presets):
            self.dismiss(self._presets[idx])

    def action_cancel(self):
        self.dismiss(None)


class SavePresetModal(ModalScreen[str | None]):
    BINDINGS = [("escape", "dismiss", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("[b]Save as Preset[/b]", markup=True)
            yield Label("Preset Name")
            yield Input(id="preset-name", placeholder="my-preset")
            yield Label("[dim]Enter to save, Esc to cancel[/dim]", markup=True)

    def on_input_submitted(self, event: Input.Submitted):
        name = self.query_one("#preset-name", Input).value.strip()
        if name:
            self.dismiss(name)


class ImportExportModal(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Cancel")]

    def __init__(self, cases: list[TestCase], on_import: callable):
        super().__init__()
        self._cases = cases
        self._on_import = on_import

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("[b]Import / Export[/b]", markup=True)
            yield Label("Path (JSON file)")
            yield Input(id="ie-path", placeholder="./test_cases.json")
            yield Label("[dim]i:import  e:export  Esc:cancel[/dim]", markup=True)

    def key_e(self):
        path = Path(self.query_one("#ie-path", Input).value.strip())
        if path.suffix == ".json":
            export_cases(self._cases, path)
            self.notify("Exported", severity="information")
        self.dismiss()

    def key_i(self):
        path = Path(self.query_one("#ie-path", Input).value.strip())
        if path.exists():
            cases = import_cases(path)
            self._on_import(cases)
            self.notify(f"Imported {len(cases)} cases", severity="information")
        else:
            self.notify("File not found", severity="error")
        self.dismiss()


# --- Main App ---


class FastStressApp(App):
    CSS_PATH = "styles/app.tcss"
    TITLE = "FastStress"
    BINDINGS = [
        Binding("a", "add_case", "Add"),
        Binding("d", "delete_case", "Delete"),
        Binding("r", "run_case", "Run"),
        Binding("R", "run_all", "Run All", key_display="shift+r"),
        Binding("x", "stop_run", "Stop"),
        Binding("b", "batch_update", "Batch"),
        Binding("o", "optimizer", "Optimizer"),
        Binding("p", "load_preset", "Presets"),
        Binding("P", "save_preset", "Save Preset", key_display="shift+p"),
        Binding("i", "import_export", "Import/Export"),
        Binding("right", "focus_editor", "→ Editor", show=False),
        Binding("left", "focus_list", "← List", show=False),
        Binding("q", "request_quit", "Quit"),
        Binding("ctrl+c", "request_quit", "Quit", show=False, priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.cases: list[TestCase] = [TestCase(name="default")]
        self.group = TestGroup(name="default", cases=self.cases)
        self.runner = BenchRunner()
        self._current_index = 0
        self._quit_pending = False
        self._load_saved()

    def _load_saved(self):
        from .storage import DATA_DIR
        default_path = DATA_DIR / "default.json"
        if default_path.exists():
            try:
                self.group = load_group(default_path)
                self.cases = self.group.cases
                if not self.cases:
                    self.cases = [TestCase(name="default")]
                    self.group.cases = self.cases
            except Exception:
                pass

    def compose(self) -> ComposeResult:
        yield Header()
        yield CaseListPanel(self.cases, id="case-list-panel")
        with Vertical(id="right-panel"):
            yield CaseEditor(self.cases[0] if self.cases else TestCase(), id="editor-panel")
            yield RunPanel(id="run-panel")
        yield Footer()

    # --- Message handlers ---

    def on_case_list_panel_case_selected(self, event: CaseListPanel.CaseSelected):
        self._current_index = event.index
        self.query_one(CaseEditor).case = event.case

    def on_case_editor_case_updated(self, event: CaseEditor.CaseUpdated):
        self.cases[self._current_index] = event.case
        self.group.cases = self.cases
        save_group(self.group)
        panel = self.query_one(CaseListPanel)
        panel.cases = self.cases
        panel.refresh_list()

    def on_case_editor_focus_released(self, event: CaseEditor.FocusReleased):
        self._focus_case_list()

    # --- Focus / Navigation ---

    def action_focus_editor(self):
        editor = self.query_one(CaseEditor)
        editor.focus_first_input()

    def action_focus_list(self):
        self._focus_case_list()

    def _focus_case_list(self):
        try:
            lv = self.query_one("#case-listview")
            lv.focus()
        except Exception:
            pass

    def action_request_quit(self):
        if self._quit_pending:
            self.runner.cancel()
            self.exit()
        else:
            self._quit_pending = True
            self.notify("Press again to quit", severity="warning", timeout=2)
            self.set_timer(2.0, self._reset_quit)

    def _reset_quit(self):
        self._quit_pending = False

    def action_stop_run(self):
        if self.runner.is_running:
            self.runner.cancel()
            run_panel = self.query_one(RunPanel)
            run_panel.append_output("⏹ Stopped by user")
            run_panel.show_error("Run cancelled")
            self.notify("Run stopped")

    # --- Actions ---

    def action_add_case(self):
        new_case = TestCase(name=f"case-{len(self.cases) + 1}")
        self.cases.append(new_case)
        self.group.cases = self.cases
        panel = self.query_one(CaseListPanel)
        panel.cases = self.cases
        panel.refresh_list()
        self._current_index = len(self.cases) - 1
        self.query_one(CaseEditor).case = new_case

    def action_delete_case(self):
        if len(self.cases) <= 1:
            self.notify("Cannot delete last case", severity="warning")
            return
        del self.cases[self._current_index]
        self._current_index = min(self._current_index, len(self.cases) - 1)
        self.group.cases = self.cases
        panel = self.query_one(CaseListPanel)
        panel.cases = self.cases
        panel.refresh_list()
        self.query_one(CaseEditor).case = self.cases[self._current_index]

    def action_run_case(self):
        if not self.cases:
            return
        case = self.cases[self._current_index]
        self._do_run_case(case)

    def action_run_all(self):
        self._do_run_all()

    @work(exclusive=True, exit_on_error=False)
    async def _do_run_case(self, case: TestCase):
        panel = self.query_one(CaseListPanel)
        run_panel = self.query_one(RunPanel)
        run_panel.clear_output()
        panel.set_status(case.name, RunStatus.RUNNING)
        run_panel.append_output(f"▶ Running: {case.name}")
        run_panel.append_output(f"  python -m sglang.bench_serving {' '.join(case.to_bench_args()[:8])}...")
        run_panel.append_output("─" * 50)

        result, error = await self.runner.run(case, on_output=run_panel.append_output)

        if error:
            panel.set_status(case.name, RunStatus.FAILED)
            run_panel.show_error(error[-200:] if len(error) > 200 else error)
        elif result:
            panel.set_status(case.name, RunStatus.COMPLETED)
            save_result_csv(case.name, result)
            summary = (
                f"Throughput: {_fmt(result.request_throughput)} req/s | "
                f"TTFT: {_fmt(result.median_ttft_ms)}ms (p99: {_fmt(result.p99_ttft_ms)}ms) | "
                f"TPOT: {_fmt(result.median_tpot_ms)}ms (p99: {_fmt(result.p99_tpot_ms)}ms)"
            )
            run_panel.show_result(summary)
        else:
            panel.set_status(case.name, RunStatus.FAILED)
            run_panel.show_error("No result and no error — unexpected state")

    @work(exclusive=True, exit_on_error=False)
    async def _do_run_all(self):
        for case in self.cases:
            await self._execute_single(case)

    async def _execute_single(self, case: TestCase):
        panel = self.query_one(CaseListPanel)
        run_panel = self.query_one(RunPanel)
        run_panel.clear_output()
        panel.set_status(case.name, RunStatus.RUNNING)
        run_panel.append_output(f"▶ Running: {case.name}")

        result, error = await self.runner.run(case, on_output=run_panel.append_output)

        if error:
            panel.set_status(case.name, RunStatus.FAILED)
            run_panel.show_error(error[-200:] if len(error) > 200 else error)
        elif result:
            panel.set_status(case.name, RunStatus.COMPLETED)
            save_result_csv(case.name, result)
            run_panel.show_result(f"{case.name}: {_fmt(result.request_throughput)} req/s")

    # --- Modals ---

    def action_batch_update(self):
        self.push_screen(BatchUpdateModal(self.cases), callback=self._on_batch_done)

    def _on_batch_done(self, _result) -> None:
        self.group.cases = self.cases
        save_group(self.group)
        panel = self.query_one(CaseListPanel)
        panel.cases = self.cases
        panel.refresh_list()
        self.query_one(CaseEditor).case = self.cases[self._current_index]
        self.notify("Batch update applied", severity="information")

    def action_load_preset(self):
        presets = list_presets()
        if not presets:
            self.notify("No presets found. Use Shift+P to save current as preset.", severity="warning")
            return
        self.push_screen(PresetSelectModal(presets), callback=self._on_preset_selected)

    def _on_preset_selected(self, name: str | None) -> None:
        if not name:
            return
        preset = load_preset(name)
        if preset and preset.group.cases:
            self.cases.clear()
            self.cases.extend(preset.group.cases)
            self.group = preset.group
            self._current_index = 0
            panel = self.query_one(CaseListPanel)
            panel.cases = self.cases
            panel.statuses.clear()
            panel.refresh_list()
            self.query_one(CaseEditor).case = self.cases[0]
            self.notify(f"Loaded preset: {name}", severity="information")

    def action_save_preset(self):
        self.push_screen(SavePresetModal(), callback=self._on_save_preset)

    def _on_save_preset(self, name: str | None) -> None:
        if not name:
            return
        editor = self.query_one(CaseEditor)
        self.cases[self._current_index] = editor.collect_case()
        self.group.cases = self.cases
        preset = Preset(name=name, group=self.group.model_copy(deep=True))
        save_preset(preset)
        self.notify(f"Saved preset: {name}", severity="information")

    def action_import_export(self):
        def on_import(cases: list[TestCase]):
            self.cases.clear()
            self.cases.extend(cases)
            self.group.cases = self.cases
            self._current_index = 0
            panel = self.query_one(CaseListPanel)
            panel.cases = self.cases
            panel.statuses.clear()
            panel.refresh_list()
            if self.cases:
                self.query_one(CaseEditor).case = self.cases[0]

        self.push_screen(ImportExportModal(self.cases, on_import))

    def action_optimizer(self):
        current = self.cases[self._current_index] if self.cases else TestCase()
        self.push_screen(OptimizerScreen(current))


def main():
    app = FastStressApp()
    app.run()


if __name__ == "__main__":
    main()
