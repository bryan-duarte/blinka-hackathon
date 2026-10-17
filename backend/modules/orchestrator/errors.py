class OrchestratorError(Exception):
    pass


class AgentProviderError(OrchestratorError):
    pass


class MissingStructuredResponseError(AgentProviderError):
    pass
