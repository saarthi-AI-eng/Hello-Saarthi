"""Map a question to a course topic name (for the weak-topic list, spec §4.4 / §4.5)."""
from __future__ import annotations

import re

from src.retrieval.bm25 import tokenize

# Longest phrases first so "inverse z-transform" wins over "z-transform".
TOPICS = sorted([
    "fourier transform", "fourier series", "laplace transform", "z-transform", "inverse z-transform",
    "inverse laplace transform", "dtft", "dft", "fft", "convolution", "circular convolution",
    "correlation", "autocorrelation", "sampling", "nyquist", "aliasing", "region of convergence", "roc",
    "lti system", "impulse response", "step response", "frequency response", "bode plot", "transfer function",
    "poles and zeros", "stability", "causality", "fir filter", "iir filter", "butterworth", "chebyshev",
    "window", "bilinear transform", "difference equation", "differential equation", "modulation",
    "quantization", "decimation", "interpolation", "parseval", "energy", "power", "group delay",
    "phase response", "gibbs", "zero padding", "spectral leakage",
], key=len, reverse=True)


def topic_of(text: str) -> str:
    low = (text or "").lower()
    for t in TOPICS:
        if re.search(rf"\b{re.escape(t)}\b", low):
            return t
    words = [w for w in tokenize(low) if len(w) > 3 and not w.isdigit()]
    return " ".join(words[:3]) or "general"
