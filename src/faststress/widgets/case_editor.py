from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, Select, Static

from ..models import (
    Backend,
    DatasetType,
    GspParams,
    LoadConfig,
    RandomIdsParams,
    ServerConfig,
    SharegptParams,
    TestCase,
)


class CaseEditor(Widget):
    class CaseUpdated(Message):
        def __init__(self, case: TestCase):
            super().__init__()
            self.case = case

    def __init__(self, case: TestCase | None = None):
        super().__init__()
        self._case = case or TestCase()

    @property
    def case(self) -> TestCase:
        return self._case

    @case.setter
    def case(self, value: TestCase):
        self._case = value
        self._refresh_inputs()

    def compose(self) -> ComposeResult:
        c = self._case
        with Vertical(id="editor-panel"):
            yield Label("[b]Case Editor[/b]  [dim]Enter:save Esc:cancel[/dim]", markup=True)
            with Vertical(id="form-container"):
                yield Label("[b]Name[/b]", markup=True)
                yield Input(value=c.name, id="input-name", placeholder="Test case name")

                yield Static("")
                yield Label("[b]── Server ──[/b]", classes="form-group-title", markup=True)
                yield Label("Backend")
                yield Select(
                    [(b.value, b.value) for b in Backend],
                    value=c.server.backend.value,
                    id="select-backend",
                )
                yield Label("Host")
                yield Input(value=c.server.host, id="input-host", placeholder="127.0.0.1")
                yield Label("Port")
                yield Input(value=str(c.server.port), id="input-port", placeholder="30000")
                yield Label("Base URL (overrides host:port)")
                yield Input(value=c.server.base_url or "", id="input-base-url", placeholder="http://...")

                yield Static("")
                yield Label("[b]── Dataset ──[/b]", classes="form-group-title", markup=True)
                yield Label("Type")
                yield Select(
                    [(d.value, d.value) for d in DatasetType],
                    value=c.dataset.dataset_type.value,
                    id="select-dataset",
                )

                # Random IDs params
                yield Label("Input Length", id="lbl-input-len")
                yield Input(value=str(c.dataset.random_ids.input_len), id="input-random-input-len")
                yield Label("Output Length", id="lbl-output-len")
                yield Input(value=str(c.dataset.random_ids.output_len), id="input-random-output-len")

                # ShareGPT params
                yield Label("Dataset Path", id="lbl-dataset-path")
                yield Input(value=c.dataset.sharegpt.dataset_path, id="input-sharegpt-path")

                # GSP params
                yield Label("Num Groups", id="lbl-gsp-groups")
                yield Input(value=str(c.dataset.gsp.num_groups), id="input-gsp-groups")
                yield Label("Prompts/Group", id="lbl-gsp-ppg")
                yield Input(value=str(c.dataset.gsp.prompts_per_group), id="input-gsp-ppg")
                yield Label("System Prompt Len", id="lbl-gsp-spl")
                yield Input(value=str(c.dataset.gsp.system_prompt_len), id="input-gsp-spl")
                yield Label("Question Len", id="lbl-gsp-ql")
                yield Input(value=str(c.dataset.gsp.question_len), id="input-gsp-ql")
                yield Label("Output Len", id="lbl-gsp-ol")
                yield Input(value=str(c.dataset.gsp.output_len), id="input-gsp-ol")

                yield Static("")
                yield Label("[b]── Load ──[/b]", classes="form-group-title", markup=True)
                yield Label("Request Rate (inf=burst)")
                rate_str = "inf" if c.load.request_rate == float("inf") else str(c.load.request_rate)
                yield Input(value=rate_str, id="input-rate")
                yield Label("Max Concurrency (empty=unlimited)")
                yield Input(
                    value=str(c.load.max_concurrency) if c.load.max_concurrency else "",
                    id="input-concurrency",
                )
                yield Label("Num Prompts")
                yield Input(value=str(c.load.num_prompts), id="input-num-prompts")

    def _refresh_inputs(self):
        try:
            c = self._case
            self.query_one("#input-name", Input).value = c.name
            self.query_one("#select-backend", Select).value = c.server.backend.value
            self.query_one("#input-host", Input).value = c.server.host
            self.query_one("#input-port", Input).value = str(c.server.port)
            self.query_one("#input-base-url", Input).value = c.server.base_url or ""
            self.query_one("#select-dataset", Select).value = c.dataset.dataset_type.value
            self.query_one("#input-random-input-len", Input).value = str(c.dataset.random_ids.input_len)
            self.query_one("#input-random-output-len", Input).value = str(c.dataset.random_ids.output_len)
            self.query_one("#input-sharegpt-path", Input).value = c.dataset.sharegpt.dataset_path
            self.query_one("#input-gsp-groups", Input).value = str(c.dataset.gsp.num_groups)
            self.query_one("#input-gsp-ppg", Input).value = str(c.dataset.gsp.prompts_per_group)
            self.query_one("#input-gsp-spl", Input).value = str(c.dataset.gsp.system_prompt_len)
            self.query_one("#input-gsp-ql", Input).value = str(c.dataset.gsp.question_len)
            self.query_one("#input-gsp-ol", Input).value = str(c.dataset.gsp.output_len)
            rate_str = "inf" if c.load.request_rate == float("inf") else str(c.load.request_rate)
            self.query_one("#input-rate", Input).value = rate_str
            self.query_one("#input-concurrency", Input).value = (
                str(c.load.max_concurrency) if c.load.max_concurrency else ""
            )
            self.query_one("#input-num-prompts", Input).value = str(c.load.num_prompts)
        except Exception:
            pass

    def collect_case(self) -> TestCase:
        name = self.query_one("#input-name", Input).value.strip() or "unnamed"
        backend = Backend(self.query_one("#select-backend", Select).value)
        host = self.query_one("#input-host", Input).value.strip() or "127.0.0.1"
        port_str = self.query_one("#input-port", Input).value.strip()
        port = int(port_str) if port_str.isdigit() else 30000
        base_url = self.query_one("#input-base-url", Input).value.strip() or None

        dataset_type = DatasetType(self.query_one("#select-dataset", Select).value)

        random_ids = RandomIdsParams(
            input_len=self._int_val("input-random-input-len", 1024),
            output_len=self._int_val("input-random-output-len", 128),
        )
        sharegpt = SharegptParams(
            dataset_path=self.query_one("#input-sharegpt-path", Input).value.strip(),
        )
        gsp = GspParams(
            num_groups=self._int_val("input-gsp-groups", 4),
            prompts_per_group=self._int_val("input-gsp-ppg", 8),
            system_prompt_len=self._int_val("input-gsp-spl", 512),
            question_len=self._int_val("input-gsp-ql", 128),
            output_len=self._int_val("input-gsp-ol", 128),
        )

        rate_str = self.query_one("#input-rate", Input).value.strip()
        rate = float("inf") if rate_str.lower() == "inf" else float(rate_str or "inf")
        conc_str = self.query_one("#input-concurrency", Input).value.strip()
        concurrency = int(conc_str) if conc_str.isdigit() else None
        num_prompts = self._int_val("input-num-prompts", 100)

        from ..models import DatasetConfig
        return TestCase(
            name=name,
            server=ServerConfig(backend=backend, host=host, port=port, base_url=base_url),
            dataset=DatasetConfig(
                dataset_type=dataset_type,
                random_ids=random_ids,
                sharegpt=sharegpt,
                gsp=gsp,
            ),
            load=LoadConfig(
                request_rate=rate,
                max_concurrency=concurrency,
                num_prompts=num_prompts,
            ),
        )

    def _int_val(self, input_id: str, default: int) -> int:
        v = self.query_one(f"#{input_id}", Input).value.strip()
        return int(v) if v.isdigit() else default
