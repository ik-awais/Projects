<!-- SEO KEYWORDS: Compiler Construction C++ Lexer Parser AST Interpreter x86-64 JIT Just-In-Time Compilation Tree-Walking Interpreter Recursive Descent Parser Toy Language Muhammad Awais -->

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=venom&color=0:0d1117,30:0a0e1a,60:0d1f3c,100:00d4ff&height=180&section=header&text=Compiler&fontSize=70&fontColor=ffffff&animation=fadeIn&fontAlignY=40&desc=Lexer%20%7C%20Parser%20%7C%20AST%20%7C%20JIT%20%7C%20Interpreter&descAlignY=65&descAlign=50&descSize=16&descColor=7dd3fc" alt="Compiler Banner" />

<br/>

[![Typing SVG](https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=18&pause=900&color=00D4FF&center=true&vCenter=true&multiline=false&width=720&lines=Three+Hand-Written+C%2B%2B+Language+Implementations;From+x86-64+JIT+to+a+Class-Based+Interpreter;Lexing+%E2%86%92+Parsing+%E2%86%92+AST+%E2%86%92+Execution)](https://github.com/ik-awais/Projects/tree/main/compiler)

<br/>

<a href="https://github.com/ik-awais"><img src="https://img.shields.io/badge/Author-Muhammad%20Awais-00d4ff?style=for-the-badge&logo=github&logoColor=white" /></a>
<a href="https://github.com/ik-awais/Projects"><img src="https://img.shields.io/badge/Language-C%2B%2B17-f97316?style=for-the-badge&logo=cplusplus&logoColor=white" /></a>
<a href="#"><img src="https://img.shields.io/badge/Build-g%2B%2B-00ff88?style=for-the-badge&logo=gnu&logoColor=white" /></a>

</div>

<br/>

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## ⚡ About

This folder contains **three standalone, single-file C++ programs** that build up — step by step — the core machinery of a programming language implementation: a lexer, a recursive-descent parser, an AST, and either a code generator or a tree-walking evaluator on top of it. Each file is self-contained (no shared headers, no build system) and embeds its own example source program directly in `main()`, so it compiles and runs as-is with nothing but a C++17 compiler.

They're ordered by complexity rather than by pipeline stage — each one is a complete mini-language on its own, and each adds a layer of capability on top of the last:

| # | File | What it adds |
|:-:|:---|:---|
| 1 | [`basic-compiler.cpp`](./basic-compiler.cpp) | Lexer → parser → AST → **real x86-64 machine code**, JIT-compiled and executed in memory |
| 2 | [`basicII-compiler.cpp`](./basicII-compiler.cpp) | Same front end, but **tree-walking evaluation** instead of codegen, plus variables & multi-statement programs |
| 3 | [`inter-compiler.cpp`](./inter-compiler.cpp) | A much larger interpreter: **classes, methods, arrays, `if`/`else`, `while`, relational operators, `return`** |

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🧩 1. `basic-compiler.cpp` — x86-64 JIT Compiler

The most "compiler" of the three: source is **not interpreted**, it's lexed, parsed into an AST, then walked a second time by an `X86JIT` class that emits raw x86-64 machine code byte-by-byte (`mov`, `push`/`pop`, `add`, `imul`, `idiv`, REX prefixes, and a `call` into a C++ runtime helper). The resulting bytes are written into an executable page via `mmap(..., PROT_EXEC, ...)` and called directly as a function pointer.

**Pipeline:** `Lexer` → `Parser` (recursive descent) → `ExprAST` (`NumberExpr`, `BinaryExpr`) → `X86JIT::compile_print` → `mmap` + direct execution

**Supports:** integer literals, `+ - * /`, parentheses, a single `print <expr>;` statement

**Embedded example:**
```cpp
print (2 + 3) * 4;
```
```
$ g++ -std=c++17 -O2 basic-compiler.cpp -o basic-compiler && ./basic-compiler
20
```

> Note: `mmap`/`PROT_EXEC` and the hand-written x86-64 encoding make this file POSIX/Linux-specific — it won't build as-is on native Windows (MSYS2/WSL works fine).

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🧩 2. `basicII-compiler.cpp` — Tree-Walking Interpreter with Variables

Same front-end shape as the first file, but instead of emitting machine code, each `ExprAST` node implements `eval()` directly — a **tree-walking interpreter**. This version drops the JIT entirely and adds identifiers, assignment, and a global symbol table (`std::unordered_map<std::string, int64_t> globals`), so programs can now have multiple statements that read and write state.

**Pipeline:** `Lexer` → `Parser` → `ExprAST` (`NumberExpr`, `VariableExpr`, `BinaryExpr`, `AssignAST`, `PrintAST`) → direct `eval()`

**Supports:** integer literals, named variables, assignment (`x = expr;`), `+ - * /`, parentheses, multiple `print` statements per program

**Embedded example:**
```cpp
x = 10;
y = 20;
z = x + y;
print z;
print x * y;
```
```
$ g++ -std=c++17 -O2 basicII-compiler.cpp -o basicII-compiler && ./basicII-compiler
30
200
```

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🧩 3. `inter-compiler.cpp` — Class-Based Interpreter

The largest of the three (~850 lines) and a meaningfully bigger language: it introduces a typed `Value` (int or object), control flow, fixed-size arrays, and full class definitions with member variables and methods — including a `this`-style binding scheme where method bodies access members as plain locals that get copied in and written back on return.

**Pipeline:** `Lexer` → `Parser` → `Expr` / `Stmt` AST hierarchy → `execute()` / `eval()` over a global environment, with classes resolved into `ClassDef` + `Object` instances

**Supports:**
- `int` variable declarations, with or without initializers
- Fixed-size arrays: `int arr[5];`, `arr[i] = expr;`, `arr[i]`
- `class Name { int member; int method(int p) { ... } }` — member variables and methods
- Object declarations (`ClassName obj;`), method calls (`obj.method(args)`), member access/assignment (`obj.member`, `obj.member = expr;`)
- Control flow: `if (cond) { } else { }`, `while (cond) { }`
- Relational operators: `== != < <= > >=`
- `return expr;` (implemented via a thrown `ReturnException`, unwound by the calling method)

**Embedded example:**
```cpp
class Counter {
    int value;
    void inc() { value = value + 1; }
    int get() { return value; }
}

int arr[5];
int i;
i = 0;
while (i < 5) {
    arr[i] = i * 10;
    i = i + 1;
}

Counter c;
c.inc();
c.inc();
print c.get();

i = 0;
while (i < 5) {
    print arr[i];
    i = i + 1;
}
```
```
$ g++ -std=c++17 -O2 inter-compiler.cpp -o inter-compiler && ./inter-compiler
2
0
10
20
30
40
```

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🚀 Build & Run

There's no build system here — each file is a complete, independent translation unit. Compile and run any one of them directly:

```bash
# from inside the compiler/ folder
g++ -std=c++17 -O2 basic-compiler.cpp   -o basic-compiler   && ./basic-compiler
g++ -std=c++17 -O2 basicII-compiler.cpp -o basicII-compiler && ./basicII-compiler
g++ -std=c++17 -O2 inter-compiler.cpp   -o inter-compiler   && ./inter-compiler
```

To experiment with a different program, edit the `const char* source = R"( ... )";` literal inside each file's `main()` — none of the three currently read source from a file or command-line argument.

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🎓 Concepts Demonstrated

- Hand-written lexing (no flex/lex) and recursive-descent parsing (no yacc/bison)
- AST design via a polymorphic `Expr`/`Stmt` base class hierarchy
- Two different execution strategies for the same general front-end shape: **direct machine-code generation (JIT)** vs. **tree-walking evaluation**
- x86-64 instruction encoding by hand: REX prefixes, `mov`/`push`/`pop`/`add`/`imul`/`idiv`, calling into native C++ from generated code
- Symbol tables, scoping, and environment management for variables, arrays, and object members
- Exception-based control-flow transfer (`return` implemented as a thrown/caught signal)
- Minimal OOP semantics: class definitions, method dispatch, and member binding without a "real" runtime object model

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🌐 Author

<table>
<tr>
<td width="60%">

**Muhammad Awais** is an AI Engineer and **Managing Director** at **AI GenMat**, and is pursuing a **BS in Artificial Intelligence** at **FAST-NUCES Peshawar**.

</td>
<td width="40%" align="center">

[![GitHub](https://img.shields.io/badge/GitHub-ik--awais-181717?style=for-the-badge&logo=github)](https://github.com/ik-awais)
[![Portfolio](https://img.shields.io/badge/Portfolio-ik--awais.github.io-00d4ff?style=for-the-badge&logo=firefoxbrowser&logoColor=white)](https://ik-awais.github.io)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0a66c2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/muhammad-awais-ai-engineer/)

</td>
</tr>
</table>

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

<div align="center">

[⬅ Back to Projects](https://github.com/ik-awais/Projects)

</div>