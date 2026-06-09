from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, RichLog, Select, Static

from ..models import ServerConfig, TestCase
from ..optimizer import Optimizer, SLOTarget, SearchConfig, SearchResult


def _fmt(val: float | None) -> str:
    return f"{val:.1f}" if val is not None else "N/A"


class OptimizerScreen(Screen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("s", "start_search", "Start"),
        ("c", "cancel_search", "Cancel"),
    ]

    def __init__(self, base_case: TestCase | None = None, server: ServerConfig | None = None):
        super().__init__()
        self.base_case = base_case or TestCase()
        self.server = server or ServerConfig()
        self._optimizer: Optimizer | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="optimizer-screen"):
            with Vertical(id="optimizer-form"):
                yield Label("[b]SLO-Based Auto-Optimization[/b]", markup=True)
                yield Static("[dim]Find max throughput within latency targets[/dim]", markup=True)
                yield Static("")
                yield Label("TTFT SLO (ms)")
                yield Input(value="500", id="opt-ttft")
                yield Label("TPOT SLO (ms)")
                yield Input(value="50", id="opt-tpot")
                yield Label("Percentile")
                yield Select(
                    [("Median", "median"), ("P99", "p99")],
                    value="median",
                    id="opt-percentile",
                    allow_blank=False,
                )
                yield Static("")
                yield Label("[b]Search Range[/b]", markup=True)
                yield Label("Rate: min, max, step")
                yield Input(value="1, 100, 5", id="opt-rate-range")
                yield Label("Concurrency: min, max, step")
                yield Input(value="1, 128, 8", id="opt-conc-range")
                yield Label("Num prompts per trial")
                yield Input(value="50", id="opt-num-prompts")
                yield Static("")
                yield Label("Search mode")
                yield Select(
                    [("Binary Search (fast)", "binary"), ("Grid Search (thorough)", "grid")],
                    value="binary",
                    id="opt-mode",
                    allow_blank=False,
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
            self.query_one("#optimizer-progress", RichLog).write("[yellow]Cancelling...[/yellow]")

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

        mode = str(self.query_one("#opt-mode", Select).value)

        self._optimizer = Optimizer(self.base_case, slo, search, server=self.server)
        log = self.query_one("#optimizer-progress", RichLog)
        log.clear()
        log.write(f"Starting {mode} search...")
        log.write(f"SLO: TTFT ≤ {slo.max_ttft_ms}ms, TPOT ≤ {slo.max_tpot_ms}ms ({'p99' if slo.use_p99 else 'median'})")

        self._run_search(mode)

    @work(exclusive=True, exit_on_error=False)
    async def _run_search(self, mode: str):
        log = self.query_one("#optimizer-progress", RichLog)

        def on_progress(sr: SearchResult):
            icon = "✓" if sr.meets_slo else "✗"
            ttft = sr.result.p99_ttft_ms if self._optimizer.slo.use_p99 else sr.result.median_ttft_ms
            tpot = sr.result.p99_tpot_ms if self._optimizer.slo.use_p99 else sr.result.median_tpot_ms
            log.write(
                f"  {icon} rate={sr.rate:.1f} conc={sr.concurrency or '∞'} "
                f"TTFT={_fmt(ttft)}ms TPOT={_fmt(tpot)}ms "
                f"throughput={_fmt(sr.result.request_throughput)} req/s"
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
                f"→ {_fmt(b.result.request_throughput)} req/s "
                f"(TTFT={_fmt(b.result.median_ttft_ms)}ms, TPOT={_fmt(b.result.median_tpot_ms)}ms)[/green]"
            )
        else:
            msg = "[red]No configuration found meeting SLO targets.[/red]"
            if result.stopped:
                msg = "[yellow]Search cancelled. No valid configuration found yet.[/yellow]"
            summary_widget.update(msg)
