---
applyTo: "**/*"
---

# Security Review Instructions

Use this file when reviewing changes for security risks in internal business applications.

These applications are primarily intended for internal staff use and are not deliberately exposed to the public internet. Do not assume that makes them safe. Review for realistic internal-app risks: privilege mistakes, data exposure, weak authentication, unsafe file handling, secrets leakage, audit gaps, and accidental external exposure.

## Review posture

- Be practical and specific.
- Prioritize concrete risks over theoretical ones.
- Do not block on low-value security theatre.
- Call out assumptions clearly.
- Prefer simple mitigations that fit an internal line-of-business application.
- If no meaningful issue is found, say so directly.

## High-priority checks

### Authentication

Check whether the change affects login, session handling, identity providers, cookies, API keys, service accounts, or token usage.

Look for:

- Missing authentication on pages, API endpoints, background jobs, or admin routes.
- New endpoints that rely only on UI hiding rather than server-side checks.
- Weak session handling.
- Tokens, credentials, or API keys passed through query strings.
- Authentication bypasses in development or test-only code that could reach production.

### Authorization

Authorization issues are usually the biggest internal-app risk.

Look for:

- Users accessing records they should not see.
- Admin-only actions available to regular users.
- Manager/team/customer/tenant boundaries not enforced server-side.
- Reliance on client-side checks only.
- “Current user” assumptions that are not validated.
- ID-based access where changing an ID could expose another user’s data.

Example concern:

> This endpoint accepts `employeeId` but does not verify that the current user is allowed to access that employee.

### Sensitive data exposure

Check whether the change reads, writes, logs, exports, emails, or displays sensitive data.

Sensitive data may include:

- Personal information.
- Employee records.
- Customer records.
- Financial data.
- Health or benefits information.
- Authentication tokens.
- Internal notes.
- Audit records.
- Business-confidential data.

Look for:

- Sensitive values in logs.
- Sensitive values in exception messages.
- Overbroad exports.
- Debug output in production paths.
- Unnecessary fields returned from APIs.
- Data shown in dropdowns, reports, or search results without permission checks.

### Secrets and configuration

Look for:

- Passwords, API keys, connection strings, certificates, or tokens committed to source.
- Secrets in config files intended for source control.
- Secrets in test data that look real.
- Secrets logged during startup or error handling.
- Use of production credentials in local/dev examples.

Prefer:

- Environment variables.
- Secret managers.
- Local-only sample config files.
- Redacted examples.

### Input validation

Review all external or semi-external input, including forms, query strings, uploaded files, imported spreadsheets, webhook payloads, and internal API calls.

Look for:

- Missing validation.
- Trusting hidden form fields.
- Trusting client-generated IDs, roles, prices, totals, or permissions.
- Unsafe parsing.
- Missing length limits.
- Missing type or range checks.
- Overly broad model binding.

### Database safety

Look for:

- String-concatenated SQL.
- Dynamic SQL without parameterization.
- Unsafe filtering, sorting, or search expressions.
- Missing tenant/user filters.
- Updates or deletes without appropriate scope.
- Migrations that could destroy data unexpectedly.
- Logging raw SQL with sensitive parameter values.

Prefer:

- Parameterized queries.
- ORM-safe query construction.
- Explicit ownership or tenant filters.
- Conservative migration scripts.

### File upload and document handling

For file uploads, imports, generated reports, and attachments, check for:

- Missing file type validation.
- Trusting file extensions only.
- Unsafe file names or paths.
- Path traversal risks.
- Files saved into web-accessible locations unnecessarily.
- Unbounded file size.
- Missing malware-scanning consideration where appropriate.
- Sensitive exports stored permanently without access controls.

### Logging and auditability

Internal applications often need enough logging to investigate misuse or mistakes.

Look for:

- Sensitive data logged unnecessarily.
- Important administrative actions not logged.
- Bulk exports not logged.
- Permission changes not logged.
- Failed authorization attempts silently ignored.
- Logs that cannot identify the acting user.

Prefer logging:

- Acting user ID.
- Affected entity ID.
- Action performed.
- Timestamp.
- Success/failure.
- Correlation/request ID where available.

Avoid logging:

- Passwords.
- Tokens.
- Full connection strings.
- Full personal records.
- Large request/response bodies containing sensitive data.

### Error handling

Look for:

- Stack traces shown to users.
- Raw exception messages returned from APIs.
- Error responses that reveal internal paths, SQL, secrets, or infrastructure details.
- Catch-all handlers that hide security-relevant failures.

Prefer:

- Generic user-facing errors.
- Detailed server-side logs with sensitive data redacted.
- Proper status codes for APIs.

### Dependency and supply-chain risk

Look for:

- New dependencies added without clear need.
- Unmaintained packages.
- Packages used for trivial functionality.
- Direct use of scripts or assets from unknown sources.
- Package versions left floating where reproducibility matters.

For internal apps, do not overreact to every dependency, but flag unnecessary or risky additions.

### Frontend-specific checks

Look for:

- Trusting frontend-only validation.
- Hidden buttons used as security controls.
- Sensitive data stored in localStorage/sessionStorage unnecessarily.
- Tokens exposed to JavaScript when avoidable.
- Unsafe HTML rendering.
- Markdown or rich text rendered without sanitization.
- Cross-site scripting risks from user-entered content.

### API-specific checks

Look for:

- Missing authentication/authorization attributes.
- Overbroad DTOs.
- Returning internal domain models directly.
- Missing ownership checks.
- Missing rate/abuse controls on expensive operations.
- Endpoints accidentally reachable outside the intended network.

### Admin and support tooling

Review admin features carefully.

Look for:

- Impersonation without audit logging.
- Bulk update/delete/export without confirmation or audit trail.
- User role changes without protection.
- Support tools that bypass normal authorization.
- “Temporary” admin routes left in place.

## Internal-app specific risks

For internal applications, pay special attention to:

- Accidental public exposure through reverse proxies, cloud networking, firewall changes, or misconfigured hosting.
- Overly broad access for “all staff.”
- Weak separation between departments, teams, managers, clients, or tenants.
- Assumptions that internal users are always trustworthy.
- Lack of audit trails for privileged actions.
- Reports or exports that leak more data than the screen view allows.
- Test/dev utilities available in production.
- Shared service accounts with unclear ownership.

## Severity guidance

Use these severity levels:

### Critical

Use when the change could allow:

- Authentication bypass.
- Privilege escalation to admin or cross-tenant access.
- Exposure of secrets.
- Large-scale sensitive data exposure.
- Destructive data changes without proper authorization.

### High

Use when the change could allow:

- Access to records outside the user’s scope.
- Sensitive data leakage through logs, exports, APIs, or reports.
- Unsafe file handling with meaningful impact.
- Missing authorization on important internal workflows.

### Medium

Use when the change creates:

- Incomplete validation.
- Weak auditability.
- Excessive data returned from APIs.
- Risky dependency choices.
- Error handling that reveals unnecessary internal details.

### Low

Use for:

- Minor hardening suggestions.
- Cleanup that improves consistency.
- Defence-in-depth improvements.
- Documentation gaps with security relevance.

## Review output format

When reporting findings, use this format:

```md
## Security Review

### Summary

State whether security concerns were found.

### Findings

#### [Severity] Short title

**Risk:** Explain the security risk.

**Evidence:** Point to the file, method, endpoint, or pattern.

**Why it matters:** Explain the realistic internal-app impact.

**Recommendation:** Give a specific fix.

### Positive notes

Mention any good security practices observed.

### Assumptions

List any assumptions made during the review.