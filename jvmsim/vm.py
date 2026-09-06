"""
The mini-JVM virtual machine itself.

Design notes
------------
* The operand stack and local variable ("register") array are both
  fixed-size Python lists, defaulting to 10 slots each, per the
  assignment spec. Both sizes are configurable (`stack_size`,
  `num_locals`) since real programs may need more headroom -- the
  spec explicitly allows this ("you may use a larger size, if you need it").
* `print` is *non-destructive by default is NOT what we chose* -- to keep
  stack hygiene simple and predictable (and to mirror how a real
  `invokevirtual println(I)V` call would consume its argument), `print`
  POPS the top of stack after printing it. This is documented here and in
  the project docs so it isn't a surprise when writing bytecode: if you
  want to print a value and keep using it, `dup` before `print`.
* `read` pushes one integer read from the configured input source.
* All the arithmetic/branch instructions match the semantics described in
  the JVM spec (section 6.5) for the equivalent `i*` opcodes, restricted
  to 32-bit-ish Python ints (we don't emulate overflow/wraparound).
* `newarray` / `iaload` / `iastore` add real, INDIRECTLY-addressed
  arrays: the index is popped off the operand stack at runtime, unlike
  `iload`/`istore` whose index is a constant baked into the instruction.
  This is what the base `ldc/iload/istore/...` subset from the
  assignment is missing, and its absence is why programs like sorting a
  runtime-variable number of elements otherwise require unrolling every
  possible loop iteration ahead of time (see programs/sort.jvm's history
  / tools/generate_sort_program.py, kept for reference, versus the new
  loop-based programs/sort.jvm that uses these opcodes instead).
  Arrays are modelled as a small table (`self.arrays`) mapping an
  integer "array reference" (returned by `newarray`, just like the JVM
  returns an object reference) to a live Python list.
"""

from typing import List, Optional, Callable, TextIO, Dict
import sys

from .loader import Instruction
from .errors import (
    StackUnderflowError,
    StackOverflowError,
    InvalidLocalError,
    DivisionByZeroError,
    UninitializedLocalError,
    InputExhaustedError,
    NegativeArraySizeError,
    ArrayIndexOutOfBoundsError,
    InvalidArrayReferenceError,
)

_UNINITIALIZED = object()  # sentinel for a local slot that was never stored to


class JVMSimulator:
    def __init__(
        self,
        instructions: List[Instruction],
        stack_size: int = 10,
        num_locals: int = 10,
        input_stream: Optional[TextIO] = None,
        output_stream: Optional[TextIO] = None,
        trace: bool = False,
    ):
        self.instructions = instructions
        self.stack_size = stack_size
        self.num_locals = num_locals
        self.input_stream = input_stream if input_stream is not None else sys.stdin
        self.output_stream = output_stream if output_stream is not None else sys.stdout
        self.trace = trace

        self.stack: List[int] = []
        self.locals: List = [_UNINITIALIZED] * num_locals
        self.pc = 0
        self.printed: List[int] = []   # everything `print` has emitted, for tests
        self.steps = 0

        # array reference (int) -> live Python list of ints, backing
        # `newarray`/`iaload`/`iastore`. References start at 1 so that
        # 0 is never a valid array reference (mirrors `null` being 0/None
        # in real JVMs, and lets a program deliberately push 0 to signal
        # "no array" if it wants to, without that ever colliding with a
        # real reference).
        self.arrays: Dict[int, List[int]] = {}
        self._next_arrayref = 1

        # a small buffer of tokens pulled from input_stream, so `read`
        # can consume whitespace-separated integers regardless of how many
        # appear per line
        self._input_tokens: List[str] = []

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _push(self, value: int):
        if len(self.stack) >= self.stack_size:
            raise StackOverflowError(
                f"Operand stack overflow (limit={self.stack_size}) at pc={self.pc}"
            )
        self.stack.append(value)

    def _pop(self) -> int:
        if not self.stack:
            raise StackUnderflowError(f"Operand stack underflow at pc={self.pc}")
        return self.stack.pop()

    def _peek(self) -> int:
        if not self.stack:
            raise StackUnderflowError(f"Operand stack underflow at pc={self.pc}")
        return self.stack[-1]

    def _check_local_index(self, index: int):
        if index < 0 or index >= self.num_locals:
            raise InvalidLocalError(
                f"Local variable index {index} out of range "
                f"(register set size={self.num_locals}) at pc={self.pc}"
            )

    def _resolve_array(self, arrayref: int) -> List[int]:
        if arrayref not in self.arrays:
            raise InvalidArrayReferenceError(
                f"{arrayref} is not a live array reference at pc={self.pc} "
                f"(did you push a plain integer instead of a newarray result?)"
            )
        return self.arrays[arrayref]

    def _next_input_token(self) -> str:
        while not self._input_tokens:
            line = self.input_stream.readline()
            if line == "":
                raise InputExhaustedError(
                    "`read` requires an integer but input is exhausted"
                )
            self._input_tokens = line.split()
        return self._input_tokens.pop(0)

    # ------------------------------------------------------------------
    # execution
    # ------------------------------------------------------------------
    def run(self, max_steps: int = 2_000_000):
        """Execute the loaded program until it falls off the end.

        max_steps guards against runaway/infinite loops in buggy or
        malicious bytecode; it is generous enough for any legitimate
        program in this instruction subset.
        """
        while self.pc < len(self.instructions):
            self.steps += 1
            if self.steps > max_steps:
                raise RuntimeError(
                    f"Execution exceeded {max_steps} steps -- possible infinite loop"
                )
            instr = self.instructions[self.pc]
            if self.trace:
                print(
                    f"[trace] pc={self.pc:<4} {instr.opcode:<10} "
                    f"{instr.operand if instr.operand is not None else '':<6} "
                    f"stack={self.stack} locals={self._printable_locals()}",
                    file=sys.stderr,
                )
            self._execute(instr)
        return self

    def _printable_locals(self):
        return [
            "_" if v is _UNINITIALIZED else v
            for v in self.locals
        ]

    def _execute(self, instr: Instruction):
        op = instr.opcode
        next_pc = self.pc + 1  # default: fall through to next instruction

        if op == "ldc":
            self._push(instr.operand)

        elif op == "iload":
            self._check_local_index(instr.operand)
            val = self.locals[instr.operand]
            if val is _UNINITIALIZED:
                raise UninitializedLocalError(
                    f"iload {instr.operand}: local variable was never "
                    f"initialized (at pc={self.pc})"
                )
            self._push(val)

        elif op == "istore":
            self._check_local_index(instr.operand)
            self.locals[instr.operand] = self._pop()

        elif op == "iinc":
            local_idx, delta = instr.operand
            self._check_local_index(local_idx)
            val = self.locals[local_idx]
            if val is _UNINITIALIZED:
                raise UninitializedLocalError(
                    f"iinc {local_idx}: local variable was never initialized"
                )
            self.locals[local_idx] = val + delta

        elif op == "iadd":
            b, a = self._pop(), self._pop()
            self._push(a + b)
        elif op == "isub":
            b, a = self._pop(), self._pop()
            self._push(a - b)
        elif op == "imul":
            b, a = self._pop(), self._pop()
            self._push(a * b)
        elif op == "idiv":
            b, a = self._pop(), self._pop()
            if b == 0:
                raise DivisionByZeroError(f"idiv by zero at pc={self.pc}")
            # Truncate toward zero, like Java integer division
            q = abs(a) // abs(b)
            if (a < 0) != (b < 0):
                q = -q
            self._push(q)
        elif op == "irem":
            b, a = self._pop(), self._pop()
            if b == 0:
                raise DivisionByZeroError(f"irem by zero at pc={self.pc}")
            r = abs(a) % abs(b)
            if a < 0:
                r = -r
            self._push(r)
        elif op == "ineg":
            self._push(-self._pop())

        elif op == "dup":
            self._push(self._peek())
        elif op == "pop":
            self._pop()
        elif op == "swap":
            b, a = self._pop(), self._pop()
            self._push(b)
            self._push(a)
        elif op == "nop":
            pass

        elif op == "newarray":
            size = self._pop()
            if size < 0:
                raise NegativeArraySizeError(
                    f"newarray: negative size {size} at pc={self.pc}"
                )
            ref = self._next_arrayref
            self._next_arrayref += 1
            self.arrays[ref] = [0] * size
            self._push(ref)

        elif op == "iaload":
            index = self._pop()
            arrayref = self._pop()
            arr = self._resolve_array(arrayref)
            if not (0 <= index < len(arr)):
                raise ArrayIndexOutOfBoundsError(
                    f"iaload: index {index} out of bounds for array of "
                    f"length {len(arr)} at pc={self.pc}"
                )
            self._push(arr[index])

        elif op == "iastore":
            value = self._pop()
            index = self._pop()
            arrayref = self._pop()
            arr = self._resolve_array(arrayref)
            if not (0 <= index < len(arr)):
                raise ArrayIndexOutOfBoundsError(
                    f"iastore: index {index} out of bounds for array of "
                    f"length {len(arr)} at pc={self.pc}"
                )
            arr[index] = value

        elif op == "read":
            token = self._next_input_token()
            try:
                self._push(int(token))
            except ValueError:
                raise InputExhaustedError(f"`read` expected an integer, got '{token}'")

        elif op == "print":
            val = self._pop()
            self.printed.append(val)
            print(val, file=self.output_stream)

        elif op in (
            "ifeq", "ifne", "iflt", "ifgt", "ifle", "ifge",
        ):
            val = self._pop()
            taken = {
                "ifeq": val == 0,
                "ifne": val != 0,
                "iflt": val < 0,
                "ifgt": val > 0,
                "ifle": val <= 0,
                "ifge": val >= 0,
            }[op]
            if taken:
                next_pc = instr.operand

        elif op in (
            "if_icmpeq", "if_icmpne", "if_icmplt",
            "if_icmpgt", "if_icmple", "if_icmpge",
        ):
            b, a = self._pop(), self._pop()
            taken = {
                "if_icmpeq": a == b,
                "if_icmpne": a != b,
                "if_icmplt": a < b,
                "if_icmpgt": a > b,
                "if_icmple": a <= b,
                "if_icmpge": a >= b,
            }[op]
            if taken:
                next_pc = instr.operand

        elif op == "goto":
            next_pc = instr.operand

        else:  # pragma: no cover - loader already rejects unknown opcodes
            raise RuntimeError(f"Unimplemented opcode '{op}'")

        self.pc = next_pc
