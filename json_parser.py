# json_parser.py
# Hand-rolled JSON lexer and parser for Coding United Challenge 3
# Author: Bradley Saucier - call sign viper1
#
# Disclaimer:
# This is a personal project submitted for a coding competition.
# It does not represent or reflect the views, policies, or positions
# of the United States Department of Defense or Anduril Industries.
#
# =============================================================================
#  PARSER IMPLEMENTATION: RECURSIVE DESCENT FOR STRUCTURE
# =============================================================================
#
# This parser uses a classic recursive-descent strategy for JSON, which is
# expression-free and thus well-suited for direct, predictable control flow
# without an expression parser layer [geeksforgeeks.org, Recursive Descent Parser;
# cs.rochester.edu, Recursive-Descent Parsing].
#
# Design Rationale:
# 1. JSON grammar is LL(1)-friendly: No left recursion or complex precedence
#    rules, making a hand-coded descent parser both fast and transparent
#    [online.stanford.edu, Compilers I].
# 2. Direct function-to-rule mapping keeps the control graph thin and
#    the branch predictor warm [tutorialspoint.com, Compiler Design Tutorial].
# 3. LookAhead iterator provides a one-token pushback without the
#    overhead of a full token buffer.
#
# Lexer uses a single compiled regex to keep branch misses low, based on
# the principle that scanning in large, predictable strides is more cache-
# efficient than per-character loops [craftinginterpreters.com, Scanning].
#
# Depth guard defaults to 19 (mirroring JSON_checker), a defensive measure
# against resource-exhaustion payloads [RFC 8259; hypertextbookshop.com,
# Parser Error Handling and Recovery].
#
# =============================================================================
#  REFERENCES
# =============================================================================
# [1] geeksforgeeks.org - Recursive Descent Parser
# [2] cs.rochester.edu - Recursive-Descent Parsing
# [3] craftinginterpreters.com - Scanning
# [4] RFC 8259 - The JavaScript Object Notation (JSON) standard
# [5] hypertextbookshop.com - Parser Error Handling and Recovery
# =============================================================================

import argparse
import os
import re
import sys
from typing import Iterator, List, Tuple

# ---------------------------------------------------------------------------
# CONSTANTS AND TUNABLES
# ---------------------------------------------------------------------------
DEPTH_LIMIT_DEFAULT   = 19       # Matches JSON_checker - stops unbounded nesting attacks
STREAM_THRESH_DEFAULT = 262144   # 256 KiB - switch to streaming path once size exceeds this

# ---------------------------------------------------------------------------
# REGEX BLUEPRINT
# ---------------------------------------------------------------------------
# Lexer compiled as one regex with named groups. This design minimizes
# backtracking and allows immediate token classification on match, a known
# performance win in tight parse loops [craftinginterpreters.com, Scanning].
_WHITESPACE = r"\s+"
_NUMBER     = r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?'
_ESCAPE     = r'\\.'
_STRING     = r'"(?:[^"\\\x00-\x1F]|' + _ESCAPE + r')*"'
_LITERAL    = r"true|false|null"

_TOKEN_RE = re.compile(
    rf"(?P<STRING>{_STRING})|"
    rf"(?P<NUMBER>{_NUMBER})|"
    rf"(?P<LITERAL>{_LITERAL})|"
    r"(?P<BRACE>[{}])|"          # { or }
    r"(?P<BRACKET>[\[\]])|"      # [ or ]
    r"(?P<COMMA>,)|"
    r"(?P<COLON>:)|"
    rf"(?P<WHITESPACE>{_WHITESPACE})",
)

# ---------------------------------------------------------------------------
# TOKEN RECORD
# ---------------------------------------------------------------------------
class Token(Tuple[str, str, int]):
    """
    Immutable token record: (kind, value, absolute_offset).

    Rationale: Using a lightweight tuple here keeps allocations low.
    Offsets are retained for precise SyntaxError reporting [tutorialspoint.com,
    Compiler Design Tutorial; geeksforgeeks.org, Error Detection and Recovery].
    """
    pass

# ---------------------------------------------------------------------------
# LOOKAHEAD RING
# ---------------------------------------------------------------------------
class LookAhead:
    """
    One-slot pushback iterator.

    This implements minimal lookahead required for LL(1) parsing without
    incurring full buffering cost. Matches the "single token of lookahead"
    principle in top-down parsing theory [geeksforgeeks.org, Top Down Parsing].
    """
    def __init__(self, iterable: Iterator[Token]):
        self._iter = iter(iterable)
        self._buf: List[Token] = []

    def __iter__(self):
        return self

    def __next__(self):
        if self._buf:
            return self._buf.pop()
        return next(self._iter)

    def peek(self) -> Token:
        if not self._buf:
            self._buf.append(next(self._iter))
        return self._buf[-1]

# ---------------------------------------------------------------------------
# STRING VALIDATION
# ---------------------------------------------------------------------------
def _validate_string(raw: str, token_start: int) -> str:
    """
    Unescape JSON string and reject invalid escapes.

    Handles three classes of errors with precise offsets:
    1) Structural issues - unterminated string or trailing backslash before a missing quote.
    2) Escape syntax - invalid single escape, short unicode escape, invalid hex digits.
    3) Unicode correctness - unpaired surrogate code points.
    """
    # Structural integrity - ensure opening and closing quotes are present.
    if len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
        # If the last character is a backslash, report a trailing backslash at boundary.
        if len(raw) > 0 and raw[-1] == "\\":
            raise SyntaxError(f"trailing backslash in string at offset {token_start + len(raw) - 1}")
        # Otherwise the string is unterminated.
        raise SyntaxError(f"unterminated string starting at offset {token_start}")

    inner = raw[1:-1]
    i = 0
    n = len(inner)
    while i < n:
        ch = inner[i]
        if ch == "\\":
            if i + 1 >= n:
                raise SyntaxError(f"trailing backslash in string at offset {token_start + 1 + i}")
            esc = inner[i + 1]
            if esc == "u":
                if i + 6 > n:
                    raise SyntaxError(f"short unicode escape at offset {token_start + 1 + i}")
                hexpart = inner[i + 2:i + 6]
                if not all(c in '0123456789abcdefABCDEF' for c in hexpart):
                    seq = inner[i:i + 6]
                    raise SyntaxError(f"invalid hex escape {seq} at offset {token_start + 1 + i}")
                i += 6
                continue
            elif esc in "\"\\/bfnrt":
                i += 2
                continue
            else:
                raise SyntaxError(f"invalid escape \{esc} at offset {token_start + 1 + i}")
        i += 1
    try:
        decoded = inner.encode("utf-8").decode("unicode_escape")
    except UnicodeDecodeError as exc:
        raise SyntaxError(f"bad escape sequence: {exc}") from None
    for ch in decoded:
        code = ord(ch)
        if 0xD800 <= code <= 0xDFFF:
            raise SyntaxError("unpaired surrogate in string")
    return decoded

def lex(text: str) -> Iterator[Token]:
    """
    Single-pass generator producing tokens. Rejects any gap in regex coverage.

    Early conversion to Python native types moves type interpretation out
    of the parse loop, improving throughput [craftinginterpreters.com, Scanning].
    """
    pos = 0
    for m in _TOKEN_RE.finditer(text):
        kind  = m.lastgroup
        value = m.group()
        start = m.start()

        if start != pos:
            raise SyntaxError(f"invalid character at offset {pos}")  # Gap in match coverage
        pos = m.end()

        if kind == "WHITESPACE":
            continue
        if kind == "STRING":
            value = _validate_string(value, start)
        elif kind == "NUMBER":
            value = float(value) if any(c in value for c in ".eE") else int(value)
        elif kind == "LITERAL":
            value = {"true": True, "false": False, "null": None}[value]

        yield Token((kind, value, start))

    if pos != len(text):
        raise SyntaxError(f"invalid character at offset {pos}")

# ---------------------------------------------------------------------------
# PARSER UTILITY
# ---------------------------------------------------------------------------
def _expect(tokens: LookAhead, expected_kind: str, expected_value=None):
    """
    Consume and verify the next token. Raises a precise error with expected and actual.
    """
    try:
        kind, value, pos = next(tokens)
    except StopIteration:
        raise SyntaxError("unexpected end of input")
    if kind != expected_kind or (expected_value is not None and value != expected_value):
        exp = expected_kind if expected_value is None else f"{expected_kind} '{expected_value}'"
        act_val = value if isinstance(value, (str, int, float, type(None), bool)) else str(value)
        raise SyntaxError(f"unexpected token {kind} '{act_val}' at offset {pos} - expected {exp}")
    return value

# ---------------------------------------------------------------------------
# CORE VALUE PARSER
# ---------------------------------------------------------------------------
def _parse_value(tokens: LookAhead, depth: int, max_depth: int, allow_dup: bool):
    """
    Dispatch based on token type. Enforces depth limit as a hard stop against
    stack abuse [hypertextbookshop.com, Parser Error Handling and Recovery].
    """
    if depth > max_depth:
        raise SyntaxError("depth limit exceeded")
    try:
        kind, value, _ = next(tokens)
    except StopIteration:
        raise SyntaxError("unexpected end of input")

    if kind in {"STRING", "NUMBER", "LITERAL"}:
        return value
    if kind == "BRACE" and value == "{":
        return _parse_object(tokens, depth + 1, max_depth, allow_dup)
    if kind == "BRACKET" and value == "[":
        return _parse_array(tokens, depth + 1, max_depth, allow_dup)

    raise SyntaxError(f"unexpected token {kind} '{value}' - value expected")

# ---------------------------------------------------------------------------
# ARRAY PARSER
# ---------------------------------------------------------------------------
def _parse_array(tokens: LookAhead, depth: int, max_depth: int, allow_dup: bool):
    """
    Parse a JSON array.

    The loop is tight and straightforward, but in Python the primary speed wins
    come from lexer efficiency and minimizing per-token work rather than function
    call overhead. The design keeps per-element operations minimal while relying on
    the lexer to do the heavy lifting [online.stanford.edu, Compilers I].
    """
    items: List = []
    try:
        pk = tokens.peek()
    except StopIteration:
        raise SyntaxError("unexpected end of input")
    if pk[0] == "BRACKET" and pk[1] == "]":
        next(tokens)
        return items

    while True:
        items.append(_parse_value(tokens, depth, max_depth, allow_dup))
        try:
            pk = tokens.peek()
        except StopIteration:
            raise SyntaxError("unexpected end of input")
        if pk[0] == "BRACKET" and pk[1] == "]":
            next(tokens)
            break
        _expect(tokens, "COMMA", ",")
    return items

# ---------------------------------------------------------------------------
# OBJECT PARSER
# ---------------------------------------------------------------------------
def _parse_object(tokens: LookAhead, depth: int, max_depth: int, allow_dup: bool):
    """
    Parses a JSON object. Enforces duplicate key policy at parse time.

    Duplicate key rejection here is a design choice: catching policy violations
    early prevents downstream semantic errors [geeksforgeeks.org, Error Detection].
    """
    obj = {}
    try:
        pk = tokens.peek()
    except StopIteration:
        raise SyntaxError("unexpected end of input")
    if pk[0] == "BRACE" and pk[1] == "}":
        next(tokens)
        return obj

    while True:
        key = _expect(tokens, "STRING")
        _expect(tokens, "COLON", ":")
        if not allow_dup and key in obj:
            raise SyntaxError("duplicate key")
        obj[key] = _parse_value(tokens, depth, max_depth, allow_dup)
        try:
            pk = tokens.peek()
        except StopIteration:
            raise SyntaxError("unexpected end of input")
        if pk[0] == "BRACE" and pk[1] == "}":
            next(tokens)
            break
        _expect(tokens, "COMMA", ",")
    return obj

# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------
def parse(text: str, *, max_depth: int = DEPTH_LIMIT_DEFAULT, allow_dup: bool = False):
    """
    Parses JSON text into Python structures.

    Entry point enforces RFC 8259's root constraint that payload must be
    an object or array. Rejects trailing tokens to maintain full input
    consumption [RFC 8259; craftinginterpreters.com, Parsing Expressions].
    """
    tokens = LookAhead(lex(text))
    first_kind, _, _ = tokens.peek()
    if first_kind not in ("BRACE", "BRACKET"):
        _, first_val, first_pos = tokens.peek()
        raise SyntaxError(f"payload must be object or array at root - got {first_kind} '{first_val}' at offset {first_pos}")

    result = _parse_value(tokens, 0, max_depth, allow_dup)
    try:
        k2, v2, p2 = next(tokens)
    except StopIteration:
        return result
    raise SyntaxError(f"extra data after root value at offset {p2}")

# ---------------------------------------------------------------------------
# CLI ENTRYPOINT
# ---------------------------------------------------------------------------
def _cli(argv: List[str]):
    """
    Command-line interface for parser validation runs.

    Follows the standard exit code pattern for build integration:
    0 on success, non-zero on SyntaxError [tutorialspoint.com, Compiler Design].
    """
    ap = argparse.ArgumentParser(description="CCT JSON validator")
    ap.add_argument("file", help="JSON file to verify")
    ap.add_argument("--debug", action="store_true", help="dump token stream and exit")
    ap.add_argument("--max-depth", type=int, default=DEPTH_LIMIT_DEFAULT)
    ap.add_argument("--allow-dup-keys", action="store_true")
    ap.add_argument("--streaming-threshold", type=int, default=STREAM_THRESH_DEFAULT)
    args = ap.parse_args(argv)

    fsize = os.path.getsize(args.file)
    read_mode = "stream" if fsize > args.streaming_threshold else "buffer"
    # Streaming roadmap - true stream parsing will require adapting the lexer to operate
    # on chunks from an input stream while preserving token boundaries and offsets.
    data = open(args.file, "r", encoding="utf-8").read()

    if args.debug:
        for tok in lex(data):
            print(tok)
        return 0

    try:
        parse(data, max_depth=args.max_depth, allow_dup=args.allow_dup_keys)
        print("OK" if read_mode == "buffer" else "OK (stream mode placeholder)")
        return 0
    except SyntaxError as exc:
        print(f"SyntaxError: {exc}", file=sys.stderr)
        return 1

# ---------------------------------------------------------------------------
# MAIN GUARD
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
# viper1 out
