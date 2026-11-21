# Bundled RAW decoder

The app dynamically loads the JTL bridge and LibRaw built into one native library per target. The bridge exports a small stable C interface; private C++ or Python object layouts never cross the boundary. The version and full commit are read from the loaded binary and checked before opening a file. LibRaw is unmodified; the app's BayerNet path consumes the unpacked mosaic, while unsupported CFA layouts use the same library's normal linear RGB processing.

- LibRaw upstream: https://github.com/LibRaw/LibRaw , master commit `40fb564486681a04eba0318058b0519f4f69eba8` (2026-11-20), `0.23.0-Snapshot202611`. Distributed under LGPL 2.1; upstream also offers CDDL. Copyright and both licenses are in the source archive.
- zlib 1.3.1: https://github.com/madler/zlib , `51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf`.
- IJG libjpeg 9f: https://www.ijg.org/files/jpegsrc.v9f.tar.gz , SHA-256 `04705c110cb2469caa79fb71fba3d7bf834914706e9641a4589485c1f832565b`. This software is based in part on the work of the Independent JPEG Group.

Extract `LibRaw-source.zip`, `zlib-source.zip` and `jpegsrc.v9f.tar.gz` into separate build directories. Call `python build.py win LIBRAW ZLIB JPEG WORK` on 64-bit Windows with LLVM clang and the MSVC/Windows SDK available. For the two Darwin targets use `arm64` or `x86_64` instead of `win` and append `--zig PATH/TO/zig` (Zig 0.13.0). Sources and licenses remain available offline. To develop against a different LibRaw revision update the compile-time pin and the matching loader pin in `raw_core.py` together.
