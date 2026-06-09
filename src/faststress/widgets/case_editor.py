from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Label, RadioButton, Static

from ..models import (
    Backend,
    DatasetConfig,
    DatasetType,
    GspParams,
    LoadConfig,
    RandomIdsParams,
    ServerConfig,
    SharegptParams,
    TestCase,
)

# Flat ordered list of ALL focusable widget IDs
FIELD_ORDER = [
    "input-name",
    "btn-load-env",
    "radio-backend-sglang",
    "radio-backend-sglang-oai",
    "input-host",
    "input-port",
    "input-base-url",
    "input-api-key",
    "radio-dataset-random-ids",
    "radio-dataset-sharegpt",
    "radio-dataset-gsp",
    "input-random-input-len",
    "input-random-output-len",
    "input-random-range-ratio",
    "input-sharegpt-path",
    "input-sharegpt-ctx",
    "input-sharegpt-out",
    "input-gsp-groups",
    "input-gsp-ppg",
    "input-gsp-spl",
    "input-gsp-ql",
    "input-gsp-ol",
    "radio-gsp-dist-uniform",
    "radio-gsp-dist-zipf",
    "input-gsp-zipf",
    "input-rate",
    "input-concurrency",
    "input-num-prompts",
]


class CaseEditor(Widget):
    can_focus = True

    class CaseUpdated(Message):
        def __init__(self, case: TestCase):
            super().__init__()
            self.case = case

    class FocusRequested(Message):
        pass

    class FocusReleased(Message):
        pass

    def __init__(self, case: TestCase | None = None, **kwargs):
        super().__init__(**kwargs)
        self._case = case or TestCase()

    @property
    def case(self) -> TestCase:
        return self._case

    @case.setter
    def case(self, value: TestCase):
        self._case = value
        if self.is_mounted:
            self._refresh_inputs()

    def compose(self) -> ComposeResult:
        c = self._case
        with Vertical(id="form-container"):
            yield Label("[b]Case Editor[/b]  [dim]↑↓:nav  Enter:next  Esc:save & back[/dim]", markup=True)

            yield Label("Name")
            yield Input(value=c.name, id="input-name", placeholder="Test case name")

            # Server
            yield Label("[b]Server[/b]", classes="form-section-title", markup=True)
            yield Button("▶ Load from env (FASTSTRESS_SERVER_*)", id="btn-load-env", variant="default")
            yield Label("Backend")
            yield RadioButton("sglang", id="radio-backend-sglang", value=c.server.backend == Backend.SGLANG)
            yield RadioButton("sglang-oai", id="radio-backend-sglang-oai", value=c.server.backend == Backend.SGLANG_OAI)
            yield Label("Host")
            yield Input(value=c.server.host, id="input-host", placeholder="127.0.0.1")
            yield Label("Port")
            yield Input(value=str(c.server.port), id="input-port", placeholder="30000")
            yield Label("Base URL (overrides host:port)")
            yield Input(value=c.server.base_url or "", id="input-base-url", placeholder="http://...")
            yield Label("API Key")
            yield Input(value=c.server.api_key or "", id="input-api-key", placeholder="sk-...", password=True)

            # Dataset
            yield Label("[b]Dataset[/b]", classes="form-section-title", markup=True)
            yield RadioButton("random-ids", id="radio-dataset-random-ids", value=c.dataset.dataset_type == DatasetType.RANDOM_IDS)
            yield RadioButton("sharegpt", id="radio-dataset-sharegpt", value=c.dataset.dataset_type == DatasetType.SHAREGPT)
            yield RadioButton("generated-shared-prefix", id="radio-dataset-gsp", value=c.dataset.dataset_type == DatasetType.GENERATED_SHARED_PREFIX)

            with Vertical(classes="dataset-group", id="group-random-ids"):
                yield Label("Input Length")
                yield Input(value=str(c.dataset.random_ids.input_len), id="input-random-input-len")
                yield Label("Output Length")
                yield Input(value=str(c.dataset.random_ids.output_len), id="input-random-output-len")
                yield Label("Range Ratio")
                yield Input(value=str(c.dataset.random_ids.range_ratio), id="input-random-range-ratio")

            with Vertical(classes="dataset-group", id="group-sharegpt"):
                yield Label("Dataset Path")
                yield Input(value=c.dataset.sharegpt.dataset_path, id="input-sharegpt-path", placeholder="/path/to/sharegpt.json")
                yield Label("Context Length (optional)")
                yield Input(value=str(c.dataset.sharegpt.context_len or ""), id="input-sharegpt-ctx")
                yield Label("Output Length (optional)")
                yield Input(value=str(c.dataset.sharegpt.output_len or ""), id="input-sharegpt-out")

            with Vertical(classes="dataset-group", id="group-gsp"):
                yield Label("Num Groups")
                yield Input(value=str(c.dataset.gsp.num_groups), id="input-gsp-groups")
                yield Label("Prompts/Group")
                yield Input(value=str(c.dataset.gsp.prompts_per_group), id="input-gsp-ppg")
                yield Label("System Prompt Length")
                yield Input(value=str(c.dataset.gsp.system_prompt_len), id="input-gsp-spl")
                yield Label("Question Length")
                yield Input(value=str(c.dataset.gsp.question_len), id="input-gsp-ql")
                yield Label("Output Length")
                yield Input(value=str(c.dataset.gsp.output_len), id="input-gsp-ol")
                yield Label("Group Distribution")
                yield RadioButton("uniform", id="radio-gsp-dist-uniform", value=c.dataset.gsp.group_distribution == "uniform")
                yield RadioButton("zipf", id="radio-gsp-dist-zipf", value=c.dataset.gsp.group_distribution == "zipf")
                yield Label("Zipf Alpha (when distribution=zipf)")
                yield Input(
                    value=str(c.dataset.gsp.zipf_alpha) if c.dataset.gsp.zipf_alpha else "",
                    id="input-gsp-zipf",
                    placeholder="1.0",
                )

            # Load
            yield Label("[b]Load[/b]", classes="form-section-title", markup=True)
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

    def on_mount(self) -> None:
        self._update_dataset_visibility(self._case.dataset.dataset_type.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-load-env":
            self._load_from_env()

    def _load_from_env(self) -> None:
        env_config = ServerConfig.from_env()
        self._set_backend_radio(env_config.backend.value)
        self.query_one("#input-host", Input).value = env_config.host
        self.query_one("#input-port", Input).value = str(env_config.port)
        self.query_one("#input-base-url", Input).value = env_config.base_url or ""
        self.query_one("#input-api-key", Input).value = env_config.api_key or ""

    def on_radio_button_changed(self, event: RadioButton.Changed) -> None:
        if not event.value:
            return
        btn_id = event.radio_button.id or ""
        # Backend group
        if btn_id.startswith("radio-backend-"):
            for rid in ("radio-backend-sglang", "radio-backend-sglang-oai"):
                if rid != btn_id:
                    self.query_one(f"#{rid}", RadioButton).value = False
        # Dataset group
        elif btn_id.startswith("radio-dataset-"):
            for rid in ("radio-dataset-random-ids", "radio-dataset-sharegpt", "radio-dataset-gsp"):
                if rid != btn_id:
                    self.query_one(f"#{rid}", RadioButton).value = False
            ds_map = {
                "radio-dataset-random-ids": "random-ids",
                "radio-dataset-sharegpt": "sharegpt",
                "radio-dataset-gsp": "generated-shared-prefix",
            }
            self._update_dataset_visibility(ds_map.get(btn_id, "random-ids"))
        # GSP distribution group
        elif btn_id.startswith("radio-gsp-dist-"):
            for rid in ("radio-gsp-dist-uniform", "radio-gsp-dist-zipf"):
                if rid != btn_id:
                    self.query_one(f"#{rid}", RadioButton).value = False

    # --- Navigation ---

    def _get_visible_fields(self) -> list[Widget]:
        """Get currently visible focusable fields in order."""
        visible = []
        current_dataset = self._get_selected_dataset()

        hidden_groups = {
            "random-ids": ("group-sharegpt", "group-gsp"),
            "sharegpt": ("group-random-ids", "group-gsp"),
            "generated-shared-prefix": ("group-random-ids", "group-sharegpt"),
        }
        hidden_ids = hidden_groups.get(current_dataset, ())

        for field_id in FIELD_ORDER:
            try:
                widget = self.query_one(f"#{field_id}")
                parent = widget.parent
                skip = False
                while parent and parent != self:
                    if hasattr(parent, "id") and parent.id in hidden_ids:
                        skip = True
                        break
                    parent = parent.parent
                if not skip:
                    visible.append(widget)
            except Exception:
                pass
        return visible

    def _focus_field_at(self, index: int) -> None:
        fields = self._get_visible_fields()
        if fields:
            idx = max(0, min(index, len(fields) - 1))
            fields[idx].focus()

    def _get_focused_index(self) -> int:
        focused = self.app.focused
        if focused is None:
            return -1
        fields = self._get_visible_fields()
        for i, field in enumerate(fields):
            if field is focused:
                return i
        # Walk up parents to find containing field
        node = focused
        while node:
            for i, field in enumerate(fields):
                if node is field:
                    return i
            node = node.parent
        return -1

    def focus_first_input(self) -> None:
        self._focus_field_at(0)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        idx = self._get_focused_index()
        fields = self._get_visible_fields()
        if idx >= 0 and idx < len(fields) - 1:
            fields[idx + 1].focus()
        else:
            self._save_and_release()

    def on_key(self, event: Key) -> None:
        focused = self.app.focused

        if event.key == "escape":
            idx = self._get_focused_index()
            if idx >= 0:
                self._save_and_release()
                event.prevent_default()
                event.stop()
            else:
                self.post_message(self.FocusReleased())
                event.prevent_default()
                event.stop()
            return

        if event.key == "up":
            idx = self._get_focused_index()
            if idx > 0:
                self._focus_field_at(idx - 1)
                event.prevent_default()
                event.stop()
            return

        if event.key == "down":
            idx = self._get_focused_index()
            fields = self._get_visible_fields()
            if idx >= 0 and idx < len(fields) - 1:
                self._focus_field_at(idx + 1)
                event.prevent_default()
                event.stop()
            elif idx == -1:
                self.focus_first_input()
                event.prevent_default()
                event.stop()
            return

        if event.key == "left":
            if isinstance(focused, Input) and focused.cursor_position == 0:
                self._save_and_release()
                event.prevent_default()
                event.stop()
            elif isinstance(focused, (RadioButton, Button)):
                self._save_and_release()
                event.prevent_default()
                event.stop()
            return

    def _save_and_release(self) -> None:
        case = self.collect_case()
        self._case = case
        self.post_message(self.CaseUpdated(case))
        self.screen.set_focus(None)
        self.post_message(self.FocusReleased())

    # --- Helpers ---

    def _get_selected_dataset(self) -> str:
        try:
            if self.query_one("#radio-dataset-sharegpt", RadioButton).value:
                return "sharegpt"
            if self.query_one("#radio-dataset-gsp", RadioButton).value:
                return "generated-shared-prefix"
        except Exception:
            pass
        return "random-ids"

    def _set_backend_radio(self, value: str) -> None:
        self.query_one("#radio-backend-sglang", RadioButton).value = (value == "sglang")
        self.query_one("#radio-backend-sglang-oai", RadioButton).value = (value == "sglang-oai")

    def _update_dataset_visibility(self, dataset_type: str) -> None:
        mapping = {
            "random-ids": "group-random-ids",
            "sharegpt": "group-sharegpt",
            "generated-shared-prefix": "group-gsp",
        }
        for key, group_id in mapping.items():
            try:
                group = self.query_one(f"#{group_id}")
                if key == dataset_type:
                    group.add_class("-visible")
                else:
                    group.remove_class("-visible")
            except Exception:
                pass

    def _refresh_inputs(self):
        c = self._case
        try:
            self.query_one("#input-name", Input).value = c.name
            self._set_backend_radio(c.server.backend.value)
            self.query_one("#input-host", Input).value = c.server.host
            self.query_one("#input-port", Input).value = str(c.server.port)
            self.query_one("#input-base-url", Input).value = c.server.base_url or ""
            self.query_one("#input-api-key", Input).value = c.server.api_key or ""
            self.query_one("#radio-dataset-random-ids", RadioButton).value = (c.dataset.dataset_type == DatasetType.RANDOM_IDS)
            self.query_one("#radio-dataset-sharegpt", RadioButton).value = (c.dataset.dataset_type == DatasetType.SHAREGPT)
            self.query_one("#radio-dataset-gsp", RadioButton).value = (c.dataset.dataset_type == DatasetType.GENERATED_SHARED_PREFIX)
            self.query_one("#input-random-input-len", Input).value = str(c.dataset.random_ids.input_len)
            self.query_one("#input-random-output-len", Input).value = str(c.dataset.random_ids.output_len)
            self.query_one("#input-random-range-ratio", Input).value = str(c.dataset.random_ids.range_ratio)
            self.query_one("#input-sharegpt-path", Input).value = c.dataset.sharegpt.dataset_path
            self.query_one("#input-sharegpt-ctx", Input).value = str(c.dataset.sharegpt.context_len or "")
            self.query_one("#input-sharegpt-out", Input).value = str(c.dataset.sharegpt.output_len or "")
            self.query_one("#input-gsp-groups", Input).value = str(c.dataset.gsp.num_groups)
            self.query_one("#input-gsp-ppg", Input).value = str(c.dataset.gsp.prompts_per_group)
            self.query_one("#input-gsp-spl", Input).value = str(c.dataset.gsp.system_prompt_len)
            self.query_one("#input-gsp-ql", Input).value = str(c.dataset.gsp.question_len)
            self.query_one("#input-gsp-ol", Input).value = str(c.dataset.gsp.output_len)
            self.query_one("#radio-gsp-dist-uniform", RadioButton).value = (c.dataset.gsp.group_distribution == "uniform")
            self.query_one("#radio-gsp-dist-zipf", RadioButton).value = (c.dataset.gsp.group_distribution == "zipf")
            self.query_one("#input-gsp-zipf", Input).value = str(c.dataset.gsp.zipf_alpha) if c.dataset.gsp.zipf_alpha else ""
            rate_str = "inf" if c.load.request_rate == float("inf") else str(c.load.request_rate)
            self.query_one("#input-rate", Input).value = rate_str
            self.query_one("#input-concurrency", Input).value = (
                str(c.load.max_concurrency) if c.load.max_concurrency else ""
            )
            self.query_one("#input-num-prompts", Input).value = str(c.load.num_prompts)
            self._update_dataset_visibility(c.dataset.dataset_type.value)
        except Exception:
            pass

    def collect_case(self) -> TestCase:
        name = self.query_one("#input-name", Input).value.strip() or "unnamed"

        backend = Backend.SGLANG
        if self.query_one("#radio-backend-sglang-oai", RadioButton).value:
            backend = Backend.SGLANG_OAI

        host = self.query_one("#input-host", Input).value.strip() or "127.0.0.1"
        port_str = self.query_one("#input-port", Input).value.strip()
        port = int(port_str) if port_str.isdigit() else 30000
        base_url = self.query_one("#input-base-url", Input).value.strip() or None
        api_key = self.query_one("#input-api-key", Input).value.strip() or None

        dataset_type = DatasetType.RANDOM_IDS
        if self.query_one("#radio-dataset-sharegpt", RadioButton).value:
            dataset_type = DatasetType.SHAREGPT
        elif self.query_one("#radio-dataset-gsp", RadioButton).value:
            dataset_type = DatasetType.GENERATED_SHARED_PREFIX

        random_ids = RandomIdsParams(
            input_len=self._int_val("input-random-input-len", 1024),
            output_len=self._int_val("input-random-output-len", 128),
            range_ratio=self._float_val("input-random-range-ratio", 1.0),
        )

        sharegpt_ctx = self._opt_int_val("input-sharegpt-ctx")
        sharegpt_out = self._opt_int_val("input-sharegpt-out")
        sharegpt = SharegptParams(
            dataset_path=self.query_one("#input-sharegpt-path", Input).value.strip(),
            context_len=sharegpt_ctx,
            output_len=sharegpt_out,
        )

        gsp_dist = "zipf" if self.query_one("#radio-gsp-dist-zipf", RadioButton).value else "uniform"
        zipf_str = self.query_one("#input-gsp-zipf", Input).value.strip()
        gsp = GspParams(
            num_groups=self._int_val("input-gsp-groups", 4),
            prompts_per_group=self._int_val("input-gsp-ppg", 8),
            system_prompt_len=self._int_val("input-gsp-spl", 512),
            question_len=self._int_val("input-gsp-ql", 128),
            output_len=self._int_val("input-gsp-ol", 128),
            group_distribution=gsp_dist,
            zipf_alpha=float(zipf_str) if zipf_str else None,
        )

        rate_str = self.query_one("#input-rate", Input).value.strip()
        rate = float("inf") if rate_str.lower() in ("inf", "") else float(rate_str)
        conc_str = self.query_one("#input-concurrency", Input).value.strip()
        concurrency = int(conc_str) if conc_str.isdigit() else None
        num_prompts = self._int_val("input-num-prompts", 100)

        return TestCase(
            name=name,
            server=ServerConfig(backend=backend, host=host, port=port, base_url=base_url, api_key=api_key),
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
        try:
            return int(v)
        except (ValueError, TypeError):
            return default

    def _float_val(self, input_id: str, default: float) -> float:
        v = self.query_one(f"#{input_id}", Input).value.strip()
        try:
            return float(v)
        except (ValueError, TypeError):
            return default

    def _opt_int_val(self, input_id: str) -> int | None:
        v = self.query_one(f"#{input_id}", Input).value.strip()
        try:
            return int(v) if v else None
        except (ValueError, TypeError):
            return None
