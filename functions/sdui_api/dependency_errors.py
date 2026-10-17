class DependencyError(Exception):
    def __init__(self, dependency: str, detail: str) -> None:
        super().__init__(f"{dependency}: {detail}")
        self.dependency = dependency
        self.detail = detail


class DependencyUnavailableError(DependencyError):
    pass


class DependencyFailureError(DependencyError):
    pass
