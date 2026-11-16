"""Seed sample MCQ quizzes on startup so MCQ practice is not empty in a demo.

Each quiz is attached to the first course whose title matches `course`. A quiz is
added only if that course has no quiz with the same title, so this is safe to run
on every startup and never touches quizzes that teachers created.
"""

import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model.course_model import Course
from saarthi_backend.model.quiz_model import Quiz, QuizQuestion
from saarthi_backend.utils.logging import get_logger

logger = get_logger(__name__)

# (question, options, correct index, difficulty, explanation)
_QUIZZES = [
    {
        "course": "DSP",
        "title": "FFT Basics",
        "topic": "Fast Fourier Transform",
        "description": "Radix-2 FFT, twiddle factors and why the FFT is faster than the DFT.",
        "duration": 10,
        "questions": [
            ("How many complex multiplications does a direct N-point DFT need?",
             ["N", "N log2 N", "N^2", "2N"], 2, "recall",
             "Each of the N outputs is a sum of N products, so the direct DFT needs N^2 complex multiplications."),
            ("A radix-2 FFT of N points needs about how many complex multiplications?",
             ["(N/2) log2 N", "N^2 / 2", "N / 2", "N^2 log2 N"], 0, "recall",
             "There are log2 N stages, each with N/2 butterflies and one multiplication per butterfly."),
            ("For N = 1024, roughly how much faster is the radix-2 FFT than the direct DFT (in multiplications)?",
             ["About 2 times", "About 10 times", "About 200 times", "About 1000 times"], 2, "application",
             "N^2 = 1,048,576 and (N/2) log2 N = 512 x 10 = 5,120, a ratio of about 205."),
            ("Which twiddle-factor property does the FFT butterfly use?",
             ["W_N^(k+N/2) = -W_N^k", "W_N^(k+N/2) = W_N^k", "W_N^k = 1 for all k", "W_N^(2k) = 2 W_N^k"], 0, "recall",
             "Symmetry: W_N^(k+N/2) = -W_N^k, so one product serves both outputs of a butterfly."),
            ("Which property of W_N = e^(-j2pi/N) states W_N^(k+N) = W_N^k?",
             ["Symmetry", "Periodicity", "Linearity", "Conjugate symmetry"], 1, "recall",
             "W_N is periodic with period N, so adding N to the exponent gives the same value."),
            ("In decimation-in-time, how is the input sequence split at the first stage?",
             ["First half and second half", "Even-indexed and odd-indexed samples",
              "Positive and negative samples", "Real and imaginary parts"], 1, "application",
             "Decimation in time splits x[n] into x[2m] and x[2m+1] and computes two N/2-point DFTs."),
            ("A signal has 1000 samples. What do you do before a radix-2 FFT?",
             ["Drop samples down to 512", "Zero-pad to 1024 samples", "Repeat the signal twice", "Nothing; any length works"], 1, "analysis",
             "Radix-2 needs a power of two. Zero-padding to 1024 keeps all the data and only interpolates the spectrum."),
        ],
    },
    {
        "course": "DSP",
        "title": "Digital Filters",
        "topic": "Filters",
        "description": "FIR and IIR filters, Butterworth response and stability.",
        "duration": 10,
        "questions": [
            ("Which filter type always has a finite-length impulse response?",
             ["IIR", "FIR", "Butterworth", "Chebyshev"], 1, "recall",
             "FIR (finite impulse response) filters have no feedback, so their impulse response ends after M+1 samples."),
            ("What is the gain of a Butterworth low-pass filter at its cutoff frequency?",
             ["0 dB", "-1 dB", "-3 dB", "-6 dB"], 2, "recall",
             "|H(fc)| = 1/sqrt(2), which is 20 log10(0.707) = -3.01 dB, for any order."),
            ("How fast does an n-th order Butterworth filter roll off far above cutoff?",
             ["6 dB per octave", "20n dB per decade", "3 dB per decade", "It does not roll off"], 1, "application",
             "|H| falls like (fc/f)^n, which is 20n dB per decade (6n dB per octave)."),
            ("A causal IIR filter is stable when its poles are…",
             ["On the unit circle", "Outside the unit circle", "Inside the unit circle", "At the origin only"], 2, "recall",
             "A causal LTI system is BIBO-stable when every pole of H(z) lies strictly inside |z| = 1."),
            ("You need exactly linear phase. Which filter do you choose?",
             ["Symmetric FIR", "Butterworth IIR", "Chebyshev IIR", "Elliptic IIR"], 0, "analysis",
             "An FIR filter with symmetric coefficients has exactly linear phase; IIR filters cannot in real time."),
        ],
    },
    {
        "course": "DSP",
        "title": "Random Variables",
        "topic": "Probability",
        "description": "PDFs, expectation and transformations of random variables.",
        "duration": 10,
        "questions": [
            ("What does the area under a probability density function equal?",
             ["0", "0.5", "1", "It depends on the variable"], 2, "recall",
             "Total probability is 1, so the PDF integrates to 1 over the whole real line."),
            ("If Y = aX + b, what is E[Y]?",
             ["a E[X]", "a E[X] + b", "a^2 E[X] + b", "E[X] + b"], 1, "application",
             "Expectation is linear: E[aX + b] = a E[X] + b."),
            ("If Y = aX + b, what is Var(Y)?",
             ["a Var(X) + b", "a^2 Var(X)", "a^2 Var(X) + b", "Var(X)"], 1, "application",
             "Adding a constant does not change spread, and scaling by a scales variance by a^2."),
            ("X is uniform on [0, 1]. What is P(X <= 0.3)?",
             ["0.3", "0.7", "0.09", "0.5"], 0, "application",
             "For U[0, 1] the CDF is F(x) = x, so P(X <= 0.3) = 0.3."),
        ],
    },
    {
        "course": "Machine Learning",
        "title": "Perceptron and Neural Networks",
        "topic": "Neural Networks",
        "description": "The perceptron, activation functions and gradient descent.",
        "duration": 10,
        "questions": [
            ("What does a single perceptron compute?",
             ["A weighted sum of inputs passed through a step function", "The average of its inputs",
              "A decision tree split", "The k nearest neighbours"], 0, "recall",
             "y = step(w . x + b): a weighted sum plus bias, then a threshold."),
            ("Which problem can a single-layer perceptron NOT solve?",
             ["AND", "OR", "XOR", "NOT"], 2, "analysis",
             "XOR is not linearly separable, so no single straight line separates its classes."),
            ("Why is a non-linear activation needed in hidden layers?",
             ["To make training faster", "Without it, stacked layers collapse into one linear map",
              "To reduce the number of weights", "To normalise the inputs"], 1, "application",
             "A composition of linear layers is still linear; the non-linearity lets the network model curved boundaries."),
            ("In gradient descent, what does the learning rate control?",
             ["The number of layers", "The size of each weight update", "The number of training samples", "The activation function"], 1, "recall",
             "w <- w - eta * dL/dw: the learning rate eta scales every step."),
        ],
    },
]


async def seed_quizzes(session: AsyncSession) -> None:
    added = 0
    for spec in _QUIZZES:
        course = (await session.execute(
            select(Course).where(func.lower(Course.title) == spec["course"].lower()).order_by(Course.id).limit(1)
        )).scalar_one_or_none()
        if course is None:
            continue
        exists = (await session.execute(
            select(Quiz.id).where(Quiz.course_id == course.id, Quiz.title == spec["title"]).limit(1)
        )).scalar_one_or_none()
        if exists:
            continue
        quiz = Quiz(
            course_id=course.id, title=spec["title"], description=spec["description"],
            duration_minutes=spec["duration"], passing_score=60.0, topic=spec["topic"],
        )
        session.add(quiz)
        await session.flush()
        for i, (text, options, correct, difficulty, explanation) in enumerate(spec["questions"]):
            session.add(QuizQuestion(
                quiz_id=quiz.id, question_text=text, options_json=json.dumps(options),
                correct_index=correct, sort_order=i, topic=spec["topic"],
                difficulty=difficulty, explanation=explanation,
            ))
        added += 1
    if added:
        await session.commit()
        logger.info("Seeded %d sample quizzes", added)
