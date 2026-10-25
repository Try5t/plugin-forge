# Decision widget (prototype)

An interactive decision card for Claude's inline widget tool (`show_widget`). Claude
recommends one option; the person picks any option, re-weights the criteria and sends the
pick, the changed weights and a note, or a question, back into the chat through
`sendPrompt()`.

**Status:** prototype, not in use. It is no plugin, no skill and not registered in the
marketplace, so nothing loads it into a session's context.

## What it shows

- The question, a one-line context and its source (issue, area).
- "Background and sources" (collapsed): what the decision changes, what it touches, links
  to the issue, the concept section and an earlier decision, and one line per question
  already asked.
- A card for the picked option: label, weighted score, why, the strongest argument
  against it, and a flip line (the smallest single-weight change that puts another option
  ahead, or that would put this one ahead). The card is accent-bordered for the
  recommendation and warning-bordered when the pick differs from it.
- Every option as a clickable card with a bar split by criterion, its strongest pro and
  con; a legend below.
- "Adjust weights" (collapsed): steppers per criterion, 0 to 10, with Claude's original
  weight shown beside a changed one, and a reset.
- A note or question field, a send button and an ask button.

## What reaches Claude

- Pick: `Decision "<question>": <option>. Changed weights: <criterion> 2→5; with them:
  <option> 36, <option> 34, … Note: <note>` (weights and note only when given).
- Question: `Question on decision "<question>": <text>`.

## Using it

`decision-widget.html` is the widget fragment exactly as tested, filled with a made-up
example. To use it, replace the data at the top of the script (`Q`, `C` criteria with
weights, `O` options with points 1 to 5, pro, con, why, against; `REC` the recommended
index) and the texts in the background block, then pass the whole file as `widget_code`.

## Cost (estimated, not measured)

About 3,000 to 3,500 output tokens per decision and the same amount kept in the session
context, against roughly 300 for the built-in question dialog; it takes 30 to 60 seconds
to stream. A compact generic template would bring it to about 2,000 tokens; the widget
tool takes the code inline, so the script travels with every call.

## Why not a mod pane

A Claude Code mod pane draws only plain elements (`Box`, `Text`, `Button`, `Input`); only
a `Button` takes a click and it holds text only, and an `Svg` is drawn as an image. Rich,
clickable option cards are therefore not possible in a pane; the widget is plain HTML and
is.
