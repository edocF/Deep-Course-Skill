"""Package boundaries; agent decisions are evaluated by the scenario suite."""

import ast
from pathlib import Path
import re
import sys
import unittest
from urllib.parse import unquote, urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]


class SkillPackageTests(unittest.TestCase):
    def read_required(self, relative):
        path = ROOT / relative
        self.assertTrue(path.is_file(), f"Missing package resource: {relative}")
        return path.read_text(encoding="utf-8")

    def test_frontmatter_is_loadable_and_identifies_the_skill(self):
        text = self.read_required("SKILL.md")
        match = re.match(r"\A---\n(.*?)\n---(?:\n|$)", text, re.S)
        self.assertIsNotNone(match, "Missing YAML frontmatter")
        metadata = yaml.safe_load(match.group(1))
        self.assertIsInstance(metadata, dict)
        self.assertEqual(metadata.get("name"), "deep-course")
        self.assertLessEqual(set(metadata), {"name", "description", "license", "allowed-tools", "metadata"})
        description = metadata.get("description")
        self.assertIsInstance(description, str)
        self.assertTrue(description.strip())
        self.assertLessEqual(len(description), 500)

    def test_ui_metadata_exposes_explicit_invocation_only(self):
        metadata = yaml.safe_load(self.read_required("agents/openai.yaml"))
        self.assertIsInstance(metadata, dict)
        self.assertIs(metadata.get("policy", {}).get("allow_implicit_invocation"), False)
        interface = metadata.get("interface", {})
        self.assertTrue(interface.get("display_name", "").strip())
        self.assertLessEqual(25, len(interface.get("short_description", "")))
        self.assertLessEqual(len(interface.get("short_description", "")), 64)
        self.assertIn("$deep-course", interface.get("default_prompt", ""))

    def test_director_routes_to_existing_contained_resources(self):
        expected = {
            "references/state-contracts.md",
            "references/onboarding-and-curriculum.md",
            "references/research-and-sources.md",
            "references/lesson-design.md",
            "references/assessment-and-adaptation.md",
        }
        pending = [ROOT / "SKILL.md"]
        visited = set()
        while pending:
            source = pending.pop()
            if source in visited:
                continue
            visited.add(source)
            text = self.read_required(source.relative_to(ROOT))
            for link in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", text):
                url = urlsplit(link)
                if url.scheme or not url.path:
                    continue
                target = (source.parent / unquote(url.path)).resolve()
                self.assertTrue(target.is_relative_to(ROOT), f"Link escapes package: {link}")
                self.assertTrue(target.is_file(), f"Broken link in {source.name}: {link}")
                if target.suffix == ".md":
                    pending.append(target)
        self.assertTrue(expected <= {path.relative_to(ROOT).as_posix() for path in visited})

    def test_runtime_has_no_direct_llm_or_third_party_dependency(self):
        scripts = list((ROOT / "scripts").glob("*.py"))
        self.assertTrue(scripts)
        local_modules = {path.stem for path in scripts}
        for script in scripts:
            tree = ast.parse(script.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                for module in modules:
                    self.assertIn(module.split(".")[0], sys.stdlib_module_names | local_modules)
        metadata = yaml.safe_load(self.read_required("agents/openai.yaml"))
        self.assertFalse(metadata.get("dependencies"), "Generic kernel requires no external service")

    def test_package_has_no_domain_pack_or_unfinished_scaffolds(self):
        self.read_required("SKILL.md")
        for path in ROOT.rglob("*"):
            self.assertNotIn(path.name.lower(), {"domains", "domain-packs", "domain_packs"})
        instructions = [ROOT / "SKILL.md", ROOT / "agents/openai.yaml", *(ROOT / "references").glob("*.md")]
        for path in instructions:
            text = self.read_required(path.relative_to(ROOT))
            self.assertIsNone(re.search(r"\b(?:TODO|TBD|FIXME)\b|\[(?:INSERT|REPLACE)[^\]]*\]|\{\{[^}]+\}\}", text), str(path))


if __name__ == "__main__":
    unittest.main()
