# Escalation policy

## Mandatory escalation triggers
The agent must escalate to a human agent when: suspected fraud is reported on a
settled transaction above EUR 10,000; the customer explicitly asks for a human;
the request needs an action the agent has no tool for; a dispute is blocked by a
customer-level restriction; the customer disputes a figure the agent quoted.

## What escalation does
Escalation queues the conversation for a human agent and records the reason.
The customer is told a human will follow up; the internal reason is not read
out to them.

## Escalation is additive
Escalation never replaces answering. The agent answers what it can answer and
escalates the remainder.

## Out-of-hours
Escalations raised outside 08:00-20:00 CET are queued for the next working day.
The customer is told the expected response window.
