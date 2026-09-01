#!/usr/bin/env python3
"""The Claude Code skill: what --install-skill writes, and takes away again.

Needs no display and touches no real home directory; the skill directory is
replaced with a temporary one, the same way the other suites replace the
preferences path.

    python3 tests/test_skill.py
"""

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "src"))

from programmers_screenshot import skill  # noqa: E402


class Checker:
    def __init__(self):
        self.failures = []

    def section(self, title):
        print("\n%s" % title)

    def __call__(self, name, condition, detail=""):
        suffix = "  [%s]" % (detail,) if detail != "" and detail is not None else ""
        print("%s %s%s" % ("  ok  " if condition else " FAIL ", name, suffix))
        if not condition:
            self.failures.append(name)

    def report(self):
        print("\n%d failure(s)" % len(self.failures))
        return 1 if self.failures else 0


def frontmatter(text):
    """The --- block at the top, as a dict, or None if there isn't one."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end == -1:
        return None
    fields = {}
    key = None
    for line in text[4:end].splitlines():
        if line.startswith(" ") and key:      # a folded value carries on
            fields[key] += " " + line.strip()
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
    return fields


def main():
    check = Checker()
    home = tempfile.mkdtemp(prefix="programmers-screenshot-skill-")
    real = skill.directory
    skill.directory = lambda: os.path.join(home, "skills", skill.NAME)

    try:
        check.section("installing writes one file, where skills are looked for")
        check("it reports success", skill.install() == 0)
        check("the file is there", os.path.exists(skill.path()), skill.path())
        check("named SKILL.md", os.path.basename(skill.path()) == "SKILL.md")
        check("in a directory named after the command",
              os.path.basename(os.path.dirname(skill.path())) == "programmers-screenshot")

        written = open(skill.path(), encoding="utf-8").read()
        # Searched with the line breaks taken out: a phrase that happens to
        # wrap is still the phrase, and a test should not pin the wrapping.
        flat = " ".join(written.split())
        fields = frontmatter(written)

        check.section("the front matter is what makes it findable")
        check("there is front matter at all", fields is not None)
        check("it names itself", (fields or {}).get("name") == "programmers-screenshot")
        description = (fields or {}).get("description", "")
        check("it has a description", len(description) > 40, len(description))
        for word in ("screenshot", "annotat", "window", "tab"):
            check("  the description says %r" % word, word in description.lower())

        check.section("the body sends the reader to the generated reference")
        # The point of keeping the skill thin: anything that could go stale
        # lives in --recipe-help, which is built from the parser's own table.
        check("it points at --recipe-help", "--recipe-help" in written)
        check("it covers the three ways in",
              all(flag in written for flag in ("--region", "--window", "--input")))
        check("it explains why a tab needs --input",
              "a tab is not a window" in flat and "background tab" in flat)
        check("it says the switch is the person's to make",
              "settings window" in flat and "their decision" in flat)
        check("and warns about what a screen may be showing",
              "redact" in flat and "averages leak" in flat)

        check.section("installing again is the same file, not a second one")
        check("it succeeds", skill.install() == 0)
        check("the content is unchanged",
              open(skill.path(), encoding="utf-8").read() == written)

        check.section("uninstalling takes back exactly what it put there")
        check("it reports success", skill.uninstall() == 0)
        check("the file is gone", not os.path.exists(skill.path()))
        check("and so is its directory", not os.path.exists(skill.directory()))
        check("doing it twice is not an error", skill.uninstall() == 0)

        check.section("a directory somebody else has added to is left alone")
        skill.install()
        beside = os.path.join(skill.directory(), "notes.md")
        open(beside, "w", encoding="utf-8").write("mine\n")
        skill.uninstall()
        check("their file survives", os.path.exists(beside))
        check("ours does not", not os.path.exists(skill.path()))
    finally:
        skill.directory = real
        shutil.rmtree(home, ignore_errors=True)

    return check.report()


if __name__ == "__main__":
    sys.exit(main())
