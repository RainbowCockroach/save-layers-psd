"""
Save PSD Layers as PNGs
Extracts each layer from a PSD file as a separate PNG.
Groups become folders, leaf layers become PNGs.

Two modes:
  - paper: full canvas size, layer positioned correctly
  - actual: cropped to layer content bounding box

Usage:
  python save_layers.py                          # opens file dialog
  python save_layers.py "file.psd"               # opens mode dialog
  python save_layers.py "file.psd" --mode paper  # fully automated
  python save_layers.py "file.psd" --mode actual

Also supports drag-and-drop onto the executable on both Windows and macOS.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image
from psd_tools import PSDImage


def sanitize_name(name: str) -> str:
    """Normalize a layer name to a filesystem-safe lowercase_underscore format."""
    name = name.strip().lower()
    name = name.replace(" ", "_")
    name = re.sub(r"[^a-z0-9_\-]", "", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")
    name = name[:50].rstrip("_")
    return name or "unnamed_layer"


def unique_name(name: str, seen: dict) -> str:
    """Append _2, _3, etc. if name already used in the same folder."""
    if name not in seen:
        seen[name] = 1
        return name
    seen[name] += 1
    return f"{name}_{seen[name]}"


def export_layer_image(layer, psd, mode: str):
    """Render a single layer to a PIL Image. Returns None on failure."""
    if layer.width == 0 or layer.height == 0:
        return None

    viewport = (0, 0, psd.width, psd.height) if mode == "paper" else None
    original_visible = layer.visible

    # Strategy 1: composite() with forced visibility
    try:
        layer.visible = True
        image = layer.composite(viewport=viewport, layer_filter=lambda l: True)
        if image is not None:
            return image
    except Exception:
        pass
    finally:
        layer.visible = original_visible

    # Strategy 2: topil() fallback
    try:
        layer.visible = True
        image = layer.topil()
        if image is not None:
            if mode == "paper":
                canvas = Image.new("RGBA", (psd.width, psd.height), (0, 0, 0, 0))
                canvas.paste(image, (layer.left, layer.top))
                return canvas
            return image
    except Exception:
        pass
    finally:
        layer.visible = original_visible

    return None


def export_layers(layers, output_dir: Path, psd, mode: str, depth: int = 0,
                   progress_update=None):
    """Recursively export layers. Groups become folders, leaves become PNGs."""
    seen = {}
    exported = 0
    indent = "  " * depth

    for layer in layers:
        safe_name = sanitize_name(layer.name)
        safe_name = unique_name(safe_name, seen)

        if layer.is_group():
            group_dir = output_dir / safe_name
            group_dir.mkdir(exist_ok=True)
            print(f"{indent}[folder] {layer.name} -> {safe_name}/")
            exported += export_layers(layer, group_dir, psd, mode, depth + 1,
                                      progress_update=progress_update)
        else:
            if progress_update:
                progress_update("Exporting layers...", layer.name)

            image = export_layer_image(layer, psd, mode)
            if image is None:
                print(f"{indent}[skip]   {layer.name} (could not render)")
                continue

            png_path = output_dir / f"{safe_name}.png"
            image.save(str(png_path), "PNG")
            print(f"{indent}[saved]  {layer.name} -> {safe_name}.png")
            exported += 1

    return exported


def show_done_dialog(count: int, output_dir: Path):
    """Show a completion dialog and offer to open the output folder."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        open_folder = messagebox.askyesno(
            "Export Complete",
            f"Done! Exported {count} layers.\n\n"
            f"Output: {output_dir}\n\n"
            "Open the output folder?",
        )
        root.destroy()

        if open_folder:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(output_dir)])
            elif sys.platform == "win32":
                os.startfile(str(output_dir))
    except ImportError:
        pass


def show_error_dialog(message: str):
    """Show an error dialog."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror("Error", message)
        root.destroy()
    except ImportError:
        pass


def show_progress_window():
    """Create a small progress window. Returns (root, label, update_fn, close_fn)."""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.title("Exporting layers...")
        root.attributes("-topmost", True)
        root.resizable(False, False)

        frame = tk.Frame(root, padx=30, pady=20)
        frame.pack()

        label = tk.Label(frame, text="Starting export...", font=("Arial", 12),
                         width=40, anchor="w")
        label.pack()

        progress_label = tk.Label(frame, text="", font=("Arial", 10),
                                  fg="gray", anchor="w", width=40)
        progress_label.pack(pady=(5, 0))

        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"+{x}+{y}")

        def update(status: str, detail: str = ""):
            label.config(text=status)
            progress_label.config(text=detail)
            root.update()

        def close():
            root.destroy()

        return root, update, close
    except ImportError:
        return None, lambda s, d="": None, lambda: None


def process_psd(psd_path_str: str, mode: str = None):
    """Main processing: open PSD, pick mode if needed, export layers."""
    psd_path = Path(psd_path_str.strip().strip('"').strip("'")).resolve()

    if not psd_path.exists():
        msg = f"File not found: {psd_path}"
        print(f"Error: {msg}")
        show_error_dialog(msg)
        return

    if not psd_path.suffix.lower() == ".psd":
        msg = f"Not a PSD file: {psd_path.name}"
        print(f"Error: {msg}")
        show_error_dialog(msg)
        return

    if mode is None:
        mode = pick_mode()

    _root, progress_update, progress_close = show_progress_window()

    progress_update("Opening PSD...", psd_path.name)
    print(f"Opening: {psd_path.name}")
    psd = PSDImage.open(str(psd_path))
    print(f"Canvas:  {psd.width}x{psd.height}")
    print(f"Mode:    {mode}")

    output_dir = psd_path.parent / psd_path.stem
    output_dir.mkdir(exist_ok=True)
    print(f"Output:  {output_dir}")
    print()

    progress_update("Exporting layers...", f"Mode: {mode} | Canvas: {psd.width}x{psd.height}")
    count = export_layers(psd, output_dir, psd, mode, progress_update=progress_update)
    print(f"\nDone! Exported {count} layers.")

    progress_close()
    show_done_dialog(count, output_dir)


def pick_psd_file() -> str:
    """Open a file dialog to pick a PSD file."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="Select a PSD file",
            filetypes=[("PSD files", "*.psd"), ("All files", "*.*")],
        )
        root.destroy()
        if not path:
            print("No file selected.")
            sys.exit(0)
        return path
    except ImportError:
        print("Error: tkinter is not available. Please provide a PSD file path as argument.")
        print("  python save_layers.py <file.psd>")
        sys.exit(1)


def pick_mode() -> str:
    """Open a simple tkinter window with two buttons to pick the export mode."""
    try:
        import tkinter as tk

        result = [None]

        def choose(mode):
            result[0] = mode
            root.destroy()

        root = tk.Tk()
        root.title("Export Mode")
        root.attributes("-topmost", True)
        root.resizable(False, False)

        frame = tk.Frame(root, padx=30, pady=20)
        frame.pack()

        tk.Label(frame, text="Choose export mode:", font=("Arial", 14)).pack(pady=(0, 15))

        btn_frame = tk.Frame(frame)
        btn_frame.pack()

        tk.Button(
            btn_frame, text="Paper Size", font=("Arial", 12), width=14, height=2,
            command=lambda: choose("paper"),
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame, text="Actual Size", font=("Arial", 12), width=14, height=2,
            command=lambda: choose("actual"),
        ).pack(side=tk.LEFT, padx=5)

        # Center the window on screen
        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"+{x}+{y}")

        root.protocol("WM_DELETE_WINDOW", lambda: (result.__setitem__(0, None), root.destroy()))
        root.mainloop()

        if result[0] is None:
            print("No mode selected.")
            sys.exit(0)
        return result[0]
    except ImportError:
        print("Error: tkinter is not available. Please use --mode flag.")
        print("  python save_layers.py <file.psd> --mode paper")
        print("  python save_layers.py <file.psd> --mode actual")
        sys.exit(1)


def run_with_macos_events():
    """On macOS .app, use tkinter Apple Event handler for drag-and-drop."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()

    def on_open_document(*args):
        """Called by macOS when files are dropped onto the .app."""
        for file_path in args:
            process_psd(file_path)
        root.after(100, root.destroy)

    # Register macOS open-document handler
    root.createcommand("::tk::mac::OpenDocument", on_open_document)

    # Give macOS a moment to deliver the Apple Event, then check if
    # we got a file. If not after 2 seconds, fall back to file picker.
    def check_or_pick():
        psd_path = pick_psd_file()
        process_psd(psd_path)
        root.destroy()

    root.after(500, check_or_pick)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Export PSD layers as PNGs")
    parser.add_argument("psd_file", nargs="?", help="Path to the PSD file")
    parser.add_argument("--mode", choices=["paper", "actual"],
                        help="Export mode: paper (full canvas) or actual (cropped)")
    args = parser.parse_args()

    # If a file was passed via CLI argument (works on both platforms,
    # and is how Windows drag-and-drop onto .exe delivers the path)
    if args.psd_file:
        process_psd(args.psd_file, args.mode)
        return

    # On macOS bundled .app, drag-and-drop delivers via Apple Events.
    # Detect if we're running inside a PyInstaller macOS bundle.
    is_macos_bundle = (
        sys.platform == "darwin"
        and getattr(sys, "frozen", False)
        and hasattr(sys, "_MEIPASS")
    )

    if is_macos_bundle:
        run_with_macos_events()
    else:
        # Interactive: open file picker
        psd_path = pick_psd_file()
        process_psd(psd_path, args.mode)


if __name__ == "__main__":
    main()
