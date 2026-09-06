# JVMSIM — A Mini JVM Bytecode Simulator

A small Python simulator for a subset of Java bytecode.
It reads a text file of instructions (one per line), loads them into an
internal representation, and executes them on a simulated operand stack
and local-variable ("register") array — the same basic execution model
the real JVM uses.

Built as a course project and extended into a small, tested, documented
tool: a resolvable-label loader, a real CLI, a disassembler, error
handling with specific exception types, and a bytecode generator for
programs the base instruction set can't express by hand.

## Instruction set

**Required subset:** `ldc`, `iload`, `istore`, `iadd`, `isub`, `imul`,
`idiv`, `ifeq`, `iflt`, `ifgt`, plus the two non-standard I/O instructions
`read` and `print`.

**Extensions added in this project:**

| Category | Instructions |
|---|---|
| More arithmetic | `irem`, `ineg` |
| More conditionals | `ifne`, `ifle`, `ifge` |
| Two-operand comparisons | `if_icmpeq`, `if_icmpne`, `if_icmplt`, `if_icmpgt`, `if_icmple`, `if_icmpge` |
| Control flow | `goto` (unconditional jump), symbolic **labels** instead of raw offsets |
| Stack manipulation | `dup`, `pop`, `swap` |
| Local variable helper | `iinc <local> <delta>` |
| Arrays (indirect addressing) | `newarray`, `iaload`, `iastore` |
| Misc | `nop` |


## Project layout

```
jvm-bytecode-simulator/
├── jvmsim/                  # the simulator package (pure Python, stdlib only)
│   ├── loader.py            #   parses .jvm text -> resolved Instruction list
│   ├── vm.py                #   the JVMSimulator execution engine
│   ├── cli.py                #   `run` / `disasm` command-line interface
│   └── errors.py             #   specific exception types
├── programs/                 # bytecode source programs (.jvm)
│   ├── min_max.jvm            # (a) min/max of 3 integers
│   ├── sort.jvm                # (b) read n, sort n integers  [hand-written, uncapped]
│   ├── matrix_sum.jvm           # (c) sum of two 2x2 matrices
│   ├── factorial.jvm            # bonus: n! via a while-loop
│   ├── fibonacci.jvm             # bonus: first n Fibonacci numbers
│   ├── gcd.jvm                    # bonus: GCD via Euclid's algorithm
│   └── sort_unrolled.jvm        # earlier bare-subset-only sort (10-element cap)
├── inputs/                   # sample input files matching each program
│   ├── factorial.txt      
│   ├── fibonacci.txt          
│   ├── gcd.txt          
│   ├── matrixsum.txt          
│   ├── minmax.txt            
│   ├── sort.txt                         
├── tools/
│   └── generate_sort_program.py  # generator that produced sort_unrolled.jvm
├── tests/
│   └── test_vm.py             # 48 unit tests (loader, VM, all 6 programs, fuzz test)
├── run_demos.py               # runs every program against its sample input
├── setup.py
└── README.md                   # this file
```

## Requirements

Python 3.7+. No third-party packages — everything is standard library.

## Quick start

```bash
git clone <your-repo-url>
cd jvm-bytecode-simulator

# run every demo program against its sample input:
python3 run_demos.py

# run one program interactively (type integers, one or more per line):
python3 -m jvmsim run programs/min_max.jvm

# run one program with input piped from a file:
python3 -m jvmsim run programs/sort.jvm --input inputs/sort_input.txt --stack-size 20

# see the resolved instruction listing (labels -> indices):
python3 -m jvmsim disasm programs/gcd.jvm

# step-by-step execution trace (stack/locals after each instruction):
python3 -m jvmsim run programs/factorial.jvm --trace <<< "5"
```

### Running the tests

```bash
python3 -m unittest discover tests -v
# or, if you have pytest installed:
python3 -m pytest tests/ -v
```

All 40+ tests should pass.

## The three required programs

| Task | Program | Sample input | Sample output |
|---|---|---|---|
| (a) min & max of 3 ints | `programs/min_max.jvm` | `7 3 9` | `3` then `9` |
| (b) read n, sort n ints | `programs/sort.jvm` | `5 9 3 7 1 8` | `1 3 7 8 9` |
| (c) sum of two 2x2 matrices | `programs/matrix_sum.jvm` | `1 2 3 4 5 6 7 8` | `6 8 10 12` |

Each `.jvm` file has the Java-like high-level equivalent written directly
above the bytecode as a comment block, and a full explanation is in
`DOCUMENTATION.md`.

**Note on `sort.jvm`:** the *base* instruction subset from the
assignment (`ldc/iload/istore/iadd/isub/imul/idiv/ifeq/iflt/ifgt`) has
no array opcodes, so a truly generic "index by a runtime variable" isn't
expressible with only those. This project extends the instruction set
with real, indirectly-addressed arrays — `newarray`, `iaload`, `iastore`
— where the index is popped off the operand stack at runtime instead of
being a literal baked into the instruction. `sort.jvm` is a genuine,
hand-written, ~70-line nested loop using them, with **no cap on `n`**.
(An earlier version that stayed strictly within the bare assignment
subset by unrolling a bounded bubble sort is kept at
`programs/legacy_unrolled/sort_unrolled.jvm` for comparison —
`DOCUMENTATION.md` explains both approaches.)

## Bytecode file format

```
# comments start with # or //
LABEL_NAME:              # a label, referenced by branch/goto instructions
ldc 42                    # push a constant
istore 0                  # pop into local variable 0
iload 0                   # push local variable 0
iadd                       # pop two, push their sum
ifgt LABEL_NAME             # pop one, jump if > 0
goto LABEL_NAME               # unconditional jump
read                            # push an integer read from input
print                            # pop and print the top of stack
```

## Design highlights

- **Labels, not raw offsets.** Branch targets are symbolic names resolved
  to instruction indices by the loader before execution starts, which is
  far more pleasant to hand-write than real JVM byte offsets.
- **Specific exceptions**, not one generic error: `StackUnderflowError`,
  `StackOverflowError`, `InvalidLocalError`, `DivisionByZeroError`,
  `UninitializedLocalError`, `InputExhaustedError`, `ParseError`,
  `LabelError` all report exactly what went wrong and where.
- **Configurable but spec-compliant sizes.** Operand stack and local
  register set both default to 10 slots (per the assignment), and can be
  raised with `--stack-size` / `--locals` when a program legitimately
  needs more, which the assignment explicitly allows.
- **`--trace`** prints the stack and locals after every instruction, for
  debugging your own bytecode.


