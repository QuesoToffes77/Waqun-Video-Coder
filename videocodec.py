"""
VideoCodec — Constantes, header, encode y decode (módulo único).
Modo: 16 colores (4 bits/celda), bloques 16×16px, robusto ante compresión YouTube.
"""

import cv2
import numpy as np
import struct
import hashlib
import os
import shutil
import subprocess
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

# OpenCV trae su propio threadpool interno; al paralelizar nosotros con hilos
# conviene limitarlo a 1 para que no compita por los nucleos (evita oversubscription).
try:
    _CV_DEFAULT_THREADS = cv2.getNumThreads()
except Exception:
    _CV_DEFAULT_THREADS = None

DEFAULT_WORKERS = os.cpu_count() or 1


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES Y CONFIGURACIÓN GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

BLOCK  = 16         # Tamaño de celda en píxeles (16×16 para sobrevivir compresión)
REPEAT = 3          # Redundancia: cada frame de datos se graba N veces (mayoría en decode)
FPS    = 30         # 30 fps es suficiente y reduce tamaño del video

# Resolución: 1920×1080 (Full HD 16:9).
# 1920 / 16 = 120 columnas exactas, 1080 / 16 = 67 filas exactas.
SIZE   = (1920, 1080)

COLS   = SIZE[0] // BLOCK      # 120 columnas
ROWS   = SIZE[1] // BLOCK      # 67 filas

# Cada celda almacena 4 bits (1 nibble = 1 de 16 colores)
NIBBLES_PER_FRAME = COLS * ROWS          # 8.040 nibbles
BITS_PER_FRAME    = NIBBLES_PER_FRAME * 4  # 32.160 bits = 4.020 bytes

EXT_MAX = 32

# ── Header ────────────────────────────────────────────────────────────────
MAGIC   = b"VBCO"
VERSION = 2   # versión 2 = modo 16 colores

# ══════════════════════════════════════════════════════════════════════════════
# PALETA DE 16 COLORES  (diseñada para sobrevivir 4:2:0 + compresión H.264)
# ══════════════════════════════════════════════════════════════════════════════
#
# Estrategia:
#   • 4 niveles de luminancia: Y ≈ 50, 100, 155, 210  (ΔY ≈ 55 entre niveles)
#   • 4 combinaciones de crominancia (Cb, Cr) bien separadas:
#       A = (128, 128)  gris neutro
#       B = (180,  80)  azulado
#       C = ( 76, 180)  anaranjado/rojo
#       D = ( 76,  76)  verdoso
#   • ΔCb o ΔCr ≥ 52 entre cualquier par de grupos → sobrevive subsampling 4:2:0
#   • Separación mínima entre los 16 colores en YCbCr: ~55 unidades
#
# Índice nibble → BGR (para OpenCV)
# Conversión YCbCr→BGR: B=Y+1.773*(Cb-128), G=Y-0.344*(Cb-128)-0.714*(Cr-128), R=Y+1.403*(Cr-128)

def _ycbcr_to_bgr(Y, Cb, Cr):
    R = Y + 1.403 * (Cr - 128)
    G = Y - 0.344 * (Cb - 128) - 0.714 * (Cr - 128)
    B = Y + 1.773 * (Cb - 128)
    return (
        int(np.clip(B, 0, 255)),
        int(np.clip(G, 0, 255)),
        int(np.clip(R, 0, 255)),
    )

# 4 niveles Y × 4 combinaciones Cb/Cr = 16 colores
_Y_LEVELS  = [50, 105, 160, 215]
_CBR_PAIRS = [(128, 128), (185, 75), (75, 185), (75, 75)]

PALETTE_BGR = np.array([
    _ycbcr_to_bgr(y, cb, cr)
    for y in _Y_LEVELS
    for cb, cr in _CBR_PAIRS
], dtype=np.uint8)   # shape (16, 3)  — cada fila es (B, G, R)

# Paleta en float32 para cálculos de distancia
_PALETTE_F32 = PALETTE_BGR.astype(np.float32)

# ── Tabla de lookup inversa en YCbCr para clasificación robusta ──────────────
# Convertimos la paleta a YCbCr para comparar en ese espacio en el decoder
def _bgr_palette_to_ycbcr():
    bgr_img = PALETTE_BGR.reshape(1, 16, 3)
    ycbcr   = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2YCrCb)  # OpenCV usa YCrCb
    # Reordenar a YCbCr convencional
    y  = ycbcr[0, :, 0].astype(np.float32)
    cr = ycbcr[0, :, 1].astype(np.float32)
    cb = ycbcr[0, :, 2].astype(np.float32)
    return np.stack([y, cb, cr], axis=1)   # (16, 3)

_PALETTE_YCBCR = _bgr_palette_to_ycbcr()

# ── Clasificador de nibbles: Numba JIT si está disponible, si no numpy ────────
# (acelera ~10x la asignacion al color de paleta mas cercano en YCbCr)
try:
    from numba import njit

    @njit(fastmath=True, cache=True)
    def _classify_njit(avg, pal):           # avg (N,3) YCbCr float32, pal (16,3)
        n = avg.shape[0]
        out = np.empty(n, np.uint8)
        for i in range(n):
            best = 1e18; bj = 0
            for j in range(16):
                dy  = (avg[i, 0] - pal[j, 0]) * 1.5
                dcb =  avg[i, 1] - pal[j, 1]
                dcr =  avg[i, 2] - pal[j, 2]
                d = dy * dy + dcb * dcb + dcr * dcr
                if d < best:
                    best = d; bj = j
            out[i] = bj
        return out

    # warm-up de compilacion para no pagar el JIT en el primer frame
    _classify_njit(np.zeros((1, 3), np.float32), _PALETTE_YCBCR.astype(np.float32))
    _PAL_NJIT = _PALETTE_YCBCR.astype(np.float32)
    _HAVE_NUMBA = True
except Exception:
    _HAVE_NUMBA = False


def _classify(avg):
    """avg: (N,3) en YCbCr float32 -> nibbles uint8 (0-15)."""
    if _HAVE_NUMBA:
        return _classify_njit(np.ascontiguousarray(avg, np.float32), _PAL_NJIT)
    diff = avg[:, None, :] - _PALETTE_YCBCR[None, :, :]
    diff[:, :, 0] *= 1.5
    dists = np.einsum('nij,nij->ni', diff, diff)
    return np.argmin(dists, axis=1).astype(np.uint8)


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════

def _build_header(file_bytes: bytes, ext: str) -> bytes:
    checksum  = hashlib.sha256(file_bytes).digest()[:4]
    ext_bytes = ext.encode("utf-8")[:EXT_MAX].ljust(EXT_MAX, b"\x00")
    header    = (MAGIC
                 + struct.pack(">I", VERSION)
                 + struct.pack(">I", len(file_bytes))
                 + checksum
                 + ext_bytes)
    return header.ljust(800, b"\x00")

def _parse_header(header_bytes: bytes) -> dict:
    if header_bytes[:4] != MAGIC:
        raise ValueError(f"Magic inválido: {header_bytes[:4]!r} (esperado {MAGIC!r})")
    version   = struct.unpack(">I", header_bytes[4:8])[0]
    file_size = struct.unpack(">I", header_bytes[8:12])[0]
    checksum  = header_bytes[12:16]
    ext       = header_bytes[16:16+EXT_MAX].rstrip(b"\x00").decode("utf-8", errors="replace")
    return {"version": version, "file_size": file_size, "checksum": checksum, "ext": ext}


# ══════════════════════════════════════════════════════════════════════════════
# PRIMITIVAS
# ══════════════════════════════════════════════════════════════════════════════

def _bytes_to_nibbles(data: bytes) -> np.ndarray:
    """bytes → array uint8 de nibbles (4 bits cada uno, 0–15), MSB first."""
    arr = np.frombuffer(data, dtype=np.uint8)
    hi  = (arr >> 4) & 0x0F
    lo  = arr & 0x0F
    return np.stack([hi, lo], axis=1).flatten()

def _nibbles_to_bytes(nibbles: np.ndarray) -> bytes:
    """array uint8 de nibbles → bytes. Requiere longitud par."""
    n = (len(nibbles) // 2) * 2
    pairs = nibbles[:n].reshape(-1, 2)
    return ((pairs[:, 0].astype(np.uint8) << 4) | pairs[:, 1].astype(np.uint8)).tobytes()

def _make_frame(nibbles_chunk: np.ndarray) -> np.ndarray:
    """Array de nibbles (0-15) -> frame BGR 1920x1080. Expansion de bloques via
    cv2.resize INTER_NEAREST (identico a kron pero ~1.26x mas rapido)."""
    padded = np.zeros(NIBBLES_PER_FRAME, dtype=np.uint8)
    n = min(len(nibbles_chunk), NIBBLES_PER_FRAME)
    padded[:n] = nibbles_chunk[:n]
    color_map = PALETTE_BGR[padded].reshape(ROWS, COLS, 3)
    big = cv2.resize(color_map, (COLS * BLOCK, ROWS * BLOCK),
                     interpolation=cv2.INTER_NEAREST)
    frame_bgr = np.zeros((SIZE[1], SIZE[0], 3), dtype=np.uint8)
    frame_bgr[:big.shape[0], :big.shape[1]] = big
    return frame_bgr

def _read_frame_nibbles(frame_bgr: np.ndarray) -> np.ndarray:
    """
    Frame BGR → array uint8 de nibbles (0–15).
    Clasificación por vecino más cercano en espacio YCbCr, promediando el centro
    del bloque (50% central) para evitar artefactos de borde.
    """
    if frame_bgr.shape[:2] != (SIZE[1], SIZE[0]):
        frame_bgr = cv2.resize(frame_bgr, SIZE, interpolation=cv2.INTER_AREA)

    # Convertir a YCrCb (OpenCV) y luego reordenar a YCbCr
    ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb).astype(np.float32)
    Y  = ycrcb[:, :, 0]
    Cr = ycrcb[:, :, 1]
    Cb = ycrcb[:, :, 2]

    # Centro del bloque: píxeles [B//4 : 3*B//4] dentro de cada celda
    margin = BLOCK // 4   # 4px de margen en bloques de 16px
    inner  = BLOCK - 2 * margin   # 8px de zona interior

    nibbles = np.empty(NIBBLES_PER_FRAME, dtype=np.uint8)
    idx = 0
    for row in range(ROWS):
        ry = row * BLOCK + margin
        for col in range(COLS):
            cx = col * BLOCK + margin
            patch_Y  = Y [ry:ry+inner, cx:cx+inner]
            patch_Cb = Cb[ry:ry+inner, cx:cx+inner]
            patch_Cr = Cr[ry:ry+inner, cx:cx+inner]

            avg = np.array([
                patch_Y.mean(),
                patch_Cb.mean(),
                patch_Cr.mean(),
            ], dtype=np.float32)

            # Distancia euclidiana a cada color de la paleta en YCbCr
            # Ponderamos Y más porque es más robusto tras compresión
            diff = _PALETTE_YCBCR - avg
            diff[:, 0] *= 1.5   # peso extra a luminancia
            dists = np.einsum('ij,ij->i', diff, diff)
            nibbles[idx] = np.argmin(dists)
            idx += 1

    return nibbles


def _read_frame_nibbles_fast(frame_bgr: np.ndarray) -> np.ndarray:
    """Frame BGR -> nibbles (0-15) via imagen integral (~2.65x mas rapido,
    salida bit-identica al metodo de promedio de centro de bloque)."""
    if frame_bgr.shape[:2] != (SIZE[1], SIZE[0]):
        frame_bgr = cv2.resize(frame_bgr, SIZE, interpolation=cv2.INTER_AREA)
    ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)   # uint8, sin astype global
    margin = BLOCK // 4
    inner  = BLOCK - 2 * margin
    ii = cv2.integral(ycrcb)                               # (H+1,W+1,3) suma acumulada
    r0 = np.arange(ROWS) * BLOCK + margin
    c0 = np.arange(COLS) * BLOCK + margin
    r1 = r0 + inner; c1 = c0 + inner
    A = ii[np.ix_(r0, c0)]; B = ii[np.ix_(r0, c1)]
    C = ii[np.ix_(r1, c0)]; D = ii[np.ix_(r1, c1)]
    s = (D - B - C + A)                                    # (ROWS,COLS,3) sumas de centro
    avg = s.astype(np.float32) / (inner * inner)
    avg = avg[:, :, [0, 2, 1]].reshape(-1, 3)             # YCrCb -> YCbCr
    return _classify(avg)


# ══════════════════════════════════════════════════════════════════════════════
# ENCODE
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# WRITER DE VIDEO  —  ffmpeg/H.264 (apto YouTube) con autodeteccion de encoder
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


@lru_cache(maxsize=1)
def _nvenc_works() -> bool:
    """Prueba real: codifica 1 frame con h264_nvenc. True solo si la GPU responde."""
    if not _have_ffmpeg():
        return False
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
             "-c:v", "h264_nvenc", "-frames:v", "1", "-f", "null", "-"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def _h264_cmd(output_path, encoder, crf, preset, threads):
    """Construye el comando ffmpeg para H.264 yuv420p compatible con YouTube."""
    base = ["ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{SIZE[0]}x{SIZE[1]}", "-r", str(FPS), "-i", "-", "-an"]
    if encoder == "nvenc":
        # GPU: codificacion por hardware, no consume CPU
        vid = ["-c:v", "h264_nvenc", "-preset", preset or "p4",
               "-rc", "constqp", "-qp", str(crf), "-profile:v", "high"]
    else:  # libx264 (CPU multihilo)
        vid = ["-c:v", "libx264", "-preset", preset or "veryfast",
               "-crf", str(crf), "-threads", str(threads)]
    tail = ["-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path]
    return base + vid + tail


def _resolve_encoder(encoder: str) -> str:
    """'auto' -> nvenc si la GPU responde, si no x264, si no falta ffmpeg -> mp4v."""
    if not _have_ffmpeg():
        return "mp4v"
    if encoder == "auto":
        return "nvenc" if _nvenc_works() else "x264"
    if encoder == "nvenc" and not _nvenc_works():
        return "x264"
    return encoder


# ══════════════════════════════════════════════════════════════════════════════
# ENCODE
# ══════════════════════════════════════════════════════════════════════════════

def encode_file(input_path: str, output_path: str = "output.mp4",
                progress_cb=None, encoder: str = "auto",
                crf: int = 16, preset: str = None,
                gen_workers: int = DEFAULT_WORKERS, threads: int = 0) -> dict:
    """Convierte cualquier archivo en un video de 16 colores 1920×1080.

    Salida H.264/yuv420p (apta YouTube) cuando hay ffmpeg; fallback a mp4v si no.
    encoder: 'auto' (nvenc->x264), 'nvenc', 'x264', 'mp4v'.
    crf: calidad (menor = mas calidad/robustez; 16 conserva bien los bloques).
    gen_workers: hilos para generar frames en paralelo (make_frame libera el GIL).
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Archivo no encontrado: {input_path}")

    with open(input_path, "rb") as f:
        file_bytes = f.read()
    ext = os.path.splitext(input_path)[1].lower() or ".bin"

    def _prog(pct, msg):
        if progress_cb: progress_cb(pct, msg)
        else: print(f"  [{pct:3.0f}%] {msg}")

    _prog(0, f"Leyendo {os.path.basename(input_path)}  ({len(file_bytes):,} bytes)")

    header_bytes  = _build_header(file_bytes, ext)
    payload_bytes = header_bytes + file_bytes
    nibbles       = _bytes_to_nibbles(payload_bytes)

    total_data_frames  = -(-len(nibbles) // NIBBLES_PER_FRAME)
    total_video_frames = total_data_frames * REPEAT

    used_encoder = _resolve_encoder(encoder)
    _prog(5, (f"Payload: {len(payload_bytes):,} bytes  →  {total_data_frames} frames de datos "
              f"({total_video_frames} de video a {FPS} fps)  |  encoder: {used_encoder}"))

    def gen(i):
        return _make_frame(nibbles[i * NIBBLES_PER_FRAME:(i + 1) * NIBBLES_PER_FRAME])

    report_every = max(1, total_data_frames // 20)
    gen_workers  = max(1, int(gen_workers))

    # ── Camino A: ffmpeg (H.264, YouTube) ────────────────────────────────────
    if used_encoder in ("nvenc", "x264"):
        if gen_workers > 1:
            cv2.setNumThreads(1)  # evitar oversubscription con la generacion paralela
        cmd  = _h264_cmd(output_path, used_encoder, crf, preset, threads)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        BATCH = 16
        try:
            ex = ThreadPoolExecutor(max_workers=gen_workers) if gen_workers > 1 else None
            try:
                for start in range(0, total_data_frames, BATCH):
                    idx = range(start, min(start + BATCH, total_data_frames))
                    batch = list(ex.map(gen, idx)) if ex else [gen(i) for i in idx]
                    for fr in batch:
                        buf = fr.tobytes()
                        for _ in range(REPEAT):
                            proc.stdin.write(buf)      # codificacion en paralelo (otro proceso)
                    if start % (report_every * BATCH) < BATCH:
                        _prog(5 + 90 * start / total_data_frames,
                              f"Codificando frame {start+1}/{total_data_frames}")
            finally:
                if ex: ex.shutdown()
        finally:
            proc.stdin.close(); rc = proc.wait()
            if gen_workers > 1:
                cv2.setNumThreads(_CV_DEFAULT_THREADS or 0)
        if rc != 0:
            raise RuntimeError(f"ffmpeg falló (código {rc}) con encoder {used_encoder}")

    # ── Camino B: fallback mp4v (sin ffmpeg) ─────────────────────────────────
    else:
        writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*"mp4v"),
                                 FPS, SIZE, isColor=True)
        if not writer.isOpened():
            raise RuntimeError(f"No se pudo crear el video en: {output_path}")
        for i in range(total_data_frames):
            frame = gen(i)
            for _ in range(REPEAT):
                writer.write(frame)
            if i % report_every == 0:
                _prog(5 + 90 * i / total_data_frames,
                      f"Escribiendo frame {i+1}/{total_data_frames}")
        writer.release()

    _prog(100, f"Listo → {output_path}  ({used_encoder})")
    return {
        "input":         input_path,
        "output":        output_path,
        "ext":           ext,
        "encoder":       used_encoder,
        "file_size":     len(file_bytes),
        "payload_bytes": len(payload_bytes),
        "data_frames":   total_data_frames,
        "video_frames":  total_video_frames,
        "duration_s":    total_video_frames / FPS,
    }


# ══════════════════════════════════════════════════════════════════════════════
# DECODE
# ══════════════════════════════════════════════════════════════════════════════

def _majority_vote_batch(buf_batch: np.ndarray) -> np.ndarray:
    """
    buf_batch: (n_grp, REPEAT, NIBBLES_PER_FRAME) uint8 (valores 0-15).
    Devuelve (n_grp, NIBBLES_PER_FRAME) con el nibble mayoritario por posicion.
    Identico al criterio original: gana el mas votado; en empate, el menor indice.
    """
    n_grp = buf_batch.shape[0]
    if REPEAT == 1:
        return buf_batch[:, 0, :].copy()
    votes = np.zeros((n_grp, 16, NIBBLES_PER_FRAME), dtype=np.uint8)
    for v in range(16):                        # 16 ops vectorizadas sobre todo el lote
        votes[:, v, :] = (buf_batch == v).sum(axis=1)
    return np.argmax(votes, axis=1).astype(np.uint8)


def decode_video(video_path: str, output_dir: str = ".",
                 progress_cb=None, n_workers: int = DEFAULT_WORKERS,
                 batch_groups: int = 8) -> dict:
    """Recupera el archivo original desde un video de 16 colores 1920×1080.

    n_workers: hilos para procesar frames en paralelo (cvtColor+integral liberan el GIL).
               1 = camino secuencial sin overhead de hilos.
    batch_groups: cuantos grupos (de REPEAT frames) leer y procesar por lote (acota RAM).
    """

    def _prog(pct, msg):
        if progress_cb: progress_cb(pct, msg)
        else: print(f"  [{pct:3.0f}%] {msg}")

    _prog(0, f"Abriendo {os.path.basename(video_path)}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"No se pudo abrir: {video_path}")

    total_v_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    n_groups       = total_v_frames // REPEAT
    _prog(2, f"Total frames: {total_v_frames}  ({n_groups} grupos de {REPEAT})")

    recovered_nibbles = np.empty((n_groups, NIBBLES_PER_FRAME), dtype=np.uint8)
    report_every = max(1, n_groups // 20)

    n_workers = max(1, int(n_workers))
    ZERO = np.zeros(NIBBLES_PER_FRAME, dtype=np.uint8)

    # Evitar oversubscription: si paralelizamos nosotros, OpenCV en 1 hilo por tarea.
    if n_workers > 1 and _CV_DEFAULT_THREADS is not None:
        cv2.setNumThreads(1)

    def _read_raw():
        ret, frame = cap.read()
        return frame if ret else None

    def _proc(frame):
        return ZERO if frame is None else _read_frame_nibbles_fast(frame)

    executor = ThreadPoolExecutor(max_workers=n_workers) if n_workers > 1 else None
    try:
        g = 0
        while g < n_groups:
            gb = min(batch_groups, n_groups - g)         # grupos en este lote
            nf = gb * REPEAT                              # frames a leer (secuencial, inevitable)
            frames = [_read_raw() for _ in range(nf)]
            if executor is not None:
                nibs = list(executor.map(_proc, frames)) # procesamiento paralelo, en orden
            else:
                nibs = [_proc(f) for f in frames]
            buf_batch = np.stack(nibs).reshape(gb, REPEAT, NIBBLES_PER_FRAME)
            recovered_nibbles[g:g+gb] = _majority_vote_batch(buf_batch)
            g += gb
            if (g // batch_groups) % max(1, (report_every // batch_groups + 1)) == 0:
                _prog(2 + 75 * g / n_groups, f"Procesando grupo {g}/{n_groups}")
    finally:
        if executor is not None:
            executor.shutdown()
        if n_workers > 1 and _CV_DEFAULT_THREADS is not None:
            cv2.setNumThreads(_CV_DEFAULT_THREADS)

    cap.release()
    _prog(77, "Convirtiendo nibbles a bytes...")

    flat      = recovered_nibbles.flatten()
    all_bytes = _nibbles_to_bytes(flat)

    _prog(80, "Desempaquetando header...")
    meta = _parse_header(all_bytes[:800])
    _prog(85, f"Header: ext={meta['ext']}  tamaño={meta['file_size']:,} bytes")

    file_bytes = all_bytes[800 : 800 + meta["file_size"]]

    if len(file_bytes) < meta["file_size"]:
        raise ValueError(
            f"Faltan bytes: esperaba {meta['file_size']}, got {len(file_bytes)}"
        )

    actual_checksum = hashlib.sha256(file_bytes).digest()[:4]
    if actual_checksum != meta["checksum"]:
        raise ValueError(
            f"Checksum inválido — video corrupto o recomprimido.\n"
            f"  Esperado: {meta['checksum'].hex()}\n"
            f"  Obtenido: {actual_checksum.hex()}"
        )

    _prog(95, "Checksum OK — guardando archivo...")

    os.makedirs(output_dir, exist_ok=True)
    base_name   = os.path.splitext(os.path.basename(video_path))[0]
    output_path = os.path.join(output_dir, base_name + "_recovered" + meta["ext"])

    with open(output_path, "wb") as f:
        f.write(file_bytes)

    _prog(100, f"Archivo recuperado → {output_path}")

    return {
        "video":       video_path,
        "output":      output_path,
        "ext":         meta["ext"],
        "file_size":   meta["file_size"],
        "checksum_ok": True,
    }