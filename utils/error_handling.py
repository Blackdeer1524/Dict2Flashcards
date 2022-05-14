import sys
import traceback


def error_handler(error_processing=None):
    def error_decorator(func):
        def method_wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                if error_processing is None:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
                    error_log = ''.join(lines)
                    print(error_log)
                else:
                    error_processing(self, e, *args, **kwargs)
        return method_wrapper
    return error_decorator
