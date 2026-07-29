"""Package marker — its module name must collapse to `sub`, not `sub.__init__`."""


class Marker:
    def ping(self) -> None:
        pass
