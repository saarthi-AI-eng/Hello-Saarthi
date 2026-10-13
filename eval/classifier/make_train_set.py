"""Generate the Tier 1 / Tier 2 TRAINING set for the query classifier (spec §4.1).

Labels follow spec §4.1:
  Tier 1  simple / definitional — single-concept lookups, vocabulary, factual recall
  Tier 2  complex / reasoning   — multi-step problems, code debugging, analysis
(Tier 0 is not learned: it is a semantic-cache match against stored queries.)

Training items are template-generated over course topics. The 100-query TEST set
(eval/classifier/tier_test.jsonl) is written by hand with different phrasing so the
score measures generalisation, not template recall. Replace / extend both with real
student queries once Q&A logs exist (spec: "trained on labelled query examples
drawn from past student Q&A logs").

    python eval/classifier/make_train_set.py
"""
import json
import random
from pathlib import Path

random.seed(7)
OUT = Path(__file__).with_name("tier_train.jsonl")

TOPICS = [
    "the Fourier transform", "the Laplace transform", "the Z-transform", "convolution", "the sampling theorem",
    "the Nyquist rate", "aliasing", "the region of convergence", "an LTI system", "the impulse response",
    "the frequency response", "a Bode plot", "the DFT", "the FFT", "an FIR filter", "an IIR filter",
    "a Butterworth filter", "windowing", "BIBO stability", "causality", "the transfer function",
    "poles and zeros", "the Fourier series", "Parseval's theorem", "autocorrelation", "cross-correlation",
    "the unit step function", "the Dirac delta", "linearity", "time invariance", "amplitude modulation",
    "quantization", "decimation", "interpolation", "the bilinear transform", "group delay", "phase response",
    "the convolution sum", "the Gibbs phenomenon", "the inverse Z-transform", "the DTFT", "zero padding",
]
PAIRS = [
    ("the Fourier transform", "the Laplace transform"), ("FIR filters", "IIR filters"), ("the DFT", "the DTFT"),
    ("linear convolution", "circular convolution"), ("the Z-transform", "the DTFT"), ("sampling", "quantization"),
    ("autocorrelation", "cross-correlation"), ("overlap-add", "overlap-save"), ("Butterworth", "Chebyshev filters"),
    ("energy signals", "power signals"), ("causal systems", "stable systems"), ("the FFT", "the direct DFT"),
]
SIGNALS = [
    "x(t) = e^{-2t}u(t)", "x[n] = 0.5^n u[n]", "x(t) = rect(t/T)", "x(t) = cos(5t)", "h(t) = e^{-t}u(t)",
    "x[n] = {1, 2, 3, 4}", "x(t) = t e^{-t} u(t)", "x[n] = u[n] - u[n-4]", "x(t) = sin(100 pi t)",
    "H(s) = (s+1)/(s^2 + 3s + 2)", "H(z) = 1/(1 - 0.8 z^{-1})", "x(t) = e^{-|t|}",
]

T1 = [
    "What is {t}?", "Define {t}.", "What does {t} mean?", "Give the definition of {t}.", "What is the formula for {t}?",
    "what is {t}", "Can you tell me what {t} is?", "Meaning of {t}?", "Briefly, what is {t}?",
    "What is the symbol used for {t}?", "Which lecture covers {t}?", "Is {t} covered in this course?",
    "What is {t} in one line?", "Give a one-sentence definition of {t}.", "Explain {t}.",
    "explain {t} simply", "What is meant by {t}?", "State the definition of {t}.",
]
T1_FIXED = [
    "hi", "hello", "thanks!", "thank you so much", "ok got it", "good morning", "who are you?",
    "What is the unit of frequency?", "What does LTI stand for?", "What is the full form of DFT?",
    "What does ROC stand for?", "What is the sampling frequency?", "Is the Fourier transform linear?",
    "What is j in signals and systems?", "What is omega?", "Who proposed the Fourier series?",
    "What is a discrete-time signal?", "What is a continuous-time signal?", "What is a periodic signal?",
    "What is an even signal?", "What is an odd signal?", "What is the period of cos(2 pi t)?",
    "What is the value of the unit step at t = 0?", "What is the Laplace transform of u(t)?",
    "What is the Fourier transform of the delta function?", "What is a pole?", "What is a zero of H(z)?",
]
T2 = [
    "Derive {t} from first principles.", "Prove the main property of {t} step by step.",
    "Compute {t} for {s}.", "Find {t} of {s} and sketch it.", "Solve: find {t} for {s}.",
    "How do I solve a problem on {t} for {s}?", "Calculate {t} of {s}, showing all steps.",
    "Evaluate {t} for {s} and explain the result.", "Work out {t} for {s}.",
    "Analyze the stability of {s}.", "Determine whether {s} is causal and stable, and justify.",
    "Find the poles and zeros of {s} and comment on stability.", "Find the impulse response of {s}.",
    "Determine the output when {s} is applied to an LTI system with h(t) = e^{{-t}}u(t).",
]
T2_PAIR = [
    "Compare {a} and {b} and explain when to use each.", "What is the difference between {a} and {b}, and why does it matter?",
    "Explain how {a} relates to {b}, with an example.", "Contrast {a} with {b} in terms of complexity and accuracy.",
    "Why would an engineer choose {a} over {b}?",
]
T2_FIXED = [
    "My MATLAB code for the FFT gives 'Index exceeds matrix dimensions', how do I fix it?",
    "My Python convolution result is shifted by one sample, what is wrong with my code?",
    "Why does my filter output blow up when I implement this IIR difference equation in MATLAB?",
    "Debug this: y = conv(x, h) returns the wrong length, why?",
    "My plot of the DFT magnitude looks mirrored, what am I doing wrong in numpy?",
    "Design a low-pass FIR filter with cutoff 1 kHz using the Hamming window and explain each step.",
    "Design a second-order Butterworth low-pass filter and find its poles.",
    "Explain the entire signal processing pipeline from sampling to reconstruction with the key equations.",
    "Walk me through solving a convolution integral of two exponentials.",
    "Using the bilinear transform, convert H(s) = 1/(s+1) to H(z) with T = 1 and explain frequency warping.",
    "Show that convolution in time is multiplication in frequency.",
    "Why does zero padding not increase frequency resolution? Explain with the DFT definition.",
    "If a signal band-limited to 4 kHz is sampled at 6 kHz, what frequencies alias and why?",
    "Analyze how pole locations affect the magnitude and phase response of a second-order system.",
    "Compute the 4-point DFT of x[n] = {1, 0, -1, 0} and then verify with the inverse DFT.",
]


def main():
    items = []
    for t in TOPICS:
        for tmpl in random.sample(T1, 3):
            items.append({"query": tmpl.format(t=t), "tier": 1})
    items += [{"query": q, "tier": 1} for q in T1_FIXED]
    topics2 = ["the Fourier transform", "the Laplace transform", "the Z-transform", "the convolution",
               "the DFT", "the frequency response", "the inverse Z-transform", "the energy", "the autocorrelation"]
    for tmpl in T2:
        for _ in range(5):
            items.append({"query": tmpl.format(t=random.choice(topics2), s=random.choice(SIGNALS)), "tier": 2})
    for a, b in PAIRS:
        for tmpl in random.sample(T2_PAIR, 2):
            items.append({"query": tmpl.format(a=a, b=b), "tier": 2})
    items += [{"query": q, "tier": 2} for q in T2_FIXED]
    uniq = {i["query"]: i for i in items}
    items = list(uniq.values())
    random.shuffle(items)
    with OUT.open("w", encoding="utf-8") as f:
        for i in items:
            f.write(json.dumps(i, ensure_ascii=False) + "\n")
    n1 = sum(i["tier"] == 1 for i in items)
    print(f"{OUT.name}: {len(items)} items (tier1={n1}, tier2={len(items) - n1})")


if __name__ == "__main__":
    main()
