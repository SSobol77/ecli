# Security Review Checklist

## Subprocess and Command Execution

- [ ] All subprocess invocations use explicit argument arrays (no shell=True or string commands).
- [ ] Working directory assumptions are validated.
- [ ] Timeout behavior is defined for external commands.
- [ ] Error output is sanitized before user display where needed.

## Credential Handling

- [ ] API keys are loaded from expected env/config sources only.
- [ ] No credentials are committed in repository.
- [ ] Provider errors do not leak sensitive values.

## Integration Boundaries

- [ ] AI/Git/LSP adapters do not mutate editor state without contract path.
- [ ] External process failures cannot crash the editor loop.

## Release and Artifact Safety

- [ ] Artifacts include checksums.
- [ ] Release pipeline validates expected files only.
- [ ] Unexpected binary artifacts are rejected by contract checks.
