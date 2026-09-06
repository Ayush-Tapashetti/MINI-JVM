#!/usr/bin/env python3
"""
Convenience script: runs every demo program in programs/ against its
matching sample input in inputs/, and prints the results.

    python3 run_demos.py            # run everything
    python3 run_demos.py sort       # run just programs/sort.jvm
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from jvmsim.loader import load_program
from jvmsim.vm import JVMSimulator

ROOT = os.path.dirname(__file__)
PROGRAMS_DIR = os.path.join(ROOT, "programs")
INPUTS_DIR = os.path.join(ROOT, "inputs")

DEMOS = [
    ("min_max", "min_max.jvm", "min_max_input.txt", 10, 10),
    ("sort", "sort.jvm", "sort_input.txt", 20, 24),
    ("matrix_sum", "matrix_sum.jvm", "matrix_sum_input.txt", 10, 12),
    ("factorial", "factorial.jvm", "factorial_input.txt", 10, 10),
    ("fibonacci", "fibonacci.jvm", "fibonacci_input.txt", 10, 10),
    ("gcd", "gcd.jvm", "gcd_input.txt", 10, 10),
]


def run_one(name, program_file, input_file, stack_size, num_locals):
    program_path = os.path.join(PROGRAMS_DIR, program_file)
    input_path = os.path.join(INPUTS_DIR, input_file)

    instructions = load_program(program_path)
    with open(input_path) as f:
        input_text = f.read()

    vm = JVMSimulator(
        instructions,
        stack_size=stack_size,
        num_locals=num_locals,
        input_stream=io.StringIO(input_text),
        output_stream=io.StringIO(),
    )
    vm.run()

    print(f"=== {name} ===")
    print(f"  program : programs/{program_file}")
    print(f"  input   : {input_text.strip()}")
    print(f"  output  : {' '.join(str(v) for v in vm.printed)}")
    print()


def main():
    requested = sys.argv[1:]
    for name, program_file, input_file, stack_size, num_locals in DEMOS:
        if requested and name not in requested:
            continue
        run_one(name, program_file, input_file, stack_size, num_locals)


if __name__ == "__main__":
    main()
