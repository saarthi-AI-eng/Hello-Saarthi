"""Seed coding lab problems on startup if the table is empty."""

import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saarthi_backend.model.code_problem_model import CodeProblem

_PROBLEMS = [
    {
        "title": "Butterworth Low-Pass Filter",
        "difficulty": "medium",
        "points": 50,
        "description": "Implement a Butterworth low-pass filter and print its frequency response in dB at key frequencies.",
        "requirements": [
            "Order: 4",
            "Cutoff frequency: 1000 Hz",
            "Evaluate at 0, 500, 1000, 2000, 4000 Hz",
            "Print magnitude table (dB vs Hz)",
            "Show -3dB point at cutoff",
        ],
        "expected_output": (
            "Freq (Hz) | Magnitude (dB)\n"
            "       0  |   0.00\n"
            "     500  |  -0.97\n"
            "    1000  |  -3.01\n"
            "    2000  | -18.06\n"
            "    4000  | -48.13"
        ),
        "hints": [
            "H(f) = 1 / sqrt(1 + (f/fc)^(2n))",
            "Use 20*log10() to convert to dB",
            "numpy linspace for frequency array",
        ],
        "starter_code": {
            "python": (
                "import numpy as np\n\n"
                "# Butterworth Low-Pass Filter\n"
                "def butterworth_magnitude(f, cutoff=1000, order=4):\n"
                "    return 1 / np.sqrt(1 + (f / cutoff) ** (2 * order))\n\n"
                "# TODO: compute frequency response and print table\n"
                "freqs = [0, 500, 1000, 2000, 4000]\n"
            )
        },
        "topics": "DSP · Filters",
        "sort_order": 1,
    },
    {
        "title": "DFT from Scratch",
        "difficulty": "hard",
        "points": 100,
        "description": (
            "Implement the Discrete Fourier Transform (DFT) from scratch without using numpy.fft. "
            "Compute the DFT of a simple signal and print the magnitude spectrum."
        ),
        "requirements": [
            "Implement DFT using the definition: X[k] = sum(x[n] * e^(-j2πkn/N))",
            "Input: x = [1, 2, 3, 4] (N=4)",
            "Print magnitude |X[k]| for k=0,1,2,3",
            "Round to 2 decimal places",
        ],
        "expected_output": (
            "|X[0]| = 10.00\n"
            "|X[1]| =  2.83\n"
            "|X[2]| =  2.00\n"
            "|X[3]| =  2.83"
        ),
        "hints": [
            "Use cmath.exp for complex exponential",
            "e^(-j2πkn/N) = cos(2πkn/N) - j*sin(2πkn/N)",
            "Magnitude = abs(complex number)",
        ],
        "starter_code": {
            "python": (
                "import cmath\n"
                "import math\n\n"
                "x = [1, 2, 3, 4]\n"
                "N = len(x)\n\n"
                "# TODO: implement DFT\n"
                "# X[k] = sum over n of x[n] * e^(-j*2*pi*k*n/N)\n"
            )
        },
        "topics": "DSP · Fourier Analysis",
        "sort_order": 2,
    },
    {
        "title": "Linear Regression Gradient Descent",
        "difficulty": "medium",
        "points": 75,
        "description": (
            "Implement linear regression using gradient descent from scratch. "
            "Find the best-fit line for the given data points."
        ),
        "requirements": [
            "Data: x=[1,2,3,4,5], y=[2,4,5,4,5]",
            "Learning rate: 0.01",
            "Iterations: 1000",
            "Print final slope and intercept (2 decimal places)",
            "Print final MSE",
        ],
        "expected_output": (
            "Slope: 0.60\n"
            "Intercept: 2.20\n"
            "MSE: 0.56"
        ),
        "hints": [
            "MSE = mean((y_pred - y_true)^2)",
            "Gradient for slope: mean((y_pred - y)*x)",
            "Gradient for intercept: mean(y_pred - y)",
            "Update: param -= learning_rate * gradient",
        ],
        "starter_code": {
            "python": (
                "x = [1, 2, 3, 4, 5]\n"
                "y = [2, 4, 5, 4, 5]\n\n"
                "slope = 0.0\n"
                "intercept = 0.0\n"
                "lr = 0.01\n"
                "n = len(x)\n\n"
                "# TODO: implement gradient descent\n"
                "for i in range(1000):\n"
                "    pass  # compute predictions, gradients, update\n\n"
                'print(f"Slope: {slope:.2f}")\n'
                'print(f"Intercept: {intercept:.2f}")\n'
            )
        },
        "topics": "ML · Regression",
        "sort_order": 3,
    },
    {
        "title": "Binary Search",
        "difficulty": "easy",
        "points": 25,
        "description": (
            "Implement binary search to find a target in a sorted array. "
            "Return the index, or -1 if not found."
        ),
        "requirements": [
            "Input: arr=[1,3,5,7,9,11,13,15], target=7",
            "Return the index of target (0-based)",
            "Print: 'Found at index: X' or 'Not found'",
            "Must run in O(log n) time",
        ],
        "expected_output": "Found at index: 3",
        "hints": [
            "Maintain left and right pointers",
            "mid = (left + right) // 2",
            "If arr[mid] == target, return mid",
            "Narrow the search space each iteration",
        ],
        "starter_code": {
            "python": (
                "def binary_search(arr, target):\n"
                "    left, right = 0, len(arr) - 1\n"
                "    # TODO: implement binary search\n"
                "    return -1\n\n"
                "arr = [1, 3, 5, 7, 9, 11, 13, 15]\n"
                "target = 7\n"
                "result = binary_search(arr, target)\n"
                'print(f"Found at index: {result}" if result != -1 else "Not found")\n'
            )
        },
        "topics": "Algorithms · Search",
        "sort_order": 4,
    },
]


async def seed_code_problems(db: AsyncSession) -> None:
    """Insert seed problems if the saarthi_code_problems table is empty."""
    count_result = await db.execute(select(func.count()).select_from(CodeProblem))
    count = count_result.scalar_one()
    if count > 0:
        return

    for p in _PROBLEMS:
        problem = CodeProblem(
            title=p["title"],
            difficulty=p["difficulty"],
            points=p["points"],
            description=p["description"],
            requirements_json=json.dumps(p["requirements"]),
            expected_output=p["expected_output"],
            hints_json=json.dumps(p["hints"]),
            starter_code_json=json.dumps(p["starter_code"]),
            topics=p["topics"],
            sort_order=p["sort_order"],
        )
        db.add(problem)

    await db.commit()
