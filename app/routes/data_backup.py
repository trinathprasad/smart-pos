from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy.engine import make_url

from ..extensions import db
from ..schema import upgrade_category_schema


data_backup_bp = Blueprint("data_backup", __name__, url_prefix="/data-backup")

BACKUP_NAME_PATTERN = re.compile(r"^billing-(?:backup|safety)-\d{8}-\d{6}-\d{6}\.db$")
REQUIRED_TABLES = {
    "customer",
    "customer_ledger",
    "product",
    "sale",
    "sale_item",
    "shop_setting",
}


class BackupError(Exception):
    """A safe, user-facing backup or restore error."""


def _database_path() -> Path:
    url = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"])
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        raise BackupError("Data backup is available only when the application uses a file-based SQLite database.")
    return Path(url.database).expanduser().resolve()


def _backup_dir() -> Path:
    return Path(current_app.config["BACKUP_DIR"]).expanduser().resolve()


def _safe_backup_path(filename: str) -> Path:
    if not filename or not BACKUP_NAME_PATTERN.fullmatch(filename):
        raise BackupError("That backup filename is not valid for this application.")
    backup_dir = _backup_dir()
    path = (backup_dir / filename).resolve()
    if path.parent != backup_dir:
        raise BackupError("That backup location is not allowed.")
    return path


def _required_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    return {row[0] for row in rows}


def _validate_database(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "The backup file is missing."
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA query_only = ON")
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                return False, "SQLite integrity validation failed."
            missing = REQUIRED_TABLES - _required_tables(connection)
            if missing:
                return False, "The file is missing required application tables."
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        return False, "The file is not a readable SQLite database."
    return True, "Valid application backup."


def _copy_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(str(source))
    destination_connection = sqlite3.connect(str(destination))
    try:
        source_connection.backup(destination_connection)
        destination_connection.commit()
    finally:
        destination_connection.close()
        source_connection.close()


def _dispose_database_connections() -> None:
    """Close this request's SQLAlchemy session and idle pool connections.

    Checked-out connections are not force-closed because they may belong to
    unrelated work. A restore must stop safely if one remains active.
    """
    db.session.remove()
    pool = db.engine.pool
    checked_out = pool.checkedout() if hasattr(pool, "checkedout") else 0
    if checked_out:
        raise BackupError(
            "The database is still in use by another application operation. "
            "Close other billing activity and try restoring again."
        )
    db.engine.dispose(close=True)

def _restore_database_in_place(source: Path, destination: Path) -> None:
    """Restore with SQLite's backup API without renaming the live Windows file."""
    source_connection = None
    destination_connection = None
    try:
        source_connection = sqlite3.connect(
            f"file:{source.as_posix()}?mode=ro",
            uri=True,
        )
        destination_connection = sqlite3.connect(str(destination), timeout=30)
        destination_connection.execute("PRAGMA busy_timeout = 30000")
        source_connection.backup(destination_connection, pages=100, sleep=0.1)
        destination_connection.commit()
    except Exception:
        if destination_connection is not None:
            destination_connection.rollback()
        raise
    finally:
        if source_connection is not None:
            source_connection.close()
        if destination_connection is not None:
            destination_connection.close()


def _timestamped_name(kind: str) -> str:
    now = datetime.now(timezone.utc)
    return f"billing-{kind}-{now:%Y%m%d-%H%M%S-%f}.db"


def _create_backup(kind: str = "backup") -> Path:
    database_path = _database_path()
    if not database_path.is_file():
        raise BackupError("The application database file does not exist.")
    backup_dir = _backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / _timestamped_name(kind)
    _copy_database(database_path, destination)
    valid, reason = _validate_database(destination)
    if not valid:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise BackupError(f"The backup could not be validated: {reason}")
    return destination


def _backup_rows() -> list[dict]:
    backup_dir = _backup_dir()
    rows = []
    try:
        candidates = sorted(
            (path for path in backup_dir.iterdir() if path.is_file() and BACKUP_NAME_PATTERN.fullmatch(path.name)),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return rows
    for path in candidates:
        try:
            stat = path.stat()
            valid, reason = _validate_database(path)
        except OSError:
            valid, reason, stat = False, "The backup file could not be read.", None
        rows.append(
            {
                "filename": path.name,
                "created_at": datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc) if stat else None,
                "size": stat.st_size if stat else None,
                "valid": valid,
                "validation_message": reason,
            }
        )
    return rows


@data_backup_bp.route("/")
def index():
    try:
        database_path = _database_path()
        database_exists = database_path.is_file()
        database_size = database_path.stat().st_size if database_exists else None
        database_status = "Available" if database_exists else "Unavailable"
        database_status_class = "success" if database_exists else "danger"
    except BackupError as error:
        database_path = None
        database_size = None
        database_status = "Unavailable"
        database_status_class = "danger"
        flash(str(error), "danger")
    return render_template(
        "data_backup/index.html",
        database_path=database_path,
        database_size=database_size,
        database_status=database_status,
        database_status_class=database_status_class,
        backup_dir=_backup_dir(),
        backups=_backup_rows(),
    )


@data_backup_bp.route("/create", methods=["POST"])
def create():
    try:
        backup = _create_backup()
        flash(f"Backup created successfully: {backup.name}", "success")
    except (BackupError, OSError, sqlite3.Error) as error:
        current_app.logger.exception("Could not create database backup")
        flash(f"Backup could not be created: {error}", "danger")
    return redirect(url_for("data_backup.index"))


@data_backup_bp.route("/restore", methods=["POST"])
def restore():
    filename = request.form.get("filename", "")
    if request.form.get("confirm") != "1":
        flash("Confirm that you understand the current application data will be replaced.", "danger")
        return redirect(url_for("data_backup.index"))

    try:
        selected_backup = _safe_backup_path(filename)
        valid, reason = _validate_database(selected_backup)
        if not valid:
            raise BackupError(f"Restore rejected: {reason}")

        database_path = _database_path()
        safety_backup = _create_backup("safety")
        valid, reason = _validate_database(safety_backup)
        if not valid:
            raise BackupError(f"Safety backup could not be validated: {reason}")

        # Remove request-scoped sessions and close pooled SQLAlchemy connections
        # before opening the live file directly. In-place SQLite backup avoids a
        # Windows rename over a file that another process may still have open.
        _dispose_database_connections()
        try:
            _restore_database_in_place(selected_backup, database_path)
        except BackupError:
            raise
        except Exception as restore_error:
            try:
                _restore_database_in_place(safety_backup, database_path)
            except Exception as recovery_error:
                raise BackupError(
                    "Database restore failed. The verified safety backup was retained "
                    "for manual recovery."
                ) from recovery_error
            raise BackupError(
                "Database restore failed, and the original database was recovered "
                "from the safety backup."
            ) from restore_error

        upgrade_category_schema()

        valid, reason = _validate_database(database_path)
        if not valid:
            raise BackupError(f"Restored database could not be validated: {reason}")

        flash(f"Database restored successfully from {selected_backup.name}.", "success")
    except (BackupError, OSError, sqlite3.Error) as error:
        current_app.logger.exception("Could not restore database backup")
        flash(f"Database restore failed safely: {error}", "danger")
    return redirect(url_for("data_backup.index"))
