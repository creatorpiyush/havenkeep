from typing import List, Dict, Any

class ContextCompressor:
    """
    Trims and compresses execution history / tool scratchpads for long-running agent loops.
    Prevents token bloat and keeps execution prompts within budget bounds.
    """
    
    @classmethod
    def compress_tool_outputs(
        cls, 
        outputs: List[Dict[str, Any]], 
        max_chars_per_output: int = 1500,
        max_total_items: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Trims individual verbose tool output strings and caps total retained history items.
        """
        trimmed = outputs[-max_total_items:] if len(outputs) > max_total_items else outputs
        compressed = []
        for item in trimmed:
            item_copy = dict(item)
            output_text = str(item_copy.get("output", ""))
            if len(output_text) > max_chars_per_output:
                truncated_chars = len(output_text) - max_chars_per_output
                item_copy["output"] = (
                    output_text[:max_chars_per_output] + 
                    f"\n... [Truncated {truncated_chars} characters for token optimization] ..."
                )
                item_copy["is_truncated"] = True
            compressed.append(item_copy)
        return compressed

    @classmethod
    def summarize_plan_history(cls, plan_steps: List[Dict[str, Any]]) -> str:
        """
        Generates a compact markdown summary of executed plan steps.
        """
        summary_lines = ["### Execution Plan History (Compressed)"]
        for idx, step in enumerate(plan_steps, 1):
            status = step.get("status", "COMPLETED")
            desc = step.get("description", step.get("action", f"Step {idx}"))
            summary_lines.append(f"{idx}. [{status}] {desc}")
        return "\n".join(summary_lines)
