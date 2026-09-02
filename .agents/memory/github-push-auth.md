---
name: GitHub push authentication
description: How to authenticate Git pushes in this Replit environment without persisting the token in the remote URL.
---

When GitHub CLI cannot complete a noninteractive device login, authenticate a push with the configured personal access token through a short-lived `GIT_ASKPASS` helper, while keeping `origin` as a clean HTTPS URL.

**Why:** `gh auth login` can remain waiting for browser confirmation or exit without persisting a session, while embedding a token in `.git/config` risks exposing it through repository configuration and diagnostics.

**How to apply:** Verify the secret exists, create an ephemeral askpass helper that returns `x-access-token` and the secret only to Git, run the push with terminal prompts disabled, and remove the helper on exit. Never print the token or include it in the remote URL.