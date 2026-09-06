"""
Loader for the mini JVM bytecode "assembly" text format used by this
simulator.

File format
-----------
* One instruction per line.
* Blank lines and lines starting with ``#`` or ``//`` are ignored (comments).
* Inline comments after an instruction (``iadd   # add them``) are stripped.
* A line consisting of just ``name:`` declares a *label* that later
  branch/goto instructions can target. Labels make writing loops far more
  pleasant than hand-computing raw byte offsets, which is why the loader
  resolves them into concrete instruction indices before execution starts
  (this is the "additional feature" beyond the bare JVM spec: real JVM
  bytecode uses raw offsets, we use symbolic labels and resolve them here).
* Instructions that take an operand are written as ``opcode operand``,
  e.g. ``ldc 42`` or ``istore 3`` or ``ifgt LOOP_END``.
* Instructions without an operand are written alone, e.g. ``iadd``.

Two passes are used:
  1. Scan every line, recording the index (in the final instruction list)
     at which each label appears.
  2. Build the final ``Instruction`` list, replacing any label operand on
     a branch instruction with its resolved integer index.
"""

from dataclasses import dataclass
from typing import List, Optional, Union

from .errors import ParseError, LabelError

# Instructions that take a single integer operand that is NOT a label
INT_OPERAND_OPS = {"ldc", "iload", "istore", "iinc"}

# Instructions that take a label operand (control flow)
BRANCH_OPS = {
    "ifeq", "ifne", "iflt", "ifgt", "ifle", "ifge",
    "if_icmpeq", "if_icmpne", "if_icmplt", "if_icmpgt",
    "if_icmple", "if_icmpge",
    "goto",
}

# Instructions that take no operand at all
# (newarray/iaload/iastore take all their arguments from the operand
# stack -- size, array-ref, index, value -- rather than as a literal
# baked into the instruction, exactly like `iadd` takes its two operands
# from the stack rather than from the instruction text. That's what
# makes them "indirect": the index/size can be a runtime-computed value,
# not just a constant written in the source file.)
NO_OPERAND_OPS = {
    "iadd", "isub", "imul", "idiv", "irem", "ineg",
    "dup", "pop", "swap", "nop",
    "read", "print",
    "newarray", "iaload", "iastore",
}

ALL_OPS = INT_OPERAND_OPS | BRANCH_OPS | NO_OPERAND_OPS

# iinc takes TWO integer operands: local index and constant delta
TWO_INT_OPERAND_OPS = {"iinc"}


@dataclass
class Instruction:
    opcode: str
    # operand can be: None, a single int, a resolved branch target (int),
    # or (for iinc) a tuple of two ints.
    operand: Optional[Union[int, tuple]]
    line_no: int          # original source line number, for error messages
    raw: str               # original source line, for disassembly/debug output


def _strip_comment(line: str) -> str:
    for marker in ("#", "//"):
        idx = line.find(marker)
        if idx != -1:
            line = line[:idx]
    return line.strip()


def load_program(path: str) -> List[Instruction]:
    """Read a bytecode text file and return a resolved list of Instructions."""
    with open(path, "r") as f:
        raw_lines = f.readlines()
    return parse_program(raw_lines)


def parse_program(raw_lines: List[str]) -> List[Instruction]:
    # ---- Pass 1: strip comments/blank lines, find labels ----
    cleaned = []  # list of (original_line_no, text)
    for i, line in enumerate(raw_lines, start=1):
        text = _strip_comment(line)
        if not text:
            continue
        cleaned.append((i, text))

    labels = {}
    body = []  # entries that are actual instructions (label lines removed)
    for line_no, text in cleaned:
        if text.endswith(":") and " " not in text[:-1] and "\t" not in text[:-1]:
            label_name = text[:-1].strip()
            if not label_name:
                raise ParseError(f"Line {line_no}: empty label name")
            if label_name in labels:
                raise ParseError(f"Line {line_no}: duplicate label '{label_name}'")
            labels[label_name] = len(body)  # points at the NEXT instruction
        else:
            body.append((line_no, text))

    # ---- Pass 2: build Instruction objects, resolving branch targets ----
    instructions: List[Instruction] = []
    for line_no, text in body:
        parts = text.split(None, 1)
        opcode = parts[0].lower()
        operand_str = parts[1].strip() if len(parts) > 1 else None

        if opcode not in ALL_OPS:
            raise ParseError(f"Line {line_no}: unknown opcode '{opcode}'")

        if opcode in NO_OPERAND_OPS:
            if operand_str:
                raise ParseError(
                    f"Line {line_no}: '{opcode}' does not take an operand "
                    f"(got '{operand_str}')"
                )
            operand = None

        elif opcode in TWO_INT_OPERAND_OPS:
            if not operand_str:
                raise ParseError(f"Line {line_no}: '{opcode}' requires two operands")
            bits = operand_str.split()
            if len(bits) != 2:
                raise ParseError(
                    f"Line {line_no}: '{opcode}' requires exactly two integer "
                    f"operands (local index, delta)"
                )
            try:
                operand = (int(bits[0]), int(bits[1]))
            except ValueError:
                raise ParseError(f"Line {line_no}: '{opcode}' operands must be integers")

        elif opcode in INT_OPERAND_OPS:
            if operand_str is None:
                raise ParseError(f"Line {line_no}: '{opcode}' requires an integer operand")
            try:
                operand = int(operand_str)
            except ValueError:
                raise ParseError(
                    f"Line {line_no}: '{opcode}' operand must be an integer "
                    f"(got '{operand_str}')"
                )

        elif opcode in BRANCH_OPS:
            if not operand_str:
                raise ParseError(f"Line {line_no}: '{opcode}' requires a label operand")
            target_label = operand_str
            if target_label not in labels:
                raise LabelError(
                    f"Line {line_no}: '{opcode}' targets undefined label "
                    f"'{target_label}'"
                )
            operand = labels[target_label]  # resolved instruction index
        else:  # pragma: no cover - defensive, ALL_OPS covers every case above
            raise ParseError(f"Line {line_no}: unhandled opcode '{opcode}'")

        instructions.append(Instruction(opcode, operand, line_no, text))

    return instructions
