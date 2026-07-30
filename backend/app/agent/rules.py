CLEAN_CODE_RULES = """\
1. Naming: names must be descriptive, unambiguous, and pronounceable. Avoid \
noise words (data, info, manager, helper) and abbreviations that aren't \
domain-standard. Judge naming in context — don't nitpick a name that \
already matches the established convention elsewhere in the file/project;
flag it only where it's genuinely unclear.
2. Function size and purpose: functions should do one thing, stay short \
enough to read without scrolling, and take few arguments (prefer ≤3). \
Avoid boolean/flag parameters that silently branch behavior.
3. DRY: no duplicated logic — repeated blocks should be extracted into a \
shared function, not copy-pasted.
4. Simplicity (YAGNI): no speculative abstractions, unused configuration \
surface, or generalization for requirements that don't exist yet. Prefer \
the simplest design that solves the actual problem.
5. Structure: related code lives together; unrelated concerns are \
separated (single responsibility per function/class/module). Avoid deeply \
nested control flow — prefer early returns/guard clauses over pyramids of \
conditionals.
6. Error handling: don't silently swallow exceptions; don't use exceptions \
for normal control flow; catch specific exception types, not bare/broad \
catches; error messages and logs must never leak sensitive information \
(secrets, internal paths, raw stack traces) to an end user.
7. Dead code: no unused imports, variables, functions, or commented-out \
code left behind.
8. Consistency: formatting, naming conventions, and idioms should match \
the rest of the codebase, the language's own conventions, and the \
framework's idiomatic patterns where one is in use (e.g. React hook \
dependency arrays, Next.js data-fetching/lifecycle conventions, Pythonic \
iteration over manual index loops) — not just generic "clean code" in the \
abstract.
9. Comments: code should be self-explanatory through naming and structure; \
comments should explain WHY something non-obvious is done, not restate \
WHAT the code does.
10. Magic values: no unexplained literal numbers or strings — use named \
constants where a value's meaning isn't self-evident.
11. Testability: logic should be structured so it can be tested in \
isolation — prefer pure functions and injected dependencies over hidden \
global state.

Out of scope — do NOT flag: line length, tabs vs. spaces, quote style, \
trailing commas, or any other purely cosmetic formatting. That's a \
linter/formatter's job, not yours. Spend your attention on things that \
affect correctness, security, performance, or real maintainability — \
findings that only restate a style preference just bury the ones that \
matter.
"""
