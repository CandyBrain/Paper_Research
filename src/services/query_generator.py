"""AI-powered query generator and relevance ranker using Claude."""

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

        prompt = f"""당신은 학술 논문 검색 전문가입니다. 사용자의 연구 설명을 분석하여,
학술 DB API(OpenAlex, Semantic Scholar, PubMed 등)에서 **정확히 관련된** 논문만 찾을 수 있는
검색 쿼리를 생성해주세요.

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
      "query": "검색 쿼리 문자열",
      "purpose": "이 쿼리가 찾으려는 논문의 범위 설명 (한국어)"
    }}
  ]
}}

## 쿼리 생성 규칙 (매우 중요)

### 정확도 최우선
1. **모든 쿼리가 사용자의 핵심 연구 주제에 직접적으로 관련**되어야 합니다
2. 범위를 넓히는 것보다 **정확하게 맞는 논문을 찾는 것**이 훨씬 중요합니다
3. 사용자가 언급한 핵심 개념을 반드시 포함하세요

### 쿼리 작성 방법
1. 3~5개의 쿼리를 생성하되, 모두 핵심 주제와 직접 관련되어야 합니다
2. 각 쿼리는 **같은 주제를 다른 학술 용어로 표현**한 것이어야 합니다 (범위 확장이 아님)
3. 쿼리는 **간결하게** 작성하세요 — 3~6개 핵심 단어 조합이 최적입니다
4. 복잡한 Boolean 연산(괄호 중첩, 긴 OR 체인)은 피하세요 — 학술 DB API에서 잘 작동하지 않습니다
5. 간단한 형태만 사용: "keyword1 keyword2 keyword3" 또는 "keyword1 AND keyword2"

### 나쁜 쿼리 예시 (하지 마세요)
- "(growth chamber OR plant chamber) AND (environmental variability OR chamber difference OR inter-chamber difference) AND (statistical validation OR statistical comparison)"
  → 너무 길고 복잡하며, API가 제대로 처리 못함
- "plant biology experiment" → 너무 일반적, 관련 없는 논문이 수천 개 나옴

### 좋은 쿼리 예시
- "growth chamber reproducibility inter-chamber variability"
- "controlled environment chamber replication experiment"
- "phytotron environmental uniformity validation"

### 키워드 선정
- 사용자의 연구에서 **고유하고 구체적인 용어**를 추출하세요
- 너무 일반적인 단어(plant, study, analysis, method)만으로 쿼리를 구성하지 마세요
- 해당 분야의 **전문 학술 용어**를 사용하세요
"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
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

    def rerank_papers(
        self,
        description: str,
        papers: list[dict],
        top_n: int = 30,
    ) -> list[dict]:
        """
        Use Claude to score and rerank papers by relevance to the user's description.

        Args:
            description: User's original research description.
            papers: List of paper dicts with at least 'title' and optionally 'abstract'.
            top_n: Max number of papers to return.

        Returns:
            List of {"index": int, "score": int, "reason": str} sorted by score desc.
        """
        if not papers:
            return []

        # Build paper list string (limit to avoid token overflow)
        max_papers = min(len(papers), 80)
        paper_lines = []
        for i in range(max_papers):
            p = papers[i]
            title = p.get("title", "Untitled")
            abstract = (p.get("abstract") or "")[:200]
            line = f"[{i}] {title}"
            if abstract:
                line += f" | {abstract}"
            paper_lines.append(line)

        papers_text = "\n".join(paper_lines)

        prompt = f"""당신은 학술 논문 관련도 평가 전문가입니다.

## 사용자의 연구 설명
{description}

## 검색된 논문 목록
{papers_text}

## 작업
위 논문 목록에서 사용자의 연구 설명과 **직접적으로 관련된 논문만** 선택하고 관련도 점수를 매기세요.

## 평가 기준
- **5점**: 사용자의 연구 주제와 직접적으로 일치하는 핵심 논문
- **4점**: 연구 주제에 매우 밀접하게 관련된 논문
- **3점**: 관련은 있지만 직접적이지는 않은 논문
- **2점**: 간접적으로 참고할 수 있는 논문
- **1점**: 거의 관련 없음

## 응답 형식
JSON 배열만 출력하세요. **3점 이상인 논문만** 포함하세요. 점수 내림차순으로 정렬하세요.

[
  {{"index": 0, "score": 5, "reason": "관련 이유 (한국어, 1문장)"}},
  {{"index": 3, "score": 4, "reason": "관련 이유"}}
]

JSON만 출력하고 다른 텍스트는 출력하지 마세요.
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            rankings = json.loads(text)
            # Ensure sorted by score desc
            rankings.sort(key=lambda x: x.get("score", 0), reverse=True)
            return rankings[:top_n]
        except Exception:
            # On failure, return all papers without reranking
            return []

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
