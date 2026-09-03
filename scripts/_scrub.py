"""Take the defect register out of comments and docstrings, leave code alone.

Round-2 student acceptance found that removing docs/defect-catalog.md achieved
much less than it looked like. The module docstring of app/agent/tools.py named
seven defects and said what each one does; app/engines/fx.py described the
eighth; app/engines/policy.py pointed at a secret by identifier. One grep over
*.py answered the question the homework asks, and the student agent knew the
answer before its first request to the stand.

`if defects.is_on("D22")` has to stay — it is the mechanism, and the student
runs this code. Reading it and working out what it does is the work. A comment
that already explains what it does is not.

Two strengths, because one was not enough.

`scrub` works line by line: a comment naming a defect goes, a docstring line
that maps an identifier to a behaviour goes, an identifier used as a label on
an otherwise ordinary sentence is simply removed. It is used for tests/ and
scripts/, which are worked examples worth reading.

`blank_prose` removes commentary entirely, and app/ gets that instead. Line
scrubbing proved unsound there: dropping the sentence that named a defect left
the sentences around it explaining the same mechanism anonymously — the
register with the labels filed off, entries still in order. No token matches
that; it is ordinary English describing what the code does, and when the code
is the defect, describing it is giving the answer.

Code is never touched: only COMMENT tokens and docstrings are rewritten, and
the result is re-parsed before it is accepted. Behaviour was verified live —
the same request on the stripped build produces the same corrupted tool result
as on the full one.
"""
import ast
import io
import re
import tokenize

ID_RE = re.compile(r"(?<![A-Za-z0-9])D[0-9]{2}(?![0-9])")

# "(D16)" / "(D19, D20)" — a label in brackets on an otherwise normal sentence
_PAREN_RE = re.compile(r"\s*\((?:D[0-9]{2})(?:[,/ ]+D[0-9]{2})*\)")
# "D03: ..." / "D19 - ..." at the head of a line
_PREFIX_RE = re.compile(r"^(\s*)D[0-9]{2}(?:[,/ ]+D[0-9]{2})*\s*[:—-]\s*")

_STMT_START = {tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
               tokenize.ENCODING}


def _strip_ids(line):
    """Return the line without its identifiers, or None if the line has to go.

    A leading "D09 - ..." is a register entry: the rest of the line IS the
    explanation, so stripping just the identifier leaves the answer intact and
    merely anonymised — worse than useless, because the entries stay in order
    and map straight back. Those lines go whole. Only a parenthetical label on
    a sentence that stands without it is salvaged.
    """
    if _PREFIX_RE.match(line):
        return None
    out = _PAREN_RE.sub("", line)
    if ID_RE.search(out):
        return None          # still a mapping: drop the whole line
    return out if out.strip() else None


def _clean_block(text):
    lines = text.split("\n")
    kept, i = [], 0
    while i < len(lines):
        if ID_RE.search(lines[i]):
            salvaged = _strip_ids(lines[i])
            if salvaged is not None:
                kept.append(salvaged)
                i += 1
                continue
            # drop the line and any lines wrapped under it
            base = len(lines[i]) - len(lines[i].lstrip())
            i += 1
            while (i < len(lines) and lines[i].strip()
                   and len(lines[i]) - len(lines[i].lstrip()) > base):
                i += 1
            continue
        kept.append(lines[i])
        i += 1
    while kept and (not kept[-1].strip() or kept[-1].rstrip().endswith(":")):
        kept.pop()
    return "\n".join(kept)


def scrub(source):
    """Rewrite one module. Returns the source unchanged if anything goes wrong:
    a build that silently produces broken Python is worse than one that leaks."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return source

    lines = source.split("\n")
    edits = []
    prev_type = tokenize.ENCODING
    for tok in toks:
        if tok.type == tokenize.COMMENT and ID_RE.search(tok.string):
            edits.append((tok.start, tok.end, None))
        elif (tok.type == tokenize.STRING and prev_type in _STMT_START
              and ID_RE.search(tok.string)):
            quote = '"""' if tok.string.count('"""') >= 2 else "'''"
            if tok.string.count(quote) < 2:
                continue
            head, _, rest = tok.string.partition(quote)
            body, _, _tail = rest.rpartition(quote)
            new = _clean_block(body).rstrip()
            indent = " " * tok.start[1]
            if not new.strip():
                new = "Implementation detail."
                edits.append((tok.start, tok.end, f'{head}{quote}{new}{quote}'))
                continue
            edits.append((tok.start, tok.end,
                          f"{head}{quote}{new}\n{indent}{quote}"))
        if tok.type not in (tokenize.NL, tokenize.COMMENT):
            prev_type = tok.type

    for (srow, scol), (erow, ecol), repl in reversed(edits):
        before, after = lines[srow - 1][:scol], lines[erow - 1][ecol:]
        if repl is None:
            merged = (before.rstrip() + after).rstrip()
            if not merged.strip():
                del lines[srow - 1:erow]
                continue
            lines[srow - 1:erow] = [merged]
        else:
            lines[srow - 1:erow] = (before + repl + after).split("\n")

    out = "\n".join(lines)
    try:
        ast.parse(out)
    except SyntaxError:
        return source
    return out


def prose_ids(source):
    """Identifiers left in comments or docstrings — what --check looks for.
    Identifiers inside ordinary code, such as defects.is_on("D22"), are the
    mechanism and are expected to remain."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    found, prev_type = set(), tokenize.ENCODING
    for tok in toks:
        if tok.type == tokenize.COMMENT or (
                tok.type == tokenize.STRING and prev_type in _STMT_START):
            found.update(ID_RE.findall(tok.string))
        if tok.type not in (tokenize.NL, tokenize.COMMENT):
            prev_type = tok.type
    return sorted(found)


def blank_prose(source):
    """Remove every comment and docstring, leaving the code exactly as it runs.

    Line-level scrubbing turned out to be unsound for flowing prose. Dropping
    the sentence that named a defect left the sentences around it explaining
    the same mechanism anonymously — the register with the labels filed off,
    entries still in order. Nothing catches that, because there is no token to
    match: it is ordinary English describing what the code does, and when the
    code is the defect, describing it is describing the answer.

    So the agent-facing layer ships without its author's notes. This is not a
    loss for the exercise. The student is auditing a system, not reading the
    developer's commentary, and production code under audit rarely explains
    its own faults. Behaviour, signatures, tool schemas and the engines'
    arithmetic are all still there — those are what an oracle needs.

    Nothing in this application reads __doc__ at runtime, and tool descriptions
    are data rather than docstrings, so the surfaces students audit survive.
    """
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return source

    lines = source.split("\n")
    edits = []
    prev_type = tokenize.ENCODING
    for tok in toks:
        if tok.type == tokenize.COMMENT:
            edits.append((tok.start, tok.end, None))
        elif tok.type == tokenize.STRING and prev_type in _STMT_START:
            edits.append((tok.start, tok.end, '""'))
        if tok.type not in (tokenize.NL, tokenize.COMMENT):
            prev_type = tok.type

    for (srow, scol), (erow, ecol), repl in reversed(edits):
        before, after = lines[srow - 1][:scol], lines[erow - 1][ecol:]
        if repl is None:
            merged = (before.rstrip() + after).rstrip()
            if not merged.strip():
                del lines[srow - 1:erow]
                continue
            lines[srow - 1:erow] = [merged]
        else:
            lines[srow - 1:erow] = [before + repl + after]

    out = "\n".join(lines)
    try:
        ast.parse(out)
    except SyntaxError:
        return source
    return out


def prose_text(source):
    """All comment and docstring text — what a leak check reads."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return ""
    out, prev_type = [], tokenize.ENCODING
    for tok in toks:
        if tok.type == tokenize.COMMENT or (
                tok.type == tokenize.STRING and prev_type in _STMT_START):
            out.append(tok.string)
        if tok.type not in (tokenize.NL, tokenize.COMMENT):
            prev_type = tok.type
    return "\n".join(out)
