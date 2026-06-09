import pytest

from faststress.app import FastStressApp
from faststress.models import DatasetType, ServerConfig, TestCase
from faststress.widgets.case_editor import CaseEditor
from faststress.widgets.case_list import CaseListPanel
from faststress.widgets.run_panel import RunPanel
from faststress.widgets.server_panel import ServerPanel


@pytest.mark.asyncio
async def test_app_starts_with_layout():
    """Verify all four panels are rendered in the 2x2 grid."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        assert app.query_one("#case-list-panel") is not None
        assert app.query_one("#server-panel") is not None
        assert app.query_one("#editor-panel") is not None
        assert app.query_one("#run-panel") is not None


@pytest.mark.asyncio
async def test_app_has_server_panel():
    """App has a server config panel."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        server_panel = app.query_one(ServerPanel)
        assert server_panel is not None
        assert isinstance(server_panel.server, ServerConfig)


@pytest.mark.asyncio
async def test_app_has_default_case():
    """App starts with at least one case."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        assert len(app.cases) >= 1
        assert app.cases[0].name == "default"


@pytest.mark.asyncio
async def test_add_case():
    """Pressing 'a' adds a new test case."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        initial_count = len(app.cases)
        await pilot.press("a")
        assert len(app.cases) == initial_count + 1
        assert app.cases[-1].name == f"case-{initial_count + 1}"


@pytest.mark.asyncio
async def test_delete_case():
    """Pressing 'd' removes a case (when more than one exists)."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        await pilot.press("a")  # now 2 cases
        assert len(app.cases) == 2
        await pilot.press("d")
        assert len(app.cases) == 1


@pytest.mark.asyncio
async def test_cannot_delete_last_case():
    """Cannot delete the only remaining case."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        assert len(app.cases) == 1
        await pilot.press("d")
        assert len(app.cases) == 1


@pytest.mark.asyncio
async def test_dataset_visibility_random_ids():
    """Default dataset is random-ids, so that group should be visible."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        random_group = app.query_one("#group-random-ids")
        sharegpt_group = app.query_one("#group-sharegpt")
        gsp_group = app.query_one("#group-gsp")
        assert random_group.has_class("-visible")
        assert not sharegpt_group.has_class("-visible")
        assert not gsp_group.has_class("-visible")


@pytest.mark.asyncio
async def test_dataset_visibility_switch():
    """Switching dataset type updates group visibility."""
    from textual.widgets import RadioButton

    app = FastStressApp()
    async with app.run_test() as pilot:
        radio = app.query_one("#radio-dataset-sharegpt", RadioButton)
        radio.value = True
        await pilot.pause()

        random_group = app.query_one("#group-random-ids")
        sharegpt_group = app.query_one("#group-sharegpt")
        assert not random_group.has_class("-visible")
        assert sharegpt_group.has_class("-visible")


@pytest.mark.asyncio
async def test_editor_collect_case():
    """CaseEditor.collect_case() builds a valid TestCase from input values."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        editor = app.query_one(CaseEditor)
        case = editor.collect_case()
        assert case.name == "default"
        assert case.load.num_prompts == 100


@pytest.mark.asyncio
async def test_save_on_escape():
    """Esc in input saves current editor state and returns focus to list."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        name_input = app.query_one("#input-name")
        name_input.focus()
        await pilot.pause()
        name_input.value = "renamed-case"
        await pilot.press("escape")
        await pilot.pause()
        assert app.cases[0].name == "renamed-case"


@pytest.mark.asyncio
async def test_optimizer_screen():
    """Pressing 'o' opens the optimizer screen."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        await pilot.press("o")
        await pilot.pause()
        screen = app.screen
        assert screen.query_one("#optimizer-form") is not None
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_run_panel_output():
    """RunPanel can display output and clear it."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        run_panel = app.query_one(RunPanel)
        run_panel.append_output("test line 1")
        run_panel.append_output("test line 2")
        run_panel.show_result("done!")
        await pilot.pause()


@pytest.mark.asyncio
async def test_run_panel_clear():
    """RunPanel.clear_output works."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        run_panel = app.query_one(RunPanel)
        run_panel.append_output("something")
        run_panel.clear_output()
        await pilot.pause()


@pytest.mark.asyncio
async def test_arrow_nav_to_editor():
    """Right arrow focuses editor's first input."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        await pilot.press("right")
        await pilot.pause()
        from textual.widgets import Input
        assert isinstance(app.focused, Input)


@pytest.mark.asyncio
async def test_enter_moves_to_next_field():
    """Enter in an input moves focus to the next field."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        name_input = app.query_one("#input-name")
        name_input.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        from textual.widgets import RadioButton
        focused = app.focused
        assert isinstance(focused, RadioButton)


@pytest.mark.asyncio
async def test_server_config_shared():
    """All cases share the same server config from the app."""
    app = FastStressApp()
    async with app.run_test() as pilot:
        assert app.server_config is not None
        assert app.server_config.host == "127.0.0.1"
