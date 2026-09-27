# Evidence

Mill 1.1.10 and ZIO 2.1.26, the latest stable releases checked on 2026-09-27.
Scala 3.8.4; JDK 21.0.10; macOS arm64.

`uv run reproduce.py` reported one passing test. While main waited for shutdown
hooks, the same ZIO hook's CPU time increased from 3302.92 ms to
4503.60 ms between samples in the failure-reporting path. The watchdog
captured the dumps, stopped its process group, and exited 124.
