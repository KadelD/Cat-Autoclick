"""Legacy CustomTkinter entry point (fallback during PySide6 migration)."""

from app.ui_ctk.main_window import run_app


def main() -> None:
    """Start the classic Cat Autoclick UI."""
    run_app()


if __name__ == "__main__":
    main()
