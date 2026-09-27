# Mill / ZIO shutdown hang

A passing ZIO 2.1.26 test leaves Mill 1.1.10 spinning at one CPU core instead
of exiting.

During test discovery, ZIO acquires a shared bootstrap runtime. Mill discards
the discovery runner without calling `done()`, then closes its classloader.
The runtime survives until JVM shutdown, when cleanup needs classes that the
closed loader can no longer load. ZIO then fails while constructing the error's
stack trace and repeatedly enters the same failure-reporting path.

The trigger is a scoped no-op finalizer in [ReproSpec.scala](repro/test/src/repro/ReproSpec.scala).
The finalizer itself finishes during bootstrap. The proposed fixes are to
[finalize Mill's discovery runner](ISSUE-MILL.md) before closing its loader and
[stop ZIO's error-reporting loop](ISSUE-ZIO.md).

Targets [Mill 1.1.10](https://github.com/com-lihaoyi/mill/releases/tag/1.1.10) and
[ZIO 2.1.26](https://github.com/zio/zio/releases/tag/v2.1.26), the latest stable
releases as of 2026-09-27. Verified with Scala 3.8.4, JDK 21.0.10, macOS arm64.
On macOS/Linux, with `uv` and a JDK providing `jcmd` on PATH:

```sh
uv run reproduce.py
```

The script uses Mill's PID file, captures two thread dumps, and kills its own
process group. Inspect `out/repro-*/run.log` for test success, then `threads-*.txt`
for `main` waiting on shutdown hooks and a hook in `failCause` / `generateStackTrace`.
Its CPU time increases between samples. Exit `124` means the watchdog stopped
the run; a timeout alone does not prove this bug. Use `--timeout 300` for slow downloads.
One captured run is included under [evidence](evidence/README.md).

The underlying command, without the watchdog, is:

```sh
./mill --no-daemon --ticker false repro.test
```
