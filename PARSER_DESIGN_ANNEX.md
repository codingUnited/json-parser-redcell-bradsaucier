# Parser Design Annex - JSON Parser: Red Cell Sweep
[Back to README](./README.md)

**Author**: Bradley Saucier  
**Call Sign**: viper1  

---

## 1. Mission Statement
This annex documents the doctrinal basis for the `json_parser.py` design.  
Every architectural decision is grounded in recognized compiler-construction best practices.  
The goal is to demonstrate that the implementation is not just functional, but a deliberate execution of field-proven techniques - built for speed, resilience, and maintainability under operational constraints.

---

## 2. Lexer Design
### Doctrinal Basis
- Use one compiled regex with named capture groups to tokenize in a single pass.
- Convert to native Python types during lexing to minimize parser workload.
- This matches scanning best practices outlined in Crafting Interpreters and Compiler Design Tutorial.

> Why:  
> A unified pattern reduces branch mispredictions and improves cache line utilization.  
> Early type conversion avoids re-interpreting strings in the parse phase.

**Reference pseudocode** (Crafting Interpreters - Scanning):
```
while not at_end():
    start = current
    scan_token()
```

**Our implementation excerpt**:
```python
_TOKEN_RE = re.compile(
    rf"(?P<STRING>{_STRING})|..."
)

for m in _TOKEN_RE.finditer(text):
    kind  = m.lastgroup
    value = m.group()
    if kind == "STRING":
        value = _validate_string(value)
    elif kind == "NUMBER":
        value = float(value) if any(c in value for c in ".eE") else int(value)
```
**Citations**: craftinginterpreters.com, tutorialspoint.com

---

## 3. Parser Strategy
### Doctrinal Basis
- JSON grammar is expression-free and LL(1)-compatible.
- Hand-coded recursive descent ensures maximum control over parsing flow.
- Eliminates need for parser generators or grammar transformation.

> Why:  
> Direct mapping of grammar rules to functions improves readability and makes debugging surgical.

**Reference pseudocode** (geeksforgeeks.org, Recursive Descent Parser):
```
function value():
    if current_token == STRING: return string()
    if current_token == NUMBER: return number()
    if current_token == '{': return object()
    if current_token == '[': return array()
```

**Our implementation excerpt**:
```python
def _parse_value(tokens, depth, max_depth, allow_dup):
    if kind in {"STRING", "NUMBER", "LITERAL"}:
        return value
    if kind == "BRACE" and value == "{":
        return _parse_object(...)
    if kind == "BRACKET" and value == "[":
        return _parse_array(...)
```
**Citations**: geeksforgeeks.org, cs.rochester.edu, online.stanford.edu

---

## 4. LookAhead Mechanism
### Doctrinal Basis
- Implements single-token pushback using a one-slot buffer.
- Matches LL(1) parsing theory, where at most one token of lookahead is required.

> Why:  
> Minimal memory footprint, predictable behavior, zero overhead from full deques or tee iterators.

**Reference pseudocode** (Top Down Parsing - geeksforgeeks.org):
```
function peek():
    if buffer_empty: buffer.append(next_token())
    return buffer[-1]
```

**Our implementation excerpt**:
```python
class LookAhead:
    def peek(self) -> Token:
        if not self._buf:
            self._buf.append(next(self._iter))
        return self._buf[-1]
```
**Citations**: geeksforgeeks.org, Top Down Parsing

---

## 5. Depth Guard
### Doctrinal Basis
- Maximum nesting depth set to 19 (JSON_checker standard).
- Hard stop prevents stack overflow or excessive resource use.

> Why:  
> Acts as a denial-of-service safeguard, stopping deep nesting attacks.

**Reference pseudocode** (Parser Error Handling - hypertextbookshop.com):
```
if depth > MAX_DEPTH:
    raise SyntaxError
```

**Our implementation excerpt**:
```python
if depth > max_depth:
    raise SyntaxError("depth limit exceeded")
```
**Citations**: RFC 8259, hypertextbookshop.com

---

## 6. Duplicate Key Policy
### Doctrinal Basis
- Optional enforcement of RFC 8259's guidance on duplicate keys.
- Operator decides based on mission profile whether strictness or speed takes priority.

> Why:  
> Flexibility in bulk ingest operations where key uniqueness is irrelevant.

**Reference pseudocode**:
```
if not allow_dup and key in object:
    raise SyntaxError
```

**Our implementation excerpt**:
```python
if not allow_dup and key in obj:
    raise SyntaxError("duplicate key")
```
**Citations**: RFC 8259

---

## 7. Error Handling
### Doctrinal Basis
- Immediate failure on malformed tokens.
- Could be extended to panic mode recovery if multi-error reporting is required.

> Why:  
> Current mission profile prioritizes speed over multi-error diagnostics.

**Reference pseudocode** (panic mode - hypertextbookshop.com):
```
while current_token not in sync_tokens:
    advance()
```

**Our implementation excerpt**:
```python
raise SyntaxError(f"invalid character at offset {pos}")
```
**Citations**: hypertextbookshop.com, geeksforgeeks.org

---

## 8. AST Considerations
### Doctrinal Basis
- No explicit AST is constructed because JSON’s semantic form is identical to its Python-native representation.

> Why:  
> Eliminates unnecessary transformation stage, reducing latency without loss of semantic fidelity.

**Reference pseudocode** (Abstract Syntax Tree Creation - meegle.com):
```
Node:
    type
    children[]
```

**Contrast**:
- Reference: Builds a hierarchy of nodes for later traversal.
- Our parser: Returns dict/list/values directly as the semantic form.

**Citations**: meegle.com, blog.trailofbits.com

---


---

## 9. Potential Areas for Enhancement
Minor items for future iterations. Current build adds more specific error messages as described below.

- **Streaming placeholder**: The `--streaming-threshold` flag is present. `_cli` contains a streaming roadmap comment. When the threshold is exceeded, the tool prints `OK (stream mode placeholder)`. A future enhancement would adapt `lex` to process input chunks safely.

## 9. Source Reference Summary
1. geeksforgeeks.org - Recursive Descent Parser  
2. cs.rochester.edu - Recursive-Descent Parsing  
3. craftinginterpreters.com - Scanning  
4. RFC 8259 - The JavaScript Object Notation (JSON) standard  
5. hypertextbookshop.com - Parser Error Handling and Recovery  
6. tutorialspoint.com - Compiler Design Tutorial  
7. meegle.com - Abstract Syntax Tree Creation  
8. blog.trailofbits.com - The Life and Times of an AST  

---

**End of Annex**  
//viper1//
