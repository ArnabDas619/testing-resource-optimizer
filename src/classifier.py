# src/classifier.py
import os
import json
from src.config import ROLE_KEYWORDS

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

# Import corrections loader with a safe fallback
try:
    from src.database import get_recent_corrections
except ImportError:
    def get_recent_corrections(n=5):
        return []


class TaskClassifier:
    def __init__(self, provider="Keyword Only", skill_list: list[str] | None = None):
        self.provider = provider
        self.gemini_model = None
        self.openai_client = None
        # Flat list of known skills from the tester matrix (used to constrain LLM output)
        self.skill_list = skill_list or []

        if self.provider == "Gemini" and _GENAI_AVAILABLE:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                # Use gemini-2.0-flash (latest)
                self.gemini_model = genai.GenerativeModel("gemini-2.0-flash")
            else:
                self.provider = "Keyword Only"

        elif self.provider == "OpenAI" and _OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
            else:
                self.provider = "Keyword Only"

    # ------------------------------------------------------------------
    # Keyword fallback
    # ------------------------------------------------------------------
    def classify_keyword(self, task_description: str) -> dict:
        """Keyword-matching against ROLE_KEYWORDS config."""
        text = task_description.lower()
        matched_skills = []

        # Try to match against the known skill list first (most specific)
        for skill in self.skill_list:
            if skill.lower() in text:
                matched_skills.append(skill)

        # Fall back to config keyword groups
        if not matched_skills:
            for role, keywords in ROLE_KEYWORDS.items():
                if any(kw.lower() in text for kw in keywords):
                    matched_skills.append(role)

        if not matched_skills:
            matched_skills = ["Manual Testing"]

        return {
            "skills": matched_skills,
            "confidence": "Medium (Keyword)",
            "reasoning": f"Matched keywords for: {', '.join(matched_skills)}",
        }

    # ------------------------------------------------------------------
    # LLM classification with few-shot corrections
    # ------------------------------------------------------------------
    def _build_few_shot_block(self) -> str:
        corrections = get_recent_corrections(5)
        if not corrections:
            return ""
        lines = ["### Historical PM Corrections (use as guidance):", ""]
        for c in corrections:
            lines.append(
                f"- Task: \"{c.get('task_description', '')}\" → "
                f"Correct Skills: \"{c.get('required_skills_original', '')}\" → "
                f"Correct Tester: \"{c.get('corrected_tester', '')}\""
            )
        return "\n".join(lines)

    def classify_llm(self, task_description: str) -> dict:
        """Uses the configured LLM (Gemini 2.0 Flash or GPT-4o-mini)."""
        skill_list_str = ", ".join(self.skill_list) if self.skill_list else \
            "Manual Testing, Automation, Selenium, Cypress, Playwright, Performance Testing, Security Testing, Accessibility, WCAG Audit, API Testing, SQL Testing"

        few_shot = self._build_few_shot_block()

        prompt = f"""You are a QA staffing assistant. Analyse the following task description and 
identify which skills from the provided Skill Matrix are required.

Available Skills (from Tester Skill Matrix):
{skill_list_str}

{few_shot}

Task Description: "{task_description}"

Return ONLY a JSON object with this exact structure (no markdown, no code fences):
{{
    "skills": ["Skill1", "Skill2"],
    "confidence": "High",
    "reasoning": "One-sentence explanation."
}}

Rules:
- Only include skills that APPEAR in the Available Skills list above.
- Include 1-4 skills maximum.
- If unsure, return ["Manual Testing"].
"""
        try:
            if self.provider == "Gemini" and self.gemini_model:
                response = self.gemini_model.generate_content(prompt)
                resp_text = (response.text.strip()
                             .removeprefix("```json").removeprefix("```")
                             .removesuffix("```").strip())
                result = json.loads(resp_text)
                return result

            elif self.provider == "OpenAI" and self.openai_client:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )
                return json.loads(response.choices[0].message.content)

        except Exception as e:
            fallback = self.classify_keyword(task_description)
            fallback["reasoning"] += f" (LLM Error: {e})"
            return fallback

        return self.classify_keyword(task_description)

    # ------------------------------------------------------------------
    def classify(self, task_description: str) -> dict:
        if self.provider == "Keyword Only":
            return self.classify_keyword(task_description)
        return self.classify_llm(task_description)
