class ThingsError(Exception):
    """An error safe to show without exposing credentials or task payloads."""


class CloudError(ThingsError):
    def __init__(self, status):
        self.status = status
        messages = {
            401: "Things Cloud authentication failed; run connect again.",
            403: "Things Cloud denied access; run connect again.",
            404: "Things Cloud history was not found; run connect again.",
            409: "The cloud history changed during this write. Sync and review before retrying.",
            412: "Things Cloud rejected the history ancestor. Sync before retrying.",
            429: "Things Cloud rate limit reached; try again later.",
        }
        super().__init__(messages.get(status, f"Things Cloud returned HTTP {status}."))


class UncertainWrite(ThingsError):
    pass
