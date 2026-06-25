"""
VideoCodec — Interfaz gráfica (Tkinter).
Multilenguaje: Español / English / 简体中文
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from videocodec import (SIZE, BLOCK, COLS, ROWS, BITS_PER_FRAME, REPEAT, FPS,
                        encode_file, decode_video)

# ─────────────────────────────────────────────
#  Diccionario de traducciones
# ─────────────────────────────────────────────
LANG = {
    "es": {
        "title":            "● Waqün",
        "title2":           "Video Coder",
        "subtitle":         "   cualquier archivo ↔ video hexadecimal",
        "mode_label":       "Modo:",
        "encode_radio":     "Codificar  (archivo → video)",
        "decode_radio":     "Decodificar  (video → archivo)",
        "src_label":        "Origen:",
        "dst_label":        "Destino:",
        "pick_btn":         "Elegir…",
        "run_encode":       "▶  CODIFICAR",
        "run_decode":       "▶  DECODIFICAR",
        "status_ready":     "Listo.",
        "status_done":      "✔ Completado.",
        "warn_src_title":   "Falta origen",
        "warn_src_msg":     "Elegí un archivo de origen.",
        "warn_dst_title":   "Falta destino",
        "warn_dst_msg":     "Indicá el destino.",
        "err_title":        "Error",
        "pick_src_encode":  "Elegir archivo a codificar",
        "pick_src_decode":  "Elegir video a decodificar",
        "pick_dst_encode":  "Guardar video como",
        "pick_dst_decode":  "Carpeta de salida",
        "ft_mp4":           "MP4",
        "ft_all":           "Todos",
        "log_encoded":      "✔ Codificado exitosamente",
        "log_original":     "Archivo original",
        "log_ext":          "Extensión",
        "log_frames":       "Frames de datos",
        "log_duration":     "Duración del video",
        "log_saved":        "Guardado en",
        "log_decoded":      "✔ Decodificado exitosamente",
        "log_ext_rec":      "Extensión recuperada",
        "log_size":         "Tamaño del archivo",
        "log_checksum":     "Checksum",
        "log_checksum_ok":  "OK ✔",
        "lang_label":       "Idioma:",
    },
    "en": {
        "title":            "● Waqün",
        "title2":           "Video Coder",
        "subtitle":         "   any file ↔ hexadecimal video",
        "mode_label":       "Mode:",
        "encode_radio":     "Encode  (file → video)",
        "decode_radio":     "Decode  (video → file)",
        "src_label":        "Source:",
        "dst_label":        "Destination:",
        "pick_btn":         "Browse…",
        "run_encode":       "▶  ENCODE",
        "run_decode":       "▶  DECODE",
        "status_ready":     "Ready.",
        "status_done":      "✔ Done.",
        "warn_src_title":   "Missing source",
        "warn_src_msg":     "Please choose a source file.",
        "warn_dst_title":   "Missing destination",
        "warn_dst_msg":     "Please specify a destination.",
        "err_title":        "Error",
        "pick_src_encode":  "Choose file to encode",
        "pick_src_decode":  "Choose video to decode",
        "pick_dst_encode":  "Save video as",
        "pick_dst_decode":  "Output folder",
        "ft_mp4":           "MP4",
        "ft_all":           "All files",
        "log_encoded":      "✔ Successfully encoded",
        "log_original":     "Original file",
        "log_ext":          "Extension",
        "log_frames":       "Data frames",
        "log_duration":     "Video duration",
        "log_saved":        "Saved to",
        "log_decoded":      "✔ Successfully decoded",
        "log_ext_rec":      "Recovered extension",
        "log_size":         "File size",
        "log_checksum":     "Checksum",
        "log_checksum_ok":  "OK ✔",
        "lang_label":       "Language:",
    },
    "zh": {
        "title":            "● Waqün",
        "title2":           "视频编码器",
        "subtitle":         "   任意文件 ↔ 十六进制视频",
        "mode_label":       "模式：",
        "encode_radio":     "编码  （文件 → 视频）",
        "decode_radio":     "解码  （视频 → 文件）",
        "src_label":        "来源：",
        "dst_label":        "目标：",
        "pick_btn":         "浏览…",
        "run_encode":       "▶  编码",
        "run_decode":       "▶  解码",
        "status_ready":     "就绪。",
        "status_done":      "✔ 已完成。",
        "warn_src_title":   "缺少来源",
        "warn_src_msg":     "请选择一个源文件。",
        "warn_dst_title":   "缺少目标",
        "warn_dst_msg":     "请指定输出目标。",
        "err_title":        "错误",
        "pick_src_encode":  "选择要编码的文件",
        "pick_src_decode":  "选择要解码的视频",
        "pick_dst_encode":  "另存视频为",
        "pick_dst_decode":  "输出文件夹",
        "ft_mp4":           "MP4",
        "ft_all":           "所有文件",
        "log_encoded":      "✔ 编码成功",
        "log_original":     "原始文件",
        "log_ext":          "扩展名",
        "log_frames":       "数据帧",
        "log_duration":     "视频时长",
        "log_saved":        "保存至",
        "log_decoded":      "✔ 解码成功",
        "log_ext_rec":      "恢复的扩展名",
        "log_size":         "文件大小",
        "log_checksum":     "校验和",
        "log_checksum_ok":  "OK ✔",
        "lang_label":       "语言：",
    },
}

LANG_NAMES   = {"es": "Español", "en": "English", "zh": "简体中文"}
LANG_KEYS    = list(LANG_NAMES.keys())
LANG_DISPLAY = [LANG_NAMES[k] for k in LANG_KEYS]


# ─────────────────────────────────────────────
#  Función principal
# ─────────────────────────────────────────────
def run_gui():
    BG        = "#0d0d0d"
    PANEL     = "#1a1a1a"
    ACCENT    = "#00ff88"
    DIM       = "#888888"
    WHITE     = "#f0f0f0"
    FONT_MONO = ("Courier New", 10)
    FONT_UI   = ("Segoe UI", 10)

    root = tk.Tk()
    root.title("Waqün Video Coder — Archivos ↔ Video HEXADECIMAL")
    root.configure(bg=BG)
    root.resizable(True, True)

    # Ventana maximizada
    try:
        root.state("zoomed")
    except Exception:
        root.geometry("1400x900")

    # ── Variables de estado ──────────────────
    mode_var     = tk.StringVar(value="encode")
    src_var      = tk.StringVar()
    dst_var      = tk.StringVar()
    status_var   = tk.StringVar(value="Listo.")
    progress_var = tk.DoubleVar(value=0)
    lang_var     = tk.StringVar(value="Español")   # nombre para mostrar

    current_lang = {"code": "es"}   # dict mutable para cerrar sobre él

    def t(key):
        return LANG[current_lang["code"]][key]

    # ── Layout responsivo ────────────────────
    root.columnconfigure(0, weight=1)
    # filas: 0 header, 1 separator, 2 mode, 3 panel, 4 progress, 5 status, 6 log, 7 btn, 8 footer
    for r in range(9):
        root.rowconfigure(r, weight=0)
    root.rowconfigure(6, weight=1)   # log se expande verticalmente

    # ── Referencias a widgets que cambian texto ──
    refs = {}

    # ────────────────────────────────────────────
    #  HEADER (fila 0)
    # ────────────────────────────────────────────
    hdr = tk.Frame(root, bg=BG)
    hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 4))
    hdr.columnconfigure(1, weight=1)   # subtitle se estira

    lbl_title  = tk.Label(hdr, text="● Waqün", bg=BG, fg=ACCENT,
                          font=("Courier New", 18, "bold"))
    lbl_title.grid(row=0, column=0, sticky="w")

    lbl_title2 = tk.Label(hdr, text="Video Coder", bg=BG, fg=WHITE,
                          font=("Courier New", 18, "bold"))
    lbl_title2.grid(row=0, column=1, sticky="w")

    lbl_sub    = tk.Label(hdr, text="   cualquier archivo ↔ video hexadecimal",
                          bg=BG, fg=DIM, font=FONT_MONO)
    lbl_sub.grid(row=0, column=2, sticky="w", padx=8)

    # Selector de idioma (parte derecha del header)
    lang_frame = tk.Frame(hdr, bg=BG)
    lang_frame.grid(row=0, column=3, sticky="e", padx=(16, 0))

    lbl_lang = tk.Label(lang_frame, text="Idioma:", bg=BG, fg=DIM, font=FONT_UI)
    lbl_lang.pack(side="left")

    combo_lang = ttk.Combobox(lang_frame, textvariable=lang_var,
                              values=LANG_DISPLAY, state="readonly",
                              width=12, font=FONT_UI)
    combo_lang.pack(side="left", padx=6)
    combo_lang.set("Español")

    refs["lbl_title"]  = lbl_title
    refs["lbl_title2"] = lbl_title2
    refs["lbl_sub"]    = lbl_sub
    refs["lbl_lang"]   = lbl_lang

    # ── Separador ───────────────────────────
    tk.Frame(root, bg=ACCENT, height=1).grid(
        row=1, column=0, sticky="ew", padx=24, pady=4)

    # ────────────────────────────────────────────
    #  MODO (fila 2)
    # ────────────────────────────────────────────
    mf = tk.Frame(root, bg=BG)
    mf.grid(row=2, column=0, sticky="ew", padx=24, pady=8)

    lbl_mode = tk.Label(mf, text="Modo:", bg=BG, fg=DIM, font=FONT_UI)
    lbl_mode.pack(side="left")

    rb_encode = tk.Radiobutton(mf, text="Codificar  (archivo → video)",
                               variable=mode_var, value="encode",
                               bg=BG, fg=WHITE, selectcolor=BG,
                               activebackground=BG, activeforeground=ACCENT,
                               font=FONT_UI)
    rb_encode.pack(side="left", padx=14)

    rb_decode = tk.Radiobutton(mf, text="Decodificar  (video → archivo)",
                               variable=mode_var, value="decode",
                               bg=BG, fg=WHITE, selectcolor=BG,
                               activebackground=BG, activeforeground=ACCENT,
                               font=FONT_UI)
    rb_decode.pack(side="left", padx=14)

    refs["lbl_mode"] = lbl_mode
    refs["rb_encode"] = rb_encode
    refs["rb_decode"] = rb_decode

    # ────────────────────────────────────────────
    #  PANEL ORIGEN / DESTINO (fila 3)
    # ────────────────────────────────────────────
    panel = tk.Frame(root, bg=PANEL)
    panel.grid(row=3, column=0, sticky="ew", padx=24, pady=4)
    panel.columnconfigure(1, weight=1)

    pick_btns = []

    def make_row(row, label_key, var, picker_fn):
        lbl = tk.Label(panel, text=LANG["es"][label_key], bg=PANEL, fg=DIM,
                       font=FONT_UI, width=12, anchor="e")
        lbl.grid(row=row, column=0, padx=(12, 6), pady=8, sticky="e")

        entry = tk.Entry(panel, textvariable=var, bg="#111", fg=WHITE,
                         insertbackground=ACCENT, font=FONT_MONO,
                         relief="flat", bd=4)
        entry.grid(row=row, column=1, sticky="ew", padx=4, pady=8)

        btn = tk.Button(panel, text=LANG["es"]["pick_btn"],
                        command=picker_fn,
                        bg="#222", fg=ACCENT, relief="flat",
                        font=FONT_UI, padx=10, cursor="hand2")
        btn.grid(row=row, column=2, padx=(4, 12), pady=8)

        refs[f"row_lbl_{label_key}"] = (lbl, label_key)
        pick_btns.append(btn)
        return lbl, btn

    def pick_src():
        if mode_var.get() == "encode":
            path = filedialog.askopenfilename(title=t("pick_src_encode"))
        else:
            path = filedialog.askopenfilename(
                title=t("pick_src_decode"),
                filetypes=[(t("ft_mp4"), "*.mp4"), (t("ft_all"), "*.*")])
        if path:
            src_var.set(path)
            if not dst_var.get():
                d = os.path.dirname(path)
                if mode_var.get() == "encode":
                    dst_var.set(os.path.join(
                        d, os.path.splitext(os.path.basename(path))[0] + "_codec.mp4"))
                else:
                    dst_var.set(d)

    def pick_dst():
        if mode_var.get() == "encode":
            path = filedialog.asksaveasfilename(
                title=t("pick_dst_encode"),
                defaultextension=".mp4",
                filetypes=[(t("ft_mp4"), "*.mp4")])
        else:
            path = filedialog.askdirectory(title=t("pick_dst_decode"))
        if path:
            dst_var.set(path)

    lbl_src, btn_src = make_row(0, "src_label", src_var, pick_src)
    lbl_dst, btn_dst = make_row(1, "dst_label", dst_var, pick_dst)

    refs["lbl_src"] = lbl_src
    refs["lbl_dst"] = lbl_dst
    refs["btn_src"] = btn_src
    refs["btn_dst"] = btn_dst

    # ────────────────────────────────────────────
    #  BARRA DE PROGRESO (fila 4)
    # ────────────────────────────────────────────
    pf = tk.Frame(root, bg=BG)
    pf.grid(row=4, column=0, sticky="ew", padx=24, pady=(6, 2))
    pf.columnconfigure(0, weight=1)

    style = ttk.Style()
    style.theme_use("default")
    style.configure("TProgressbar", troughcolor=PANEL,
                    background=ACCENT, thickness=8)
    prog_bar = ttk.Progressbar(pf, variable=progress_var,
                               maximum=100, style="TProgressbar")
    prog_bar.grid(row=0, column=0, sticky="ew")

    # ── Etiqueta de estado ───────────────────
    lbl_status = tk.Label(root, textvariable=status_var,
                          bg=BG, fg=DIM, font=FONT_MONO,
                          anchor="w", wraplength=800)
    lbl_status.grid(row=5, column=0, sticky="ew", padx=28, pady=2)

    # ────────────────────────────────────────────
    #  LOG (fila 6) — expansible
    # ────────────────────────────────────────────
    lf = tk.Frame(root, bg=BG)
    lf.grid(row=6, column=0, sticky="nsew", padx=24, pady=4)
    lf.columnconfigure(0, weight=1)
    lf.rowconfigure(0, weight=1)

    log = tk.Text(lf, bg="#0a0a0a", fg="#44ff99", font=FONT_MONO,
                  relief="flat", state="disabled", wrap="word")
    log_scroll = ttk.Scrollbar(lf, orient="vertical", command=log.yview)
    log.configure(yscrollcommand=log_scroll.set)
    log.grid(row=0, column=0, sticky="nsew")
    log_scroll.grid(row=0, column=1, sticky="ns")

    def log_write(msg):
        log.configure(state="normal")
        log.insert("end", msg + "\n")
        log.see("end")
        log.configure(state="disabled")

    # ────────────────────────────────────────────
    #  BOTÓN PRINCIPAL (fila 7)
    # ────────────────────────────────────────────
    run_btn = tk.Button(root, text="▶  CODIFICAR",
                        bg=ACCENT, fg="#000",
                        font=("Segoe UI", 12, "bold"),
                        relief="flat", padx=28, pady=10,
                        cursor="hand2")
    run_btn.grid(row=7, column=0, pady=16)
    refs["run_btn"] = run_btn

    # ────────────────────────────────────────────
    #  PIE DE PÁGINA (fila 8)
    # ────────────────────────────────────────────
    footer_text = (f"Codec: {SIZE[0]}×{SIZE[1]}px  |  {BLOCK}px/celda  |  "
                   f"{COLS}×{ROWS} celdas  |  "
                   f"{BITS_PER_FRAME:,} bits/frame  |  {REPEAT}× redundancia  |  {FPS} fps")
    tk.Label(root, text=footer_text,
             bg=BG, fg="#333", font=("Courier New", 8)).grid(
                 row=8, column=0, pady=(0, 10))

    # ────────────────────────────────────────────
    #  Lógica de actualización de idioma
    # ────────────────────────────────────────────
    def apply_language(lang_code):
        current_lang["code"] = lang_code
        L = LANG[lang_code]

        refs["lbl_title"].config(text=L["title"])
        refs["lbl_title2"].config(text=L["title2"])
        refs["lbl_sub"].config(text=L["subtitle"])
        refs["lbl_lang"].config(text=L["lang_label"])
        refs["lbl_mode"].config(text=L["mode_label"])
        refs["rb_encode"].config(text=L["encode_radio"])
        refs["rb_decode"].config(text=L["decode_radio"])
        refs["lbl_src"].config(text=L["src_label"])
        refs["lbl_dst"].config(text=L["dst_label"])
        refs["btn_src"].config(text=L["pick_btn"])
        refs["btn_dst"].config(text=L["pick_btn"])

        # Botón principal según modo actual
        mode = mode_var.get()
        refs["run_btn"].config(
            text=L["run_encode"] if mode == "encode" else L["run_decode"])

        # Estado (sólo si dice "Listo" o "Completado" — no sobreescribir errores en curso)
        cur = status_var.get()
        for code in LANG_KEYS:
            if cur in (LANG[code]["status_ready"], LANG[code]["status_done"]):
                status_var.set(L["status_ready"] if cur == LANG[code]["status_ready"]
                               else L["status_done"])
                break

    def on_lang_change(event=None):
        display = lang_var.get()
        # Mapear nombre → código
        for code, name in LANG_NAMES.items():
            if name == display:
                apply_language(code)
                break

    combo_lang.bind("<<ComboboxSelected>>", on_lang_change)

    # ────────────────────────────────────────────
    #  Cambio de modo
    # ────────────────────────────────────────────
    def update_mode(*_):
        mode = mode_var.get()
        L = LANG[current_lang["code"]]
        run_btn.config(text=L["run_encode"] if mode == "encode" else L["run_decode"])
        src_var.set("")
        dst_var.set("")
        progress_var.set(0)
        status_var.set(L["status_ready"])

    mode_var.trace_add("write", update_mode)

    # ────────────────────────────────────────────
    #  Callback de progreso
    # ────────────────────────────────────────────
    def progress_cb(pct, msg):
        progress_var.set(pct)
        status_var.set(msg)
        log_write(f"[{pct:3.0f}%] {msg}")
        root.update_idletasks()

    # ────────────────────────────────────────────
    #  Tarea principal (encode / decode)
    # ────────────────────────────────────────────
    def run_task():
        src  = src_var.get().strip()
        dst  = dst_var.get().strip()
        L    = LANG[current_lang["code"]]

        if not src:
            messagebox.showwarning(L["warn_src_title"], L["warn_src_msg"])
            return
        if not dst:
            messagebox.showwarning(L["warn_dst_title"], L["warn_dst_msg"])
            return

        run_btn.config(state="disabled")
        progress_var.set(0)

        def task():
            try:
                if mode_var.get() == "encode":
                    info = encode_file(src, dst, progress_cb)
                    Lx = LANG[current_lang["code"]]
                    log_write(
                        f"\n{Lx['log_encoded']}\n"
                        f"   {Lx['log_original']}  : {info['file_size']:,} bytes\n"
                        f"   {Lx['log_ext']}        : {info['ext']}\n"
                        f"   {Lx['log_frames']}     : {info['data_frames']}\n"
                        f"   {Lx['log_duration']}   : {info['duration_s']:.1f} s\n"
                        f"   {Lx['log_saved']}      : {info['output']}\n")
                else:
                    info = decode_video(src, dst, progress_cb)
                    Lx = LANG[current_lang["code"]]
                    log_write(
                        f"\n{Lx['log_decoded']}\n"
                        f"   {Lx['log_ext_rec']}    : {info['ext']}\n"
                        f"   {Lx['log_size']}       : {info['file_size']:,} bytes\n"
                        f"   {Lx['log_checksum']}   : {Lx['log_checksum_ok']}\n"
                        f"   {Lx['log_saved']}      : {info['output']}\n")
                status_var.set(LANG[current_lang["code"]]["status_done"])
            except Exception as e:
                log_write(f"\n✖ ERROR: {e}\n")
                status_var.set(f"Error: {e}")
                messagebox.showerror(
                    LANG[current_lang["code"]]["err_title"], str(e))
            finally:
                run_btn.config(state="normal")

        threading.Thread(target=task, daemon=True).start()

    run_btn.config(command=run_task)

    root.mainloop()