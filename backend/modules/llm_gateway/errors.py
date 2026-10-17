class LlmGatewayError(Exception):
    pass


class ModelNotConfiguredError(LlmGatewayError):
    pass


class StructuredExtractionError(LlmGatewayError):
    pass
