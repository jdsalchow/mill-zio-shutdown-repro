# Test discovery leaves a ZIO runtime alive after closing its classloader

## Problem

On Mill 1.1.10, a ZIO 2.1.26 test passes, but Mill never exits and consumes one
CPU core. The JVM's `main` thread waits for a ZIO shutdown hook that is spinning
on class-loading failures.

## Cause

During discovery, ZIO's runner acquires a shared bootstrap runtime, released by
`runner.done()`. Mill's
[`getTestTasks0`](https://github.com/com-lihaoyi/mill/blob/1.1.10/libs/javalib/testrunner/src/mill/javalib/testrunner/TestRunnerUtils.scala#L399-L411)
discards the runner without calling `done()`. Its classloader is subsequently
closed, leaving runtime cleanup to a JVM shutdown hook. Class loading during
cleanup then fails, and ZIO loops while constructing the failure's stack trace
([related ZIO issue](https://github.com/zio/zio/issues/10208)).

## Suggested fix

Retain the discovery runner and call `done()` before its classloader closes.
The minimal candidate change in `getTestTasks0` is:

```diff
-    val ( /*runner*/ _, tasksArr) =
+    val (runner, tasksArr) =
       getTestTasks(framework, args, classFilter, cl, testClassfilePath, discoveredTestClasses)
-    tasksArr.flatten.map(_.taskDef()).filter(_ != null).map(_.fullyQualifiedName())
+    try tasksArr.flatten.map(_.taskDef()).filter(_ != null).map(_.fullyQualifiedName())
+    finally runner.done()
```

This covers cleanup after `getTestTasks` returns. If that helper throws during
discovery or task creation, it must also clean up its runner before rethrowing.
The patch above has not been tested against a patched Mill.

## Reproduction

Verified with Scala 3.8.4, JDK 21.0.10, macOS arm64.
The single test's bootstrap is:

```scala
ZLayer.fromZIO(ZIO.scoped(ZIO.addFinalizer(ZIO.unit))) >>> testEnvironment
```

Run the attached project with `uv` and a JDK providing `jcmd` on PATH:

```sh
uv run reproduce.py
```
