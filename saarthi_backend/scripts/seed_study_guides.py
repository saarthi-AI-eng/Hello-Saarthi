"""Seed one high-quality study guide: Convolution in Signals & Systems."""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from saarthi_backend.model.study_guide_model import StudyGuide, StudyGuidePrompt

logger = logging.getLogger(__name__)

GUIDE_TITLE = "Convolution in Signals & Systems"
GUIDE_DESC  = "End-to-end mastery of convolution — from theory to exam numericals. 6 structured prompts, each building on the previous."

PROMPTS = [
    {
        "step": 1,
        "title": "1. Mathematical Definition & Physical Meaning",
        "text": (
            "**Goal:** Understand the convolution integral from first principles and its physical meaning.\n"
            "**Guardrails:** Focus on continuous-time only. No computation yet — only intuition and definitions.\n"
            "**Methodology:** Define → dissect each term physically → explain the flip-and-slide operation.\n\n"
            "Explain the convolution integral y(t) = x(t) * h(t) = ∫x(τ)h(t−τ)dτ. "
            "What does each variable (τ, t, x, h) represent physically? "
            "Why do we flip h(τ) to get h(−τ) and then shift it? "
            "Relate this to what an LTI system physically does to an input signal."
        ),
    },
    {
        "step": 2,
        "title": "2. Graphical Method — Step by Step",
        "text": (
            "**Goal:** Master the 5-step graphical convolution method for any two signals.\n"
            "**Guardrails:** Use rectangular pulses. Show every step explicitly with the signal sketches described.\n"
            "**Methodology:** For each step — express as τ functions → fold → shift → find overlap regions → integrate per region.\n\n"
            "Use the graphical method to convolve x(t) = u(t) − u(t−1) with h(t) = u(t) − u(t−2). "
            "Explicitly show all 5 steps: "
            "(1) rewrite both as functions of τ, "
            "(2) fold h(τ) to get h(−τ), "
            "(3) shift by t to get h(t−τ), "
            "(4) identify all time regions where overlap exists, "
            "(5) write and evaluate the integral for each region. "
            "Sketch the resulting y(t)."
        ),
    },
    {
        "step": 3,
        "title": "3. Properties of Convolution (with Proofs)",
        "text": (
            "**Goal:** Know all 4 core properties of convolution and be able to prove and apply each.\n"
            "**Guardrails:** Prove each from the integral definition. Give one real signal-processing use case per property.\n"
            "**Methodology:** State property → prove algebraically from definition → show practical application.\n\n"
            "For each of the 4 major convolution properties — "
            "(1) Commutativity: x(t)*h(t) = h(t)*x(t), "
            "(2) Associativity: [x*h1]*h2 = x*[h1*h2], "
            "(3) Distributivity over addition: x*(h1+h2) = x*h1 + x*h2, "
            "(4) Time-shift property — "
            "state the property, prove it directly from the convolution integral, "
            "and give a practical DSP scenario where that property simplifies computation."
        ),
    },
    {
        "step": 4,
        "title": "4. Why LTI Output = Input * Impulse Response",
        "text": (
            "**Goal:** Derive rigorously why y(t) = x(t)*h(t) holds for any LTI system.\n"
            "**Guardrails:** Use only the sifting property, linearity, and time-invariance — no shortcuts.\n"
            "**Methodology:** Decompose input via sifting → apply linearity → apply time-invariance → arrive at convolution.\n\n"
            "Derive from first principles why the output of ANY LTI system equals the convolution of input with impulse response. "
            "Use this exact sequence: "
            "(1) write x(t) = ∫x(τ)δ(t−τ)dτ using the sifting property, "
            "(2) pass x(t) through the system and apply linearity to move the integral outside, "
            "(3) apply time-invariance to replace the system's response to δ(t−τ) with h(t−τ), "
            "(4) conclude y(t) = ∫x(τ)h(t−τ)dτ. "
            "Then explain physically what h(t) tells you about the system."
        ),
    },
    {
        "step": 5,
        "title": "5. Exam Numerical — Exponential Signals",
        "text": (
            "**Goal:** Solve a complete exam-style convolution numerical end-to-end with full algebraic steps.\n"
            "**Guardrails:** Identify all time regions before integrating. Show every integral step. No skipping.\n"
            "**Methodology:** Define regions where u(t) terms are nonzero → write integral for each region → evaluate → sketch.\n\n"
            "Solve completely: Find y(t) = x(t) * h(t) where x(t) = e^{−2t}u(t) and h(t) = e^{−3t}u(t). "
            "Step 1: Identify the time regions based on the unit step functions. "
            "Step 2: Write the convolution integral for each region. "
            "Step 3: Evaluate each integral showing all algebra. "
            "Step 4: Write the final closed-form expression for y(t). "
            "Step 5: Sketch y(t) and describe its peak location and decay behaviour."
        ),
    },
    {
        "step": 6,
        "title": "6. Discrete-Time Convolution Sum",
        "text": (
            "**Goal:** Extend convolution to discrete-time signals and solve using the tabular method.\n"
            "**Guardrails:** Explicitly contrast with continuous-time at each step. Verify answer using polynomial multiplication.\n"
            "**Methodology:** Define sum → explain index flipping → tabular computation → polynomial verification.\n\n"
            "Define the discrete-time convolution sum y[n] = Σ_{k=−∞}^{∞} x[k]h[n−k]. "
            "Contrast with continuous convolution: what changes conceptually (sum vs integral, index flipping)? "
            "Then compute y[n] = x[n] * h[n] for x[n] = {1, 2, 3} (n = 0,1,2) and h[n] = {1, 1} (n = 0,1) "
            "using the tabular (sliding window) method showing all intermediate rows. "
            "Finally verify your answer using the polynomial multiplication method: "
            "treat x[n] coefficients as polynomial X(z) = 1 + 2z^{−1} + 3z^{−2} and multiply by H(z)."
        ),
    },
]


async def seed_study_guides(db: AsyncSession) -> None:
    """Insert the Convolution study guide if it doesn't already exist."""
    try:
        existing = await db.execute(
            select(func.count()).select_from(StudyGuide).where(StudyGuide.title == GUIDE_TITLE)
        )
        if (existing.scalar() or 0) > 0:
            logger.info("study_guides seed: '%s' already exists, skipping", GUIDE_TITLE)
            return

        guide = StudyGuide(title=GUIDE_TITLE, description=GUIDE_DESC, created_by=None)
        db.add(guide)
        await db.flush()
        await db.refresh(guide)

        for p in PROMPTS:
            db.add(StudyGuidePrompt(
                guide_id=guide.id,
                step_number=p["step"],
                title=p["title"],
                prompt_text=p["text"],
            ))

        await db.commit()
        logger.info("study_guides seed: inserted '%s' with %d prompts", GUIDE_TITLE, len(PROMPTS))
    except Exception as e:
        logger.warning("study_guides seed failed: %s", e)
