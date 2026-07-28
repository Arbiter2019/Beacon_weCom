import json
from pathlib import Path

import typer

from wecom_app.core.config import get_settings
from wecom_app.db.session import SessionLocal
from wecom_app.services.employee_import import import_employees_csv
from wecom_app.worker import run_once

app = typer.Typer(help="Operate the WeCom archive service.")
callback_app = typer.Typer(help="Callback helpers.")
import_app = typer.Typer(help="Import local data files.")
sync_app = typer.Typer(help="Manual sync helpers.")
app.add_typer(callback_app, name="callback")
app.add_typer(import_app, name="import")
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
        "attachment_storage_backend": settings.attachment_storage_backend,
        "aliyun_oss_bucket": settings.aliyun_oss_bucket,
        "aliyun_oss_prefix": settings.aliyun_oss_prefix_normalized,
        "aliyun_oss_internal_endpoint": settings.aliyun_oss_internal_endpoint,
    }
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@import_app.command("employees")
def import_employees(file: Path = typer.Option(..., "--file", exists=True, readable=True)) -> None:
    with SessionLocal() as db:
        result = import_employees_csv(db, file)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@sync_app.command("once")
def sync_once(type: str = typer.Option("message", "--type")) -> None:
    result = run_once(type)
    typer.echo(json.dumps(result, ensure_ascii=False))


@sync_app.command("external-contacts")
def sync_external_contacts_cmd(
    userids: list[str] = typer.Option([], "--userid", help="Specific userids to sync (defaults to all enabled)"),
) -> None:
    """Pull external contacts from WeCom API and upsert into DB."""
    from wecom_app.services.external_contact_sync import sync_external_contacts
    from wecom_app.wecom.customer_client import WeComCustomerClient

    settings = get_settings()
    if not settings.customer_api_secret:
        typer.echo(json.dumps({"ok": False, "error": "WECOM_CUSTOMER_API_SECRET not configured"}))
        raise typer.Exit(1)

    client = WeComCustomerClient(settings.wecom_corp_id, settings.customer_api_secret)
    with SessionLocal() as db:
        result = sync_external_contacts(db, client, userids=userids or None)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
