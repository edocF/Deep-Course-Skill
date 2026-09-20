"""Regression coverage for the lesson reading-depth gate."""
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
