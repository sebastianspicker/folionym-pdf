"""Document-analysis prompt text and builders. Pure text-in/text-out helpers."""

from __future__ import annotations

import re
from typing import Any, cast

PLACEHOLDER_ALLOWED_CATEGORIES = "%ALLOWED_CATEGORIES%"
_DOCUMENT_CONTENT_TEMPLATE = "<document_content>\n{document_content}\n</document_content>"
_SUMMARY_COMBINE_CONTENT_TEMPLATE = "<partial_summaries>\n{combined_summaries}\n</partial_summaries>"
_SUMMARY_SHORT_TEMPLATE = "{doc_type_hint}{instruction} {json_rule}\n\n{document_block}"
_SUMMARY_CHUNK_TEMPLATE = "{doc_type_hint}{instruction} {json_rule}\n\n{document_block}"
_SUMMARY_COMBINE_TEMPLATE = "{doc_type_hint}{intro}{combined}\n\n{instruction} {json_rule}\n"
_ANALYSIS_TEMPLATE = (
    "{doc_type_hint}{analysis_intro}\n"
    "{analysis_schema_intro}\n"
    "{analysis_schema}\n\n"
    "{analysis_examples}"
    "{analysis_rules_heading}\n"
    "- {analysis_summary_rule}\n"
    "- {analysis_keywords_rule}\n"
    "- category: {category_instruction}\n"
    "- {analysis_specificity_rule}\n"
    "- {analysis_generic_rule}\n"
    "- {analysis_failure_mode_rule}\n"
    "- {analysis_json_only_rule}\n\n"
    "{document_block}"
)

PROMPT_STRINGS: dict[str, dict[str, Any]] = {
    "de": {
        "doc_type_hint": (
            'Kontext: Das Dokument wurde heuristisch als Typ "{hint}" eingestuft. '
            "Betone in der Zusammenfassung den Dokumenttyp (z. B. Rechnung, Vertrag). "
        ),
        "analysis_intro": "Analysiere das folgende Dokument und gib das Ergebnis als reines JSON zurück.",
        "analysis_schema_intro": "Antworte NUR mit einem JSON-Objekt in genau dieser Struktur:",
        "analysis_schema": (
            '{"summary":"1-2 präzise Sätze","keywords":["KW1","KW2","KW3","KW4","KW5","KW6"],"category":"Kategorie"}'
        ),
        "analysis_examples_heading": "Beispiele:",
        "analysis_examples": [
            (
                '1. Text: "Rechnung Nr. INV-2025-0042 der Muster GmbH über 249,90 EUR vom 15.03.2025."\n'
                '   JSON: {"summary":"Rechnung der Muster GmbH über 249,90 EUR vom 15.03.2025.",'
                '"keywords":["Rechnung","Muster GmbH","INV-2025-0042","249,90 EUR","15.03.2025"],'
                '"category":"invoice"}'
            ),
            (
                '2. Text: "Gehaltsabrechnung März 2025 für Erika Mustermann, Nettoauszahlung 2.845,12 EUR."\n'
                '   JSON: {"summary":"Gehaltsabrechnung für März 2025 mit einer Nettoauszahlung von 2.845,12 EUR.",'
                '"keywords":["Gehaltsabrechnung","März 2025","Nettoauszahlung","2.845,12 EUR","Erika Mustermann"],'
                '"category":"payslip"}'
            ),
        ],
        "analysis_rules_heading": "Regeln:",
        "analysis_summary_rule": "summary: 1-2 präzise Sätze, die den Dokumentinhalt und -typ beschreiben",
        "analysis_keywords_rule": "keywords: 5-7 relevante Schlüsselwörter",
        "analysis_specificity_rule": (
            "Wenn mehrere Dokumenttypen möglich sind, wähle die spezifischste passende Kategorie."
        ),
        "analysis_generic_rule": (
            'Generische Kategorien wie "document" oder "letter" nur verwenden, '
            "wenn wirklich keine spezifischere Kategorie passt."
        ),
        "analysis_failure_mode_rule": (
            "Vermeide generische oder ausweichende Klassifikationen bei klar erkennbaren Dokumenttypen."
        ),
        "analysis_json_only_rule": "Keine weiteren Erklärungen, nur JSON",
        "allowed_categories_exact": "Gib genau eine dieser Kategorien oder 'unknown': {categories}",
        "allowed_categories_suggested": (
            "Vorschläge nutzen falls passend, sonst andere Kategorie. Vorschläge: {categories}."
        ),
        "allowed_categories_any": "Gib eine passende Kategorie.",
        "summary_short_variants": [
            {
                "instruction": "Fasse den folgenden Text in 1–2 präzisen Sätzen zusammen.",
                "json_rule": 'Nur reines JSON: {"summary":"..."}',
            },
            {
                "instruction": "Extrahiere die wichtigsten Informationen des Dokuments.",
                "json_rule": 'Nur reines JSON: {"summary":"..."}',
            },
        ],
        "summary_chunk_instruction": "Fasse den folgenden Text in 1–2 kurzen Sätzen zusammen.",
        "summary_chunk_json_rule": 'NUR reines JSON {"summary":"..."}, keine Erklärungen.',
        "summary_combine_intro": "Hier mehrere Teilzusammenfassungen eines langen Dokuments:\n",
        "summary_combine_instruction": (
            "Fasse sie in 1–2 prägnanten Sätzen zusammen. Stelle sicher, dass der Dokumenttyp erkennbar bleibt."
        ),
        "summary_combine_json_rule": 'Nur reines JSON {"summary":"..."}.',
    },
    "en": {
        "doc_type_hint": (
            'Context: The document was heuristically classified as type "{hint}". '
            "Emphasize in the summary what type of document this is (e.g. invoice, contract). "
        ),
        "analysis_intro": "Analyze the following document and return the result as pure JSON.",
        "analysis_schema_intro": "Respond ONLY with a JSON object in exactly this structure:",
        "analysis_schema": (
            '{"summary":"1-2 precise sentences","keywords":["KW1","KW2","KW3","KW4","KW5","KW6"],"category":"Category"}'
        ),
        "analysis_examples_heading": "Examples:",
        "analysis_examples": [
            (
                '1. Text: "Invoice INV-2025-0042 from Sample GmbH for EUR 249.90 dated 2025-03-15."\n'
                '   JSON: {"summary":"Invoice from Sample GmbH for EUR 249.90 dated 2025-03-15.",'
                '"keywords":["invoice","Sample GmbH","INV-2025-0042","EUR 249.90","2025-03-15"],'
                '"category":"invoice"}'
            ),
            (
                '2. Text: "Payslip for March 2025 for Erika Mustermann, net pay EUR 2,845.12."\n'
                '   JSON: {"summary":"Payslip for March 2025 with net pay of EUR 2,845.12.",'
                '"keywords":["payslip","March 2025","net pay","EUR 2,845.12","Erika Mustermann"],'
                '"category":"payslip"}'
            ),
        ],
        "analysis_rules_heading": "Rules:",
        "analysis_summary_rule": "summary: 1-2 precise sentences describing the document content and type",
        "analysis_keywords_rule": "keywords: 5-7 relevant keywords",
        "analysis_specificity_rule": (
            "If multiple document types seem possible, choose the most specific applicable category."
        ),
        "analysis_generic_rule": (
            'Do not return generic categories like "document" or "letter" when a more specific category applies.'
        ),
        "analysis_failure_mode_rule": "Avoid vague fallback labels when the document type is identifiable.",
        "analysis_json_only_rule": "No additional explanations, only JSON",
        "allowed_categories_exact": "Return exactly one of these or 'unknown': {categories}",
        "allowed_categories_suggested": (
            "Use one suggestion if appropriate, else another category. Suggestions: {categories}."
        ),
        "allowed_categories_any": "Return any suitable category.",
        "summary_short_variants": [
            {
                "instruction": "Summarize the following text in 1-2 precise sentences.",
                "json_rule": 'Return only valid JSON: {"summary":"..."}',
            },
            {
                "instruction": "Extract the core description of this document.",
                "json_rule": 'Return only valid JSON: {"summary":"..."}',
            },
        ],
        "summary_chunk_instruction": "Summarize the following text in 1–2 short sentences.",
        "summary_chunk_json_rule": 'Return ONLY {"summary":"..."} in JSON, no explanations.',
        "summary_combine_intro": "Here are multiple partial summaries of a large document:\n",
        "summary_combine_instruction": (
            "Combine them into 1–2 concise sentences. Ensure the document type remains clear."
        ),
        "summary_combine_json_rule": 'Return ONLY {"summary":"..."} in JSON.',
    },
}


def _language_code(language: str) -> str:
    """Normalize prompt language to a supported dictionary key."""
    normalized = language.strip().lower()
    primary = normalized.replace("_", "-").split("-", 1)[0]
    return "de" if primary == "de" else "en"


def _prompt_strings(language: str) -> dict[str, Any]:
    """Return language strings for prompt rendering."""
    return PROMPT_STRINGS[_language_code(language)]


def _render_prompt(template: str, /, **replacements: str) -> str:
    """Render a prompt template with explicit placeholders."""
    return template.format(**replacements)


def _document_block(text: str) -> str:
    """Wrap document content in the shared prompt block."""
    return _render_prompt(_DOCUMENT_CONTENT_TEMPLATE, document_content=text)


def _combine_summary_block(text: str) -> str:
    """Wrap partial summaries in a shared block so they stay data, not instructions."""
    return _render_prompt(_SUMMARY_COMBINE_CONTENT_TEMPLATE, combined_summaries=text)


def _analysis_examples(language: str) -> str:
    """Render few-shot examples for the analysis prompt."""
    strings = _prompt_strings(language)
    heading = cast(str, strings["analysis_examples_heading"])
    examples = cast(list[str], strings["analysis_examples"])
    return heading + "\n" + "\n".join(examples) + "\n\n"


def replace_prompt_placeholders(template: str, replacements: dict[str, str]) -> str:
    """
    Replace placeholders (e.g. %KEY%) in a prompt template with actual values.
    Use %...% style for all placeholder keys. Unknown placeholders are left as-is.
    New prompts should use placeholders for variable bits (language, examples, content).
    """
    result = template
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


def summary_doc_type_hint(language: str, suggested_doc_type: str | None) -> str:
    """Build doc-type hint prefix for summary prompts."""
    if not suggested_doc_type or not suggested_doc_type.strip():
        return ""
    strings = _prompt_strings(language)
    return cast(str, strings["doc_type_hint"]).format(hint=suggested_doc_type.strip())


def escape_doc_content(text: str) -> str:
    """Escape prompt block closing tags to prevent prompt injection."""
    # Escape every closing tag used as a prompt delimiter, case-insensitively.
    return re.sub(
        r"</(document_content|partial_summaries)>",
        lambda match: f"<\\/{match.group(1)}>",
        text,
        flags=re.IGNORECASE,
    )


def summary_prompts_short(language: str, doc_type_hint: str, text: str) -> list[str]:
    """Build fallback prompt variants for a short-document summary."""
    strings = _prompt_strings(language)
    safe_text = escape_doc_content(text)
    variants = cast(list[dict[str, str]], strings["summary_short_variants"])
    return [
        _render_prompt(
            _SUMMARY_SHORT_TEMPLATE,
            doc_type_hint=doc_type_hint,
            instruction=variant["instruction"],
            json_rule=variant["json_rule"],
            document_block=_document_block(safe_text),
        )
        for variant in variants
    ]


def summary_prompt_chunk(language: str, doc_type_hint: str, chunk: str) -> str:
    """Build prompt for one chunk in long-document summary."""
    safe_chunk = escape_doc_content(chunk)
    strings = _prompt_strings(language)
    return _render_prompt(
        _SUMMARY_CHUNK_TEMPLATE,
        doc_type_hint=doc_type_hint,
        instruction=cast(str, strings["summary_chunk_instruction"]),
        json_rule=cast(str, strings["summary_chunk_json_rule"]),
        document_block=_document_block(safe_chunk),
    )


def summary_prompt_combine(language: str, doc_type_hint: str, combined: str) -> str:
    """Build prompt to combine partial summaries into one."""
    strings = _prompt_strings(language)
    safe_combined = escape_doc_content(combined)
    return _render_prompt(
        _SUMMARY_COMBINE_TEMPLATE,
        doc_type_hint=doc_type_hint,
        intro=cast(str, strings["summary_combine_intro"]),
        combined=_combine_summary_block(safe_combined),
        instruction=cast(str, strings["summary_combine_instruction"]),
        json_rule=cast(str, strings["summary_combine_json_rule"]),
    )


def build_analysis_prompt(
    language: str,
    text: str,
    *,
    suggested_doc_type: str | None = None,
    allowed_categories: list[str] | None = None,
    suggested_categories: list[str] | None = None,
) -> str:
    """Build a single prompt that asks for summary, keywords, and category in one JSON response."""
    doc_type_hint = summary_doc_type_hint(language, suggested_doc_type)
    safe_text = escape_doc_content(text)
    strings = _prompt_strings(language)
    category_instruction = build_allowed_categories_instruction(
        allowed_categories=allowed_categories,
        suggested_categories=suggested_categories,
        language=language,
    )
    return _render_prompt(
        _ANALYSIS_TEMPLATE,
        doc_type_hint=doc_type_hint,
        analysis_intro=cast(str, strings["analysis_intro"]),
        analysis_schema_intro=cast(str, strings["analysis_schema_intro"]),
        analysis_schema=cast(str, strings["analysis_schema"]),
        analysis_examples=_analysis_examples(language),
        analysis_rules_heading=cast(str, strings["analysis_rules_heading"]),
        analysis_summary_rule=cast(str, strings["analysis_summary_rule"]),
        analysis_keywords_rule=cast(str, strings["analysis_keywords_rule"]),
        category_instruction=category_instruction,
        analysis_specificity_rule=cast(str, strings["analysis_specificity_rule"]),
        analysis_generic_rule=cast(str, strings["analysis_generic_rule"]),
        analysis_failure_mode_rule=cast(str, strings["analysis_failure_mode_rule"]),
        analysis_json_only_rule=cast(str, strings["analysis_json_only_rule"]),
        document_block=_document_block(safe_text),
    )


def build_allowed_categories_instruction(
    *,
    allowed_categories: list[str] | None = None,
    suggested_categories: list[str] | None = None,
    language: str,
) -> str:
    """Build the instruction string for allowed/suggested categories (replaces %ALLOWED_CATEGORIES% in prompts)."""
    strings = _prompt_strings(language)
    if allowed_categories:
        cats = ", ".join(sorted(allowed_categories))
        return cast(str, strings["allowed_categories_exact"]).format(categories=cats)
    if suggested_categories:
        cats = ", ".join(suggested_categories)
        return cast(str, strings["allowed_categories_suggested"]).format(categories=cats)
    return cast(str, strings["allowed_categories_any"])


def keyword_prompts(summary: str, language: str, suggested_category: str | None) -> list[str]:
    """Build localized keyword-extraction prompt variants."""
    cat_hint = ""
    if suggested_category and suggested_category.strip():
        category = suggested_category.strip()
        cat_hint = (
            f"Das Dokument ist voraussichtlich: {category}. "
            if language == "de"
            else f"The document is likely: {category}. "
        )

    if language == "de":
        return [
            (
                cat_hint + "Extrahiere bitte 5–7 Schlüsselwörter aus dieser Zusammenfassung.\n"
                "Gib ausschließlich eine Ausgabe in der Form:\n"
                '{"keywords":["KW1","KW2","KW3"]}\n\n'
                "Jetzt bitte NUR reines JSON, sonst nichts.\n"
                "Zusammenfassung:\n" + summary
            ),
            (
                cat_hint + "Bitte NUR reines JSON in der Form:\n"
                '{"keywords":["KW1","KW2"]}\n\n'
                "Hier die Zusammenfassung:\n" + summary
            ),
        ]
    return [
        (
            cat_hint + "Extract 5–7 keywords from this summary. Return ONLY JSON:\n"
            '{"keywords":["KW1","KW2"]}\n\n'
            "Summary:\n" + summary
        )
    ]


def category_prompts(
    summary: str,
    keywords: list[str],
    *,
    language: str,
    allowed_categories: list[str] | None = None,
    suggested_categories: list[str] | None = None,
) -> list[str]:
    """Build localized category-classification prompt variants."""
    keywords_joined = ", ".join(keywords)
    if language == "de":
        base_text = f"Zusammenfassung:\n{summary}\nKeywords:{keywords_joined}"
    else:
        base_text = f"Summary:\n{summary}\nKeywords:{keywords_joined}"
    category_instruction = build_allowed_categories_instruction(
        allowed_categories=allowed_categories,
        suggested_categories=suggested_categories,
        language=language,
    )
    content = replace_prompt_placeholders(
        base_text + "\n\n" + PLACEHOLDER_ALLOWED_CATEGORIES,
        {PLACEHOLDER_ALLOWED_CATEGORIES: category_instruction},
    )
    if language == "de":
        prompt_templates = [
            (
                "Bestimme eine sinnvolle Kategorie als reines JSON.\n"
                'Gib nur: {"category":"..."}\n\nKeine weiteren Erklärungen. Text:\n'
            ),
            'Bitte nur {"category":"..."} - ohne Zusätze:\n',
        ]
        return [t + content for t in prompt_templates]
    return [f'Determine a suitable category. Return ONLY JSON: {{"category":"..."}}\n\nText:\n{content}']


def final_summary_prompts(summary: str, keywords: list[str], category: str, language: str) -> list[str]:
    """Build localized prompts for compact final summary tokens."""
    kw_str = ", ".join(keywords)
    base_text = f"Zusammenfassung: {summary}\nSchlagworte: {kw_str}\nKategorie: {category}"

    if language == "de":
        prompts = [
            (
                "Erstelle bitte bis zu 5 Stichworte (kurz! 1–2 Wörter pro Stichwort) "
                "als reines JSON.\n"
                '{"final_summary":"stichwort1,stichwort2"}\n\n'
                "WICHTIG: Keine Sätze, nur Stichworte. Nur JSON.\n\n" + base_text
            ),
            (
                'Bitte nur reines JSON {"final_summary":"stichwort1,stichwort2"}. '
                "Max. 5 Stichworte, keine Sätze!\n\n" + base_text
            ),
        ]
    else:
        prompts = [
            (
                "Return up to 5 short keywords (1–2 words each) as JSON:\n"
                '{"final_summary":"kw1,kw2"}\n\n'
                "Only JSON.\n\n" + base_text
            )
        ]

    return prompts
