class PluginError(Exception):
    pass


class UnknownPluginName(PluginError):
    pass


class LoaderError(PluginError):
    pass


class WrongPluginProtocol(PluginError):
    pass
