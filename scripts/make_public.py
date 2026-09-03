"""Build the student-facing tree from this (private) repository.

Why this exists
---------------
The first public release was made by hand and its commit message said "without
course materials or homework answers". That was wrong. `Grids/` and
`solutions/` were indeed excluded, but `docs/defect-catalog.md` went out — and
the catalog *is* an answer key: it names, for every defect, what it does, which
profile carries it, how often it fires and **where to look for it**. A student
agent given only the public materials confirmed it could submit both of the
first homeworks without ever talking to the stand.

So the split is now mechanical and reviewable instead of remembered.

What the line is
----------------
The student gets the system and every surface needed to investigate it. The
student does not get the curated conclusions: what each defect does, which
requests reproduce it, where its effect is observable, and how often it fires.

  student  : run it, watch it, read its traces, read its source
  lecturer : the catalog, the per-lesson scripts, expected results, frequencies

What this cannot hide, stated plainly
-------------------------------------
The stand runs on the student's own machine, so its source is readable. A
student who reads `app/agent/tools.py` will find `if defects.is_on("D22")`
next to the field it corrupts. That is deliberate and unavoidable: removing it
would mean maintaining a second, divergent copy of the application, which is a
worse problem than the one it solves. Reading the code to work out what a
system does is legitimate QA work and takes real effort; copying a table that
already contains the conclusion is not. Only hosting the stand centrally —
students get a URL, never the source — closes the gap completely.

Usage:
  python scripts/make_public.py --dest D:/paypilot-public
  python scripts/make_public.py --dest D:/paypilot-public --check
"""
import argparse
import json
import re
import sys as _sys
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_sys.path.insert(0, str(ROOT))
from app.agent.prompt import overlay_slug  # noqa: E402
from scripts._scrub import blank_prose, prose_ids, prose_text, scrub  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# --- directories copied wholesale, minus the deny rules below ---------------
CODE_DIRS = ["app", "prompts", "specs", "tests", ".github"]

# --- everything else is named explicitly ------------------------------------
ROOT_FILES = ["Dockerfile", "docker-compose.yml", "LICENSE",
              "requirements.txt", ".env.example", ".gitignore"]

# Only these leave docs/. Anything added to docs/ later stays private by
# default, which is the safe direction for this particular mistake.
# docs/ ships nothing verbatim. Round-2 acceptance found that traces.md
# carried a seven-row "defect -> trace signature" table and architecture.md
# named eight defect ids in its prose — both of them answer keys shipped under
# the heading of reference material. Each public document is now written for
# the student and mapped here, private source -> public name.
PUBLIC_DOCS = {
    "architecture-student.md": "architecture.md",
    "traces-student.md": "traces.md",
}

# Same idea for root files that differ between the two audiences.
PUBLIC_ROOT_FROM_DOCS = {
    "README-student.md": "README.md",
    "Makefile.student": "Makefile",
}

# Only these leave scripts/. doctor and ci_smoke are diagnostics; the rest
# (calibrate, scenarios, walkthrough, gen_catalog) carry reproduction queries,
# detectors and expected results.
PUBLIC_SCRIPTS = ["doctor.py", "ci_smoke.py"]

# Paths inside the code dirs that must not ship.
DENY = [
    "__pycache__", ".pytest_cache",
    # names every defect's behaviour, one assertion at a time
    "tests/test_defects.py",
    # these two assert against lecturer-only artefacts (the seed-data tariff
    # table, corridors.yaml, calibration-report.json), so they cannot pass in
    # the student tree and they describe evidence the student does not get
    "tests/test_docs_match_policy.py",
    "tests/test_acceptance_findings.py",
]

# Lecturer-only, listed so --check can prove they are absent.
MUST_BE_ABSENT = [
    "docs/defect-catalog.md", "docs/lesson-guide.md", "docs/lecturer-runbook.md",
    "docs/walkthrough-report.md", "docs/calibration-report.json",
    "docs/calibration-history", "docs/divergences.md", "docs/seed-data.md",
    "docs/ONBOARDING.md", "docs/acceptance-review-customer.md",
    "docs/acceptance-review-student.md", "profiles/corridors.yaml",
    "scripts/calibrate.py", "scripts/scenarios.py", "scripts/walkthrough.py",
    "scripts/gen_catalog.py", "scripts/make_public.py",
    "tests/test_defects.py", "tests/test_docs_match_policy.py",
    "tests/test_acceptance_findings.py", "solutions", "Grids",
    # _gen_corpus builds kb_broken, i.e. it is the mechanism of D16 in prose;
    # _judge is part of the calibration harness
    "scripts/_gen_corpus.py", "scripts/_gen_corpus2.py", "scripts/_judge.py",
    "scripts/_scrub.py",
]

# Phrases that must never appear anywhere in the public tree.
FORBIDDEN_PHRASES = [
    "Застереження для лектора",
    "текстова перевірка тут зелена",
    "Видно в:",
    "заміряна частота",
]

# Grepping for phrases only catches the wording you thought of: round 2 found a
# whole answer table that none of the four phrases matched. The durable rule is
# structural — no prose in the student tree names a defect. Ids may appear only
# where the stand needs them as bare data.
# Case-insensitive, because the register also travels in lowercase runtime
# labels ("d14-retry-1", "phantom#d03"), and scoped to every text file rather
# than a suffix list. Round 3 found the answer key in a .json fixture, a .yml
# comment and a set of .md filenames — three places the suffix list did not
# reach. A leak check that only looks where the last leak was is not a check.
ID_PATTERN = re.compile(r"(?<![A-Za-z0-9])[Dd][0-9]{2}(?![0-9])")
ID_ALLOWED = {"profiles/defects.yaml", "profiles/profiles.yaml"}
_BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip",
                    ".woff", ".woff2", ".ttf", ".db", ".sqlite", ".pyc"}


def _denied(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return any(d in rel for d in DENY)


def _copy_tree(src: Path, dest: Path, log: list[str]) -> None:
    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if _denied(rel):
            log.append(f"  skip  {rel}")
            continue
        target = dest / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".py":
            # app/ ships as it runs, without its author's notes: the code is
            # the mechanism and the student needs it, the commentary explains
            # the mechanism and is the answer. tests/ and scripts/ keep their
            # prose — they are worked examples, and only the identifiers go.
            src = p.read_text(encoding="utf-8")
            out = blank_prose(src) if rel.startswith("app/") else scrub(src)
            target.write_text(out, encoding="utf-8", newline=chr(10))
            if out != src:
                log.append(f"  scrub {rel}")
            continue
        shutil.copy2(p, target)


def strip_defect_registry(text: str) -> str:
    """profiles/defects.yaml -> ids only.

    The stand needs the ids at runtime to validate a configuration and to
    report which defects are active. It does not need the titles, and a title
    like "Daily presented as monthly" is most of the homework.
    """
    out = ["# Defect registry, student build: identifiers only.",
           "#",
           "# The stand validates configuration against this list and reports",
           "# which defects are active. What each one does is not here — that",
           "# is what you are asked to find out.",
           "",
           "defects:"]
    for did in sorted(set(re.findall(r"^\s{2}(D\d{2}):", text, re.M))):
        out.append(f"  {did}: {{}}")
    return "\n".join(out) + "\n"


def strip_profiles(text: str) -> str:
    """profiles/profiles.yaml -> compositions without the commentary.

    The composition itself has to ship: the stand loads it, and the UI already
    shows which defects a profile carries. The trailing comments ("confirmed
    (L03)", "D21 now implemented") are working notes and go.
    """
    out = ["# Lesson profiles, student build.",
           "# A profile is the set of defects a lesson runs with.",
           "",
           "profiles:"]
    for name, body in re.findall(r"^\s{2}([\w-]+):\s*\[([^\]]*)\]", text, re.M):
        ids = ", ".join(x.strip() for x in body.split(",") if x.strip())
        out.append(f"  {name}: [{ids}]")
    return "\n".join(out) + "\n"


def build(dest: Path) -> None:
    if dest.exists():
        for child in dest.iterdir():
            if child.name in (".git", ".venv"):   # repo and local env survive
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    dest.mkdir(parents=True, exist_ok=True)

    # A real .env in the destination is a live key sitting in the tree that
    # gets handed out. It is gitignored, so nothing catches it — round-2
    # acceptance found one there, copied in during testing.
    stray_env = dest / ".env"
    if stray_env.exists():
        stray_env.unlink()

    # data/ and traces/ are created by the running application, not copied
    # here, so deleting them breaks whatever stand is currently using this
    # tree — it did, once, under a live session. They are gitignored and so
    # never travel in a clone; --check verifies that rather than their absence.

    log: list[str] = []
    for d in CODE_DIRS:
        _copy_tree(ROOT / d, dest, log)

    missing = [n for n in ROOT_FILES if not (ROOT / n).exists()]
    if missing:
        # A silently dropped file is how the public repo lost its LICENSE on
        # the first mechanical build. Required root files are required.
        raise SystemExit(f"missing from the private repo: {missing}")
    for name in ROOT_FILES:
        shutil.copy2(ROOT / name, dest / name)

    # Overlay files are renamed to opaque slugs. The content must ship — the
    # stand applies it at runtime — but a directory listing of D01.md..D27.md
    # is an index into the answer key, and grep gets there without running
    # anything. prompt.py resolves either name, so nothing diverges.
    overlays = dest / "prompts" / "overlays"
    for f in sorted(overlays.glob("*.md")):
        did = f.stem
        if re.fullmatch(r"D[0-9]{2}", did):
            f.rename(overlays / f"{overlay_slug(did)}.md")
            log.append(f"  rename prompts/overlays/{f.name}")

    # The judge fixture is lesson material students use, but its header named
    # the defect and stated the lesson's conclusion verbatim.
    fx_old = dest / "app" / "fixtures" / "d18_judge_pairs.json"
    if fx_old.exists():
        data = json.loads(fx_old.read_text(encoding="utf-8"))
        for key in ("defect", "description"):
            data.pop(key, None)
        fx_new = fx_old.with_name("judge_pairs.json")
        fx_new.write_text(json.dumps(data, indent=2, ensure_ascii=False)
                          + chr(10), encoding="utf-8")
        fx_old.unlink()
        log.append("  strip  app/fixtures/judge_pairs.json")

    if not (dest / ".github" / "workflows" / "stand-ci.yml").exists():
        raise SystemExit("CI workflow did not make it into the student tree")

    (dest / "docs").mkdir(exist_ok=True)
    for src_name, public_name in PUBLIC_DOCS.items():
        shutil.copy2(ROOT / "docs" / src_name, dest / "docs" / public_name)

    for src_name, public_name in PUBLIC_ROOT_FROM_DOCS.items():
        shutil.copy2(ROOT / "docs" / src_name, dest / public_name)

    (dest / "scripts").mkdir(exist_ok=True)
    for name in PUBLIC_SCRIPTS:
        shutil.copy2(ROOT / "scripts" / name, dest / "scripts" / name)

    (dest / "profiles").mkdir(exist_ok=True)
    (dest / "profiles" / "defects.yaml").write_text(
        strip_defect_registry((ROOT / "profiles" / "defects.yaml")
                              .read_text(encoding="utf-8")), encoding="utf-8")
    (dest / "profiles" / "profiles.yaml").write_text(
        strip_profiles((ROOT / "profiles" / "profiles.yaml")
                       .read_text(encoding="utf-8")), encoding="utf-8")

    for line in log:
        print(line)
    print(f"built student tree -> {dest}")

    # Rebuilding is not publishing. The tree was rebuilt many times while the
    # published repository quietly stayed a day behind — a student cloning it
    # would have got the stand from before a day of fixes. Say so.
    if (dest / ".git").exists():
        import subprocess
        try:
            # --ignore-cr-at-eol, because the build writes LF and git checks
            # out CRLF on Windows: without it every rebuild after a checkout
            # looks dirty, and a warning that always fires is one people learn
            # to ignore.
            changed = subprocess.run(
                ["git", "diff", "--name-only", "--ignore-cr-at-eol"],
                cwd=dest, capture_output=True, text=True, timeout=60).stdout
            untracked = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=dest, capture_output=True, text=True, timeout=60).stdout
            files = [x for x in (changed + untracked).splitlines() if x.strip()]
            if files:
                print(f"!! {len(files)} file(s) differ from the published "
                      f"release: {', '.join(files[:4])}"
                      + (" …" if len(files) > 4 else ""))
                print("   Rebuilding does not publish — commit and push "
                      f"{dest}.")
        except (OSError, subprocess.SubprocessError):
            pass


def check(dest: Path) -> int:
    problems = []
    for rel in MUST_BE_ABSENT:
        if (dest / rel).exists():
            problems.append(f"present but must not be: {rel}")

    for p in dest.rglob("*"):
        if not p.is_file() or ".git" in p.parts:
            continue
        if p.suffix.lower() not in (".md", ".yaml", ".yml", ".json", ".py",
                                    ".html", ".txt", ""):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for phrase in FORBIDDEN_PHRASES:
            if phrase in text:
                problems.append(
                    f"{p.relative_to(dest).as_posix()}: contains {phrase!r}")

    # A key in the student tree is a leak even when git never sees it: the
    # tree itself is the thing distributed.
    if (dest / ".env").exists():
        problems.append(".env is present in the student tree — it carries a live key")

    # The key must never be tracked either.
    ignore = [line.strip() for line in
              (dest / ".gitignore").read_text(encoding="utf-8").splitlines()]
    if ".env" not in ignore:
        problems.append(".gitignore does not exclude .env")

    # Runtime output is made of the thing being hidden — traces/traces.jsonl
    # records run.active_defects on every request — but it is generated locally
    # and must never be committed. Absence is the wrong test: the application
    # recreates these while it runs.
    for leftover in ("traces/", "data/"):
        if not any(line.rstrip("/") == leftover.rstrip("/") or
                   line.startswith(leftover) for line in ignore):
            problems.append(f".gitignore does not exclude {leftover}")

    # No student-facing text may name a defect — in its content or its name.
    for p in sorted(dest.rglob("*")):
        if not p.is_file() or ".git" in p.parts or ".venv" in p.parts:
            continue
        rel = p.relative_to(dest).as_posix()
        if p.suffix.lower() in _BINARY_SUFFIXES:
            continue
        if p.parts[0] in ("traces", "data"):
            continue          # runtime output, gitignored, checked separately
        if ID_PATTERN.search(p.name):
            problems.append(f"{rel}: the filename itself names a defect")
        if rel in ID_ALLOWED or rel.endswith(".py"):
            continue          # .py is handled by the prose rules above
        try:
            found = sorted(set(ID_PATTERN.findall(p.read_text(encoding="utf-8"))))
        except (UnicodeDecodeError, OSError):
            continue
        if found:
            problems.append(f"{rel}: names defects {', '.join(found)}")

    # app/ must carry no prose at all: a sentence describing what a defective
    # function does is the answer whether or not it names the identifier.
    # Elsewhere, prose is fine as long as it names no defect.
    for p in sorted(dest.rglob("*.py")):
        if ".venv" in p.parts:
            continue
        try:
            src = p.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = p.relative_to(dest).as_posix()
        if rel.startswith("app/"):
            left = prose_text(src).replace('""', "").strip()
            if left:
                problems.append(f"{rel}: still carries commentary "
                                f"({left[:60]!r})")
        elif (found := prose_ids(src)):
            problems.append(f"{rel}: names {', '.join(found)} in a comment "
                            f"or docstring")

    # And the same rule for the destination's git history. Twice a hint was
    # removed from the working tree and stayed reachable through
    # `git show <old commit>:<file>` — the catalog first, then the overlays
    # named after defect ids. The public repository therefore carries exactly
    # one commit per release, and this proves it.
    if (dest / ".git").exists():
        import subprocess
        try:
            revs = subprocess.run(["git", "rev-list", "--all"], cwd=dest,
                                  capture_output=True, text=True, timeout=60)
            commits = [c for c in revs.stdout.split() if c]
            if len(commits) > 1:
                problems.append(f"git history has {len(commits)} commits; a "
                                f"release tree must carry exactly one, or "
                                f"anything ever removed stays reachable")
            for c in commits:
                names = subprocess.run(["git", "ls-tree", "-r", "--name-only", c],
                                       cwd=dest, capture_output=True, text=True,
                                       timeout=60).stdout
                leaked = sorted({n for n in names.split()
                                 if ID_PATTERN.search(Path(n).name)})
                if leaked:
                    problems.append(f"commit {c[:8]} still holds "
                                    f"{', '.join(leaked[:4])}")
        except (OSError, subprocess.SubprocessError):
            problems.append("could not inspect the destination git history")

    reg = (dest / "profiles" / "defects.yaml").read_text(encoding="utf-8")
    if "title:" in reg or "mechanism:" in reg:
        problems.append("profiles/defects.yaml still carries titles/mechanisms")

    if problems:
        print("FAIL — the student build leaks:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"OK — {len(MUST_BE_ABSENT)} lecturer paths absent, "
          f"{len(FORBIDDEN_PHRASES)} answer phrases absent, registry "
          f"stripped, no defect named in student prose.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", required=True)
    ap.add_argument("--check", action="store_true",
                    help="only verify an existing tree, do not rebuild")
    args = ap.parse_args()
    dest = Path(args.dest).resolve()
    if not args.check:
        build(dest)
    return check(dest)


if __name__ == "__main__":
    sys.exit(main())
