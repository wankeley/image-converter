from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


SUPPORTED_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".dib",
    ".gif",
    ".heic",
    ".heif",
    ".jfif",
    ".jpe",
    ".jpg",
    ".jpeg",
    ".jxl",
    ".pbm",
    ".pcx",
    ".pgm",
    ".png",
    ".pnm",
    ".ppm",
    ".tif",
    ".tiff",
    ".webp",
}
JPEG_EXTENSIONS = {".jpg", ".jpeg"}


def find_magick() -> str | None:
    executable = shutil.which("magick")
    if executable:
        return executable

    for program_files in (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    ):
        for installation in program_files.glob("ImageMagick-*"):
            executable = installation / "magick.exe"
            if executable.is_file():
                return str(executable)
    return None


class ImageConverter:
    def __init__(self, root: tk.Tk, magick: str) -> None:
        self.root = root
        self.magick = magick
        self.files: list[Path] = []
        self.output_dir: Path | None = None
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.converting = False

        root.title("Image to JPEG Converter")
        root.geometry("720x500")
        root.minsize(600, 400)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(root, padding=(16, 16, 16, 8))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(0, weight=1)
        ttk.Label(
            toolbar,
            text="Convert images to JPEG",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(toolbar, text="Select images...", command=self.select_images).grid(
            row=0, column=1, padx=(8, 0)
        )
        ttk.Button(toolbar, text="Remove selected", command=self.remove_selected).grid(
            row=0, column=2, padx=(8, 0)
        )

        list_frame = ttk.Frame(root, padding=(16, 0, 16, 8))
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.file_list = tk.Listbox(
            list_frame,
            selectmode=tk.EXTENDED,
            activestyle="dotbox",
            font=("Segoe UI", 10),
        )
        self.file_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.file_list.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scrollbar.set)

        options = ttk.Frame(root, padding=(16, 0, 16, 8))
        options.grid(row=2, column=0, sticky="ew")
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="Output folder:").grid(row=0, column=0, sticky="w")
        self.output_label = ttk.Label(
            options, text="Choose images to set a default folder", anchor="w"
        )
        self.output_label.grid(row=0, column=1, sticky="ew", padx=8)
        self.output_button = ttk.Button(
            options, text="Browse...", command=self.choose_output
        )
        self.output_button.grid(row=0, column=2)

        footer = ttk.Frame(root, padding=(16, 0, 16, 16))
        footer.grid(row=3, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(footer, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.convert_button = ttk.Button(
            footer, text="Convert to JPEG", command=self.convert
        )
        self.convert_button.grid(row=0, column=1)
        self.status = ttk.Label(footer, text="Select one or more images to begin.")
        self.status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        root.after(100, self.process_messages)

    def select_images(self) -> None:
        if self.converting:
            return
        selected = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[
                (
                    "Supported images",
                    "*.avif *.bmp *.dib *.gif *.heic *.heif *.jfif *.jpe *.jpg "
                    "*.jpeg *.jxl *.pbm *.pcx *.pgm *.png *.pnm *.ppm *.tif "
                    "*.tiff *.webp",
                ),
                ("All files", "*.*"),
            ],
        )
        existing = {str(path).casefold() for path in self.files}
        added = 0
        for name in selected:
            path = Path(name)
            if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
                continue
            if str(path).casefold() not in existing:
                self.files.append(path)
                existing.add(str(path).casefold())
                added += 1

        if added and self.output_dir is None:
            self.output_dir = self.files[0].parent / "JPEG"
            self.update_output_label()
        self.refresh_list()
        self.status.configure(text=f"{len(self.files)} image(s) selected.")

    def remove_selected(self) -> None:
        if self.converting:
            return
        indices = set(self.file_list.curselection())
        self.files = [path for index, path in enumerate(self.files) if index not in indices]
        self.refresh_list()
        self.status.configure(text=f"{len(self.files)} image(s) selected.")

    def choose_output(self) -> None:
        if self.converting:
            return
        initial = str(self.output_dir) if self.output_dir else None
        selected = filedialog.askdirectory(
            title="Choose output folder", initialdir=initial
        )
        if selected:
            self.output_dir = Path(selected)
            self.update_output_label()

    def update_output_label(self) -> None:
        self.output_label.configure(
            text=str(self.output_dir) if self.output_dir else "Choose an output folder"
        )

    def refresh_list(self) -> None:
        self.file_list.delete(0, tk.END)
        for path in self.files:
            marker = " (already JPEG - will skip)" if path.suffix.casefold() in JPEG_EXTENSIONS else ""
            self.file_list.insert(tk.END, f"{path}{marker}")

    def convert(self) -> None:
        if self.converting:
            return
        if not self.files:
            messagebox.showinfo("No images selected", "Select one or more images first.")
            return
        if self.output_dir is None:
            messagebox.showinfo("Choose output folder", "Choose an output folder first.")
            return

        self.converting = True
        self.convert_button.configure(state=tk.DISABLED)
        self.output_button.configure(state=tk.DISABLED)
        self.progress.configure(maximum=len(self.files), value=0)
        self.status.configure(text="Converting...")
        threading.Thread(target=self.convert_files, daemon=True).start()

    def convert_files(self) -> None:
        assert self.output_dir is not None
        results: list[tuple[str, str]] = []
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            results = [
                ("skipped", f"{source.name}: already JPEG")
                if source.suffix.casefold() in JPEG_EXTENSIONS
                else ("failed", f"{source.name}: could not create output folder: {error}")
                for source in self.files
            ]
            self.messages.put(("done", results))
            return
        reserved: set[str] = set()

        for index, source in enumerate(self.files):
            if source.suffix.casefold() in JPEG_EXTENSIONS:
                results.append(("skipped", f"{source.name}: already JPEG"))
            else:
                target = self.output_dir / f"{source.stem}.jpg"
                if target.exists():
                    results.append(("skipped", f"{source.name}: {target.name} already exists"))
                else:
                    duplicate_number = 2
                    while str(target).casefold() in reserved or target.exists():
                        target = self.output_dir / f"{source.stem}_{duplicate_number}.jpg"
                        duplicate_number += 1
                    reserved.add(str(target).casefold())
                    command = [
                        self.magick,
                        f"{source}[0]",
                        "-auto-orient",
                        "-background",
                        "white",
                        "-alpha",
                        "remove",
                        "-alpha",
                        "off",
                        "-quality",
                        "92",
                        str(target),
                    ]
                    try:
                        result = subprocess.run(
                            command,
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            check=False,
                        )
                        if result.returncode == 0:
                            results.append(("converted", f"{source.name} -> {target.name}"))
                        else:
                            detail = result.stderr.strip() or "ImageMagick could not convert this file."
                            target.unlink(missing_ok=True)
                            results.append(("failed", f"{source.name}: {detail}"))
                    except OSError as error:
                        target.unlink(missing_ok=True)
                        results.append(("failed", f"{source.name}: {error}"))

            self.messages.put(
                ("progress", (index + 1, len(self.files), index, results[-1]))
            )

        self.messages.put(("done", results))

    def process_messages(self) -> None:
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "progress":
                    completed, total, row, result = payload
                    outcome, detail = result
                    self.progress.configure(value=completed)
                    self.status.configure(text=f"{completed}/{total}: {detail}")
                    marker = {
                        "converted": "Converted",
                        "skipped": "Skipped",
                        "failed": "Failed",
                    }[outcome]
                    self.file_list.delete(row)
                    self.file_list.insert(row, f"{self.files[row]} - {marker}")
                elif kind == "done":
                    results = payload
                    converted = sum(outcome == "converted" for outcome, _ in results)
                    skipped = sum(outcome == "skipped" for outcome, _ in results)
                    failed = sum(outcome == "failed" for outcome, _ in results)
                    self.converting = False
                    self.convert_button.configure(state=tk.NORMAL)
                    self.output_button.configure(state=tk.NORMAL)
                    self.status.configure(
                        text=f"Finished: {converted} converted, {skipped} skipped, {failed} failed."
                    )
                    failures = [detail for outcome, detail in results if outcome == "failed"]
                    if failures:
                        messagebox.showwarning(
                            "Some images could not be converted",
                            "\n\n".join(failures[:8]),
                        )
        except queue.Empty:
            pass
        self.root.after(100, self.process_messages)


def main() -> None:
    magick = find_magick()
    if not magick:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "ImageMagick not found",
            "Could not find ImageMagick's 'magick' executable. Install ImageMagick "
            "or add magick.exe to your PATH, then try again.",
        )
        root.destroy()
        return

    root = tk.Tk()
    ImageConverter(root, magick)
    root.mainloop()


if __name__ == "__main__":
    main()
