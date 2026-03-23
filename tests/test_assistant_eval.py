import unittest

from fastapi.testclient import TestClient

from app.main import app


class AssistantEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def ask(self, message: str, session_id: str) -> dict:
        response = self.client.post(
            "/api/chat",
            json={"message": message, "session_id": session_id},
            headers={"Origin": "http://localhost:5174"},
        )
        self.assertEqual(response.status_code, 200, msg=message)
        return response.json()

    def assertContains(self, text: str, expected: list[str], message: str) -> None:
        lowered = text.lower()
        for item in expected:
            self.assertIn(item.lower(), lowered, msg=message)

    def assertNotContains(self, text: str, forbidden: list[str], message: str) -> None:
        lowered = text.lower()
        for item in forbidden:
            self.assertNotIn(item.lower(), lowered, msg=message)

    def test_direct_and_summary_queries(self):
        cases = [
            {
                "message": "What is Alba focused on right now?",
                "expected": ["fullstack", "artificial intelligence", "data"],
            },
            {
                "message": "What is Alba doing at Siemens right now?",
                "expected": ["siemens", "backend apis", "internal applications"],
            },
            {
                "message": "What projects has Alba built?",
                "expected": ["8 portfolio projects", "ai knowledge assistant", "pomodoro pokémon"],
            },
            {
                "message": "Which project is related to LangChain?",
                "expected": ["ai knowledge assistant"],
            },
            {
                "message": "What certifications does Alba have?",
                "expected": ["completed", "currently preparing", "cloud practitioner", "data engineer"],
                "forbidden": ["two certifications"],
            },
            {
                "message": "How can I contact Alba?",
                "expected": ["github.com/albamdls", "linkedin.com/in/alba-mora-de-la-sen"],
            },
            {
                "message": "Does Alba use Python?",
                "expected": ["yes", "python"],
                "section": "stack",
            },
            {
                "message": "What backend technologies does Alba work with?",
                "expected": ["java", "python", "spring boot", "django", "flask"],
                "section": "stack",
            },
        ]

        for idx, case in enumerate(cases):
            with self.subTest(case=case["message"]):
                payload = self.ask(case["message"], f"direct-{idx}")
                self.assertContains(payload["answer"], case["expected"], case["message"])
                self.assertNotContains(payload["answer"], case.get("forbidden", []), case["message"])
                if "section" in case:
                    self.assertEqual(payload["section_hint"], case["section"], case["message"])

    def test_trap_and_out_of_scope_queries(self):
        cases = [
            {
                "message": "Does Alba know Go?",
                "expected": ["not included", "go"],
            },
            {
                "message": "Has Alba worked with Azure?",
                "expected": ["not included", "azure"],
            },
            {
                "message": "What's the weather in Madrid today?",
                "expected": ["only help with questions about alba mora de la sen"],
            },
            {
                "message": "Compare React vs Vue in general.",
                "expected": ["only help with questions about alba mora de la sen"],
            },
        ]

        for idx, case in enumerate(cases):
            with self.subTest(case=case["message"]):
                payload = self.ask(case["message"], f"scope-{idx}")
                self.assertContains(payload["answer"], case["expected"], case["message"])

    def test_spanish_queries(self):
        cases = [
            {
                "message": "¿En qué está enfocada Alba ahora mismo?",
                "expected": ["desarrollo fullstack", "inteligencia artificial", "datos"],
            },
            {
                "message": "¿Qué certificaciones tiene Alba?",
                "expected": ["certificación completada", "en progreso", "cloud practitioner", "data engineer"],
            },
            {
                "message": "¿Cómo puedo contactar con Alba?",
                "expected": ["github", "linkedin"],
            },
        ]

        for idx, case in enumerate(cases):
            with self.subTest(case=case["message"]):
                payload = self.ask(case["message"], f"es-{idx}")
                self.assertContains(payload["answer"], case["expected"], case["message"])

    def test_follow_up_resolution_for_current_role(self):
        session = "followup-current-role"
        self.ask("Tell me about Alba's experience.", session)
        second = self.ask("What about her current role?", session)
        third = self.ask("What does she use there?", session)
        fourth = self.ask("Is that current or past?", session)
        fifth = self.ask("Tell me more.", session)

        self.assertContains(second["answer"], ["siemens", "backend apis"], "current role follow-up")
        self.assertContains(third["answer"], ["python", "flask", "docker"], "current role tech follow-up")
        self.assertContains(fourth["answer"], ["current"], "status follow-up")
        self.assertContains(fifth["answer"], ["software developer intern", "siemens"], "tell me more follow-up")

    def test_follow_up_resolution_for_stack(self):
        session = "followup-stack"
        first = self.ask("What technologies does Alba use?", session)
        second = self.ask("And her stack?", session)

        self.assertContains(first["answer"], ["python", "react", "docker"], "stack summary")
        self.assertContains(second["answer"], ["python", "react", "docker"], "stack follow-up")

    def test_style_requests(self):
        bullet = self.ask("Give me only bullet points about Alba's current role.", "style-bullets")
        short = self.ask("Keep it under 20 words: what is Alba focused on?", "style-short")
        english = self.ask("Answer in English: what certifications does Alba have?", "style-english")
        spanish = self.ask("Answer in Spanish: what does Alba do?", "style-spanish")

        self.assertContains(bullet["answer"], ["•", "python", "docker"], "bullet style")
        self.assertLessEqual(len(short["answer"].split()), 20, "very short style")
        self.assertContains(english["answer"], ["completed", "currently preparing"], "english style")
        self.assertContains(spanish["answer"], ["alba"], "spanish override")


if __name__ == "__main__":
    unittest.main()

