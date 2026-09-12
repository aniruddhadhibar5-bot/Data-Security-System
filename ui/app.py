"""Desktop interface for Data Security System."""

import importlib
import secrets
import string
import tkinter as tk
from typing import Any
from pathlib import Path
from tkinter import filedialog, messagebox

try:
    ctk: Any = importlib.import_module("customtkinter")
except ModuleNotFoundError as error:
    raise RuntimeError("CustomTkinter is required. Run: python -m pip install -r requirements.txt") from error

from config import APP_NAME, APP_VERSION, CLIPBOARD_CLEAR_SECONDS, CREDITS, IDLE_TIMEOUT_SECONDS
from core.audit import AuditService
from core.catalog import CatalogService
from core.database import Database
from core.diagnostics import DiagnosticsService
from core.metrics import MetricsService
from core.passwords import PasswordGenerator, PasswordStrength
from core.settings import SettingsService
from core.policy import RateLimiter, SecurityPolicy
from core.vault import VaultService
from ui.analytics_view import AnalyticsView
from ui.catalog_view import CatalogView
from ui.command_palette import CommandRegistry, bind_palette
from ui.dashboard_view import DashboardView
from ui.motion import HoverMotion, MotionGroup, PressMotion, tween
from ui.security_center import SecurityCenterView

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LoginView(ctk.CTkFrame):
    def __init__(self, master, service: VaultService, on_success):
        super().__init__(master, fg_color="#101418")
        self.service = service
        self.on_success = on_success
        self.first_run = not service.is_configured
        self.policy = SecurityPolicy()
        self.login_limiter = RateLimiter(self.policy.maximum_failed_logins)
        self.motion = MotionGroup()
        self._build()

    def _build(self):
        panel = ctk.CTkFrame(self, width=460, height=510, corner_radius=14, fg_color="#171d22")
        panel.place(relx=0.5, rely=0.56, anchor="center")
        self.motion.add(tween(self, 0.56, 0.5, duration=360, steps=18, on_step=lambda value: panel.place_configure(rely=value)))
        panel.grid_propagate(False)
        ctk.CTkLabel(panel, text="DATA SECURITY SYSTEM", font=ctk.CTkFont(size=24, weight="bold"), text_color="#f1f4f6").pack(pady=(48, 8))
        ctk.CTkLabel(panel, text="Private storage, clearly organized.", text_color="#8e9aa4", font=ctk.CTkFont(size=13)).pack(pady=(0, 30))
        self.password = ctk.CTkEntry(panel, width=330, height=42, placeholder_text="Create master password" if self.first_run else "Master password", show="*")
        self.password.pack(pady=8)
        if self.first_run:
            self.confirm = ctk.CTkEntry(panel, width=330, height=42, placeholder_text="Confirm master password", show="*")
            self.confirm.pack(pady=8)
        self.pin = ctk.CTkEntry(panel, width=330, height=42, placeholder_text="6-digit verification PIN", show="*")
        self.pin.pack(pady=8)
        submit = ctk.CTkButton(panel, width=330, height=42, text="Create secure vault" if self.first_run else "Unlock workspace", command=self._submit)
        submit.pack(pady=(22, 10))
        HoverMotion(submit, "#1f6876", "#80c5d2")
        PressMotion(submit, "#2c5962")
        ctk.CTkButton(panel, text="Forgot master password?", width=220, height=28, fg_color="transparent", hover_color="#24323a", text_color="#9aa7ae", command=self._forgot_password).pack(pady=(2, 6))
        ctk.CTkLabel(panel, text="Simulated 2FA verification is required on every login.", text_color="#68747d", font=ctk.CTkFont(size=11)).pack(pady=8)
        ctk.CTkLabel(panel, text=f"{CREDITS}  |  v{APP_VERSION}", text_color="#68747d", font=ctk.CTkFont(size=10)).pack(side="bottom", pady=24)

    def _submit(self):
        password, pin = self.password.get(), self.pin.get()
        if self.login_limiter.blocked:
            messagebox.showerror("Authentication locked", "Too many failed attempts. Close and reopen the application before trying again.")
            return
        if self.first_run:
            password_result = self.policy.validate_master_password(password)
        else:
            password_result = True
        pin_result = self.policy.validate_pin(pin)
        if not password_result or not pin_result:
            messagebox.showerror("Authentication", getattr(password_result, "message", "") or getattr(pin_result, "message", "Invalid PIN"))
            return
        if self.first_run:
            if password != self.confirm.get():
                messagebox.showerror("Authentication", "The master passwords do not match.")
                return
            self.service.configure_master(password, pin)
        elif not self.service.authenticate(password, pin):
            self.login_limiter.record_failure()
            messagebox.showerror("Authentication failed", "The master password or PIN is incorrect.")
            return
        self.login_limiter.record_success()
        self.on_success()

    def _forgot_password(self):
        messagebox.showinfo(
            "Master password recovery",
            "The master password cannot be recovered or bypassed because it derives the vault encryption key. "
            "Check for an encrypted .dssbackup file first. If no backup exists, close the app and run "
            "python reset_vault.py --confirm RESET. The old encrypted data will be archived, not deleted, "
            "but it will still require the original password.",
        )

    def destroy(self):
        self.motion.cancel_all()
        super().destroy()


class DashboardApp(ctk.CTkFrame):
    def __init__(self, master, service: VaultService, database: Database, on_lock):
        super().__init__(master, fg_color="#101418")
        self.service, self.database, self.on_lock = service, database, on_lock
        self.diagnostics = DiagnosticsService(database)
        self.metrics = MetricsService(database)
        self.audit = AuditService(database)
        self.catalog = CatalogService(database)
        self.settings = SettingsService(database)
        self.password_generator = PasswordGenerator()
        self.password_strength = PasswordStrength()
        self.current_view = None
        self.last_clipboard_job = None
        self.recovery_revealed = False
        self.nav_map = {}
        self.commands = CommandRegistry()
        self._build_shell()
        self._register_commands()
        self.unbind_palette = bind_palette(self, self.commands)
        self.show_dashboard()

    def _build_shell(self):
        self.sidebar = ctk.CTkFrame(self, width=232, corner_radius=0, fg_color="#171d22")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ctk.CTkLabel(self.sidebar, text="DSS", font=ctk.CTkFont(size=30, weight="bold"), text_color="#76b7c5").pack(anchor="w", padx=26, pady=(28, 0))
        ctk.CTkLabel(self.sidebar, text="SECURE WORKSPACE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#68747d").pack(anchor="w", padx=28, pady=(0, 28))
        self.nav_buttons = []
        for text, command in [("Dashboard", self.show_dashboard), ("File & Photo Vault", self.show_files), ("Password Manager", self.show_passwords), ("Central Recovery", self.show_recovery), ("Secure Notes", self.show_notes), ("Organization", self.show_organization), ("Security Center", self.show_security_center), ("Analytics", self.show_analytics), ("Diagnostics & Audit", self.show_diagnostics), ("Settings & Backup", self.show_settings)]:
            button = ctk.CTkButton(self.sidebar, text=text, anchor="w", height=40, fg_color="transparent", hover_color="#24323a", text_color="#b3bec5", command=command)
            button.pack(fill="x", padx=14, pady=2)
            self.nav_buttons.append(button)
            self.nav_map[text] = button
            HoverMotion(button, "transparent", "#24323a")
            PressMotion(button, "#376c78")
        ctk.CTkButton(self.sidebar, text="Lock workspace", height=38, fg_color="#3a2729", hover_color="#593034", command=self.on_lock).pack(side="bottom", fill="x", padx=14, pady=(8, 24))
        ctk.CTkLabel(self.sidebar, text=CREDITS, wraplength=175, justify="left", text_color="#68747d", font=ctk.CTkFont(size=10)).pack(side="bottom", padx=24, pady=(0, 14))
        self.content = ctk.CTkFrame(self, fg_color="#101418", corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

    def _header(self, title, subtitle):
        for child in self.content.winfo_children(): child.destroy()
        self.current_view = title
        self._set_active_navigation(title)
        top = ctk.CTkFrame(self.content, fg_color="transparent")
        top.pack(fill="x", padx=38, pady=(32, 22))
        ctk.CTkLabel(top, text=title, font=ctk.CTkFont(size=28, weight="bold"), text_color="#f1f4f6").pack(anchor="w")
        ctk.CTkLabel(top, text=subtitle, text_color="#8e9aa4", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(5, 0))

    def _set_active_navigation(self, title):
        section_map = {
            "Security overview": "Dashboard",
            "File & Photo Vault": "File & Photo Vault",
            "Password Manager": "Password Manager",
            "Central Recovery": "Central Recovery",
            "Secure Notes": "Secure Notes",
            "Organization": "Organization",
            "Security center": "Security Center",
            "Analytics": "Analytics",
            "Diagnostics & Audit Log": "Diagnostics & Audit",
            "Settings & Backup": "Settings & Backup",
        }
        active = section_map.get(title)
        for label, button in self.nav_map.items():
            button.configure(fg_color="#24323a" if label == active else "transparent", text_color="#f1f4f6" if label == active else "#b3bec5")

    def _register_commands(self):
        self.commands.register("Open dashboard", "View workspace status and quick actions", self.show_dashboard, "home", "overview")
        self.commands.register("Open file vault", "Encrypt or restore local files", self.show_files, "files", "documents", "photos")
        self.commands.register("Open password manager", "Store, search, and copy credentials", self.show_passwords, "passwords", "credentials")
        self.commands.register("Open secure notes", "Create and edit encrypted notes", self.show_notes, "notes", "private")
        self.commands.register("Open organization", "Search, tag, favorite, and archive records", self.show_organization, "search", "tags", "favorites")
        self.commands.register("Open security center", "Review posture and recommendations", self.show_security_center, "security", "score", "recommendations")
        self.commands.register("Open analytics", "Review audit metrics and health", self.show_analytics, "audit", "events", "metrics")
        self.commands.register("Open recovery", "Review protected item keys", self.show_recovery, "keys", "recovery")
        self.commands.register("Open settings", "Change appearance and export backups", self.show_settings, "preferences", "backup")
        self.commands.register("Lock workspace", "Clear the active master key", self.on_lock, "lock", "secure")

    def _card(self, parent, title, value, detail, column):
        card = ctk.CTkFrame(parent, fg_color="#171d22", corner_radius=10)
        card.grid(row=0, column=column, sticky="nsew", padx=6)
        ctk.CTkLabel(card, text=title.upper(), text_color="#7f8c95", font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=18, pady=(18, 7))
        ctk.CTkLabel(card, text=value, text_color="#f1f4f6", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=18)
        ctk.CTkLabel(card, text=detail, text_color="#76b7c5", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=18, pady=(4, 18))

    def show_dashboard(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.current_view = "Security overview"
        self._set_active_navigation("Security overview")
        DashboardView(
            self.content,
            self.database,
            self.service,
            self.show_files,
            self.show_passwords,
            self.show_notes,
            self.show_organization,
            self.show_diagnostics,
            self.on_lock,
        ).pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def show_files(self):
        self._header("File & Photo Vault", "Encrypt documents locally and restore them only when unlocked.")
        bar = ctk.CTkFrame(self.content, fg_color="#171d22", corner_radius=10); bar.pack(fill="x", padx=38, pady=(0, 16))
        ctk.CTkButton(bar, text="Select file to encrypt", command=self._encrypt_file).pack(side="left", padx=18, pady=18)
        ctk.CTkLabel(bar, text="Drop-in drag and drop can be enabled with tkinterdnd2 when available.", text_color="#7f8c95").pack(side="left", padx=8)
        self._item_list("FILE", "Encrypted files")

    def _encrypt_file(self):
        path = filedialog.askopenfilename(title="Choose a file")
        if path:
            try:
                self.service.store_file(Path(path))
                messagebox.showinfo("Vault", "File encrypted and stored locally.")
                self.show_files()
            except (OSError, PermissionError, ValueError) as error:
                messagebox.showerror("Encryption failed", str(error))

    def _item_list(self, kind, heading):
        box = ctk.CTkScrollableFrame(self.content, fg_color="#171d22", corner_radius=10); box.pack(fill="both", expand=True, padx=38, pady=(0, 24))
        ctk.CTkLabel(box, text=heading, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=14)
        for row in self.database.list_items(kind):
            line = ctk.CTkFrame(box, fg_color="#20282e", corner_radius=7); line.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(line, text=row["title"], anchor="w").pack(side="left", fill="x", expand=True, padx=14, pady=12)
            if kind == "FILE":
                ctk.CTkButton(line, text="Decrypt", width=85, command=lambda item=row["id"]: self._decrypt_file(item)).pack(side="right", padx=6)
            ctk.CTkButton(line, text="Delete", width=70, fg_color="#593034", hover_color="#713b42", command=lambda item=row["id"]: self._delete(item)).pack(side="right", padx=8)

    def _decrypt_file(self, item_id):
        row = next(row for row in self.database.list_items("FILE") if row["id"] == item_id)
        path = filedialog.asksaveasfilename(initialfile=row["title"])
        if path: self.service.decrypt_file(item_id, Path(path)); messagebox.showinfo("Vault", "File decrypted successfully."); self.show_files()

    def _delete(self, item_id):
        if not messagebox.askyesno("Delete item", "Permanently delete this encrypted item?"):
            return
        try:
            self.service.remove_item(item_id)
            self.catalog.clear_item(item_id)
            self.show_dashboard()
        except (KeyError, OSError, PermissionError) as error:
            messagebox.showerror("Delete failed", str(error))

    def show_passwords(self):
        self._header("Password Manager", "Store, search, and copy account credentials without exposing them in the database.")
        form = ctk.CTkFrame(self.content, fg_color="#171d22", corner_radius=10); form.pack(fill="x", padx=38, pady=(0, 16))
        fields = []
        for placeholder in ("Account or service", "Username / email", "Password"):
            entry = ctk.CTkEntry(form, placeholder_text=placeholder, show="*" if placeholder == "Password" else ""); entry.pack(side="left", fill="x", expand=True, padx=(16 if not fields else 5, 5), pady=18); fields.append(entry)
        ctk.CTkButton(form, text="Generate", width=80, command=lambda: self._fill_generated_password(fields[2])).pack(side="left", padx=5)
        ctk.CTkButton(form, text="Save", width=70, command=lambda: self._save_password(fields)).pack(side="left", padx=(5, 16))
        search = ctk.CTkEntry(self.content, placeholder_text="Search saved accounts")
        search.pack(fill="x", padx=38, pady=(0, 10))
        password_list = ctk.CTkScrollableFrame(self.content, fg_color="#171d22", corner_radius=10); password_list.pack(fill="both", expand=True, padx=38, pady=(0, 24))
        self._password_list(password_list, search)
        search.bind("<KeyRelease>", lambda _event: self._refresh_password_list(password_list, search))

    def _generate_password(self): return self.password_generator.generate(24)
    def _fill_generated_password(self, field):
        field.delete(0, "end")
        field.insert(0, self._generate_password())
    def _save_password(self, fields):
        if not all(field.get().strip() for field in fields):
            messagebox.showwarning("Password Manager", "Complete all credential fields.")
            return
        try:
            self.service.store_secret("PASSWORD", fields[0].get().strip(), {"username": fields[1].get().strip(), "password": fields[2].get()})
            self.show_passwords()
        except (PermissionError, ValueError) as error:
            messagebox.showerror("Password Manager", str(error))

    def _password_list(self, box, search):
        ctk.CTkLabel(box, text="Saved credentials", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=14)
        query = search.get().lower()
        for row in self.service.search_items("PASSWORD", query):
            if query and query not in row["title"].lower(): continue
            line = ctk.CTkFrame(box, fg_color="#20282e", corner_radius=7); line.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(line, text=row["title"], anchor="w").pack(side="left", fill="x", expand=True, padx=14, pady=12)
            ctk.CTkButton(line, text="View", width=65, command=lambda item=row["id"]: self._view_password(item)).pack(side="right", padx=5)
            ctk.CTkButton(line, text="Delete", width=70, fg_color="#593034", hover_color="#713b42", command=lambda item=row["id"]: self._delete(item)).pack(side="right", padx=8)
        ctk.CTkLabel(box, text="Type a service name to filter results, then select View to reveal details.", text_color="#68747d", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16, pady=14)

    def _refresh_password_list(self, box, search):
        for child in box.winfo_children():
            child.destroy()
        self._password_list(box, search)

    def _view_password(self, item_id):
        values = self.service.read_secret(item_id)
        dialog = ctk.CTkToplevel(self); dialog.title("Credential details"); dialog.geometry("390x230"); dialog.transient(self)
        ctk.CTkLabel(dialog, text=f"Username\n{values['username']}", justify="left", anchor="w").pack(fill="x", padx=24, pady=(24, 8))
        ctk.CTkLabel(dialog, text="Password", anchor="w").pack(fill="x", padx=24)
        password = ctk.CTkEntry(dialog, show="*"); password.pack(fill="x", padx=24, pady=5); password.insert(0, values["password"])
        assessment = self.password_strength.assess(values["password"])
        ctk.CTkLabel(dialog, text=f"Strength: {assessment.label}", text_color=assessment.color).pack(pady=3)
        ctk.CTkButton(dialog, text="Copy password", command=lambda: self.copy_password(values["password"])).pack(side="left", padx=(24, 6), pady=12)
        ctk.CTkButton(dialog, text="Close", fg_color="#24323a", command=dialog.destroy).pack(side="left", padx=6, pady=12)

    def show_notes(self):
        self._header("Secure Notes", "Private text is encrypted before it reaches the local store.")
        form = ctk.CTkFrame(self.content, fg_color="#171d22", corner_radius=10); form.pack(fill="x", padx=38, pady=(0, 16))
        title = ctk.CTkEntry(form, placeholder_text="Note title"); title.pack(fill="x", padx=18, pady=(18, 8))
        body = ctk.CTkTextbox(form, height=130); body.pack(fill="x", padx=18, pady=8)
        ctk.CTkButton(form, text="Encrypt note", command=lambda: self._save_note(title, body)).pack(anchor="e", padx=18, pady=18)
        notes = ctk.CTkScrollableFrame(self.content, fg_color="#171d22", corner_radius=10); notes.pack(fill="both", expand=True, padx=38, pady=(0, 24))
        ctk.CTkLabel(notes, text="Saved notes", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=14)
        for row in self.database.list_items("NOTE"):
            line = ctk.CTkFrame(notes, fg_color="#20282e", corner_radius=7); line.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(line, text=row["title"], anchor="w").pack(side="left", fill="x", expand=True, padx=14, pady=12)
            ctk.CTkButton(line, text="Open", width=70, command=lambda item=row["id"]: self._open_note(item)).pack(side="right", padx=5)
            ctk.CTkButton(line, text="Delete", width=70, fg_color="#593034", hover_color="#713b42", command=lambda item=row["id"]: self._delete(item)).pack(side="right", padx=8)

    def _save_note(self, title, body):
        title_value = title.get().strip()
        body_value = body.get("1.0", "end").strip()
        if not title_value or not body_value:
            messagebox.showwarning("Secure Notes", "Enter both a note title and note content.")
            return
        try:
            self.service.store_secret("NOTE", title_value, {"body": body_value})
            self.show_notes()
        except (PermissionError, ValueError) as error:
            messagebox.showerror("Secure Notes", str(error))

    def _open_note(self, item_id):
        values = self.service.read_secret(item_id)
        dialog = ctk.CTkToplevel(self); dialog.title("Secure note"); dialog.geometry("640x440"); dialog.transient(self)
        title = ctk.CTkEntry(dialog); title.pack(fill="x", padx=24, pady=(24, 10))
        row = self.database.get_item(item_id); title.insert(0, row["title"])
        body = ctk.CTkTextbox(dialog); body.pack(fill="both", expand=True, padx=24, pady=8); body.insert("1.0", values["body"])
        def save():
            self.service.update_secret(item_id, title.get(), {"body": body.get("1.0", "end").strip()})
            dialog.destroy(); self.show_notes()
        ctk.CTkButton(dialog, text="Save encrypted note", command=save).pack(anchor="e", padx=24, pady=18)

    def show_recovery(self):
        self._header("Central Recovery", "Master-authenticated access to the unique keys protecting every stored item.")
        toolbar = ctk.CTkFrame(self.content, fg_color="transparent"); toolbar.pack(fill="x", padx=38, pady=(0, 14))
        ctk.CTkLabel(toolbar, text="Keys remain masked until explicitly revealed and are never written to audit logs.", text_color="#d8b878", wraplength=700, anchor="w", justify="left").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(toolbar, text="Hide keys" if self.recovery_revealed else "Reveal keys", width=110, command=self._toggle_recovery).pack(side="right", padx=(12, 0))
        box = ctk.CTkScrollableFrame(self.content, fg_color="#171d22", corner_radius=10); box.pack(fill="both", expand=True, padx=38, pady=(0, 24))
        for item in self.service.recovery_items():
            key = item["key"] if self.recovery_revealed else "•" * 16 + item["key"][-8:]
            row = ctk.CTkFrame(box, fg_color="#20282e", corner_radius=7); row.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(row, text=f"{item['kind']}  ·  {item['title']}\n{key}", anchor="w", justify="left", text_color="#aab5bc").pack(side="left", fill="x", expand=True, padx=14, pady=10)
            if self.recovery_revealed:
                ctk.CTkButton(row, text="Copy", width=65, command=lambda value=item["key"]: self.copy_password(value)).pack(side="right", padx=10)

    def _toggle_recovery(self):
        self.recovery_revealed = not self.recovery_revealed
        self.show_recovery()

    def show_organization(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.current_view = "Organization"
        self._set_active_navigation("Organization")
        CatalogView(self.content, self.database, self._open_catalog_item).pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def show_analytics(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.current_view = "Analytics"
        self._set_active_navigation("Analytics")
        AnalyticsView(self.content, self.database, on_refresh=self.show_analytics).pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def show_security_center(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.current_view = "Security center"
        self._set_active_navigation("Security center")
        SecurityCenterView(
            self.content,
            self.database,
            self.show_diagnostics,
            self.show_settings,
            self.show_organization,
        ).pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def _open_catalog_item(self, item_id: int):
        row = self.database.get_item(item_id)
        if row is None:
            return
        if row["kind"] == "PASSWORD":
            self._view_password(item_id)
        elif row["kind"] == "NOTE":
            self._open_note(item_id)
        else:
            messagebox.showinfo("Encrypted file", f"Select File & Photo Vault to restore {row['title']}.")

    def show_diagnostics(self):
        self._header("Diagnostics & Audit Log", "Operational checks and access history for this local security workspace.")
        box = ctk.CTkFrame(self.content, fg_color="#171d22", corner_radius=10); box.pack(fill="both", expand=True, padx=38, pady=(0, 24))
        for result in self.diagnostics.run_all():
            color = {"success": "#7fc69a", "warning": "#d8b878", "error": "#cf7777"}.get(result.severity, "#76b7c5")
            ctk.CTkLabel(box, text=result.name, anchor="w").pack(fill="x", padx=22, pady=(18, 0)); ctk.CTkLabel(box, text=f"{result.status}  ·  {result.detail}", anchor="w", text_color=color).pack(fill="x", padx=22, pady=(2, 0))
        ctk.CTkButton(box, text="Export diagnostic report", command=self._export_diagnostics).pack(anchor="w", padx=22, pady=20)
        ctk.CTkLabel(box, text="\nAUDIT EVENTS", anchor="w", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x", padx=22, pady=16)
        for log in self.database.recent_audit(12): ctk.CTkLabel(box, text=f"{log['created_at']}  {log['event']}  {log['detail']}", anchor="w", text_color="#aab5bc").pack(fill="x", padx=22, pady=3)

    def _export_diagnostics(self):
        path = filedialog.asksaveasfilename(title="Save diagnostic report", defaultextension=".txt", filetypes=[("Text report", "*.txt")])
        if path:
            Path(path).write_text(self.diagnostics.report_text(), encoding="utf-8")
            messagebox.showinfo("Diagnostics", "Diagnostic report exported.")

    def show_settings(self):
        self._header("Settings & Backup", "Control local workspace preferences and create encrypted recovery copies.")
        panel = ctk.CTkFrame(self.content, fg_color="#171d22", corner_radius=10); panel.pack(fill="x", padx=38, pady=(0, 18))
        ctk.CTkLabel(panel, text="Encrypted backup", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=22, pady=(22, 5))
        ctk.CTkLabel(panel, text="Backups include the encrypted database and encrypted file payloads. The active master key protects the backup archive.", text_color="#8e9aa4", wraplength=720, justify="left").pack(anchor="w", padx=22, pady=(0, 15))
        ctk.CTkButton(panel, text="Export encrypted backup", command=self._export_backup).pack(anchor="w", padx=22, pady=(0, 22))
        appearance = ctk.CTkFrame(self.content, fg_color="#171d22", corner_radius=10); appearance.pack(fill="x", padx=38, pady=(0, 18))
        ctk.CTkLabel(appearance, text="Interface", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=22, pady=(22, 8))
        ctk.CTkLabel(appearance, text="Appearance mode", text_color="#8e9aa4").pack(side="left", padx=22, pady=(0, 22))
        mode = ctk.CTkOptionMenu(appearance, values=["Dark", "Light", "System"], command=self._set_appearance); mode.set(self.settings.get("appearance", "Dark")); mode.pack(side="left", padx=10, pady=(0, 22))
        ctk.CTkLabel(appearance, text="The security model remains local and unchanged by appearance settings.", text_color="#68747d").pack(side="left", padx=18)

    def _set_appearance(self, value: str):
        ctk.set_appearance_mode(value)
        self.settings.update(appearance=value)

    def _export_backup(self):
        path = filedialog.asksaveasfilename(title="Export encrypted backup", defaultextension=".dssbackup", filetypes=[("DSS encrypted backup", "*.dssbackup")])
        if path:
            try:
                self.service.export_backup(Path(path))
                messagebox.showinfo("Backup", "Encrypted backup exported successfully.")
            except (OSError, PermissionError, ValueError) as error:
                messagebox.showerror("Backup failed", str(error))

    def copy_password(self, text):
        self.clipboard_clear(); self.clipboard_append(text)
        if self.last_clipboard_job: self.after_cancel(self.last_clipboard_job)
        self.last_clipboard_job = self.after(CLIPBOARD_CLEAR_SECONDS * 1000, self.clipboard_clear)

    def destroy(self):
        self.unbind_palette()
        super().destroy()
