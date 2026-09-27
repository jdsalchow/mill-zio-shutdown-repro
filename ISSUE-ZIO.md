# Shutdown spins when reporting a class-loading failure

## Problem

On ZIO 2.1.26 with Mill 1.1.10, a passing test can leave a JVM shutdown hook
consuming one CPU core indefinitely. This reproduces the failure-reporting loop
discussed in [#10208](https://github.com/zio/zio/issues/10208).

## Cause

Mill triggers it by leaving a discovery runtime alive after closing its
classloader. At shutdown, class loading fails.
[`FiberRuntime.evaluateEffect`](https://github.com/zio/zio/blob/v2.1.26/core/shared/src/main/scala/zio/internal/FiberRuntime.scala#L463-L468)
handles the exception by calling `ZIO.failCause`, but its `generateStackTrace`
also needs an unavailable class. That failure returns to the same handler,
which calls `failCause` again indefinitely.

## Suggested fix

Guard diagnostics in
[`ZIO.failCause`](https://github.com/zio/zio/blob/v2.1.26/core/shared/src/main/scala/zio/ZIO.scala#L3256-L3264)
and preserve the original cause if they throw. Extend the
[previous suggestion](https://github.com/zio/zio/issues/10208#issuecomment-3456939881)
by appending the diagnostics failure as a defect:

```scala
def failCause[E](cause: => Cause[E])(implicit trace0: Trace): IO[E, Nothing] =
  ZIO.withFiberRuntime[Any, E, Nothing] { (state, _) =>
    val original = cause
    try {
      val trace = state.generateStackTrace()
      val refs  = state.getFiberRefs(false)
      val spans = refs.getOrDefault(FiberRef.currentLogSpan)
      val anns  = refs.getOrDefault(FiberRef.currentLogAnnotations)
      Exit.failCause(original.applyAll(trace, spans, anns))
    } catch {
      case t if nonFatal(t) => Exit.failCause(original ++ Cause.die(t))
    }
  }
```

Evaluate the by-name `cause` once, before collecting diagnostics.
[`++`](https://github.com/zio/zio/blob/v2.1.26/core/shared/src/main/scala/zio/Cause.scala#L35-L41)
records the original failure followed by the diagnostics failure.
`Exit.failCause` constructs a result directly, without collecting another fiber
stack trace or re-entering `ZIO.failCause`.
This uses ZIO's existing
[`nonFatal` predicate](https://github.com/zio/zio/blob/v2.1.26/core/shared/src/main/scala/zio/package.scala#L63), which catches `LinkageError`
while leaving `VirtualMachineError` fatal. The candidate patch has not been
tested against a patched ZIO. Mill should also fix its discovery-runtime lifetime.

## Reproduction

Verified with Scala 3.8.4, JDK 21.0.10, macOS arm64.
The attached project has one test and this bootstrap:

```scala
ZLayer.fromZIO(ZIO.scoped(ZIO.addFinalizer(ZIO.unit))) >>> testEnvironment
```

Run the attached project with `uv` and a JDK providing `jcmd` on PATH:

```sh
uv run reproduce.py
```
