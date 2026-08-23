import pytest
import asyncio
from app.governance.cost_tracker import CostTracker
from app.services.cache_service import ToolResultCache
from app.governance.context_compressor import ContextCompressor
from app.services.batch_processor import BatchProcessor

def test_prompt_caching_token_accounting():
    """Verify CostTracker handles prompt caching token discounts and creation surcharges."""
    base_cost = CostTracker.calculate_cost(
        model_name="claude-3-5-sonnet-20240620",
        prompt_tokens=1_000_000,
        completion_tokens=0,
        cache_creation_tokens=0,
        cache_read_tokens=0
    )
    assert base_cost == 3.0

    # Cache read tokens (90% discount -> $0.30 per 1M tokens)
    read_cached_cost = CostTracker.calculate_cost(
        model_name="claude-3-5-sonnet-20240620",
        prompt_tokens=0,
        completion_tokens=0,
        cache_creation_tokens=0,
        cache_read_tokens=1_000_000
    )
    assert read_cached_cost == 0.30

    # Cache creation tokens (+25% surcharge -> $3.75 per 1M tokens)
    create_cached_cost = CostTracker.calculate_cost(
        model_name="claude-3-5-sonnet-20240620",
        prompt_tokens=0,
        completion_tokens=0,
        cache_creation_tokens=1_000_000,
        cache_read_tokens=0
    )
    assert create_cached_cost == 3.75

def test_tool_result_caching():
    """Verify ToolResultCache sets, retrieves, and clears cached read-only tool results."""
    ToolResultCache.clear()
    assert ToolResultCache.size() == 0

    tool = "file_read"
    kwargs = {"path": "docs/architecture.md"}
    result_data = {"content": "Havenkeep Architecture Details"}

    # Initially cache miss
    assert ToolResultCache.get(tool, kwargs) is None

    # Set cache entry
    ToolResultCache.set(tool, kwargs, result_data, ttl_seconds=60)
    assert ToolResultCache.size() == 1

    # Cache hit
    cached_res = ToolResultCache.get(tool, kwargs)
    assert cached_res == result_data

    # Clear cache
    ToolResultCache.clear()
    assert ToolResultCache.get(tool, kwargs) is None

def test_context_compressor_trimming():
    """Verify ContextCompressor trims verbose outputs and formats plan history."""
    verbose_outputs = [
        {"tool": "file_read", "output": "x" * 3000},
        {"tool": "web_search", "output": "short output"}
    ]
    compressed = ContextCompressor.compress_tool_outputs(verbose_outputs, max_chars_per_output=500)
    
    assert len(compressed) == 2
    assert compressed[0]["is_truncated"] is True
    assert "... [Truncated" in compressed[0]["output"]
    assert len(compressed[0]["output"]) < 600
    assert compressed[1].get("is_truncated") is not True

    plan_steps = [
        {"status": "COMPLETED", "description": "Fetch documentation"},
        {"status": "IN_PROGRESS", "description": "Generate summary"}
    ]
    summary = ContextCompressor.summarize_plan_history(plan_steps)
    assert "1. [COMPLETED] Fetch documentation" in summary
    assert "2. [IN_PROGRESS] Generate summary" in summary

@pytest.mark.asyncio
async def test_batch_processor():
    """Verify BatchProcessor processes batch items with concurrency limit."""
    processed_items = []

    async def mock_worker(item: int) -> dict:
        await asyncio.sleep(0.01)
        processed_items.append(item)
        return {"item": item, "status": "SUCCESS"}

    items = list(range(10))
    results = await BatchProcessor.process_batch(items, mock_worker, concurrency_limit=3)

    assert len(results) == 10
    assert len(processed_items) == 10
    assert all(r["status"] == "SUCCESS" for r in results)
