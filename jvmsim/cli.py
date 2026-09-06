"""
Command-line entry point.

Usage:
    python -m jvmsim run programs/min_max.jvm
    python -m jvmsim run programs/sort.jvm --input inputs/sort_input.txt
    python -m jvmsim run programs/min_max.jvm --stack-size 10 --locals 10 --trace
    python -m jvmsim disasm programs/min_max.jvm
"""

import argparse
import sys

from .loader import load_program
from .vm import JVMSimulator
from .errors import SimulatorError, ParseError


def _cmd_run(args):
    try:
        instructions = load_program(args.program)
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 1

    input_stream = sys.stdin
    opened_file = None
    if args.input:
        opened_file = open(args.input, "r")
        input_stream = opened_file

    vm = JVMSimulator(
        instructions,
        stack_size=args.stack_size,
        num_locals=args.locals,
        input_stream=input_stream,
        trace=args.trace,
    )
    try:
        vm.run()
    except SimulatorError as e:
        print(f"Runtime error: {e}", file=sys.stderr)
        return 1
    finally:
        if opened_file:
            opened_file.close()
    return 0


def _cmd_disasm(args):
    try:
        instructions = load_program(args.program)
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return 1
    for i, instr in enumerate(instructions):
        operand = "" if instr.operand is None else str(instr.operand)
        print(f"{i:>4}: {instr.opcode:<12} {operand}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="jvmsim",
        description="A tiny Java-bytecode-subset simulator (pure Python).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Execute a bytecode program")
    p_run.add_argument("program", help="Path to the .jvm bytecode source file")
    p_run.add_argument(
        "--input", "-i", default=None,
        help="File to read `read` instruction input from (default: stdin)"
    )
    p_run.add_argument(
        "--stack-size", type=int, default=10,
        help="Operand stack size (default: 10, per assignment spec)"
    )
    p_run.add_argument(
        "--locals", type=int, default=10,
        help="Number of local variable slots / registers (default: 10)"
    )
    p_run.add_argument(
        "--trace", action="store_true",
        help="Print a step-by-step execution trace to stderr"
    )
    p_run.set_defaults(func=_cmd_run)

    p_dis = sub.add_parser("disasm", help="Print resolved instructions (labels -> indices)")
    p_dis.add_argument("program", help="Path to the .jvm bytecode source file")
    p_dis.set_defaults(func=_cmd_disasm)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
