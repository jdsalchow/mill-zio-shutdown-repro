package repro
import zio._
import zio.test._

object ReproSpec extends ZIOSpecDefault {
  override val bootstrap = ZLayer.fromZIO(ZIO.scoped(ZIO.addFinalizer(ZIO.unit))) >>> testEnvironment
  def spec = test("passes")(assertTrue(true))
}
