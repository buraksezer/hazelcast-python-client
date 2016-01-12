import logging
import threading
import sys
from hazelcast.util import thread_id

NONE_RESULT = object()


class Future(object):
    _result = None
    _exception = None
    _traceback = None
    _threading_locals = threading.local()
    logger = logging.getLogger("Future")

    def __init__(self):
        self._callbacks = []
        self._event = threading.Event()
        pass

    def set_result(self, result):
        if result is None:
            self._result = NONE_RESULT
        else:
            self._result = result
        self._event.set()
        self._invoke_callbacks()

    def set_exception(self, exception, traceback=None):
        if not isinstance(exception, BaseException):
            raise RuntimeError("Exception must be of BaseException type")
        self._exception = exception
        self._traceback = traceback
        self._event.set()
        self._invoke_callbacks()

    def result(self):
        self._reactor_check()
        self._event.wait()
        if self._exception:
            raise self._exception
        if self._result == NONE_RESULT:
            return None
        else:
            return self._result

    def _reactor_check(self):
        if not self._event.isSet() and hasattr(self._threading_locals, 'is_reactor_thread'):
            raise RuntimeError(
                "Synchronous result for incomplete operation must not be called from Reactor thread. "
                "Use add_done_callback instead.")

    def is_success(self):
        return self._result is not None

    def done(self):
        return self._event.isSet()

    def running(self):
        return not self.done()

    def exception(self):
        self._reactor_check()
        self._event.wait()
        return self._exception

    def traceback(self):
        self._reactor_check()
        self._event.wait()
        return self._traceback

    def add_done_callback(self, callback):
        self._callbacks.append(callback)
        if self.done():
            self._invoke_cb(callback)

    def _invoke_callbacks(self):
        for callback in self._callbacks:
            self._invoke_cb(callback)

    def _invoke_cb(self, callback):
        try:
            callback(self)
        except:
            logging.exception("Exception when invoking callback")

    def continue_with(self, continuation_func):
        """
        Create a continuation that executes when the future is completed
        :param continuation_func: A function which takes the future as the only parameter. Return value of the function
        will be set as the result of the continuation future
        :return: A new future which will be completed when the continuation is done
        """
        future = Future()

        def callback(f):
            try:
                future.set_result(continuation_func(f))
            except:
                future.set_exception(sys.exc_info()[1], sys.exc_info()[2])

        self.add_done_callback(callback)
        return future


class ImmediateFuture(Future):
    def __init__(self, result):
        self._result = result
        pass

    def set_exception(self, exception):
        raise NotImplementedError()

    def set_result(self, result):
        raise NotImplementedError()

    def done(self):
        return True

    def is_success(self):
        return True

    def exception(self):
        return None