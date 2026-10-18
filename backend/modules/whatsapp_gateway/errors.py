class WhatsAppGatewayError(Exception):
    pass


class WhatsAppSignatureError(WhatsAppGatewayError):
    pass


class WhatsAppProviderError(WhatsAppGatewayError):
    pass


class WhatsAppPhoneInvalidError(WhatsAppGatewayError):
    pass


class WhatsAppNumberUnverifiedError(WhatsAppGatewayError):
    pass
