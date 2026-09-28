# AWS: Bedrock guardrails for the ApplyGuardrail suites

Four guardrails, each versioned: denied topics, word filters, contextual grounding, PII masking. They cost nothing
to exist; ApplyGuardrail calls bill per 1,000 text units (docs/09). `InvokeGuardrailChecks` (content, prompt
attacks, PII detection) needs none of this.

```bash
cd infra/aws && terraform init && terraform apply     # AWS_PROFILE/AWS_REGION from your shell or .env
```

The benchmark reads ids and versions from `terraform output -json` at run time. Changing a topic definition or a
word list creates a new guardrail version, and the config hash in every ledger record changes with it.
