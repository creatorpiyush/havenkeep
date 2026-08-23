import asyncio
from typing import List, Dict, Any, Callable, Awaitable

class BatchProcessor:
    """
    Asynchronous batch processing engine for non-interactive tasks
    (bulk risk classification, audit summary generation, embeddings).
    """
    
    @classmethod
    async def process_batch(
        cls, 
        items: List[Any], 
        async_worker_func: Callable[[Any], Awaitable[Dict[str, Any]]],
        concurrency_limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Executes an async worker function across a batch of items with concurrency control.
        """
        semaphore = asyncio.Semaphore(concurrency_limit)
        
        async def _bounded_worker(item: Any) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await async_worker_func(item)
                except Exception as exc:
                    return {"item": str(item), "error": str(exc), "status": "FAILED"}

        tasks = [_bounded_worker(item) for item in items]
        return await asyncio.gather(*tasks)
