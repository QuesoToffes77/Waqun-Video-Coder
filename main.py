"""
VideoCodec — Punto de entrada (CLI y GUI).
Uso:
    python main.py encode <archivo_entrada> [salida.mp4]
    python main.py decode <video.mp4> [carpeta_salida]
    python main.py gui
"""

import os
import sys

from videocodec import encode_file, decode_video
from gui import run_gui


def main():
    args = sys.argv[1:]
    if not args or args[0] == "gui":
        run_gui()
        return

    cmd = args[0].lower()

    if cmd == "encode":
        if len(args) < 2:
            print("Uso: python main.py encode <archivo> [salida.mp4]")
            sys.exit(1)
        src = args[1]
        dst = args[2] if len(args) > 2 else \
              os.path.splitext(src)[0] + "_codec.mp4"
        encode_file(src, dst)

    elif cmd == "decode":
        if len(args) < 2:
            print("Uso: python main.py decode <video.mp4> [carpeta_salida]")
            sys.exit(1)
        src     = args[1]
        out_dir = args[2] if len(args) > 2 else os.path.dirname(src) or "."
        decode_video(src, out_dir)

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()