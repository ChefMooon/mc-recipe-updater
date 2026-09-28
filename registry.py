"""
Parser Registry - maps parser names to transform functions.

Each parser takes bytes → bytes.
Add your own by following the same pattern and registering it here.

Built-in parsers:
  - strip_bom              Remove UTF-8 BOM if present
  - normalize_line_endings Convert all line endings to LF (\n)
  - strip_trailing_whitespace Remove trailing whitespace from lines
"""

# ──────────────────────────────────────────────
# Parser Functions (bytes → bytes)
# ──────────────────────────────────────────────

def strip_bom(content: bytes) -> bytes:
    """Remove UTF-8 BOM (EF BB BF) from the start of a file."""
    if content.startswith(b"\xef\xbb\xbf"):
        return content[3:]
    return content


def normalize_line_endings(content: bytes) -> bytes:
    """Normalize CRLF and CR line endings to LF."""
    return content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def strip_trailing_whitespace(content: bytes) -> bytes:
    """Remove trailing whitespace from each line."""
    lines = content.split(b"\n")
    return b"\n".join(line.rstrip() for line in lines)


# ──────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────

PARSERS = {
    "strip_bom": strip_bom,
    "normalize_line_endings": normalize_line_endings,
    "strip_trailing_whitespace": strip_trailing_whitespace,
    # Add your own here:
    # "my_custom_parser": my_custom_parser_fn,
}


def get_parser(name: str):
    """Retrieve a parser function by name. Returns None if not found."""
    return PARSERS.get(name)


def list_parsers() -> list:
    """Return names of all available parsers."""
    return list(PARSERS.keys())
