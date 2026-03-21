# Policy Service

The PoC should keep policy deterministic and outside the model.

For the first iteration, this directory holds an OPA policy bundle and control-plane data that the orchestrator can call before:

- approval submission
- payment release
- cancellation
- rail changes
- beneficiary changes

Inputs to the decision request should include:

- action
- principal scopes
- task state
- amount
- rail
- beneficiary status
- approval status
- idempotency key presence

Outputs should be normalized to:

- `allow`
- `deny`
- `escalate`
- `simulate`
