"""
Unit tests for jvmsim.

Run with:  python -m pytest tests/    (or)   python -m unittest discover tests
"""

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jvmsim.loader import parse_program, load_program
from jvmsim.vm import JVMSimulator
from jvmsim import errors

PROGRAMS_DIR = os.path.join(os.path.dirname(__file__), "..", "programs")


def run_source(source_text, input_text="", stack_size=10, num_locals=10):
    """Helper: parse `source_text`, run it with `input_text` fed to `read`,
    and return the list of values printed."""
    instructions = parse_program(source_text.splitlines())
    vm = JVMSimulator(
        instructions,
        stack_size=stack_size,
        num_locals=num_locals,
        input_stream=io.StringIO(input_text),
        output_stream=io.StringIO(),  # swallow stdout noise during tests
    )
    vm.run()
    return vm.printed


def run_file(filename, input_text, stack_size=20, num_locals=24):
    path = os.path.join(PROGRAMS_DIR, filename)
    instructions = load_program(path)
    vm = JVMSimulator(
        instructions,
        stack_size=stack_size,
        num_locals=num_locals,
        input_stream=io.StringIO(input_text),
        output_stream=io.StringIO(),
    )
    vm.run()
    return vm.printed


class TestBasicInstructions(unittest.TestCase):
    def test_ldc_print(self):
        self.assertEqual(run_source("ldc 42\nprint"), [42])

    def test_arithmetic(self):
        self.assertEqual(run_source("ldc 3\nldc 4\niadd\nprint"), [7])
        self.assertEqual(run_source("ldc 10\nldc 4\nisub\nprint"), [6])
        self.assertEqual(run_source("ldc 6\nldc 7\nimul\nprint"), [42])
        self.assertEqual(run_source("ldc 17\nldc 5\nidiv\nprint"), [3])
        self.assertEqual(run_source("ldc 17\nldc 5\nirem\nprint"), [2])

    def test_negative_division_truncates_toward_zero(self):
        # Java: -7 / 2 == -3   (truncation, not floor)
        self.assertEqual(run_source("ldc -7\nldc 2\nidiv\nprint"), [-3])
        self.assertEqual(run_source("ldc -7\nldc 2\nirem\nprint"), [-1])

    def test_ineg(self):
        self.assertEqual(run_source("ldc 5\nineg\nprint"), [-5])

    def test_locals(self):
        src = "ldc 99\nistore 0\niload 0\nprint"
        self.assertEqual(run_source(src), [99])

    def test_iinc(self):
        src = "ldc 5\nistore 0\niinc 0 3\niload 0\nprint"
        self.assertEqual(run_source(src), [8])

    def test_dup_pop_swap(self):
        self.assertEqual(run_source("ldc 5\ndup\niadd\nprint"), [10])
        self.assertEqual(run_source("ldc 5\nldc 9\npop\nprint"), [5])
        self.assertEqual(run_source("ldc 1\nldc 2\nswap\nisub\nprint"), [1])  # 2-1

    def test_read(self):
        self.assertEqual(run_source("read\nprint", input_text="123"), [123])

    def test_read_multiple_per_line(self):
        self.assertEqual(
            run_source("read\nread\niadd\nprint", input_text="3 4"), [7]
        )

    def test_newarray_iastore_iaload(self):
        src = """
        ldc 5
        newarray
        istore 0
        iload 0
        ldc 2
        ldc 77
        iastore
        iload 0
        ldc 2
        iaload
        print
        """
        self.assertEqual(run_source(src), [77])

    def test_array_defaults_to_zero(self):
        src = "ldc 3\nnewarray\nistore 0\niload 0\nldc 0\niaload\nprint"
        self.assertEqual(run_source(src), [0])

    def test_array_index_out_of_bounds(self):
        src = "ldc 3\nnewarray\nistore 0\niload 0\nldc 5\niaload"
        with self.assertRaises(errors.ArrayIndexOutOfBoundsError):
            run_source(src)

    def test_array_negative_size(self):
        with self.assertRaises(errors.NegativeArraySizeError):
            run_source("ldc -1\nnewarray")

    def test_invalid_array_reference(self):
        # 999 was never returned by newarray, so it isn't a live array ref
        with self.assertRaises(errors.InvalidArrayReferenceError):
            run_source("ldc 999\nldc 0\niaload")


class TestBranches(unittest.TestCase):
    def test_ifeq_taken(self):
        src = "ldc 0\nifeq L\nldc 1\nprint\ngoto END\nL:\nldc 2\nprint\nEND:"
        self.assertEqual(run_source(src), [2])

    def test_ifeq_not_taken(self):
        src = "ldc 5\nifeq L\nldc 1\nprint\ngoto END\nL:\nldc 2\nprint\nEND:"
        self.assertEqual(run_source(src), [1])

    def test_iflt_ifgt(self):
        self.assertEqual(
            run_source("ldc -1\niflt L\nldc 0\nprint\ngoto E\nL:\nldc 1\nprint\nE:"),
            [1],
        )
        self.assertEqual(
            run_source("ldc 5\nifgt L\nldc 0\nprint\ngoto E\nL:\nldc 1\nprint\nE:"),
            [1],
        )

    def test_if_icmp_family(self):
        self.assertEqual(
            run_source("ldc 3\nldc 5\nif_icmplt L\nldc 0\nprint\ngoto E\nL:\nldc 1\nprint\nE:"),
            [1],
        )

    def test_loop_sum_1_to_5(self):
        src = """
        ldc 0
        istore 0     # sum
        ldc 1
        istore 1     # i
        LOOP:
        iload 1
        ldc 6
        if_icmpge END
        iload 0
        iload 1
        iadd
        istore 0
        iinc 1 1
        goto LOOP
        END:
        iload 0
        print
        """
        self.assertEqual(run_source(src), [15])  # 1+2+3+4+5


class TestErrorHandling(unittest.TestCase):
    def test_unknown_opcode(self):
        with self.assertRaises(errors.ParseError):
            parse_program(["frobnicate 1"])

    def test_undefined_label(self):
        with self.assertRaises(errors.LabelError):
            parse_program(["goto NOPE"])

    def test_duplicate_label(self):
        with self.assertRaises(errors.ParseError):
            parse_program(["A:", "ldc 1", "A:", "print"])

    def test_stack_underflow(self):
        with self.assertRaises(errors.StackUnderflowError):
            run_source("iadd")

    def test_stack_overflow(self):
        src = "\n".join(["ldc 1"] * 11)
        with self.assertRaises(errors.StackOverflowError):
            run_source(src, stack_size=10)

    def test_division_by_zero(self):
        with self.assertRaises(errors.DivisionByZeroError):
            run_source("ldc 5\nldc 0\nidiv")

    def test_invalid_local_index(self):
        with self.assertRaises(errors.InvalidLocalError):
            run_source("ldc 1\nistore 99", num_locals=10)

    def test_uninitialized_local(self):
        with self.assertRaises(errors.UninitializedLocalError):
            run_source("iload 5", num_locals=10)

    def test_input_exhausted(self):
        with self.assertRaises(errors.InputExhaustedError):
            run_source("read", input_text="")


class TestRequiredPrograms(unittest.TestCase):
    """End-to-end tests for the three required task programs."""

    # ---- (a) min/max of three integers ----
    def test_min_max_typical(self):
        self.assertEqual(run_file("min_max.jvm", "7 3 9"), [3, 9])

    def test_min_max_all_equal(self):
        self.assertEqual(run_file("min_max.jvm", "5 5 5"), [5, 5])

    def test_min_max_negatives(self):
        self.assertEqual(run_file("min_max.jvm", "-4 10 -20"), [-20, 10])

    def test_min_max_descending(self):
        self.assertEqual(run_file("min_max.jvm", "9 5 1"), [1, 9])

    # ---- (b) sort n integers ----
    def test_sort_five_elements(self):
        self.assertEqual(
            run_file("sort.jvm", "5 9 3 7 1 8"), [1, 3, 7, 8, 9]
        )

    def test_sort_already_sorted(self):
        self.assertEqual(
            run_file("sort.jvm", "4 1 2 3 4"), [1, 2, 3, 4]
        )

    def test_sort_reverse_sorted(self):
        self.assertEqual(
            run_file("sort.jvm", "6 6 5 4 3 2 1"), [1, 2, 3, 4, 5, 6]
        )

    def test_sort_zero_elements(self):
        self.assertEqual(run_file("sort.jvm", "0"), [])

    def test_sort_one_element(self):
        self.assertEqual(run_file("sort.jvm", "1 42"), [42])

    def test_sort_ten_elements(self):
        self.assertEqual(
            run_file("sort.jvm", "10 5 9 3 7 1 8 2 6 4 0"),
            list(range(10)),
        )

    def test_sort_with_duplicates(self):
        self.assertEqual(
            run_file("sort.jvm", "5 3 1 3 2 1"), [1, 1, 2, 3, 3]
        )

    def test_sort_negative_numbers(self):
        self.assertEqual(
            run_file("sort.jvm", "4 -5 3 -1 0"), [-5, -1, 0, 3]
        )

    def test_sort_beyond_old_ten_element_cap(self):
        # sort.jvm now uses real newarray/iaload/iastore, so there is no
        # compile-time cap on n any more (the earlier unrolled version,
        # kept at programs/legacy_unrolled/sort_unrolled.jvm, was capped
        # at 10). 25 elements would have been impossible for that version.
        values = [17, -3, 42, 0, 8, -19, 5, 100, -50, 33,
                  1, 2, 3, 99, -100, 21, -21, 7, 6, 5, 4, 3, 2, 1, 0]
        n = len(values)
        input_text = f"{n} " + " ".join(map(str, values))
        self.assertEqual(run_file("sort.jvm", input_text), sorted(values))

    def test_sort_fuzz_against_python_sorted(self):
        # Randomized cross-check against Python's own sorted(), covering
        # n from 0 to 40 and a wide value range, to build confidence
        # beyond the hand-picked cases above.
        import random
        rng = random.Random(20260901)  # fixed seed: deterministic CI runs
        for _ in range(100):
            n = rng.randint(0, 40)
            values = [rng.randint(-1000, 1000) for _ in range(n)]
            input_text = f"{n} " + " ".join(map(str, values))
            self.assertEqual(
                run_file("sort.jvm", input_text), sorted(values),
                msg=f"mismatch for input n={n} values={values}",
            )

    # ---- (c) matrix sum ----
    def test_matrix_sum_typical(self):
        self.assertEqual(
            run_file("matrix_sum.jvm", "1 2 3 4 5 6 7 8", num_locals=12),
            [6, 8, 10, 12],
        )

    def test_matrix_sum_negatives_cancel(self):
        self.assertEqual(
            run_file("matrix_sum.jvm", "-1 -2 -3 -4 1 2 3 4", num_locals=12),
            [0, 0, 0, 0],
        )

    def test_matrix_sum_zero_matrices(self):
        self.assertEqual(
            run_file("matrix_sum.jvm", "0 0 0 0 0 0 0 0", num_locals=12),
            [0, 0, 0, 0],
        )


class TestBonusPrograms(unittest.TestCase):
    def test_factorial(self):
        self.assertEqual(run_file("factorial.jvm", "5"), [120])
        self.assertEqual(run_file("factorial.jvm", "0"), [1])
        self.assertEqual(run_file("factorial.jvm", "1"), [1])
        self.assertEqual(run_file("factorial.jvm", "10"), [3628800])

    def test_fibonacci(self):
        self.assertEqual(
            run_file("fibonacci.jvm", "8"), [0, 1, 1, 2, 3, 5, 8, 13]
        )
        self.assertEqual(run_file("fibonacci.jvm", "0"), [])
        self.assertEqual(run_file("fibonacci.jvm", "1"), [0])

    def test_gcd(self):
        self.assertEqual(run_file("gcd.jvm", "48 18"), [6])
        self.assertEqual(run_file("gcd.jvm", "17 5"), [1])
        self.assertEqual(run_file("gcd.jvm", "100 25"), [25])


if __name__ == "__main__":
    unittest.main()
