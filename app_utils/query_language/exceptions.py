class QueryLangException(Exception):
    def __init__(self, message, caught: bool = False):
        super(QueryLangException, self).__init__(message)
        self.caught = caught


class LogicOperatorError(QueryLangException):
    pass


class WrongMethodError(QueryLangException):
    pass


class WrongKeywordError(QueryLangException):
    pass


class WrongTokenError(QueryLangException):
    pass


class QuerySyntaxError(QueryLangException):
    pass


class TreeBuildingError(QueryLangException):
    pass


class ArgumentTypeError(QueryLangException):
    pass


class ResultPrint(QueryLangException):
    pass
