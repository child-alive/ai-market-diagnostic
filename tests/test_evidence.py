"""引用页面证据预审测试（纯本地，不访问网络）。"""
from __future__ import annotations

from datetime import datetime, timezone

from src.models import AIAnswer, EvidenceStatus, SourceAnnotation
from src.pipeline.evidence import PageDocument, _visible_text, verify_answers


def make_answer(**kwargs) -> AIAnswer:
    values = {
        "question_id": "q-evidence",
        "provider": "openai",
        "model": "gpt-test",
        "raw_text": "Deli está disponible en México.",
        "retrieved_at": datetime.now(timezone.utc),
        "is_mock": False,
        "search_grounded": True,
        "source_urls": ["https://example.com/deli"],
    }
    values.update(kwargs)
    return AIAnswer(**values)


def test_visible_text_removes_script_and_extracts_title() -> None:
    text, title = _visible_text(
        "<html><head><title>Deli México</title><script>bad()</script></head>"
        "<body><p>Deli está disponible en México.</p></body></html>"
    )

    assert title == "Deli México"
    assert "Deli está disponible" in text
    assert "bad()" not in text


def test_native_annotation_is_checked_against_its_mapped_page() -> None:
    answer = make_answer(
        source_annotations=[
            SourceAnnotation(
                url="https://example.com/deli",
                title="Catálogo Deli",
                start_index=0,
                end_index=31,
                cited_text="Deli está disponible en México.",
            )
        ]
    )

    reviews, metrics = verify_answers(
        [answer],
        fetcher=lambda url: PageDocument(
            url=url,
            title="Catálogo",
            text="Catálogo oficial. Deli está disponible en México. Consulta productos.",
        ),
    )

    assert reviews[0].status == EvidenceStatus.SUPPORTED
    assert reviews[0].source_url == "https://example.com/deli"
    assert "Deli está disponible" in reviews[0].evidence_quote
    assert reviews[0].requires_human_review is True
    assert metrics.supported == 1
    assert metrics.support_rate == 1.0


def test_deepseek_sentence_chooses_best_source_from_limited_pool() -> None:
    answer = make_answer(
        provider="deepseek",
        raw_text=(
            "Norma es una marca popular de papelería en México. "
            "Deli ofrece productos escolares.\n\n"
            "Fuentes recuperadas por búsqueda web:\n- fuentes"
        ),
        source_urls=["https://example.com/irrelevant", "https://example.com/norma"],
        source_annotations=[],
    )
    pages = {
        "https://example.com/irrelevant": PageDocument(
            url="https://example.com/irrelevant",
            text="Cuadernos y lápices para estudiantes.",
        ),
        "https://example.com/norma": PageDocument(
            url="https://example.com/norma",
            text="Norma es una marca popular de papelería en México.",
        ),
    }

    reviews, metrics = verify_answers(
        [answer],
        max_sources=2,
        max_claims=1,
        fetcher=pages.__getitem__,
    )

    assert reviews[0].status == EvidenceStatus.SUPPORTED
    assert reviews[0].source_url == "https://example.com/norma"
    assert metrics.total_claims == 1


def test_inaccessible_and_unmapped_are_reported_not_silently_supported() -> None:
    inaccessible = make_answer(
        source_annotations=[
            SourceAnnotation(
                url="https://example.com/down",
                cited_text="Deli está disponible en México.",
            )
        ],
        source_urls=["https://example.com/down"],
    )
    unmapped = make_answer(
        question_id="q-unmapped",
        raw_text="Respuesta breve.",
        source_urls=["https://example.com/source"],
        source_annotations=[],
    )

    reviews, metrics = verify_answers(
        [inaccessible, unmapped],
        fetcher=lambda url: PageDocument(url=url, error="timeout"),
    )

    assert [review.status for review in reviews] == [
        EvidenceStatus.INACCESSIBLE,
        EvidenceStatus.UNMAPPED,
    ]
    assert metrics.supported == 0
    assert metrics.inaccessible == 1
    assert metrics.unmapped == 1
    assert metrics.support_rate == 0.0
