"""
Custom exceptions used by the JVM bytecode simulator.

Keeping these separate from the VM logic makes error handling in the
CLI (and in unit tests) explicit and easy to reason about.
"""


class SimulatorError(Exception):
    """Base class for all simulator-related errors."""


class ParseError(SimulatorError):
    """Raised when the bytecode source file cannot be parsed."""


class LabelError(ParseError):
    """Raised when a branch/goto instruction targets an unknown label."""


class StackUnderflowError(SimulatorError):
    """Raised when an instruction needs more operands than are on the stack."""


class StackOverflowError(SimulatorError):
    """Raised when a push would exceed the configured operand stack size."""


class InvalidLocalError(SimulatorError):
    """Raised when an instruction addresses a local variable slot that
    does not exist (negative index or beyond the configured register set)."""


class DivisionByZeroError(SimulatorError):
    """Raised by idiv / irem when the divisor is zero."""


class UninitializedLocalError(SimulatorError):
    """Raised when iload reads a local variable that was never stored to."""


class InputExhaustedError(SimulatorError):
    """Raised when `read` needs an integer but the input stream has none left."""


class NegativeArraySizeError(SimulatorError):
    """Raised when `newarray` is asked to allocate an array of negative size."""


class ArrayIndexOutOfBoundsError(SimulatorError):
    """Raised when `iaload`/`iastore` uses an index outside [0, array length)."""


class InvalidArrayReferenceError(SimulatorError):
    """Raised when `iaload`/`iastore` is given a value that isn't a live
    array reference (e.g. a plain integer that was never returned by
    `newarray`, or an array reference that's already out of scope)."""
