"""Checks of the daily maintainer's tool rules (.github/maintainer/settings.json): no allow rule that runs arbitrary
code or reaches the network, no rule that writes to GitHub, and network tools denied however they are wrapped.
Claude Code matches a Bash rule against the command as written, with * matching any text; match() below does the
same. Run: python3 -m unittest discover -s .github/scripts -p 'test_maintainer*.py'"""
import json
import os
import re
import unittest

SETTINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "maintainer", "settings.json")


def load():
    with open(SETTINGS, encoding="utf-8") as f:
        return json.load(f)["permissions"]


def bash_rules(rules):
    return [r[len("Bash("):-1] for r in rules if r.startswith("Bash(")]


def match(rule, command):
    return re.fullmatch(".*".join(re.escape(part) for part in rule.split("*")), command, re.DOTALL) is not None


def denied(command, permissions):
    return any(match(rule, command) for rule in bash_rules(permissions["deny"]))


def allowed(command, permissions):
    return not denied(command, permissions) and any(match(r, command) for r in bash_rules(permissions["allow"]))


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.permissions = load()

    def test_no_broad_allow_rules(self):
        allow = bash_rules(self.permissions["allow"])
        for broad in ("python *", "python3 *", "docker run *", "docker *", "npm run *", "npm install *",
                      "pip install *", "timeout *", "env *", "bash *", "sh *", "node *", "npx *"):
            self.assertNotIn(broad, allow)
        # Interpreters and wrappers appear only in exact test and lint commands.
        for rule in allow:
            if rule.startswith(("python", "pip ", "npm ", "npx ")):
                self.assertNotRegex(rule, r"^(python3?|pip|npm|npx) \*", rule)

    def test_nothing_writes_to_github(self):
        for command in ("git push origin maint/x", "git push -u origin maint/x", "gh pr create --base main",
                        "gh pr edit 5 --add-label x", "gh pr merge 5", "gh label create x",
                        "gh workflow run ci.yml --ref maint/x", "gh api repos/ARCO-Lab/WELLWebsite/pulls/5/merge",
                        "gh api repos/ARCO-Lab/WELLWebsite/issues -f title=x", "gh api graphql -f query=x",
                        "git remote -v", "git config --list", "git -c core.sshCommand=x fetch origin"):
            self.assertFalse(allowed(command, self.permissions), command)

    def test_network_tools_are_denied_in_every_form(self):
        for tool in ("curl https://example.com", "wget https://example.com", "nc example.com 80",
                     "ssh host", "scp a host:b", "openssl s_client -connect example.com:443"):
            for wrapped in (tool, f"env {tool}", f"env A=1 {tool}", f"timeout 9 {tool}", f"nohup {tool}",
                            f"echo x | xargs {tool}", f"bash -c '{tool}'", f'sh -c "{tool}"',
                            f"/usr/bin/{tool}", f"sudo {tool}", f"nice {tool}"):
                self.assertTrue(denied(wrapped, self.permissions), wrapped)
        self.assertTrue(denied("cat < /dev/tcp/example.com/80", self.permissions))
        for tool in ("WebFetch", "WebSearch"):
            self.assertIn(tool, self.permissions["deny"])

    def test_old_bypasses_are_closed(self):
        for command in ('python3 -c "__import__(\'o\'+\'s\').system(\'id\')"', "python3 x.py",
                        "docker run -v /:/h alpine cat /h/etc/shadow", "npm run anything",
                        "timeout 9 python3 x.py", "pip install evil", "node x.js", "perl -e 1"):
            self.assertFalse(allowed(command, self.permissions), command)

    def test_the_checks_the_prompt_names_are_allowed(self):
        for command in ("git status", "git diff origin/main...maint/x", "git fetch origin main",
                        "git switch -c maint/x origin/main", "git commit -m 'Fix x'", "npm ci", "npm test",
                        "npm run build", "npm run lint", "npx tsc --noEmit",
                        "python -m unittest discover -s tests -t .",
                        "pipx run ruff==0.14.0 check --select F --target-version py311 dashboard/backend",
                        "shellcheck deploy.sh", "bash .github/scripts/test_deploy.sh", "gh pr view 5",
                        "gh run view 1 --log-failed", "gh api repos/ARCO-Lab/WELLWebsite/pulls/5/comments"):
            self.assertTrue(allowed(command, self.permissions), command)

    def test_the_automation_and_git_internals_cant_be_edited(self):
        deny = self.permissions["deny"]
        for rule in ("Edit(.github/**)", "Write(.github/**)", "Edit(.git/**)", "Write(.git/**)",
                     "Edit(.claude/**)", "Read(**/.env)"):
            self.assertIn(rule, deny)


if __name__ == "__main__":
    unittest.main()
