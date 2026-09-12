"""Application entry point for Data Security System."""

import importlib
from typing import Any

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError(
        "CustomTkinter is not installed for this Python interpreter. "
        "Run 'py -m pip install --user -r requirements.txt' and start with 'py main.py', "
        "or install into this interpreter with 'python -m pip install --user -r requirements.txt'."
    ) from error

from config import APP_NAME, IDLE_TIMEOUT_SECONDS
from core.database import Database
from core.vault import VaultService
from ui.app import DashboardApp, LoginView


class Application(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1240x780")
        self.minsize(1050, 680)
        self.configure(fg_color="#101418")
        self.database = Database()
        self.service = VaultService(self.database)
        self.idle_job = None
        self.activity_bindings: list[tuple[str, str]] = []
        self._show_login()
        root = self.winfo_toplevel()
        for sequence in ("<KeyPress>", "<Button>"):
            binding_id = root.bind(sequence, self._activity, add="+")
            self.activity_bindings.append((sequence, binding_id))
        self._reset_idle_timer()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _show_login(self):
        for child in self.winfo_children(): child.destroy()
        LoginView(self, self.service, self._show_dashboard).pack(fill="both", expand=True)

    def _show_dashboard(self):
        for child in self.winfo_children(): child.destroy()
        DashboardApp(self, self.service, self.database, self._lock).pack(fill="both", expand=True)
        self._reset_idle_timer()

    def _lock(self):
        self.service.lock()
        self.database.add_audit("LOCK", "Workspace locked")
        self._show_login()

    def _activity(self, _event=None):
        if self.service.master_key:
            self._reset_idle_timer()

    def _reset_idle_timer(self):
        if self.idle_job: self.after_cancel(self.idle_job)
        if self.service.master_key:
            self.idle_job = self.after(IDLE_TIMEOUT_SECONDS * 1000, self._lock)

    def _close(self):
        self.service.lock()
        self.database.close()
        root = self.winfo_toplevel()
        for sequence, binding_id in self.activity_bindings:
            try:
                root.unbind(sequence, binding_id)
            except (AttributeError, RuntimeError):
                pass
        self.destroy()


if __name__ == "__main__":
    Application().mainloop()
