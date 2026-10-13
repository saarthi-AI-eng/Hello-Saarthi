"""Socratic prompt pack (WBS 3.3.1) — FOR EDUCATOR REVIEW.

Two templates, kept separate from code so educators can edit wording without
touching routing logic:

  HINT_TEMPLATE    used while the student is still working the problem
  REVEAL_TEMPLATE  used after MAX_HINTS hints (spec 4.4: "after 3 failed
                   attempts, more direct") or when the student asks for it

{level} is 1..MAX_HINTS, {max_hints} the cap, {hints_given} the hints already given.
"""

HINT_LEVELS = {
    1: "Name the concept or principle the problem rests on and ask ONE guiding question "
       "that points the student toward the first step. Do not write any equations of the solution.",
    2: "Point to the specific formula, property or table entry to use and show how to set up the "
       "first step only. Ask the student to carry it out.",
    3: "Work the first part of the solution explicitly, then stop and ask the student to finish "
       "the remaining step(s). Do not state the final result.",
}

HINT_TEMPLATE = """SOCRATIC MODE — hint {level} of {max_hints}. Help the student solve it themselves.
- Never give the final answer or the full worked solution.
- {level_instruction}
- If the student tried an answer, say if it is right; if not, point to where the reasoning slips.
- Under 150 words; end with exactly one question. Keep $...$ math."""

REVEAL_TEMPLATE = """DIRECT MODE — after {hints_given} hint(s) (or on request): give the complete step-by-step
solution with each step justified, then one line "Key idea:" for similar problems."""
