Stage: adjudicator.

You receive independent hypothesis reports. Only verified evidence is included.
Write the incident report.

Requirements:
- Choose the most likely cause and give a calibrated confidence (see the rules above).
- Rank the other hypotheses and say why each ranks lower.
- Build the evidence table from verified evidence only. Do not cite anything
  that is not in a report.
- Write the inference section separately, labelled as reasoning.
- If two hypotheses remain close, name the single check an operator could run
  to tell them apart.
- Recommend one operator action.
- List what would change your mind.

JSON format:
{"verdict": "<hypothesis or inconclusive>",
 "confidence": <0 to 1>,
 "inference": "...",
 "discriminating_check": "...",
 "recommended_action": "...",
 "would_change_my_mind": ["..."]}

Reports (verified evidence only):
{reports_json}

Alert:
{alert_json}
