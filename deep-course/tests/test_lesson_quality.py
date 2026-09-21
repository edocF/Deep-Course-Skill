"""Regression coverage for the lesson reading-depth gate."""
import copy
import json
import sys
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lesson_quality


INSTRUCTIONAL_TEXT = """
# Estimating bond yield from price

A bond is a contract with promised cash flows. An investor pays a market price
today and receives coupon payments plus the face value later. Yield to maturity
is the annual return that makes the present value of those promised cash flows
equal to the price paid. It is an estimate because it assumes the investor holds
the bond to maturity and every coupon can be reinvested at that same yield.

For a two-year bond with a 1,000 dollar face value and a five percent annual
coupon, the cash flow in year one is 50 dollars. The cash flow in year two is
1,050 dollars because it includes the final coupon and repayment of principal.
If the market price is below 1,000 dollars, the yield must be above the five
percent coupon rate. The investor receives the stated coupons and also gains
value as the discounted purchase price moves toward the face value at maturity.

The pricing model discounts each future cash flow by one plus the trial yield.
For a trial yield r, price equals 50 divided by one plus r, plus 1,050 divided
by one plus r squared. This equation makes the price-yield relationship
observable: a higher trial yield increases the discounting and lowers the
calculated price. A lower trial yield does the reverse. Analysts compare a
calculated price with the market price, then adjust the trial yield until the
two values are sufficiently close.

## Worked example

Suppose the bond sells for 980 dollars. At a six percent trial yield, the first
cash flow has a present value of 47.17 dollars and the second has a present
value of 934.62 dollars. The total calculated price is 981.79 dollars. That is
slightly above the market price, so the trial yield is slightly too low. At a
6.10 percent trial yield, the two present values are 47.13 dollars and 932.82
dollars, for a total of 979.95 dollars. The market price lies between those two
results, so the estimated yield is about 6.10 percent. The calculation matters
more than memorizing the number: the trial prices show why a lower price implies
a higher required yield for the same promised cash flows.

## Practice

1. State the year-one and year-two cash flows for this bond.
2. Predict whether the price rises or falls when the trial yield changes from
   six percent to seven percent, and explain why.
3. If the market price were 1,020 dollars, would the yield be above or below the
   coupon rate? Give one sentence of reasoning.
4. Describe the next trial you would choose after calculating a price above the
   market price.
"""


class LessonQualityTests(unittest.TestCase):
    def make_lesson(self, root, *, lesson_directory="lessons/bond-yield", include_markdown=True, markdown_text=INSTRUCTIONAL_TEXT, html_text=None, planned_minutes=35):
        lesson = root / lesson_directory
        lesson.mkdir(parents=True, exist_ok=True)
        if include_markdown:
            (lesson / "lesson.md").write_text(markdown_text, encoding="utf-8")
        if html_text is None:
            html_text = """<!doctype html><html><head><style>.hidden { display: none; }</style></head>
            <body><nav>Previous Next</nav><main><h1>Bond yield</h1><p>Short lesson shell.</p>
            <form><label for=answer>Explain your estimate</label><textarea id=answer></textarea>
            <button>Check answer</button></form><script>const answer = 'not reading';</script>
            </main></body></html>"""
        (lesson / "lesson.html").write_text(html_text, encoding="utf-8")
        for name in ("exercises.md", "answers.md", "sources.md", "state.json"):
            (lesson / name).write_text("artifact", encoding="utf-8")
        return {
            "lesson_directory": lesson_directory,
            "planned_minutes": planned_minutes,
            "artifacts": [{"path": f"{lesson_directory}/{name}"} for name in (
                "lesson.md", "lesson.html", "exercises.md", "answers.md", "sources.md", "state.json"
            )],
        }

    def make_quality_lesson(self, root, *, repetitions=20):
        """Create a hand-checkable, fully declared normal-depth lesson."""
        definitions = [
            ("Why bond yield matters", "orientation", "Orientation frames the learner's decision before any calculation begins."),
            ("Bridge from present value", "prerequisite-bridge", "Present value knowledge connects earlier discounting work to the new yield estimate."),
            ("Price and yield move oppositely", "price-yield", "A fixed promised cash flow becomes less valuable when the required yield rises."),
            ("Estimate yield with trial prices", "trial-yield", "A trial yield is revised by comparing its calculated price with the observed market price."),
            ("Connect the reasoning", "synthesis", "The direction rule and trial calculation combine into one defensible estimate."),
            ("Consolidate the method", "consolidation", "The final check states the cash flows, direction, trial result, and justified conclusion."),
            ("Worked example: trial yields", "worked-full", "The complete example shows every discounting step and explains the next trial."),
            ("Faded example: changing price", "worked-faded", "The faded example supplies the cash flows while the learner chooses the yield direction."),
            ("Independent task: explain the estimate", "worked-independent", "The independent task asks the learner to calculate and justify an unseen bond estimate."),
        ]
        markdown_parts = []
        html_parts = []
        for index, (heading, html_id, sentence) in enumerate(definitions, start=1):
            body = " ".join(
                f"{sentence} Checkpoint {index} reinforces the explanation with observable evidence."
                for _ in range(repetitions)
            )
            markdown_parts.append(f"## {heading}\n\n{body}")
            html_parts.append(f'<section id="{html_id}"><h2>{heading}</h2><p>{body}</p></section>')
        question_ids = ("q-direction", "q-trial", "q-explain")
        questions = [{"id": item, "required": True} for item in question_ids]
        controls = "".join(f'<textarea data-question-id="{item}" required></textarea>' for item in question_ids)
        html = "<!doctype html><html><body><main>" + "".join(html_parts) + controls + (
            '<script id="lesson-data" type="application/json">'
            + json.dumps({"questions": questions})
            + "</script></main></body></html>"
        )
        manifest = self.make_lesson(
            root,
            markdown_text="\n\n".join(markdown_parts),
            html_text=html,
            planned_minutes=35,
        )
        manifest["learning_objectives"] = [
            "Estimate yield from a bond price.",
            "Explain the inverse price-yield relationship.",
        ]
        manifest["quality_evidence"] = {
            "contract_version": 1,
            "session_depth": "normal",
            "planned_minutes": 35,
            "reading_minutes": 25,
            "response_minutes": 10,
            "below_target_justification": "",
            "objectives": [
                {"objective_id": "estimate-yield", "text": "Estimate yield from a bond price."},
                {"objective_id": "explain-direction", "text": "Explain the inverse price-yield relationship."},
            ],
            "reading_sections": [
                {"content_id": "orientation", "role": "orientation", "markdown_heading": "Why bond yield matters", "html_id": "orientation", "objective_ids": [], "prerequisite_knowledge_ids": []},
                {"content_id": "prerequisite-bridge", "role": "prerequisite_bridge", "markdown_heading": "Bridge from present value", "html_id": "prerequisite-bridge", "objective_ids": [], "prerequisite_knowledge_ids": ["present-value"]},
                {"content_id": "price-yield", "role": "concept", "markdown_heading": "Price and yield move oppositely", "html_id": "price-yield", "objective_ids": ["explain-direction"], "prerequisite_knowledge_ids": ["present-value"]},
                {"content_id": "trial-yield", "role": "concept", "markdown_heading": "Estimate yield with trial prices", "html_id": "trial-yield", "objective_ids": ["estimate-yield"], "prerequisite_knowledge_ids": ["present-value"]},
                {"content_id": "synthesis", "role": "synthesis", "markdown_heading": "Connect the reasoning", "html_id": "synthesis", "objective_ids": ["estimate-yield", "explain-direction"], "prerequisite_knowledge_ids": []},
                {"content_id": "consolidation", "role": "consolidation", "markdown_heading": "Consolidate the method", "html_id": "consolidation", "objective_ids": ["estimate-yield", "explain-direction"], "prerequisite_knowledge_ids": []},
            ],
            "worked_examples": [
                {"example_id": "worked-full", "support": "full", "markdown_heading": "Worked example: trial yields", "html_id": "worked-full", "objective_ids": ["estimate-yield"]},
                {"example_id": "worked-faded", "support": "faded", "markdown_heading": "Faded example: changing price", "html_id": "worked-faded", "objective_ids": ["explain-direction"]},
                {"example_id": "worked-independent", "support": "independent", "markdown_heading": "Independent task: explain the estimate", "html_id": "worked-independent", "objective_ids": ["estimate-yield", "explain-direction"]},
            ],
            "response_question_ids": list(question_ids),
            "semantic_review": {
                "passed": True,
                "reviewed_at": "2026-09-15T09:30:00+00:00",
                "revision_summary": "Checked progression, examples, and question alignment.",
            },
        }
        return manifest

    def set_quality_questions(self, root, manifest, question_ids):
        old_ids = tuple(manifest["quality_evidence"]["response_question_ids"])
        html_path = root / manifest["lesson_directory"] / "lesson.html"
        html = html_path.read_text(encoding="utf-8")
        old_controls = "".join(f'<textarea data-question-id="{item}" required></textarea>' for item in old_ids)
        new_controls = "".join(f'<textarea data-question-id="{item}" required></textarea>' for item in question_ids)
        old_data = json.dumps({"questions": [{"id": item, "required": True} for item in old_ids]})
        new_data = json.dumps({"questions": [{"id": item, "required": True} for item in question_ids]})
        html_path.write_text(html.replace(old_controls, new_controls).replace(old_data, new_data), encoding="utf-8")
        manifest["quality_evidence"]["response_question_ids"] = list(question_ids)

    def assert_audit_is_read_only(self, root, manifest, expected_code):
        before_manifest = copy.deepcopy(manifest)
        lesson = root / manifest["lesson_directory"]
        before_markdown = (lesson / "lesson.md").read_bytes()
        before_html = (lesson / "lesson.html").read_bytes()

        report = lesson_quality.audit_lesson(root, manifest)

        self.assertIn(expected_code, {item["code"] for item in report["errors"]})
        self.assertEqual(before_manifest, manifest)
        self.assertEqual(before_markdown, (lesson / "lesson.md").read_bytes())
        self.assertEqual(before_html, (lesson / "lesson.html").read_bytes())
        return report

    def test_rejects_exact_quality_contract_mutations_without_writing_inputs(self):
        """Catches omitting any named semantic-quality boundary or mutating audited inputs."""
        cases = {
            "invalid_time_evidence": {"planned_minutes": 29},
            "missing_progression": {"reading_sections": []},
            "objective_uncovered": {"objectives": []},
            "missing_worked_example": {"worked_examples": []},
            "interaction_overweight": {"response_minutes": 14},
            "html_content_loss": {"html_fraction": 0.50},
            "invalid_quality_evidence": {"contract_version": 99},
        }
        for expected_code, mutation in cases.items():
            with self.subTest(expected_code=expected_code), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = self.make_quality_lesson(root)
                if "html_fraction" in mutation:
                    html_path = root / manifest["lesson_directory"] / "lesson.html"
                    html = html_path.read_text(encoding="utf-8")
                    midpoint = html.find('<section id="synthesis">')
                    controls = html.find('<textarea data-question-id="q-direction"')
                    html_path.write_text(html[:midpoint] + html[controls:], encoding="utf-8")
                else:
                    manifest["quality_evidence"].update(mutation)
                self.assert_audit_is_read_only(root, manifest, expected_code)

    def test_rejects_repeated_instructional_blocks_under_distinct_content_ids(self):
        """Catches content IDs disguising repeated filler as distinct progression."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.make_quality_lesson(root)
            lesson = root / manifest["lesson_directory"]
            markdown = (lesson / "lesson.md").read_text(encoding="utf-8")
            first_body = markdown.split("## Bridge from present value", 1)[0].split("\n\n", 1)[1].strip()
            start = markdown.index("## Price and yield move oppositely")
            end = markdown.index("## Estimate yield with trial prices")
            markdown = markdown[:start] + f"## Price and yield move oppositely\n\n{first_body}\n\n" + markdown[end:]
            bridge_start = markdown.index("## Bridge from present value")
            bridge_end = markdown.index("## Price and yield move oppositely")
            markdown = markdown[:bridge_start] + f"## Bridge from present value\n\n{first_body}\n\n" + markdown[bridge_end:]
            lesson.joinpath("lesson.md").write_text(markdown, encoding="utf-8")

            self.assert_audit_is_read_only(root, manifest, "duplicate_instructional_content")

    def test_rejects_malformed_quality_evidence_shapes(self):
        """Catches permissive schema handling for unsafe IDs, references, numbers, and review timestamps."""
        mutations = {
            "unknown top-level field": lambda evidence: evidence.update({"notes": "extra"}),
            "boolean number": lambda evidence: evidence.update({"reading_minutes": True}),
            "non-finite number": lambda evidence: evidence.update({"response_minutes": float("nan")}),
            "unsafe ID": lambda evidence: evidence["objectives"][0].update({"objective_id": "../escape"}),
            "duplicate ID": lambda evidence: evidence["objectives"][1].update({"objective_id": "estimate-yield"}),
            "duplicate declared HTML ID": lambda evidence: evidence["reading_sections"][3].update({"html_id": "price-yield"}),
            "unknown objective reference": lambda evidence: evidence["reading_sections"][2]["objective_ids"].append("missing-objective"),
            "unknown nested field": lambda evidence: evidence["worked_examples"][0].update({"answer": "extra"}),
            "naive timestamp": lambda evidence: evidence["semantic_review"].update({"reviewed_at": "2026-09-15T09:30:00"}),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = self.make_quality_lesson(root)
                mutate(manifest["quality_evidence"])
                self.assert_audit_is_read_only(root, manifest, "invalid_quality_evidence")

    def test_normalizes_valid_quality_evidence_into_a_detached_value(self):
        """Catches a missing public normalizer or one that aliases caller-owned nested values."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.make_quality_lesson(root)
            normalizer = getattr(lesson_quality, "normalize_quality_evidence", None)
            self.assertIsNotNone(normalizer)
            normalized = normalizer(manifest["quality_evidence"], manifest["learning_objectives"])
            self.assertEqual(manifest["quality_evidence"], normalized)
            normalized["objectives"][0]["text"] = "changed"
            self.assertEqual("Estimate yield from a bond price.", manifest["quality_evidence"]["objectives"][0]["text"])

    def test_reports_normalized_quality_metrics_for_a_valid_lesson(self):
        """Catches validating evidence without exposing the metrics consumed by later gates."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.make_quality_lesson(root)
            report = lesson_quality.audit_lesson(root, manifest)

        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual("normal", report["metrics"].get("session_depth"))
        self.assertEqual(35, report["metrics"].get("planned_minutes"))
        self.assertEqual(25, report["metrics"].get("reading_minutes"))
        self.assertEqual(10, report["metrics"].get("response_minutes"))
        self.assertEqual(2, report["metrics"].get("concept_count"))
        self.assertEqual(3, report["metrics"].get("response_count"))
        self.assertAlmostEqual(10 / 35, report["metrics"].get("response_share", -1))
        self.assertGreaterEqual(report["metrics"].get("html_fraction", -1), 0.90)

    def test_accepts_inclusive_depth_and_response_boundaries(self):
        """Catches off-by-one duration, response-share, or response-count limits."""
        cases = (
            ("light", 12, 2), ("light", 20, 3),
            ("normal", 30, 3), ("normal", 45, 5),
            ("deep", 60, 5), ("deep", 90, 8),
        )
        for depth, planned_minutes, response_count in cases:
            with self.subTest(depth=depth, planned_minutes=planned_minutes, response_count=response_count), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = self.make_quality_lesson(root)
                evidence = manifest["quality_evidence"]
                evidence.update({
                    "session_depth": depth,
                    "planned_minutes": planned_minutes,
                    "reading_minutes": planned_minutes - 1,
                    "response_minutes": planned_minutes * 0.35,
                })
                self.set_quality_questions(root, manifest, [f"q-{index}" for index in range(response_count)])
                report = lesson_quality.audit_lesson(root, manifest)
            self.assertTrue(report["valid"], report["errors"])

    def test_warns_below_target_and_requires_a_justification(self):
        """Catches treating the target reading band as optional without recorded rationale."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.make_quality_lesson(root, repetitions=6)
            report = lesson_quality.audit_lesson(root, manifest)
            self.assertGreaterEqual(report["metrics"]["markdown_reading_units"], 1800)
            self.assertLess(report["metrics"]["markdown_reading_units"], 2500)
            self.assertIn("below_target_reading", {item["code"] for item in report["warnings"]})
            self.assertIn("invalid_quality_evidence", {item["code"] for item in report["errors"]})

            manifest["quality_evidence"]["below_target_justification"] = "A concise bridge lesson follows prior guided practice."
            justified = lesson_quality.audit_lesson(root, manifest)
            self.assertTrue(justified["valid"], justified["errors"])
            self.assertIn("below_target_reading", {item["code"] for item in justified["warnings"]})

    def test_rejects_missing_declared_content_and_undeclared_required_questions(self):
        """Catches evidence drifting from canonical headings, HTML IDs, or lesson-data responses."""
        mutations = {
            "missing heading": lambda root, manifest: manifest["quality_evidence"]["reading_sections"][0].update({"markdown_heading": "Missing heading"}),
            "missing HTML ID": lambda root, manifest: manifest["quality_evidence"]["worked_examples"][0].update({"html_id": "missing-html-id"}),
            "undeclared required question": lambda root, manifest: manifest["quality_evidence"]["response_question_ids"].pop(),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest = self.make_quality_lesson(root)
                mutate(root, manifest)
                self.assert_audit_is_read_only(root, manifest, "artifact_correspondence")

    def test_rejects_normal_lesson_with_shallow_instructional_reading(self):
        """Catches removing the normal-depth floor from a timed lesson audit."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.make_lesson(root)

            report = lesson_quality.audit_lesson(root, manifest)

        self.assertFalse(report["valid"])
        self.assertIn(
            "insufficient_reading_depth",
            {item["code"] for item in report["errors"]},
        )
        self.assertLess(report["metrics"]["markdown_reading_units"], 1800)

    def test_returns_structured_error_when_required_lesson_artifact_is_missing(self):
        """Catches an audit raising instead of reporting a missing lesson file."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = self.make_lesson(root, include_markdown=False)

            report = lesson_quality.audit_lesson(root, manifest)

        self.assertFalse(report["valid"])
        self.assertIn("missing_artifact", {item["code"] for item in report["errors"]})

    def test_rejects_light_and_deep_lessons_below_their_reading_floors(self):
        """Catches applying the reading-depth floor only to normal lessons."""
        for minutes, text in ((12, "lesson " * 299), (60, "lesson " * 1749)):
            with self.subTest(minutes=minutes), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                report = lesson_quality.audit_lesson(root, self.make_lesson(root, planned_minutes=minutes, markdown_text=text))
            self.assertIn("insufficient_reading_depth", {item["code"] for item in report["errors"]})

    def test_rejects_missing_malformed_and_out_of_band_duration_evidence(self):
        """Catches accepting a duration that cannot identify a depth band."""
        for minutes in (None, True, "35", float("nan"), float("inf"), 25):
            with self.subTest(minutes=minutes), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                report = lesson_quality.audit_lesson(root, self.make_lesson(root, planned_minutes=minutes))
            self.assertIn("invalid_time_evidence", {item["code"] for item in report["errors"]})

    def test_excludes_html_answer_key_and_source_sections_from_reading_metric(self):
        """Catches answer-key or source prose inflating the learner-facing HTML metric."""
        html = "<main><p>Visible prose.</p><section><h2>Answer key</h2><p>" + "answer " * 1000 + "</p></section><section><h2>Sources</h2><p>" + "source " * 1000 + "</p></section></main>"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = lesson_quality.audit_lesson(root, self.make_lesson(root, html_text=html))
        self.assertEqual(4, report["metrics"]["html_reading_units"])

    def test_excludes_tilde_and_indented_markdown_code_from_reading_metric(self):
        """Catches code examples inflating the instructional Markdown reading metric."""
        markdown = "Visible prose.\n\n~~~python\nhidden_code " + "hidden_code " * 300 + "\n~~~\n\n    indented_code " + "indented_code " * 300
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = lesson_quality.audit_lesson(root, self.make_lesson(root, markdown_text=markdown))
        self.assertEqual(4, report["metrics"]["markdown_reading_units"])

    def test_excludes_named_html_answer_and_source_containers_without_headings(self):
        """Catches named support containers reaching the learner-facing HTML metric."""
        html = "<main><p>Visible prose.</p><div class='answer-key'>" + "answer " * 1000 + "</div><div id='sources'>" + "source " * 1000 + "</div></main>"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = lesson_quality.audit_lesson(root, self.make_lesson(root, html_text=html))
        self.assertEqual(4, report["metrics"]["html_reading_units"])

    def test_excludes_named_semantic_support_containers_without_headings(self):
        """Catches section and aside support containers reaching the HTML metric."""
        html = "<main><p>Visible prose.</p><section class='answer-key'><p>" + "answer " * 500 + "</p><aside><p>" + "nested_answer " * 500 + "</p></aside></section><aside id='sources'><p>" + "source " * 500 + "</p><section><p>" + "nested_source " * 500 + "</p></section></aside><p>Remaining prose.</p></main>"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = lesson_quality.audit_lesson(root, self.make_lesson(root, html_text=html))
        self.assertEqual(8, report["metrics"]["html_reading_units"])
    def test_excludes_fences_with_longer_matching_character_closers(self):
        """Catches requiring a fence closer to be exactly as long as its opener."""
        for opener, closer in (("```", "````"), ("~~~", "~~~~")):
            with self.subTest(opener=opener), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                markdown = f"Visible prose.\n\n{opener}python\nhidden_code {'hidden_code ' * 300}\n{closer}\n"
                report = lesson_quality.audit_lesson(root, self.make_lesson(root, markdown_text=markdown))
            self.assertEqual(4, report["metrics"]["markdown_reading_units"])

    def test_does_not_treat_shorter_or_mixed_fences_as_closers(self):
        """Catches ending a CommonMark fence with an invalid closer."""
        for opener, invalid_closer in (("```", "``"), ("```", "~~~"), ("~~~", "~~"), ("~~~", "```")):
            with self.subTest(opener=opener, invalid_closer=invalid_closer), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                markdown = f"Visible prose.\n\n{opener}\nhidden_code {'hidden_code ' * 300}\n{invalid_closer}\ntrailing_code {'trailing_code ' * 300}"
                report = lesson_quality.audit_lesson(root, self.make_lesson(root, markdown_text=markdown))
            self.assertEqual(4, report["metrics"]["markdown_reading_units"])
    def test_excludes_linked_navigation_labels_before_counting_markdown(self):
        """Catches normalizing navigation links too late for their labels to be excluded."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = lesson_quality.audit_lesson(root, self.make_lesson(root, markdown_text="[Previous](previous.html)\n[Next](next.html)\n\nVisible prose."))
        self.assertEqual(4, report["metrics"]["markdown_reading_units"])

    def test_returns_structured_error_for_escaping_lesson_directory(self):
        """Catches a traversal path escaping the candidate course root during audit."""
        with tempfile.TemporaryDirectory() as temporary:
            report = lesson_quality.audit_lesson(Path(temporary), {"lesson_directory": "../outside", "planned_minutes": 35})
        self.assertIn("invalid_artifact_path", {item["code"] for item in report["errors"]})

    def test_returns_structured_error_for_invalid_utf8_and_binary_controls(self):
        """Catches non-text artifacts being counted as instructional text instead of rejected."""
        for content, code in ((b"\xff", "unreadable_artifact"), (b"Visible\x01prose", "non_text_artifact")):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); manifest = self.make_lesson(root)
                (root / manifest["lesson_directory"] / "lesson.md").write_bytes(content)
                report = lesson_quality.audit_lesson(root, manifest)
            self.assertIn(code, {item["code"] for item in report["errors"]})

    def test_allows_normal_whitespace_in_text_artifacts(self):
        """Catches treating ordinary whitespace as binary data."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = lesson_quality.audit_lesson(root, self.make_lesson(root, markdown_text="Visible\tprose\r\nwith ordinary whitespace."))
        self.assertNotIn("non_text_artifact", {item["code"] for item in report["errors"]})

if __name__ == "__main__":
    unittest.main()
