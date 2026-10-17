class PromptsError(Exception):
    pass


class DuplicatePromptIdError(PromptsError):
    pass


class MissingPromptsError(PromptsError):
    pass


class MissingResponseSchemaError(PromptsError):
    pass
