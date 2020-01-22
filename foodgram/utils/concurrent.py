import asyncio


async def run_blocking(task, *args, executor=None):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, task, *args)
    return result
