import multiprocessing
import os
import queue
import shutil
import subprocess
import sys
import threading
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Skip PaddleX's model-source connectivity probe. If models are not cached,
# PaddleOCR can still download the official models on first use.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from pipeline import PDFPartsPipeline
from excel_exporter import export_to_excel


APP_NAME = "Victoria Marine BOM Extractor"
NAVY = "#0B1F33"
NAVY_2 = "#12395B"
ORANGE = "#F28C28"
BG = "#F4F7FA"
CARD = "#FFFFFF"
TEXT = "#152536"
MUTED = "#657789"
SUCCESS = "#198754"
ERROR = "#B42318"
BORDER = "#DCE3EA"


class QueueWriter:
    """Redirect text written to stdout/stderr into the Tkinter UI."""

    def __init__(self, event_queue):
        self.event_queue = event_queue

    def write(self, text):
        if text and text.strip():
            self.event_queue.put(("log", text.rstrip()))

    def flush(self):
        pass


class BOMExtractorApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.geometry("980x720")
        self.minsize(860, 640)
        self.configure(bg=BG)

        self.event_queue = queue.Queue()
        self.worker_thread = None
        self.last_excel_path = None
        self.last_output_dir = None

        self.pdf_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.progress_text_var = tk.StringVar(
            value="Choose a PDF assembly drawing to begin."
        )

        self._build_styles()
        self._build_ui()
        self.after(100, self._poll_events)

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("App.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("Header.TFrame", background=NAVY)

        style.configure(
            "Title.TLabel",
            background=NAVY,
            foreground="white",
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=NAVY,
            foreground="#C7D5E4",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Section.TLabel",
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Body.TLabel",
            background=CARD,
            foreground=MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Status.TLabel",
            background=CARD,
            foreground=TEXT,
            font=("Segoe UI", 10, "bold"),
        )

        style.configure(
            "Primary.TButton",
            background=ORANGE,
            foreground="white",
            borderwidth=0,
            focusthickness=0,
            padding=(20, 12),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#D97716"), ("disabled", "#B8C0C8")],
            foreground=[("disabled", "#F5F5F5")],
        )

        style.configure(
            "Secondary.TButton",
            background="#EAF0F5",
            foreground=NAVY,
            borderwidth=0,
            focusthickness=0,
            padding=(14, 9),
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#D9E4ED")],
        )

        style.configure(
            "VM.Horizontal.TProgressbar",
            troughcolor="#E4EAF0",
            background=ORANGE,
            bordercolor="#E4EAF0",
            lightcolor=ORANGE,
            darkcolor=ORANGE,
            thickness=14,
        )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        header = ttk.Frame(self, style="Header.TFrame", padding=(30, 20))
        header.pack(fill="x")

        ttk.Label(
            header,
            text="VICTORIA MARINE",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="PDF Bill of Material Extractor  •  Assembly-aware Excel export",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        content = ttk.Frame(self, style="App.TFrame", padding=24)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(2, weight=1)

        # Input card
        input_card = ttk.Frame(content, style="Card.TFrame", padding=20)
        input_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        input_card.columnconfigure(0, weight=1)

        ttk.Label(
            input_card,
            text="1. Select drawing",
            style="Section.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            input_card,
            text=(
                "The app reads each page's top-left Bill of Material and "
                "associates it with the ASSEMBLY value in the title block."
            ),
            style="Body.TLabel",
            wraplength=780,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))

        self.pdf_entry = tk.Entry(
            input_card,
            textvariable=self.pdf_var,
            font=("Segoe UI", 10),
            bg="#F9FBFC",
            fg=TEXT,
            relief="solid",
            bd=1,
            highlightthickness=0,
        )
        self.pdf_entry.grid(row=2, column=0, sticky="ew", ipady=8, padx=(0, 10))
        self.browse_pdf_btn = ttk.Button(
            input_card,
            text="Browse PDF",
            style="Secondary.TButton",
            command=self._choose_pdf,
        )
        self.browse_pdf_btn.grid(row=2, column=1, sticky="e")

        ttk.Label(
            input_card,
            text="Output folder",
            style="Section.TLabel",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(16, 6))

        self.output_entry = tk.Entry(
            input_card,
            textvariable=self.output_var,
            font=("Segoe UI", 10),
            bg="#F9FBFC",
            fg=TEXT,
            relief="solid",
            bd=1,
            highlightthickness=0,
        )
        self.output_entry.grid(row=4, column=0, sticky="ew", ipady=8, padx=(0, 10))
        self.browse_output_btn = ttk.Button(
            input_card,
            text="Browse Folder",
            style="Secondary.TButton",
            command=self._choose_output,
        )
        self.browse_output_btn.grid(row=4, column=1, sticky="e")

        # Run card
        run_card = ttk.Frame(content, style="Card.TFrame", padding=20)
        run_card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        run_card.columnconfigure(0, weight=1)

        top_run = ttk.Frame(run_card, style="Card.TFrame")
        top_run.grid(row=0, column=0, sticky="ew")
        top_run.columnconfigure(0, weight=1)

        ttk.Label(
            top_run,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).grid(row=0, column=0, sticky="w")

        self.run_btn = ttk.Button(
            top_run,
            text="Extract BOM to Excel",
            style="Primary.TButton",
            command=self._start_extraction,
        )
        self.run_btn.grid(row=0, column=1, rowspan=2, sticky="e")

        ttk.Label(
            top_run,
            textvariable=self.progress_text_var,
            style="Body.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.progress = ttk.Progressbar(
            run_card,
            style="VM.Horizontal.TProgressbar",
            mode="determinate",
            maximum=100,
            value=0,
        )
        self.progress.grid(row=1, column=0, sticky="ew", pady=(14, 0))

        # Log card
        log_card = ttk.Frame(content, style="Card.TFrame", padding=20)
        log_card.grid(row=2, column=0, sticky="nsew")
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)

        log_top = ttk.Frame(log_card, style="Card.TFrame")
        log_top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        log_top.columnconfigure(0, weight=1)

        ttk.Label(log_top, text="Run log", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        self.open_excel_btn = ttk.Button(
            log_top,
            text="Open Excel",
            style="Secondary.TButton",
            command=self._open_excel,
            state="disabled",
        )
        self.open_excel_btn.grid(row=0, column=1, padx=(8, 0))

        self.open_folder_btn = ttk.Button(
            log_top,
            text="Open Output Folder",
            style="Secondary.TButton",
            command=self._open_output_folder,
            state="disabled",
        )
        self.open_folder_btn.grid(row=0, column=2, padx=(8, 0))

        log_frame = tk.Frame(log_card, bg=CARD)
        log_frame.grid(row=1, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_frame,
            height=12,
            wrap="word",
            font=("Consolas", 9),
            bg="#0E1A26",
            fg="#DCE8F3",
            insertbackground="white",
            relief="flat",
            padx=12,
            pady=10,
            state="disabled",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            log_frame,
            orient="vertical",
            command=self.log_text.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    # ------------------------------------------------------------------
    # File selection
    # ------------------------------------------------------------------

    def _choose_pdf(self):
        path = filedialog.askopenfilename(
            title="Choose assembly drawing PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return

        self.pdf_var.set(path)

        pdf = Path(path)
        default_output = pdf.parent / f"{pdf.stem}_BOM_Output"
        self.output_var.set(str(default_output))
        self.status_var.set("Ready")
        self.progress_text_var.set("PDF selected. Click Extract BOM to Excel.")

    def _choose_output(self):
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output_var.set(path)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def _start_extraction(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return

        pdf_path = Path(self.pdf_var.get().strip())
        output_dir_text = self.output_var.get().strip()

        if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
            messagebox.showerror(APP_NAME, "Please choose a valid PDF file.")
            return

        if not output_dir_text:
            messagebox.showerror(APP_NAME, "Please choose an output folder.")
            return

        output_dir = Path(output_dir_text)

        self._clear_log()
        self.last_excel_path = None
        self.last_output_dir = None
        self.open_excel_btn.configure(state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.progress.configure(value=0, mode="indeterminate")
        self.progress.start(12)
        self.status_var.set("Starting extraction...")
        self.progress_text_var.set(
            "Loading OCR models. The first launch on a new PC can take a few minutes."
        )
        self._set_controls_enabled(False)

        self.worker_thread = threading.Thread(
            target=self._run_extraction_worker,
            args=(pdf_path, output_dir),
            daemon=True,
        )
        self.worker_thread.start()

    def _run_extraction_worker(self, pdf_path, output_dir):
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        queue_writer = QueueWriter(self.event_queue)
        sys.stdout = queue_writer
        sys.stderr = queue_writer

        pipeline = None
        temp_root = None
        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            # Keep all intermediate/debug files out of the user's selected
            # output folder (which may be OneDrive-synced and temporarily locked).
            # Only the final Excel workbook is written to output_dir.
            temp_root = Path(
                tempfile.mkdtemp(prefix="VictoriaMarineBOM_")
            )
            pages_dir = temp_root / "debug_pages"
            pages_dir.mkdir(parents=True, exist_ok=True)

            self.event_queue.put(("status", "Loading OCR models..."))
            pipeline = PDFPartsPipeline(
                pdf_path=str(pdf_path),
                output_root=str(pages_dir),
            )

            page_count = pipeline.reader.get_page_count()
            all_rows = []
            errors = []

            self.event_queue.put(("progress_mode", "determinate"))
            self.event_queue.put(("status", f"Processing {page_count} pages..."))

            for page_number in range(page_count):
                current = page_number + 1
                self.event_queue.put(
                    (
                        "progress",
                        current - 1,
                        page_count,
                        f"Processing page {current} of {page_count}...",
                    )
                )

                try:
                    result = pipeline.process_page(page_number)
                    all_rows.extend(result["rows"])
                except Exception as exc:
                    errors.append({"page": current, "error": str(exc)})
                    print(f"ERROR ON PAGE {current}: {exc}")

                self.event_queue.put(
                    (
                        "progress",
                        current,
                        page_count,
                        f"Finished page {current} of {page_count}.",
                    )
                )

            excel_name = f"{pdf_path.stem}_BOM.xlsx"
            excel_path = output_dir / excel_name

            self.event_queue.put(("status", "Writing Excel workbook..."))
            export_to_excel(
                rows=all_rows,
                errors=errors,
                output_path=str(excel_path),
            )

            self.event_queue.put(
                (
                    "done",
                    str(excel_path),
                    str(output_dir),
                    len(all_rows),
                    len(errors),
                    page_count,
                )
            )

        except Exception as exc:
            self.event_queue.put(
                ("fatal", str(exc), traceback.format_exc())
            )
        finally:
            if pipeline is not None:
                try:
                    pipeline.close()
                except Exception:
                    pass

            # Best-effort cleanup of temporary processing files. Never let
            # cleanup failure turn a successful extraction into an app error.
            if temp_root is not None:
                try:
                    shutil.rmtree(temp_root, ignore_errors=True)
                except Exception:
                    pass

            sys.stdout = old_stdout
            sys.stderr = old_stderr

    # ------------------------------------------------------------------
    # Queue events
    # ------------------------------------------------------------------

    def _poll_events(self):
        try:
            while True:
                event = self.event_queue.get_nowait()
                kind = event[0]

                if kind == "log":
                    self._append_log(event[1])

                elif kind == "status":
                    self.status_var.set(event[1])

                elif kind == "progress_mode":
                    self.progress.stop()
                    self.progress.configure(mode=event[1], value=0)

                elif kind == "progress":
                    current, total, text = event[1], event[2], event[3]
                    percent = (current / total * 100) if total else 0
                    self.progress.configure(value=percent)
                    self.progress_text_var.set(text)

                elif kind == "done":
                    self._handle_done(*event[1:])

                elif kind == "fatal":
                    self._handle_fatal(event[1], event[2])

        except queue.Empty:
            pass

        self.after(100, self._poll_events)

    def _handle_done(
        self,
        excel_path,
        output_dir,
        row_count,
        error_count,
        page_count,
    ):
        self.progress.stop()
        self.progress.configure(mode="determinate", value=100)
        self.last_excel_path = Path(excel_path)
        self.last_output_dir = Path(output_dir)
        self.open_excel_btn.configure(state="normal")
        self.open_folder_btn.configure(state="normal")
        self._set_controls_enabled(True)

        if error_count:
            self.status_var.set("Completed with review items")
            self.progress_text_var.set(
                f"{row_count} rows extracted from {page_count} pages • "
                f"{error_count} page(s) reported errors."
            )
        else:
            self.status_var.set("Extraction complete")
            self.progress_text_var.set(
                f"{row_count} rows extracted from {page_count} pages • Excel is ready."
            )

        self._append_log(f"\nExcel created: {excel_path}")
        messagebox.showinfo(
            APP_NAME,
            f"Extraction complete.\n\nRows extracted: {row_count}\n"
            f"Pages with errors: {error_count}\n\n{excel_path}",
        )

    def _handle_fatal(self, message, trace):
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self._set_controls_enabled(True)
        self.status_var.set("Extraction failed")
        self.progress_text_var.set(message)
        self._append_log("\nFATAL ERROR\n" + trace)
        messagebox.showerror(APP_NAME, message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_controls_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self.run_btn.configure(state=state)
        self.browse_pdf_btn.configure(state=state)
        self.browse_output_btn.configure(state=state)
        self.pdf_entry.configure(state=state)
        self.output_entry.configure(state=state)

    def _append_log(self, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _open_excel(self):
        if self.last_excel_path and self.last_excel_path.exists():
            self._open_path(self.last_excel_path)

    def _open_output_folder(self):
        if self.last_output_dir and self.last_output_dir.exists():
            self._open_path(self.last_output_dir)

    @staticmethod
    def _open_path(path):
        path = str(path)
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = BOMExtractorApp()
    app.mainloop()