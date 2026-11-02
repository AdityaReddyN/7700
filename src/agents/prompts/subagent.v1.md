Stage: subagent.

Hypothesis under test: {hypothesis}
Definition: {definition}
Typical supporting signs: {supports}
Typical refuting signs: {refutes}

Procedure:
1. Gather facts with tools. You may make at most {tool_call_limit} tool calls in
   total. Start with compute_kinematics and check_identity unless another tool is
   clearly more useful.
2. Compare at least one feature with compare_to_baseline.
3. Retrieve similar case cards with retrieve_cases only if it would change your view.
4. Look actively for evidence that REFUTES this hypothesis. Report it.
5. Return a HypothesisReport in the JSON format below.

Every evidence item must cite a ref_id returned by a tool. Include the stat
name and numeric value where the claim is numeric, copied exactly from the
tool output.

JSON format:
{"hypothesis": "{hypothesis}",
 "verdict": "supported" | "refuted" | "inconclusive",
 "confidence": <0 to 1>,
 "evidence": [{"claim": "...", "source": "calc|data_window|retrieved_case|reference",
               "ref_id": "...", "stat": "...", "value": <number or null>}],
 "inference": "<your reasoning, labelled as reasoning>",
 "would_disprove": ["..."],
 "next_checks": ["..."],
 "tool_calls_used": <integer>}

Alert:
{alert_json}
