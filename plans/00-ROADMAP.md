# Swarm Master Roadmap

## 📦 Release v1.0.0 (Target Date: 2026-09-01) - STATUS: ACTIVE
- [ ] **Milestone 1: Account Health Scorer (OPS-13)** - STATUS: ACTIVE
  - *Description:* Implement pure-function CSV ingestion, data normalization, and explainable multi-factor account health scoring service.
  - *Context:* `plans/active_milestones/account-health-scorer/context.md`
  - *Spec:* `plans/active_milestones/account-health-scorer/spec.md`
  - *Plan:* `plans/active_milestones/account-health-scorer/plan.md`
- [ ] **Milestone: CI/CD Antigravity Python SDK Migration** - STATUS: ACTIVE
  - *Description:* Migrate GitHub Actions CI/CD quality gate and PR code review from `agy` CLI to `google-antigravity` Python SDK with WIF, Vertex AI ADC, and Pydantic validation.
  - *Context:* `plans/active_milestones/ci-cd-agy-sdk-migration/context.md`
  - *Spec:* `plans/active_milestones/ci-cd-agy-sdk-migration/spec.md`
  - *Plan:* `plans/active_milestones/ci-cd-agy-sdk-migration/plan.md`

## 📦 Release v1.1.0 (Target Date: 2026-10-01) - STATUS: PENDING
- [ ] **Milestone 2: Automated Slack/Email Alerting on AT RISK Accounts** - STATUS: PENDING
  - *Description:* Dispatch weekly notification summaries to Customer Success channel for accounts entering AT RISK tier.
- [ ] **Milestone 3: Dynamic Threshold Tuning & Historical Trend Analysis** - STATUS: PENDING
  - *Description:* Support configurable risk weights and multi-quarter velocity metrics.
