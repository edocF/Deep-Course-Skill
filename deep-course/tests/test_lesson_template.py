"""Lesson artifact contracts; JavaScript runs in Node's standard-library VM."""
import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "lesson-template" / "lesson.html"
sys.path.insert(0, str(ROOT / "scripts"))
import course_state


class LessonHTML(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.scripts = {}
        self.current = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if tag == "script":
            self.current = attrs.get("id", "runtime")
            self.scripts[self.current] = ""

    def handle_data(self, value):
        if self.current is not None:
            self.scripts[self.current] += value

    def handle_endtag(self, tag):
        if tag == "script":
            self.current = None


class LessonTemplateTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(TEMPLATE.is_file(), "self-contained lesson template is missing")
        self.html = LessonHTML(TEMPLATE.read_text(encoding="utf-8"))
        self.data = json.loads(self.html.scripts["lesson-data"])

    def run_js(self, code):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node is required to run real lesson JavaScript")
        program = "const vm=require('node:vm'); const ctx={}; vm.createContext(ctx);"
        program += "vm.runInContext(" + json.dumps(self.html.scripts["lesson-core"]) + ",ctx);"
        program += "const api=ctx.Lesson; const data=" + json.dumps(self.data) + ";"
        program += code
        result = subprocess.run([node, "-e", program], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def test_semantic_navigation_and_resources_are_local(self):
        tags = [tag for tag, _ in self.html.elements]
        self.assertIn("main", tags)
        self.assertIn("nav", tags)
        ids = [attrs["id"] for _, attrs in self.html.elements if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for section in ("retrieval", "concepts", "visual", "case", "exercises", "recall"):
            self.assertIn(section, ids)
        self.assertTrue(any("aria-live" in attrs for _, attrs in self.html.elements))
        for tag, attrs in self.html.elements:
            for key in ("src", "href"):
                if key in attrs:
                    self.assertTrue(attrs[key].startswith("#"), (tag, attrs))
            if tag == "a" and attrs.get("href", "").startswith("#"):
                self.assertIn(attrs["href"][1:], ids)

    def test_example_questions_have_unique_ids_and_authored_feedback(self):
        questions = self.data["questions"]
        self.assertEqual(len(questions), len({q["question_id"] for q in questions}))
        self.assertIn("open", {q["type"] for q in questions})
        for question in questions:
            if question["type"] == "objective":
                self.assertGreaterEqual(len(question["options"]), 2)
                for option in question["options"]:
                    self.assertTrue(option["feedback"].strip())
        self.assertTrue(self.run_js("console.log(JSON.stringify(api.validate(data)));"))

    def test_duplicate_and_unsafe_ids_are_rejected(self):
        for mutation in ("data.questions.push(data.questions[0]);",
                         "data.questions[0].question_id='';",
                         "data.questions[0].question_id='bad id';"):
            result = self.run_js(mutation + "try{api.validate(data);console.log(false)}catch(e){console.log(true)}")
            self.assertTrue(result)

    def test_objective_feedback_is_authored_and_open_answers_are_ungraded(self):
        result = self.run_js("const q=data.questions.find(q=>q.type==='objective');"
            "console.log(JSON.stringify(q.options.map(o=>api.feedback(q,o.value))));")
        question = next(q for q in self.data["questions"] if q["type"] == "objective")
        self.assertEqual([o["feedback"] for o in question["options"]], result)
        self.assertIsNone(self.run_js("console.log(JSON.stringify(api.feedback(data.questions.find(q=>q.type==='open'),'arbitrary prose')));"))

    def test_actual_export_round_trips_through_append_attempt_without_mastery(self):
        payload = self.run_js("const answers={}; for(const q of data.questions) answers[q.question_id]=q.type==='objective'?q.options[0].value:'My reasoning: <text> 中文';"
            "console.log(JSON.stringify(api.buildResponse(data,answers,'2026-09-14T02:00:00.000Z','attempt-test')));")
        self.assertEqual({"schema_version", "course_id", "lesson_id", "exported_at", "submitted_at", "attempt_id", "responses"}, set(payload))
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual("2026-09-14T02:00:00.000Z", payload["exported_at"])
        self.assertEqual(len(self.data["questions"]), len(payload["responses"]))
        for response in payload["responses"]:
            self.assertEqual({"question_id", "knowledge_ids", "answer"}, set(response))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "course"
            course_state.init_course(root, payload["course_id"], "Template test", payload["exported_at"])
            path = root / "curriculum.json"
            curriculum = json.loads(path.read_text())
            ids = {kid for q in self.data["questions"] for kid in q["knowledge_ids"]}
            curriculum["knowledge_nodes"] = [{"knowledge_id": kid, "title": kid, "prerequisite_ids": []} for kid in sorted(ids)]
            course_state.atomic_write_json(path, curriculum)
            before = (root / "progress.json").read_bytes()
            course_state.append_attempt(root, payload)
            self.assertEqual(payload, json.loads((root / "attempts.jsonl").read_text(encoding="utf-8")))
            self.assertEqual(before, (root / "progress.json").read_bytes())

    def test_blank_answers_are_omitted_and_unknown_options_rejected(self):
        payload = self.run_js("console.log(JSON.stringify(api.buildResponse(data,{},'2026-09-14T02:00:00Z','empty')));")
        self.assertEqual([], payload["responses"])
        self.assertTrue(self.run_js("const q=data.questions.find(q=>q.type==='objective'); try{api.buildResponse(data,{[q.question_id]:'unknown'},'2026-09-14T02:00:00Z','bad');console.log(false)}catch(e){console.log(true)}"))

    def test_download_uses_json_blob_and_releases_temporary_link(self):
        result = self.run_js("""
            let blob, clicked=false, removed=false, appended=false, revoked=false;
            const link={click(){clicked=true},remove(){removed=true}};
            ctx.Blob=Blob;
            ctx.document={createElement(tag){if(tag!=='a')throw Error('Expected download link');return link},body:{append(item){if(item!==link)throw Error('Unexpected link');appended=true}}};
            ctx.URL={createObjectURL(value){blob=value;return 'blob:download-test'},revokeObjectURL(url){if(url!=='blob:download-test')throw Error('Wrong URL');revoked=true}};
            ctx.setTimeout=fn=>fn();
            const payload=api.buildResponse(data,{'before-reading':'My own words'},'2026-09-14T02:00:00Z','download-test');
            api.downloadResponse(payload);
            blob.text().then(text=>console.log(JSON.stringify({payload:JSON.parse(text),type:blob.type,filename:link.download,href:link.href,clicked,removed,appended,revoked})));
        """)
        self.assertEqual("application/json", result["type"])
        self.assertEqual("deep-course-response-v1.json", result["filename"])
        self.assertEqual("blob:download-test", result["href"])
        self.assertEqual([{"question_id": "before-reading", "knowledge_ids": ["retrieval"], "answer": "My own words"}], result["payload"]["responses"])
        for effect in ("clicked", "removed", "appended", "revoked"):
            self.assertTrue(result[effect], effect)

    def test_rendered_controls_keep_distinct_ids_and_correct_label_targets(self):
        # Accepted IDs used to collide across both control types and options.
        objective = next(q for q in self.data["questions"] if q["type"] == "objective")
        objective["question_id"] = "practice"
        objective["options"][0]["value"] = "reason"
        objective["options"][1]["value"] = "more-reason"
        open_question = next(q for q in self.data["questions"] if q["type"] == "open")
        open_question.update(question_id="practice-reason", section="exercises")
        other = json.loads(json.dumps(objective))
        other["question_id"] = "practice-more"
        other["options"][1]["value"] = "other"
        self.data["questions"] = [objective, open_question, other]
        # Only the DOM boundary is simulated; rendering and handlers are the
        # production scripts. ID lookup uses first-match document semantics.
        setup = """
            const elements=[];
            class Element {
                constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.listeners={};this.value='';elements.push(this)}
                append(...children){this.children.push(...children)}
                setAttribute(name,value){this.attributes[name]=value}
                addEventListener(name,handler){this.listeners[name]=handler}
                get control(){return this.htmlFor ? elements.find(e=>e.id===this.htmlFor) : this.children.find(e=>['input','textarea'].includes(e.tag))}
                click(){if(this.tag==='label')ctx.document.activeElement=this.control;this.listeners.click?.()}
                remove(){}
            }
            ctx.document={createElement:tag=>new Element(tag),getElementById:id=>elements.find(e=>e.id===id),querySelector:selector=>elements.find(e=>selector===`[data-questions="${e.attributes['data-questions']}"]`)};
        """
        setup += "for(const [tag,attributes] of " + json.dumps(self.html.elements) + ") {const element=new Element(tag);Object.assign(element.attributes,attributes);if(attributes.id)element.id=attributes.id;}"
        setup += "ctx.document.getElementById('lesson-data').textContent=JSON.stringify(data);"
        setup += "vm.runInContext(" + json.dumps(self.html.scripts["lesson-ui"]) + ",ctx);"
        result = self.run_js(setup + """
            const controls=elements.filter(e=>['input','textarea'].includes(e.tag));
            const labels=elements.filter(e=>e.tag==='label' && e.control && controls.includes(e.control));
            const openLabel=labels.find(e=>e.htmlFor);
            openLabel.click();
            const ids=elements.filter(e=>e.id).map(e=>e.id);
            console.log(JSON.stringify({valid:api.validate(data),ids,controls:controls.map(e=>({tag:e.tag,id:e.id,name:e.name})),labelTargets:labels.map(e=>e.control.name),focusedTag:ctx.document.activeElement.tag,focusedName:ctx.document.activeElement.name,error:ctx.document.getElementById('lesson-error').textContent||''}));
        """)
        self.assertTrue(result["valid"])
        self.assertEqual("", result["error"])
        with self.subTest(contract="unique IDs across every rendered element"):
            self.assertEqual(len(result["ids"]), len(set(result["ids"])), result["controls"])
        with self.subTest(contract="open label activates its textarea"):
            self.assertEqual(("textarea", "practice-reason"), (result["focusedTag"], result["focusedName"]))
        with self.subTest(contract="all labels identify their intended controls"):
            self.assertEqual(["practice", "practice", "practice-reason", "practice-more", "practice-more"], result["labelTargets"])


if __name__ == "__main__":
    unittest.main()
