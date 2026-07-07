---
name: folded-scalar
description: >-
  Fixture for the folded-scalar regression test. Use when the frontmatter parser
  must handle a multi-line folded YAML scalar whose text contains internal colons
  like key: value, timeout: 30, and retries: 5, and must still measure the full
  description length and detect the WHEN clause rather than splitting the text into
  spurious extra keys. This description is deliberately padded beyond 1024
  characters so the regression test can confirm that the >1024 length gate trips:
  clause one has a colon here: alpha; clause two has a colon here: bravo; clause
  three has a colon here: charlie; clause four has a colon here: delta; clause five
  has a colon here: echo; clause six has a colon here: foxtrot; clause seven has a
  colon here: golf; clause eight has a colon here: hotel; clause nine has a colon
  here: india; clause ten has a colon here: juliet; clause eleven has a colon here:
  kilo; clause twelve has a colon here: lima; clause thirteen has a colon here:
  mike; clause fourteen has a colon here: november; clause fifteen has a colon
  here: oscar; clause sixteen has a colon here: papa; and a final trailing clause
  so the total comfortably exceeds the documented 1024-character maximum limit.
license: MIT
---

# folded-scalar

Regression fixture. See references/notes.md for the details this body references.
