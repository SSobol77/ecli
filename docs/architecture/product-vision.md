<!--
SPDX-License-Identifier: Apache-2.0

Project: ECLI
File: docs/architecture/product-vision.md
Website: https://www.ecli.io
Author: Siergej Sobolewski
License: Apache License, Version 2.0

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->

# ECLI Product Vision

**Terminal-First Engineering Operations Workbench**

**Version:** 1.0
**Date:** 2026-05-15
**Status:** Strategic Architecture Direction
**License:** Apache-2.0

---

## 1. Vision Statement

ECLI is a **terminal-first engineering operations workbench** that combines a high-performance code editor with professional-grade operations tooling.

It combines a developer-oriented code editor with professional operations tooling for local systems, virtual machines, cloud infrastructure, Kubernetes clusters, automation workflows, CI/CD pipelines, logs, monitoring, and AI-assisted engineering workflows.

ECLI is not intended to become another heavy GUI editor. It is designed for engineers who prefer transparent, reproducible, terminal-native workflows and want one coherent tool for code, systems, runtimes, infrastructure, and operational diagnostics.

The long-term product direction is:

```text
ECLI = terminal-first IDE + DevOps control plane + VM/runtime lab + cloud/system orchestration console
````

---

## 2. Product Positioning

### Product Name

```text
ECLI
```

### Main Tagline

```text
Terminal-First Engineering Operations Workbench
```

### Short Description

```text
A terminal-first IDE and operations workbench for code, systems, VMs, cloud,
automation, and AI-assisted engineering workflows.
```

### Long Description

ECLI is a lightweight, terminal-native workbench for serious engineering workflows. It keeps the speed and transparency of the terminal while adding structured panels, typed configuration, AI-assisted operations, Git integration, diagnostics, runtime management, system doctor workflows, command plans, audit logs, and future orchestration modules.

ECLI does not hide infrastructure behind opaque dashboards. Every meaningful operation should remain visible, reviewable, reproducible, and exportable as plain text configuration, shell commands, TOML profiles, command plans, or audit records.

---

## 3. What ECLI Is

ECLI is:

* a terminal-first IDE;
* a professional engineering operations workbench;
* a lightweight alternative to heavy GUI-first development environments;
* a config-first and plain-text-first tool;
* a safe command execution surface for engineering operations;
* a future control plane for local systems, VMs, cloud, Kubernetes, automation, CI/CD, logs, and AI-assisted operations;
* a tool for engineers who want transparency and reproducibility instead of opaque automation.

ECLI should serve engineers who work daily with:

* source code;
* Git;
* local and remote systems;
* QEMU and runtime environments;
* Kubernetes and OpenShift;
* Terraform and Ansible;
* CI/CD systems;
* logs and monitoring;
* privileged system operations;
* AI-assisted diagnostics and remediation.

---

## 4. What ECLI Is Not

ECLI is not:

* an Electron-first editor;
* a web dashboard disguised as a desktop tool;
* a beginner-only simplified editor;
* a hidden automation daemon;
* a tool that silently mutates infrastructure;
* a system that hides privileged commands from the user;
* a GUI-first operations platform;
* a replacement for every specialized DevOps tool;
* a product that treats configuration as secondary to hidden state.

ECLI may integrate with tools such as QEMU, kubectl, oc, Terraform, Ansible, GitHub CLI, GitLab CLI, AWS CLI, monitoring APIs, and package managers, but it must not obscure their operational semantics.

The goal is not to replace the engineering toolchain.
The goal is to provide a coherent, safe, terminal-native workbench over that toolchain.

---

## 5. Core Values

### 5.1 Terminal-First

The terminal is the primary interface.

ECLI must work well in:

* local terminals;
* SSH sessions;
* tmux;
* minimal server environments;
* developer workstations;
* CI/debug environments where GUI tools are unavailable.

TUI and CLI are first-class interfaces. GUI Desktop may exist later, but it must remain a thin client over shared services.

### 5.2 Config-First

Configuration must be explicit, readable, versionable, and portable.

Preferred configuration formats:

* TOML for user and project configuration;
* JSON for machine-readable command plans and reports;
* shell-compatible command exports where applicable;
* plain text audit logs.

No hidden database should become the primary source of truth for core workflows.

### 5.3 Safety-First

Risky operations must be mediated through explicit plans.

Every privileged or destructive operation must be:

* explicit;
* previewable;
* confirmable;
* logged;
* reproducible;
* policy-checkable;
* blocked when unsafe.

ECLI must never run privileged operations silently.

### 5.4 Reproducibility

Operations must be reproducible outside ECLI.

Where technically possible, ECLI should expose:

* exact commands;
* exact arguments;
* environment assumptions;
* generated configuration;
* execution logs;
* rollback information.

A user must be able to understand what ECLI is going to do before it does it.

### 5.5 Lightweight Engineering

ECLI should avoid unnecessary runtime weight.

Default direction:

```text
terminal-first
config-first
plain text first
no Electron by default
no QWebEngine by default
no daemon-first architecture unless a module truly requires it
```

### 5.6 Service-Oriented Internals

The UI must not own infrastructure logic.

The internal architecture must evolve from a large central application object into clear bounded services. This is required to reduce coupling, improve testability, and allow CLI, TUI, and future GUI layers to reuse the same operational logic.
This refactor is already indicated by the current architecture audit and Phase 1–2 roadmap.

### 5.7 AI as Assistant, Not Autopilot

AI may explain, summarize, diagnose, and propose command plans.

AI must not directly execute privileged, destructive, production, cloud, Kubernetes, Terraform, Ansible, or system operations.

AI-assisted operations must go through the same planning, confirmation, policy, execution, and audit model as manually initiated operations.

---

## 6. Target User Profile

ECLI is designed primarily for:

* senior backend engineers;
* DevOps engineers;
* platform engineers;
* SRE engineers;
* infrastructure engineers;
* systems programmers;
* kernel and OS developers;
* engineers who prefer terminal-native workflows.

The target user is comfortable with command-line tools, configuration files, logs, runtime diagnostics, local and remote systems, and explicit operational control.

ECLI is not optimized for users who want infrastructure hidden behind simplified graphical abstractions.

---

## 7. Current Architecture Reality

The current ECLI implementation is a modular monolith centered around the main `Ecli` application object.

Current strengths include:

* terminal-first TUI;
* editor core;
* panels;
* AI integration;
* Git integration;
* linting integration;
* asynchronous background work;
* multi-platform packaging direction.

Current architectural risks include:

* oversized central application class;
* implicit configuration schema;
* mixed responsibilities between UI, editor state, integrations, and operations;
* limited test boundaries;
* release and packaging drift;
* insufficient service-level separation.

The strategic direction of this document is to move ECLI toward service boundaries without performing a disruptive rewrite.

---

## 8. High-Level Architecture Vision

### 8.1 UI Layers

```text
ECLI UI Layers
├── TUI
├── CLI
└── GUI Desktop
```

The TUI remains the primary interface.

The CLI must provide stable access to services, diagnostics, plans, and automation workflows.

The GUI Desktop is a later thin-client interface. It must not implement infrastructure logic directly.

### 8.2 Shared Services

```text
Shared Services
├── ConfigService
├── ProjectService
├── CommandPlanService
├── PrivilegedActionService
├── CredentialService
├── AuditLogService
├── RuntimeService
├── VMLabService
├── CloudInventoryService
├── KubernetesService
├── TerraformService
├── AnsibleService
├── CICDService
├── ObservabilityService
└── AIOrchestrationService
```

### 8.3 Execution Backends

```text
Execution Backends
├── local shell
├── sudo / doas / pkexec
├── QEMU / QMP
├── SSH
├── kubectl / oc
├── terraform
├── ansible
├── aws CLI / SDK
├── git / gh / glab
└── monitoring APIs
```

### 8.4 Core Rule

```text
UI never performs infrastructure actions directly.
UI calls services.
Services generate plans.
Plans are previewed.
User confirms.
Executor applies.
Audit log records the result.
```

This rule applies to TUI, CLI, and future GUI Desktop.

---

## 9. CommandPlanService as the Core Safety Primitive

`CommandPlanService` is the central architectural primitive for safe operations.

It must represent risky actions as explicit plans before execution.

A command plan should describe:

* operation title;
* risk level;
* required privileges;
* commands to execute;
* command arguments;
* expected effects;
* rollback actions where technically possible;
* policy checks;
* audit metadata;
* user confirmation requirements.

Example:

```json
{
  "schema_version": 1,
  "plan_id": "plan-2026-05-12-001",
  "title": "Enable KVM access for current user",
  "risk": "low",
  "requires_privilege": true,
  "requires_relogin": true,
  "commands": [
    {
      "argv": ["sudo", "usermod", "-aG", "kvm", "$USER"],
      "display": "sudo usermod -aG kvm \"$USER\"",
      "destructive": false
    }
  ],
  "rollback": [],
  "explanation": "Adds the current user to the kvm group so QEMU can access /dev/kvm."
}
```

Planned CLI surface:

```bash
ecli plan show <plan-id>
ecli plan apply <plan-id>
ecli plan export <plan-id> --format shell
```

Planned GUI/TUI behavior:

```text
[Show Plan] [Copy Commands] [Apply Selected] [Cancel]
```

---

## 10. Privileged Operations Philosophy

The correct rule is not:

```text
ECLI does not run sudo.
```

The correct rule is:

```text
ECLI does not run sudo silently.
```

ECLI supports explicit privileged workflows for engineering and DevOps use cases.

Privileged operations are allowed only through `CommandPlanService` and `PrivilegedActionService`.

Every privileged operation must be:

* previewable;
* confirmable;
* logged;
* reproducible;
* policy-checkable;
* visible as an exact shell command;
* blocked when unsafe.

ECLI must never:

* store sudo passwords;
* hide privileged commands;
* silently escalate privileges;
* perform destructive changes without explicit confirmation;
* let AI directly execute privileged operations.

---

## 11. Target Modules

### 11.1 Code / Editor Panel

The current editor remains the core daily interface.

Target capabilities:

* editing;
* syntax highlighting;
* LSP;
* diagnostics;
* Git-aware editing;
* AI-assisted refactoring;
* project-aware configuration.

### 11.2 File Manager Pro

File Manager Pro is not only a file browser.

Target capabilities:

* create;
* rename;
* delete;
* copy;
* move;
* chmod;
* chown;
* privileged save;
* safe editing of root-owned files;
* validation before privileged write;
* before/after diff;
* install file into `/usr/local/bin`, `/etc`, `/opt`;
* inspect file metadata;
* show package ownership where supported.

Privileged writes must go through `CommandPlanService`.

### 11.3 System Doctor

System Doctor detects local environment problems and proposes fix plans.

Target capabilities:

* missing packages;
* permission problems;
* kernel module checks;
* virtualization support checks;
* broken `PATH`;
* missing language servers;
* invalid configuration;
* package manager detection;
* service manager detection;
* fix plan generation;
* selected fix application.

Planned CLI surface:

```bash
ecli doctor
ecli doctor --json
ecli doctor --plan-fixes
ecli doctor --apply-fixes
```

### 11.4 VMLab / Runtime Lab

VMLab is the first major runtime-management module of the ECLI Professional Operations Workbench.

VMLab must not be designed as a simple QEMU launcher.

Target capabilities:

* QEMU VM profiles;
* QMP lifecycle control;
* VM supervisor;
* serial console;
* serial logs;
* smoke runner;
* ISO attach;
* disk attach;
* boot logs;
* VM state inspection;
* crash recovery;
* acceleration doctor;
* command plans for remediation.

VMLab is the first runtime module, not the end state of ECLI.

### 11.5 Cloud Inventory

Cloud Inventory starts as read-only infrastructure visibility.

Target direction:

```text
read-only inventory -> plan -> apply
```

Initial AWS-oriented capabilities may include:

* accounts and profiles;
* regions;
* EC2 instances;
* VPCs;
* subnets;
* security groups;
* EKS clusters;
* RDS;
* S3 buckets;
* IAM summary;
* cost hints;
* misconfiguration warnings.

No production mutation should be implicit.

### 11.6 Kubernetes / OpenShift Panel

Target capabilities:

* contexts;
* namespaces;
* pods;
* deployments;
* services;
* ingress/routes;
* configmaps;
* secret metadata;
* logs;
* events;
* describe;
* rollout restart;
* scale;
* port-forward.

Every mutating operation must be represented as a command plan.

Example:

```bash
kubectl scale deployment api --replicas=3 -n prod
```

### 11.7 Terraform Panel

Terraform integration is a control surface, not only syntax support.

Target capabilities:

* `terraform fmt`;
* `terraform validate`;
* `terraform plan`;
* workspace selection;
* state inspection;
* drift detection;
* module graph;
* variable preview.

Hard rule:

```text
terraform apply is never implicit
```

### 11.8 Ansible Panel

Target capabilities:

* inventory browser;
* playbook runner;
* check mode;
* diff mode;
* host facts;
* task result viewer;
* failed hosts;
* retry failed.

### 11.9 CI/CD Panel

Target integrations may include:

* GitHub Actions;
* GitLab CI;
* Jenkins.

Target capabilities:

* pipelines;
* workflow runs;
* failed jobs;
* artifacts;
* logs;
* rerun job;
* cancel job;
* open failed step.

### 11.10 Observability Panel

Target capabilities:

* logs viewer;
* system logs;
* Docker / Podman logs;
* Kubernetes logs;
* Prometheus query;
* Grafana link integration;
* alerts;
* service health.

The goal is not to rebuild Grafana.
The goal is to connect, query, view, diagnose, and jump to source/configuration.

### 11.11 Secrets / Credentials Panel

Secrets handling must be conservative.

Rules:

* list secret names only by default;
* never print secret values without explicit reveal;
* redact logs;
* integrate with external providers;
* avoid storing raw secrets in ECLI-owned files.

Potential future integrations:

* environment providers;
* `pass`;
* `gopass`;
* 1Password CLI;
* AWS Secrets Manager.

### 11.12 AI Operations Assistant

AI is an operations assistant, not an autonomous operator.

Target capabilities:

* explain failed pipeline;
* explain Kubernetes event;
* suggest Terraform fix;
* summarize logs;
* generate command plan draft;
* review privileged action risk;
* write runbooks.

AI must not execute changes without `CommandPlanService`.

---

## 12. Roadmap Direction

### Phase 1 — Services Foundation

Current strategic priority.

Scope:

* ConfigService;
* ProjectService;
* CommandPlanService;
* PrivilegedActionService;
* AuditLogService;
* typed config schema;
* migration and normalization layer;
* stable CLI service surface;
* System Doctor skeleton;
* refactor `Ecli.py` toward service boundaries.

Phase 1 must not attempt to implement the full Operations Workbench.

Its purpose is to create the architecture required for safe expansion.

### Phase 2 — VMLab Professional

Scope:

* QEMU profiles;
* QMP client;
* VMSupervisor;
* serial follow/attach;
* doctor integration;
* plan/apply fixes;
* smoke runner.

### Phase 3 — File Manager Pro

Scope:

* privileged save;
* chmod/chown;
* file install workflows;
* validate before apply;
* diff before write;
* admin action plans.

### Phase 4 — System Operations

Scope:

* package manager detection;
* service manager integration;
* systemd / rc.d / service control;
* logs and journal viewer;
* SSH targets.

### Phase 5 — Cloud / Kubernetes

Scope:

* AWS inventory read-only;
* Kubernetes context browser;
* pods/deployments/services/logs/events;
* command plans for changes;
* no implicit production mutation.

### Phase 6 — Orchestration

Scope:

* Terraform plan/apply wrapper;
* Ansible playbook runner;
* CI/CD integration;
* environment dashboards.

### Phase 7 — Observability + AI Ops

Scope:

* log summarization;
* failed deployment diagnosis;
* AI-generated remediation plans;
* runbook generation;
* alert explanation.

---

## 13. Non-Negotiable Design Rules

1. UI must never perform infrastructure actions directly.
2. TUI, CLI, and GUI must use shared services.
3. Command plans are required for risky operations.
4. Privileged actions must be explicit and visible.
5. ECLI must never store sudo passwords.
6. AI must not directly execute privileged or destructive operations.
7. Configuration must remain plain-text-first.
8. Hidden state must not become the primary source of truth.
9. GUI Desktop must be a thin client over services.
10. VMLab is the first runtime-management module, not the final product boundary.
11. During development, generated logs, dry-run reports, test evidence, smoke outputs, and agent debug artifacts must be contained under repository-level `logs/`.

---

## 14. Strategic Summary

ECLI is not moving toward a generic GUI editor.

ECLI is moving toward a professional engineering workbench:

```text
code + terminal + VM lab + system administration + cloud + orchestration + observability + AI
```

The immediate priority is not to build every module at once.

The immediate priority is to establish the service architecture, command planning model, privileged action model, audit trail, and typed configuration foundation required to build those modules safely.

The first major proof of this direction will be VMLab, but VMLab must be built on top of the shared services foundation, not as an isolated QEMU wrapper.

## Approval

* **Status**: Approved as Strategic Direction
* **Approved by**: Siergej Sobolewski
* **Date**: 2026-05-12
