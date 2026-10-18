class DemoError(Exception):
    pass


class DemoDisabledError(DemoError):
    pass


class DemoAccessDeniedError(DemoError):
    pass


class DemoScenarioMissingError(DemoError):
    pass


class DemoLaunchMissingError(DemoError):
    pass


class DemoBusyError(DemoError):
    pass


class DemoResetFailedError(DemoError):
    pass


class DemoLaunchLimitError(DemoError):
    pass


class DemoScenarioUnavailableError(DemoError):
    pass
