from tkinterdnd2 import TkinterDnD, DND_FILES
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageFilter
import numpy as np
import os

class DTFConverter:
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.root.title("DTF Converter")
        self.root.geometry("900x680")
        self.root.configure(bg="#1e1e1e")
        self.root.resizable(False, False)

        self.input_path = None
        self.original_preview = None
        self.result_preview = None
        self.result_image = None

        self._build_ui()

    def _build_ui(self):
        # Title
        tk.Label(
            self.root, text="DTF Converter", font=("Helvetica", 22, "bold"),
            fg="white", bg="#1e1e1e"
        ).pack(pady=(15, 3))
        tk.Label(
            self.root, text="Remove background for DTF printing — drag & drop or click to open",
            font=("Helvetica", 11), fg="#888", bg="#1e1e1e"
        ).pack(pady=(0, 10))

        # Controls row
        controls = tk.Frame(self.root, bg="#1e1e1e")
        controls.pack(pady=(0, 8))

        # Shirt color
        tk.Label(controls, text="Shirt:", font=("Helvetica", 11),
                 fg="white", bg="#1e1e1e").pack(side=tk.LEFT, padx=(0, 5))
        self.shirt_color = tk.StringVar(value="black")
        for color in ["black", "white"]:
            tk.Radiobutton(
                controls, text=color.capitalize(), variable=self.shirt_color,
                value=color, font=("Helvetica", 10), fg="white", bg="#1e1e1e",
                selectcolor="#333", activebackground="#1e1e1e", activeforeground="white"
            ).pack(side=tk.LEFT, padx=2)

        # Separator
        tk.Label(controls, text="  |  ", fg="#444", bg="#1e1e1e").pack(side=tk.LEFT)

        # Threshold slider
        tk.Label(controls, text="Strength:", font=("Helvetica", 11),
                 fg="white", bg="#1e1e1e").pack(side=tk.LEFT, padx=(0, 5))
        self.threshold = tk.IntVar(value=30)
        tk.Scale(
            controls, from_=10, to=80, orient=tk.HORIZONTAL,
            variable=self.threshold, length=150, bg="#1e1e1e", fg="white",
            highlightbackground="#1e1e1e", troughcolor="#444", showvalue=True
        ).pack(side=tk.LEFT)

        # Preview area — two panels side by side
        preview_container = tk.Frame(self.root, bg="#1e1e1e")
        preview_container.pack(pady=5, padx=20, fill=tk.BOTH)

        # Original panel (also the drop zone)
        left_col = tk.Frame(preview_container, bg="#1e1e1e")
        left_col.pack(side=tk.LEFT, padx=(0, 5), expand=True)
        tk.Label(left_col, text="ORIGINAL", font=("Helvetica", 10, "bold"),
                 fg="#666", bg="#1e1e1e").pack()
        self.drop_frame = tk.Frame(left_col, bg="#2a2a2a", width=420, height=420,
                                    highlightbackground="#444", highlightthickness=2)
        self.drop_frame.pack(pady=5)
        self.drop_frame.pack_propagate(False)
        self.original_label = tk.Label(
            self.drop_frame,
            text="Drag & Drop Image Here\n\nor click to browse",
            font=("Helvetica", 13), fg="#555", bg="#2a2a2a", justify=tk.CENTER,
            cursor="hand2"
        )
        self.original_label.pack(expand=True, fill=tk.BOTH)

        # Drop zone bindings
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self._on_drop)
        self.drop_frame.dnd_bind('<<DragEnter>>', self._on_drag_enter)
        self.drop_frame.dnd_bind('<<DragLeave>>', self._on_drag_leave)
        self.original_label.bind('<Button-1>', lambda e: self.open_image())

        # Result panel
        right_col = tk.Frame(preview_container, bg="#1e1e1e")
        right_col.pack(side=tk.LEFT, padx=(5, 0), expand=True)
        tk.Label(right_col, text="DTF RESULT", font=("Helvetica", 10, "bold"),
                 fg="#666", bg="#1e1e1e").pack()
        self.result_frame = tk.Frame(right_col, bg="#2a2a2a", width=420, height=420,
                                      highlightbackground="#444", highlightthickness=2)
        self.result_frame.pack(pady=5)
        self.result_frame.pack_propagate(False)
        self.result_label = tk.Label(
            self.result_frame, text="Result will appear here",
            font=("Helvetica", 13), fg="#555", bg="#2a2a2a", justify=tk.CENTER
        )
        self.result_label.pack(expand=True)

        # Toggle preview background (simulate shirt color)
        self.preview_bg = tk.StringVar(value="dark")
        bg_frame = tk.Frame(self.root, bg="#1e1e1e")
        bg_frame.pack(pady=(0, 5))
        tk.Label(bg_frame, text="Preview bg:", font=("Helvetica", 10),
                 fg="#666", bg="#1e1e1e").pack(side=tk.LEFT, padx=(0, 5))
        for name, val in [("Dark", "dark"), ("Light", "light"), ("Checker", "checker")]:
            tk.Radiobutton(
                bg_frame, text=name, variable=self.preview_bg, value=val,
                font=("Helvetica", 10), fg="white", bg="#1e1e1e",
                selectcolor="#333", activebackground="#1e1e1e", activeforeground="white",
                command=self._update_result_preview
            ).pack(side=tk.LEFT, padx=2)

        # Buttons
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=8)

        self.open_btn = tk.Button(
            btn_frame, text="Open Image", font=("Helvetica", 12, "bold"),
            bg="#4a90d9", fg="white", width=12, relief=tk.FLAT,
            command=self.open_image, cursor="hand2"
        )
        self.open_btn.pack(side=tk.LEFT, padx=6)

        self.convert_btn = tk.Button(
            btn_frame, text="Convert", font=("Helvetica", 12, "bold"),
            bg="#2ecc71", fg="white", width=12, relief=tk.FLAT,
            command=self.convert, cursor="hand2", state=tk.DISABLED
        )
        self.convert_btn.pack(side=tk.LEFT, padx=6)

        self.save_btn = tk.Button(
            btn_frame, text="Save As...", font=("Helvetica", 12, "bold"),
            bg="#9b59b6", fg="white", width=12, relief=tk.FLAT,
            command=self.save_as, cursor="hand2", state=tk.DISABLED
        )
        self.save_btn.pack(side=tk.LEFT, padx=6)

        # Progress bar
        self.progress = ttk.Progressbar(
            self.root, length=400, mode='determinate',
            style="Custom.Horizontal.TProgressbar"
        )
        self.progress.pack(pady=(5, 2))
        self.progress['value'] = 0

        # Style the progress bar
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Custom.Horizontal.TProgressbar",
                         troughcolor='#333', background='#2ecc71',
                         thickness=14)

        # Status
        self.status = tk.Label(
            self.root, text="Ready", font=("Helvetica", 10), fg="#888", bg="#1e1e1e"
        )
        self.status.pack(pady=(2, 8))

    def _on_drag_enter(self, event):
        self.drop_frame.config(highlightbackground="#4a90d9", highlightthickness=3)

    def _on_drag_leave(self, event):
        self.drop_frame.config(highlightbackground="#444", highlightthickness=2)

    def _on_drop(self, event):
        self.drop_frame.config(highlightbackground="#444", highlightthickness=2)
        raw = event.data.strip()
        # Handle braces from tkdnd on macOS (spaces in paths)
        if raw.startswith('{') and raw.endswith('}'):
            path = raw[1:-1]
        else:
            path = raw
        # Handle multiple files — take the first
        if '\n' in path:
            path = path.split('\n')[0].strip()
        if os.path.isfile(path):
            self._load_image(path)
        else:
            self.status.config(text=f"Could not open file: {path}", fg="#e74c3c")

    def open_image(self):
        path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.tif"),
                ("All files", "*.*")
            ]
        )
        if path:
            self._load_image(path)

    def _load_image(self, path):
        try:
            img = Image.open(path)
        except Exception:
            messagebox.showerror("Error", f"Cannot open: {path}")
            return

        self.input_path = path
        self.result_image = None
        self.convert_btn.config(state=tk.NORMAL)
        self.save_btn.config(state=tk.DISABLED)

        # Show original preview
        preview = img.copy()
        preview.thumbnail((400, 400))
        self.original_preview = ImageTk.PhotoImage(preview)
        self.original_label.config(image=self.original_preview, text="")

        # Clear result
        self.result_label.config(image='', text="Click Convert", bg="#2a2a2a")
        self.result_preview = None

        self.status.config(
            text=f"Loaded: {os.path.basename(path)} ({img.size[0]}x{img.size[1]})",
            fg="#4a90d9"
        )

    def _make_checker(self, w, h, square=10):
        xs = np.arange(w) // square
        ys = np.arange(h) // square
        grid = (xs[None, :] + ys[:, None]) % 2
        pixels = np.where(grid[:,:,None] == 0,
                          np.array([200, 200, 200, 255], dtype=np.uint8),
                          np.array([255, 255, 255, 255], dtype=np.uint8))
        return Image.fromarray(pixels)

    def _update_result_preview(self):
        if self.result_image is None:
            return

        preview = self.result_image.copy()
        preview.thumbnail((400, 400))
        w, h = preview.size

        bg_mode = self.preview_bg.get()
        if bg_mode == "dark":
            bg = Image.new("RGBA", (w, h), (30, 30, 30, 255))
        elif bg_mode == "light":
            bg = Image.new("RGBA", (w, h), (240, 240, 240, 255))
        else:
            bg = self._make_checker(w, h, 12)

        bg.paste(preview, (0, 0), preview)
        self.result_preview = ImageTk.PhotoImage(bg)
        self.result_label.config(image=self.result_preview, text="", bg="#2a2a2a")

    def _set_progress(self, value, text):
        self.progress['value'] = value
        self.status.config(text=text, fg="#f39c12")
        self.root.update_idletasks()

    def convert(self):
        if not self.input_path:
            return

        self.convert_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0

        try:
            self._set_progress(10, "Loading image...")
            img = Image.open(self.input_path).convert("RGBA")

            self._set_progress(25, "Analyzing colors...")
            pixels = np.array(img, dtype=np.float64)
            r, g, b = pixels[:,:,0], pixels[:,:,1], pixels[:,:,2]
            brightness = 0.299 * r + 0.587 * g + 0.114 * b

            self._set_progress(40, "Detecting background...")
            max_rgb = np.maximum(np.maximum(r, g), b)
            min_rgb = np.minimum(np.minimum(r, g), b)
            saturation = max_rgb - min_rgb
            thresh = self.threshold.get()

            self._set_progress(50, "Detecting background...")
            # Auto-detect background from corners
            h, w = brightness.shape
            corners = [
                brightness[:h//10, :w//10],
                brightness[:h//10, -w//10:],
                brightness[-h//10:, :w//10],
                brightness[-h//10:, -w//10:],
            ]
            bg_brightness = np.median(np.concatenate([c.flatten() for c in corners]))
            bg_threshold = bg_brightness + thresh

            self._set_progress(60, "Removing background...")
            if self.shirt_color.get() == "black":
                is_bright = brightness > max(bg_threshold, 40)
                is_colorful = saturation > 50
                keep_mask = is_bright | is_colorful
            else:
                is_dark = brightness < (255 - bg_threshold)
                is_colorful = saturation > 50
                keep_mask = is_dark | is_colorful

            # Binary alpha with edge feathering for smooth DTF edges
            alpha_binary = np.where(keep_mask, 255.0, 0.0)
            alpha_img = Image.fromarray(alpha_binary.astype(np.uint8), mode='L')
            FEATHER_RADIUS = 3
            alpha_feathered = alpha_img.filter(ImageFilter.GaussianBlur(radius=FEATHER_RADIUS))
            alpha = np.array(alpha_feathered, dtype=np.float64)
            alpha[alpha < 15] = 0  # kill faint halo

            self._set_progress(70, "Enhancing colors...")
            # Preserve original colors with depth - per-channel stretch
            kept_brightness = brightness[keep_mask]
            if len(kept_brightness) > 0:
                p5 = np.percentile(kept_brightness, 5)
                p95 = np.percentile(kept_brightness, 95)
                if p95 - p5 > 10:
                    for ch in [0, 1, 2]:
                        channel = pixels[:,:,ch]
                        stretched = np.clip((channel - p5 * 0.8) * (240.0 / (p95 - p5 * 0.8)), 0, 255)
                        normalized = stretched / 255.0
                        s_curved = normalized ** 0.9 * 255.0
                        pixels[:,:,ch] = np.where(keep_mask, s_curved, channel)

            pixels[:,:,3] = np.clip(alpha, 0, 255)
            self.result_image = Image.fromarray(pixels.astype(np.uint8))

            self._set_progress(80, "Saving file...")
            base = os.path.splitext(os.path.basename(self.input_path))[0]
            output_dir = os.path.dirname(self.input_path)
            output_path = os.path.join(output_dir, f"{base}_dtf.png")
            self.result_image.save(output_path, "PNG")

            self._set_progress(90, "Generating preview...")
            self._update_result_preview()

            self.progress['value'] = 100
            self.save_btn.config(state=tk.NORMAL)
            self.status.config(text=f"Done! Saved: {os.path.basename(output_path)}", fg="#2ecc71")

        except Exception as e:
            self.progress['value'] = 0
            messagebox.showerror("Error", str(e))
            self.status.config(text="Error during conversion", fg="#e74c3c")
        finally:
            self.convert_btn.config(state=tk.NORMAL)

    def save_as(self):
        if self.result_image is None:
            return
        path = filedialog.asksaveasfilename(
            title="Save DTF Image",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")]
        )
        if path:
            self.result_image.save(path, "PNG")
            self.status.config(text=f"Saved: {path}", fg="#2ecc71")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    DTFConverter().run()
