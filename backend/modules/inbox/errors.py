class InboxError(Exception):
    pass


class MailboxConnectionMissingError(InboxError):
    pass


class EmailMissingError(InboxError):
    pass


class WhatsAppPhoneTakenError(InboxError):
    pass
