import asyncio
import copy
import time
from collections import OrderedDict

from .exceptions import NetworkError


class RecommendationResponseCache:
    def __init__(self, capacity=64, max_pending=8):
        self.capacity = capacity
        self.max_pending = max_pending
        self.values = OrderedDict()
        self.pending = {}

    async def get(self, key, factory, ttl):
        cached = self.values.get(key)
        if ttl > 0 and cached is not None and cached[0] > time.monotonic():
            self.values.move_to_end(key)
            return copy.deepcopy(cached[1])
        self.values.pop(key, None)
        task = self.pending.get(key)
        if task is None:
            if len(self.pending) >= self.max_pending:
                raise NetworkError("推荐请求较多，请稍后再试")

            async def compute():
                try:
                    result = await factory()
                    if ttl > 0 and result.recommendations:
                        self.values[key] = (time.monotonic() + ttl, copy.deepcopy(result))
                        self.values.move_to_end(key)
                        while len(self.values) > self.capacity:
                            self.values.popitem(last=False)
                    return result
                finally:
                    self.pending.pop(key, None)

            task = asyncio.create_task(compute())
            task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            self.pending[key] = task
        return copy.deepcopy(await asyncio.shield(task))


response_cache = RecommendationResponseCache()
