"""AI-powered query generator using Claude to extract keywords from research descriptions."""

import json
import anthropic

from src.models import DatabaseSource


class QueryGenerator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-haiku-4-5-20251001"

    def generate_queries(self, description: str, databases: list[DatabaseSource]) -> dict:
        """
        Analyze a research description and generate optimized search queries.

        Returns:
            {
                "research_summary": "연구 주제 요약",
                "keywords": ["keyword1", "keyword2", ...],
                "queries": [
                    {"query": "search query string", "purpose": "이 쿼리의 목적"},
                    ...
                ]
            }
        """
        db_names = ", ".join(db.value for db in databases)

        prompt = f"""당신은 학술 논문 검색 전문가입니다. 사용자가 설명한 연구 주제를 분석하여,
학술 DB에서 관련 논문을 효과적으로 찾기 위한 검색 전략을 생성해주세요.

## 사용자의 연구 설명
{description}

## 검색 대상 DB
{db_names}

## 요청사항
아래 JSON 형식으로 정확히 응답해주세요. JSON만 출력하고 다른 텍스트는 출력하지 마세요.

{{
  "research_summary": "연구 주제를 한 문장으로 요약 (한국어)",
  "keywords": [
    "핵심 영문 키워드 8~12개를 배열로"
  ],
  "queries": [
    {{
      "query": "학술 DB 검색에 최적화된 영문 쿼리 (OR, AND 등 불리언 연산자 사용 가능)",
      "purpose": "이 쿼리가 찾으려는 논문의 범위 설명 (한국어)"
    }}
  ]
}}

## 쿼리 생성 규칙
1. 3~5개의 서로 다른 관점의 쿼리를 생성하세요
2. 첫 번째 쿼리는 가장 직접적이고 구체적인 것
3. 이후 쿼리는 점차 범위를 넓혀가며 관련 연구를 커버
4. 각 쿼리는 학술 DB API 검색에 적합하게 작성 (특수문자 최소화)
5. 키워드는 영문으로, 설명은 한국어로 작성
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            result = {
                "research_summary": "파싱 실패 - 키워드 직접 추출",
                "keywords": self._fallback_keywords(description),
                "queries": [{"query": description, "purpose": "원문 그대로 검색"}],
            }

        return result

    def _fallback_keywords(self, description: str) -> list[str]:
        """Fallback: extract simple keywords from description."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"Extract 8-10 English academic keywords from this text. Return only a comma-separated list, nothing else:\n\n{description}",
            }],
        )
        text = response.content[0].text.strip()
        return [kw.strip() for kw in text.split(",") if kw.strip()]
