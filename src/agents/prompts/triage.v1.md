Stage: triage.

You receive an alert summary. Rank the five hypotheses by prior plausibility
given ONLY the alert summary. You have not checked any data yet, so do not
say that you have.

Return JSON:
{"hypotheses": [{"hypothesis": "<name>", "prior": <0 to 1>,
                  "reason": "<one sentence>"}]}

Include all five hypotheses. Priors need not sum to 1.

Alert:
{alert_json}
