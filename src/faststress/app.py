from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, Static

from .models import BenchResult, RunStatus, TestCase, TestGroup
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


class BatchUpdateModal(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Cancel")]

    def __init__(self, cases: list[TestCase]):
        super().__init__()
        self._cases = cases

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal"):
            yield Label("[b]Batch Update[/b]", markup=True)
            yield Label("Field (host / port / base_url / rate / concurrency / num_prompts)")
            yield Input(id="batch-field", placeholder="e.g. base_url")
            yield Label("New Value")
            yield Input(id="batch-value", placeholder="e.g. http://10.0.0.1:8000")
            yield Label("[dim]Press Enter to apply, Esc to cancel[/dim]", markup=True)

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "batch-value":
            field = self.query_one("#batch-field", Input).value.strip()
            value = self.query_one("#batch-value", Input).value.strip()
            self._apply(field, value)
            self.dismiss()

    def _apply(self, field: str, value: str):
        for case in self._cases:
            if field == "host":
                case.server.host = value
            elif field == "port":
                case.server.port = int(value)
            elif field == "base_url":
                case.server.base_url = value or None
            elif field == "rate":
                case.load.request_rate = float("inf") if value == "inf" else float(value)
            elif field == "concurrency":
                case.load.max_concurrency = int(value) if value else None
            elif field == "num_prompts":
                case.load.num_prompts = int(value)


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
        export_cases(self._cases, path)
        self.dismiss()

    def key_i(self):
        path = Path(self.query_one("#ie-path", Input).value.strip())
        if path.exists():
            cases = import_cases(path)
            self._on_import(cases)
        self.dismiss()


class FastStressApp(App):
    CSS_PATH = "styles/app.tcss"
    TITLE = "FastStress"
    BINDINGS = [
        Binding("a", "add_case", "Add Case"),
        Binding("d", "delete_case", "Delete Case"),
        Binding("r", "run_case", "Run Selected"),
        Binding("R", "run_all", "Run All", key_display="shift+r"),
        Binding("s", "save", "Save"),
        Binding("b", "batch_update", "Batch Update"),
        Binding("o", "optimizer", "Optimizer"),
        Binding("p", "load_preset", "Presets"),
        Binding("i", "import_export", "Import/Export"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.cases: list[TestCase] = [TestCase(name="default")]
        self.group = TestGroup(name="default", cases=self.cases)
        self.runner = BenchRunner()
        self._current_index = 0
        self._load_saved()

    def _load_saved(self):
        from .storage import DATA_DIR
        default_path = DATA_DIR / "default.json"
        if default_path.exists():
            try:
                self.group = load_group(default_path)
                self.cases = self.group.cases
            except Exception:
                pass

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield CaseListPanel(self.cases)
            with Vertical():
                yield CaseEditor(self.cases[0] if self.cases else TestCase())
                yield RunPanel()
        yield Footer()

    def on_case_list_panel_case_selected(self, event: CaseListPanel.CaseSelected):
        self._current_index = event.index
        editor = self.query_one(CaseEditor)
        editor.case = event.case

    def action_add_case(self):
        new_case = TestCase(name=f"case-{len(self.cases) + 1}")
        self.cases.append(new_case)
        self.group.cases = self.cases
        self.query_one(CaseListPanel).cases = self.cases
        self.query_one(CaseListPanel).refresh_list()

    def action_delete_case(self):
        if len(self.cases) <= 1:
            return
        del self.cases[self._current_index]
        self._current_index = max(0, self._current_index - 1)
        self.group.cases = self.cases
        panel = self.query_one(CaseListPanel)
        panel.cases = self.cases
        panel.refresh_list()
        if self.cases:
            self.query_one(CaseEditor).case = self.cases[self._current_index]

    def action_save(self):
        editor = self.query_one(CaseEditor)
        updated = editor.collect_case()
        self.cases[self._current_index] = updated
        self.group.cases = self.cases
        save_group(self.group)
        panel = self.query_one(CaseListPanel)
        panel.cases = self.cases
        panel.refresh_list()
        self.notify("Saved", severity="information")

    def action_run_case(self):
        if not self.cases:
            return
        case = self.cases[self._current_index]
        self.run_worker(self._execute_case(case))

    def action_run_all(self):
        self.run_worker(self._execute_all())

    async def _execute_case(self, case: TestCase):
        panel = self.query_one(CaseListPanel)
        run_panel = self.query_one(RunPanel)
        run_panel.clear_output()
        panel.set_status(case.name, RunStatus.RUNNING)
        run_panel.append_output(f"Running: {case.name}")
        run_panel.append_output(f"Command: python -m sglang.bench_serving {' '.join(case.to_bench_args())}")
        run_panel.append_output("─" * 60)

        result, error = await self.runner.run(
            case, on_output=lambda line: self.call_from_thread(run_panel.append_output, line)
        )

        if error:
            panel.set_status(case.name, RunStatus.FAILED)
            run_panel.show_error(error)
        elif result:
            panel.set_status(case.name, RunStatus.COMPLETED)
            save_result_csv(case.name, result)
            summary = (
                f"Throughput: {result.request_throughput:.1f} req/s | "
                f"TTFT: {result.median_ttft_ms:.1f}ms (p99: {result.p99_ttft_ms:.1f}ms) | "
                f"TPOT: {result.median_tpot_ms:.1f}ms (p99: {result.p99_tpot_ms:.1f}ms)"
            )
            run_panel.show_result(summary)

    async def _execute_all(self):
        for i, case in enumerate(self.cases):
            await self._execute_case(case)

    def action_batch_update(self):
        self.push_screen(BatchUpdateModal(self.cases))

    def action_optimizer(self):
        current = self.cases[self._current_index] if self.cases else TestCase()
        self.push_screen(OptimizerScreen(current))

    def action_load_preset(self):
        presets = list_presets()
        if presets:
            preset = load_preset(presets[0])
            if preset:
                self.cases.clear()
                self.cases.extend(preset.group.cases)
                self.group = preset.group
                panel = self.query_one(CaseListPanel)
                panel.cases = self.cases
                panel.refresh_list()
                self.notify(f"Loaded preset: {preset.name}")
        else:
            self.notify("No presets found. Save current as preset with 'S'", severity="warning")

    def action_import_export(self):
        def on_import(cases: list[TestCase]):
            self.cases.clear()
            self.cases.extend(cases)
            self.group.cases = self.cases
            panel = self.query_one(CaseListPanel)
            panel.cases = self.cases
            panel.refresh_list()
            self.notify(f"Imported {len(cases)} cases")

        self.push_screen(ImportExportModal(self.cases, on_import))


def main():
    app = FastStressApp()
    app.run()


if __name__ == "__main__":
    main()
