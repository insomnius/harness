# Terraform / HCL

> **Illustrative, not normative.** See `TEMPLATE.md` for the six questions.

This is the **`provisions`** edge: infrastructure that defines runtime behavior.
`SKILL.md` calls these "the easiest edges to forget and the hardest breakages to
explain," and the reason is structural — **infra changes behavior with no
application code diff at all**. A timeout, a security group, an IAM policy, a
scaling floor and a feature flag are all nodes in the graph, and none of them
appear in any language's call graph.

Two things are true here that are true nowhere else in `lang/`:

1. **The graph has a runtime state as well as a source.** `main.tf` says what
   should exist; the state file says what does. They drift, and the drift is
   invisible until a plan is run.
2. **A destroy is a change.** Most of this method reasons about changed
   behavior; here, a rename can delete and recreate a database.

## 1. Walk up — who depends on this resource?

```bash
terraform graph | rg 'aws_security_group.api'          # tier: references (real graph)
terraform state list | rg api
rg -n 'aws_security_group\.api|module\.api\b' --type hcl
rg -n 'data "terraform_remote_state"' --type hcl       # cross-state consumers
```

`terraform graph` is the strongest evidence available — a real dependency graph
from the tool itself. Use it before grep.

The hard part is upstream **outside** Terraform: an application reading a
provisioned env var, queue name or bucket has an edge no HCL tool can see.

```bash
rg -n 'REFUND_MAX_CENTS|refund-events|api-uploads' --hidden -g '!.git' \
  --glob '!*.tfstate'
```

An output consumed by another state file, or a parameter read from SSM at boot,
is an **unprovable consumer set** — principle 23. Narrowing it is breaking.

## 2. Walk down — what does this resource need?

```bash
terraform providers
rg -n 'depends_on|source *= *"' --type hcl
rg -n 'module "' -A 3 --type hcl
terraform graph -type=plan | rg -A2 'module\.api'
```

## 3. Prove R

Terraform proves references at plan time but proves nothing about the values:

```bash
rg -n 'var\.|local\.' --type hcl | rg -v '^\s*#'
rg -n 'variable "' -A 4 --type hcl | rg -B1 'default'   # which vars have no default
rg -n 'data "' --type hcl                               # reads of things it does not own
rg -n 'backend "' -A 5 --type hcl                       # where state lives
```

A `variable` with no default and no value in any `.tfvars` is a hidden R that
surfaces as a prompt in an interactive run and a failure in CI. A `data` block
is a dependency on something this configuration does not create, which is
precisely a seam.

## 4. Render A / E / R

- **A** — the resource graph in dependency order. `terraform plan` is the
  rendering of A, and it is the only one that is authoritative.
- **E** — this stack's break points are unusual and each needs a policy:
  `create_before_destroy`, `prevent_destroy`, apply failures leaving partial
  state, and state lock contention. "Re-run the apply" is a retry with no
  bound; state that half-applied is the mid-stream failure case.
- **R** — provider credentials, the state backend, remote states read, and the
  variables with no defaults.

```hcl
lifecycle {
  prevent_destroy       = true      # for anything holding data
  create_before_destroy = true      # for anything serving traffic
}
```

**Cardinality is stated, not defaulted** — `count` and `for_each` are the
cardinality decision, and they differ in a way that bites: `count` is
positional, so removing the middle element of a list re-indexes and destroys
every resource after it. `for_each` is keyed and does not. Prefer `for_each`
for anything stateful.

**Make illegal states unrepresentable** (principle 14b) is available here too,
and skipped almost always:

```hcl
variable "instance_count" {
  type = number
  validation {
    condition     = var.instance_count >= 2
    error_message = "instance_count must be at least 2 for zero-downtime deploys."
  }
}
```

## 5. Detect drift

This is the one stack where drift detection is a first-class command:

```bash
terraform plan -detailed-exitcode      # 0 = no drift, 2 = drift, 1 = error
terraform validate && terraform fmt -check -recursive
tflint && checkov -d .                 # policy and security drift
git diff --name-only <traced_at_commit>...HEAD -- '*.tf' '*.tfvars'
```

`terraform plan -detailed-exitcode` is the direct analogue of running the test
suite, and it belongs in the check manifest. **A clean git diff does not mean no
drift** — someone can change infrastructure in a console and the code is
untouched, which is exactly the seam-drift failure mode `crossing.md` describes.

Contract hash inputs: `variable` blocks with their types and defaults,
`output` blocks, and the provider version constraints.

## 6. What defeats static tracing

- Console and CLI changes made outside Terraform. Only a plan finds them.
- `local-exec` / `remote-exec` provisioners shelling out — follow into
  `bash.md`.
- Provider version ranges: `~> 5.0` means a new minor changes behavior with no
  diff. Pin, and record the pin as R.
- Anything read at boot rather than at apply: SSM parameters, Secrets Manager,
  feature flags. The application reads them at runtime and Terraform never sees
  the consumer.
- Workspaces and `.tfvars` per environment: one source, several graphs. Trace
  the one that is deployed.
- The state file itself as shared state — two applies racing is a
  `reads_writes` seam on the backend.
