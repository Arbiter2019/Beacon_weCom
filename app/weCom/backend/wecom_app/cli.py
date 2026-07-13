import json

import typer

from wecom_app.core.config import get_settings
from wecom_app.worker import run_once

app = typer.Typer(help="Operate the WeCom archive service.")
callback_app = typer.Typer(help="Callback helpers.")
sync_app = typer.Typer(help="Manual sync helpers.")
app.add_typer(callback_app, name="callback")
app.add_typer(sync_app, name="sync")


CALLBACK_PATHS = {
    "通讯录回调": "/callbacks/wecom/contact",
    "客户联系回调": "/callbacks/wecom/customer",
    "客户群回调": "/callbacks/wecom/customer-chat",
    "会话存档同意回调": "/callbacks/wecom/archive-consent",
    "产生会话回调": "/callbacks/wecom/archive-event",
}


@callback_app.command("urls")
def callback_urls() -> None:
    settings = get_settings()
    for label, path in CALLBACK_PATHS.items():
        typer.echo(f"{label}: {settings.api_base_url.rstrip('/')}{path}")


@callback_app.command("verify")
def callback_verify() -> None:
    settings = get_settings()
    missing = []
    if not settings.api_base_url:
        missing.append("API_BASE_URL")
    for name in [
        "WECOM_CONTACT_CALLBACK_TOKEN",
        "WECOM_CUSTOMER_CALLBACK_TOKEN",
        "WECOM_ARCHIVE_CALLBACK_TOKEN",
    ]:
        if not getattr(settings, name.lower()):
            missing.append(name)
    if missing:
        typer.echo(json.dumps({"ok": False, "missing": missing}, ensure_ascii=False))
        raise typer.Exit(1)
    typer.echo(json.dumps({"ok": True, "callback_count": len(CALLBACK_PATHS)}, ensure_ascii=False))


@app.command("health")
def health() -> None:
    settings = get_settings()
    result = {
        "api_base_url": settings.api_base_url,
        "sdk_dir_exists": settings.wecom_sdk_lib_dir.exists(),
        "private_key_exists": settings.wecom_archive_private_key_path.exists(),
        "attachment_root": str(settings.attachment_storage_root),
        "attachment_root_exists": settings.attachment_storage_root.exists(),
    }
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@sync_app.command("once")
def sync_once(type: str = typer.Option("message", "--type")) -> None:
    result = run_once(type)
    typer.echo(json.dumps(result, ensure_ascii=False))
