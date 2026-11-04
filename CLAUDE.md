# Telegram Secretary Bot — Development Rules

## Project Context
This is an existing Python Telegram Secretary Bot project.
Preserve its current architecture, database, functionality, and user interface.

## Token Efficiency Rules
1. Never scan the entire project unless explicitly requested.
2. Read only files directly relevant to the current task.
3. Do not repeat previous analysis or explanations.
4. Do not print entire source files in responses.
5. Do not rewrite files when a targeted modification is sufficient.
6. Avoid unnecessary tool calls and repeated searches.
7. Do not run the full test suite after every small change.
8. Use focused tests relevant to modified functionality.
9. Reuse findings from the current conversation when still valid.
10. Keep reports concise and technical.

## Change Safety
1. Inspect Git status before modifying files.
2. Never discard user changes.
3. Never use destructive Git commands.
4. Preserve existing database data and use migrations when needed.
5. Do not change project architecture without approval.
6. Do not deploy or restart production services without permission.

## Workflow
For each task:
1. Identify the exact files involved.
2. Inspect only those files.
3. Explain the intended change briefly.
4. Implement the smallest safe modification.
5. Run focused tests.
6. Report changed files, test results, and remaining issues.

## Important
Do not claim that Telegram API integration works unless it has been verified.
Distinguish mocked tests from real Telegram integration tests.