from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, Static

from ..models import TestCase, DatasetConfig, DatasetType, LoadConfig, RandomIdsParams, ServerConfig
from ..optimizer import Optimizer, SLOTarget, SearchConfig, SearchResult


class OptimizerScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("s", "start_search", "Start"),
        ("c", "cancel_search", "Cancel"),
    ]

    def __init__(self, base_case: TestCase | None = None):
        super().__init__()
        self.base_case = base_case or TestCase()
        self._optimizer: Optimizer | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with Vertical(id="optimizer-form"):
                yield Label("[b]SLO-Based Auto-Optimization[/b]", markup=True)
                yield Static("[dim]Find max throughput within latency targets[/dim]", markup=True)
                yield Static("")
                yield Label("TTFT SLO (ms)")
                yield Input(value="500", id="opt-ttft")
                yield Label("TPOT SLO (ms)")
                yield Input(value="50", id="opt-tpot")
                yield Label("Use P99 (otherwise median)")
                yield Select([("Median", "median"), ("P99", "p99")], value="median", id="opt-percentile")
                yield Static("")
                yield Label("[b]Search Range[/b]", markup=True)
                yield Label("Rate min / max / step")
                yield Input(value="1, 100, 5", id="opt-rate-range")
                yield Label("Concurrency min / max / step")
                yield Input(value="1, 128, 8", id="opt-conc-range")
                yield Label("Num prompts per trial")
                yield Input(value="50", id="opt-num-prompts")
                yield Static("")
                yield Label("Search mode")
                yield Select(
                    [("Binary Search (fast)", "binary"), ("Grid Search (thorough)", "grid")],
                    value="binary",
                    id="opt-mode",
                )
                yield Button("Start Search", variant="success", id="btn-start")

            yield RichLog(id="optimizer-progress", wrap=True)
            yield Static("", id="optimizer-result")
        yield Footer()

    def action_start_search(self):
        self._do_start()

    def action_cancel_search(self):
        if self._optimizer:
            self._optimizer.cancel()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-start":
            self._do_start()

    def _do_start(self):
        slo = SLOTarget(
            max_ttft_ms=float(self.query_one("#opt-ttft", Input).value or "500"),
            max_tpot_ms=float(self.query_one("#opt-tpot", Input).value or "50"),
            use_p99=self.query_one("#opt-percentile", Select).value == "p99",
        )

        rate_parts = self.query_one("#opt-rate-range", Input).value.split(",")
        conc_parts = self.query_one("#opt-conc-range", Input).value.split(",")
        search = SearchConfig(
            rate_min=float(rate_parts[0].strip()) if len(rate_parts) > 0 else 1.0,
            rate_max=float(rate_parts[1].strip()) if len(rate_parts) > 1 else 100.0,
            rate_step=float(rate_parts[2].strip()) if len(rate_parts) > 2 else 5.0,
            concurrency_min=int(conc_parts[0].strip()) if len(conc_parts) > 0 else 1,
            concurrency_max=int(conc_parts[1].strip()) if len(conc_parts) > 1 else 128,
            concurrency_step=int(conc_parts[2].strip()) if len(conc_parts) > 2 else 8,
            num_prompts=int(self.query_one("#opt-num-prompts", Input).value or "50"),
        )

        mode = self.query_one("#opt-mode", Select).value

        self._optimizer = Optimizer(self.base_case, slo, search)
        log = self.query_one("#optimizer-progress", RichLog)
        log.clear()
        log.write(f"Starting {mode} search...")
        log.write(f"SLO: TTFT <= {slo.max_ttft_ms}ms, TPOT <= {slo.max_tpot_ms}ms ({'p99' if slo.use_p99 else 'median'})")

        self.run_worker(self._run_search(mode, log))

    async def _run_search(self, mode: str, log: RichLog):
        def on_progress(sr: SearchResult):
            icon = "✓" if sr.meets_slo else "✗"
            ttft = sr.result.median_ttft_ms or sr.result.p99_ttft_ms
            tpot = sr.result.median_tpot_ms or sr.result.p99_tpot_ms
            self.call_from_thread(
                log.write,
                f"  {icon} rate={sr.rate:.1f} conc={sr.concurrency or '∞'} "
                f"TTFT={ttft:.1f}ms TPOT={tpot:.1f}ms "
                f"throughput={sr.result.request_throughput:.1f} req/s"
            )

        if mode == "binary":
            result = await self._optimizer.search_binary(on_progress)
        else:
            result = await self._optimizer.search_grid(on_progress)

        summary_widget = self.query_one("#optimizer-result", Static)
        if result.best:
            b = result.best
            summary_widget.update(
                f"[green][b]Best:[/b] rate={b.rate:.1f} concurrency={b.concurrency or '∞'} "
                f"→ {b.result.request_throughput:.1f} req/s "
                f"(TTFT={b.result.median_ttft_ms:.1f}ms, TPOT={b.result.median_tpot_ms:.1f}ms)[/green]"
            )
        else:
            summary_widget.update("[red]No configuration found meeting SLO targets.[/red]")
