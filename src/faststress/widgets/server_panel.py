from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Label, RadioButton

from ..models import Backend, ServerConfig

FIELD_ORDER = [
    "btn-load-env",
    "radio-backend-sglang",
    "radio-backend-sglang-oai",
    "radio-backend-sglang-oai-chat",
    "input-host",
    "input-port",
    "input-base-url",
    "input-api-key",
    "input-model",
    "input-tokenizer",
]


class ServerPanel(Widget):
    can_focus = True

    class ServerUpdated(Message):
        def __init__(self, server: ServerConfig):
            super().__init__()
            self.server = server

    class FocusReleased(Message):
        """Emitted when user presses Esc to leave the panel."""
        pass

    class FocusUp(Message):
        """Emitted when user navigates up past the first field."""
        pass

    def __init__(self, server: ServerConfig | None = None, **kwargs):
        super().__init__(**kwargs)
        self._server = server or ServerConfig()

    @property
    def server(self) -> ServerConfig:
        return self._server

    @server.setter
    def server(self, value: ServerConfig):
        self._server = value
        if self.is_mounted:
            self._refresh_inputs()

    def compose(self) -> ComposeResult:
        s = self._server
        with Vertical(id="server-form"):
            yield Label("[b]Server[/b]  [dim]↑↓:nav  Enter:next  Esc:save[/dim]", markup=True)
            yield Button("▶ Load from env", id="btn-load-env", variant="default")
            yield Label("Backend")
            yield RadioButton("sglang", id="radio-backend-sglang", value=s.backend == Backend.SGLANG)
            yield RadioButton("sglang-oai", id="radio-backend-sglang-oai", value=s.backend == Backend.SGLANG_OAI)
            yield RadioButton("sglang-oai-chat", id="radio-backend-sglang-oai-chat", value=s.backend == Backend.SGLANG_OAI_CHAT)
            yield Label("Host")
            yield Input(value=s.host, id="input-host", placeholder="127.0.0.1")
            yield Label("Port")
            yield Input(value=str(s.port), id="input-port", placeholder="30000")
            yield Label("Base URL")
            yield Input(value=s.base_url or "", id="input-base-url", placeholder="http://...")
            yield Label("API Key")
            yield Input(value=s.api_key or "", id="input-api-key", placeholder="sk-...", password=True)
            yield Label("Model")
            yield Input(value=s.model or "", id="input-model", placeholder="/preset-models/QwQ-32B")
            yield Label("Tokenizer")
            yield Input(value=s.tokenizer or "", id="input-tokenizer", placeholder="Qwen/QwQ-32B")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-load-env":
            self._load_from_env()

    def _load_from_env(self) -> None:
        env_config = ServerConfig.from_env()
        self._server = env_config
        self._refresh_inputs()
        self.post_message(self.ServerUpdated(env_config))

    def on_radio_button_changed(self, event: RadioButton.Changed) -> None:
        if not event.value:
            return
        btn_id = event.radio_button.id or ""
        if btn_id.startswith("radio-backend-"):
            for rid in ("radio-backend-sglang", "radio-backend-sglang-oai", "radio-backend-sglang-oai-chat"):
                if rid != btn_id:
                    self.query_one(f"#{rid}", RadioButton).value = False

    # --- Navigation ---

    def _get_fields(self) -> list[Widget]:
        fields = []
        for field_id in FIELD_ORDER:
            try:
                fields.append(self.query_one(f"#{field_id}"))
            except Exception:
                pass
        return fields

    def _get_focused_index(self) -> int:
        focused = self.app.focused
        if focused is None:
            return -1
        fields = self._get_fields()
        for i, field in enumerate(fields):
            if field is focused:
                return i
        node = focused
        while node:
            for i, field in enumerate(fields):
                if node is field:
                    return i
            node = node.parent
        return -1

    def focus_first_input(self) -> None:
        fields = self._get_fields()
        if fields:
            fields[0].focus()

    def focus_last_input(self) -> None:
        fields = self._get_fields()
        if fields:
            fields[-1].focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        idx = self._get_focused_index()
        fields = self._get_fields()
        if idx >= 0 and idx < len(fields) - 1:
            fields[idx + 1].focus()
        else:
            self._save()

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self._save()
            self.post_message(self.FocusReleased())
            event.prevent_default()
            event.stop()
            return

        if event.key == "up":
            idx = self._get_focused_index()
            if idx > 0:
                fields = self._get_fields()
                fields[idx - 1].focus()
                event.prevent_default()
                event.stop()
            elif idx == 0:
                self._save()
                self.post_message(self.FocusUp())
                event.prevent_default()
                event.stop()
            return

        if event.key == "down":
            idx = self._get_focused_index()
            fields = self._get_fields()
            if idx >= 0 and idx < len(fields) - 1:
                fields[idx + 1].focus()
                event.prevent_default()
                event.stop()
            elif idx == -1:
                self.focus_first_input()
                event.prevent_default()
                event.stop()
            return

    def _save(self) -> None:
        server = self.collect_server()
        self._server = server
        self.post_message(self.ServerUpdated(server))

    def collect_server(self) -> ServerConfig:
        backend = Backend.SGLANG
        if self.query_one("#radio-backend-sglang-oai", RadioButton).value:
            backend = Backend.SGLANG_OAI
        elif self.query_one("#radio-backend-sglang-oai-chat", RadioButton).value:
            backend = Backend.SGLANG_OAI_CHAT

        host = self.query_one("#input-host", Input).value.strip() or "127.0.0.1"
        port_str = self.query_one("#input-port", Input).value.strip()
        port = int(port_str) if port_str.isdigit() else 30000
        base_url = self.query_one("#input-base-url", Input).value.strip() or None
        api_key = self.query_one("#input-api-key", Input).value.strip() or None
        model = self.query_one("#input-model", Input).value.strip() or None
        tokenizer = self.query_one("#input-tokenizer", Input).value.strip() or None

        return ServerConfig(
            backend=backend,
            host=host,
            port=port,
            base_url=base_url,
            api_key=api_key,
            model=model,
            tokenizer=tokenizer,
        )

    def _refresh_inputs(self):
        s = self._server
        try:
            self.query_one("#radio-backend-sglang", RadioButton).value = (s.backend == Backend.SGLANG)
            self.query_one("#radio-backend-sglang-oai", RadioButton).value = (s.backend == Backend.SGLANG_OAI)
            self.query_one("#radio-backend-sglang-oai-chat", RadioButton).value = (s.backend == Backend.SGLANG_OAI_CHAT)
            self.query_one("#input-host", Input).value = s.host
            self.query_one("#input-port", Input).value = str(s.port)
            self.query_one("#input-base-url", Input).value = s.base_url or ""
            self.query_one("#input-api-key", Input).value = s.api_key or ""
            self.query_one("#input-model", Input).value = s.model or ""
            self.query_one("#input-tokenizer", Input).value = s.tokenizer or ""
        except Exception:
            pass
