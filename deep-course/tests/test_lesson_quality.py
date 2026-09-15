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
    def make_lesson(self, root, *, lesson_directory="lessons/bond-yield", include_markdown=True):
        lesson = root / lesson_directory
        lesson.mkdir(parents=True, exist_ok=True)
        if include_markdown:
            (lesson / "lesson.md").write_text(INSTRUCTIONAL_TEXT, encoding="utf-8")
        (lesson / "lesson.html").write_text(
            """<!doctype html><html><head><style>.hidden { display: none; }</style></head>
            <body><nav>Previous Next</nav><main><h1>Bond yield</h1><p>Short lesson shell.</p>
            <form><label for=answer>Explain your estimate</label><textarea id=answer></textarea>
            <button>Check answer</button></form><script>const answer = 'not reading';</script>
            </main></body></html>""",
            encoding="utf-8",
        )
        for name in ("exercises.md", "answers.md", "sources.md", "state.json"):
            (lesson / name).write_text("artifact", encoding="utf-8")
        return {
            "lesson_directory": lesson_directory,
            "planned_minutes": 35,
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


if __name__ == "__main__":
    unittest.main()
