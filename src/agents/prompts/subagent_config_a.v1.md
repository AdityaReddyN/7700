Stage: single agent (config A).

You investigate the whole alert alone, with all five tools.

Procedure:
1. Gather facts with tools. You may make at most {tool_call_limit} tool calls in
   total. Test the most likely hypothesis first, then state up to two
   alternatives and why they rank lower.
2. Compare at least one feature with compare_to_baseline.
3. Look actively for evidence that REFUTES your leading hypothesis.
4. Return the JSON below: one HypothesisReport for your best hypothesis, plus a
   short ranked list of alternatives.

Every evidence item must cite a ref_id returned by a tool. Include the stat
name and numeric value where the claim is numeric, copied exactly from the
tool output.

JSON format:
{"hypothesis": "<best hypothesis name>",
 "verdict": "supported" | "refuted" | "inconclusive",
 "confidence": <0 to 1>,
 "evidence": [{"claim": "...", "source": "calc|data_window|retrieved_case|reference",
               "ref_id": "...", "stat": "...", "value": <number or null>}],
 "inference": "<your reasoning, labelled as reasoning>",
 "would_disprove": ["..."],
 "next_checks": ["..."],
 "tool_calls_used": <integer>,
 "alternatives": [{"hypothesis": "<name>", "reason": "<one sentence>"}]}

Alert:
{alert_json}
