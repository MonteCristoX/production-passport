---
name: Google Drive connector runtime
description: Environment-specific constraint for authenticated Google Drive uploads from the Flask application.
---

Use the supported Node connector SDK for authenticated Google Drive API calls; do not depend on the advertised standalone Python connector package in this workspace.

**Why:** The Python connector package could not be resolved from Replit's package registry, while the official Node connector SDK installed and authenticated successfully.

**How to apply:** Keep Flask responsible for report generation and invoke the isolated Node uploader for Drive operations. Never replace the connector with manually handled OAuth tokens.