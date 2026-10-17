class MailGatewayError(Exception):
    pass


class WebhookSignatureError(MailGatewayError):
    pass


class MailProviderError(MailGatewayError):
    pass


class MailboxAlreadyConnectedError(MailGatewayError):
    pass
