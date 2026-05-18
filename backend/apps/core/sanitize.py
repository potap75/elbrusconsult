"""HTML sanitization for user / admin-authored markdown.

We use ``markdown`` to render Markdown to HTML, then ``bleach`` to strip
any tag or attribute that isn't on a conservative allow-list. This keeps
the rendered output safe even if a staff account is compromised and
someone tries to embed ``<script>`` / ``<iframe>`` / inline JS handlers
in a blog post or Service body.

The allow-list mirrors what the existing templates actually display:
headings, paragraphs, lists, blockquotes, inline emphasis, code, links,
images, tables, plus the ``class`` attribute on ``<code>`` / ``<pre>``
that ``codehilite`` emits for syntax highlighting.
"""
from __future__ import annotations

from typing import Iterable

import bleach
import markdown as md

DEFAULT_MARKDOWN_EXTENSIONS: list[str] = [
    "extra",
    "sane_lists",
    "smarty",
    "toc",
    "fenced_code",
    "codehilite",
]

ALLOWED_TAGS: list[str] = [
    "a",
    "abbr",
    "acronym",
    "b",
    "blockquote",
    "br",
    "code",
    "del",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "ins",
    "li",
    "ol",
    "p",
    "pre",
    "q",
    "s",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
]

ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
    "*": ["id", "class"],
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "width", "height", "loading"],
    "abbr": ["title"],
    "acronym": ["title"],
}

# bleach's default URL schemes minus anything that can execute. Markdown
# may emit ``javascript:`` links from bad input; this allow-list blocks
# them.
ALLOWED_PROTOCOLS: list[str] = ["http", "https", "mailto", "tel"]


def safe_html(
    markdown_text: str,
    *,
    extensions: Iterable[str] | None = None,
) -> str:
    """Render ``markdown_text`` to HTML and strip unsafe tags / attrs.

    Always returns a string (empty if input is empty).
    """
    if not markdown_text:
        return ""
    html = md.markdown(
        markdown_text,
        extensions=list(extensions) if extensions is not None else DEFAULT_MARKDOWN_EXTENSIONS,
        output_format="html5",
    )
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    return bleach.linkify(cleaned, skip_tags=["pre", "code"])
