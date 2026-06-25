Transform any file into a video and recover it later with integrity verification.

This project explores a simple but interesting idea: storing arbitrary binary data inside video frames using a custom 16-color encoding scheme designed to survive video compression, including recompression by platforms such as YouTube.

The entire project was built through vibe coding: the architecture, optimizations, experimentation, debugging and implementation were iteratively developed with AI assistance and human guidance.

How It Works
Any file is read as raw bytes.
  A metadata header is added:
  Magic signature
  Codec version
  File size
  SHA-256 checksum
  Original extension
  Data is converted into 4-bit values (nibbles).
  Each nibble is represented by one of 16 carefully selected colors.
  The colors are drawn into a Full HD video (1920×1080).
  Every data frame is repeated multiple times for redundancy.
  The resulting video can be uploaded, downloaded and decoded back into the original file.
  A checksum verifies that the recovered file is identical to the original.
Features
  Encode any file type
  Decode back to the original file
  Full HD output (1920×1080)
  16-color compression-resistant palette
  SHA-256 integrity verification
  Frame redundancy system
  Multi-threaded encoding
  Multi-threaded decoding
  Optional GPU acceleration through NVIDIA NVENC
  Automatic fallback to CPU encoding
  YouTube-compatible H.264 output
  Graphical interface built with Tkinter


Technical Specifications
| Parameter     | Value     |
| ------------- | --------- |
| Resolution    | 1920×1080 |
| Cell Size     | 16×16 px  |
| Grid          | 120×67    |
| Colors        | 16        |
| Bits per Cell | 4         |
| FPS           | 30        |
| Redundancy    | 3×        |
| Codec Version | 2         |
| Hash          | SHA-256   |
