import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from nonebot.log import logger


_ACTIVE_TASKS: set[asyncio.Task] = set()
QUICK_WAIT_SECONDS = 1.0
DELIVERY_TIMEOUT_SECONDS = 900.0
MAX_ACTIVE_TASKS = 8
COMPLETED_REUSE_SECONDS = 120.0
MAX_RETAINED_TASKS = 64


class RecommendationDelivery:
    def __init__(self):
        self.tasks: dict[str, asyncio.Task] = {}
        self.deferred: set[str] = set()

    def forget(self, key, task):
        if self.tasks.get(key) is task:
            self.tasks.pop(key, None)
            self.deferred.discard(key)

    async def submit(
        self,
        key: str,
        operation: Callable[[], Awaitable[Any]],
        notify: Callable[[Any], Awaitable[None]],
    ) -> Any:
        task = self.tasks.get(key)
        created = task is None
        if task is None:
            if len(_ACTIVE_TASKS) >= MAX_ACTIVE_TASKS:
                return json.dumps({"status": "busy", "message": "推荐任务较多，请稍后再试。"}, ensure_ascii=False)
            if len(self.tasks) >= MAX_RETAINED_TASKS:
                return json.dumps({"status": "busy", "message": "推荐任务较多，请稍后再试。"}, ensure_ascii=False)

            async def run():
                try:
                    result = await asyncio.wait_for(operation(), timeout=DELIVERY_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    result = json.dumps(
                        {"status": "failed", "message": "推荐生成超时，请稍后重试。"}, ensure_ascii=False
                    )
                except Exception as error:
                    logger.warning(f"AI recommendation background failure: {type(error).__name__}")
                    result = json.dumps(
                        {"status": "failed", "message": "推荐生成失败，请稍后重试。"}, ensure_ascii=False
                    )
                if key in self.deferred:
                    try:
                        await asyncio.wait_for(notify(result), timeout=15)
                    except Exception as error:
                        logger.warning(f"AI recommendation notification failed: {type(error).__name__}")
                return result

            task = asyncio.create_task(run())
            self.tasks[key] = task
            _ACTIVE_TASKS.add(task)
            task.add_done_callback(_ACTIVE_TASKS.discard)

            def completed(done):
                if done.cancelled():
                    self.forget(key, done)
                    return
                result = done.result()
                if isinstance(result, list):
                    result = next((item.get("text") for item in result if item.get("type") == "text"), "")
                try:
                    succeeded = json.loads(result).get("status") == "sent"
                except (ValueError, TypeError, AttributeError):
                    succeeded = result == "sent"
                if not succeeded:
                    self.forget(key, done)
                    return
                asyncio.get_running_loop().call_later(COMPLETED_REUSE_SECONDS, self.forget, key, done)

            task.add_done_callback(completed)
        try:
            done, _ = await asyncio.wait([task], timeout=QUICK_WAIT_SECONDS)
        except asyncio.CancelledError:
            if created and key not in self.deferred:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                self.tasks.pop(key, None)
            raise
        if done:
            return task.result()
        self.deferred.add(key)
        return json.dumps(
            {
                "status": "pending",
                "success": True,
                "reason_code": "recommendation_queued",
                "next_action": "finish",
                "image_sent": False,
                "message": (
                    "推荐任务提交成功，图片尚未发送；完成后会自动发送。请告知用户正在准备，不要重复调用或编造推荐结果。"
                ),
            },
            ensure_ascii=False,
        )


shared_recommendation_delivery = RecommendationDelivery()
