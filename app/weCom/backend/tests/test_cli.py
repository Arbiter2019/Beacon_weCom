from typer.testing import CliRunner

from wecom_app.cli import app


def test_callback_urls_command_lists_paths():
    result = CliRunner().invoke(app, ["callback", "urls"])

    assert result.exit_code == 0
    assert "/callbacks/wecom/contact" in result.output
    assert "/callbacks/wecom/archive-event" in result.output
