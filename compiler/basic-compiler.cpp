#include <iostream>
#include <vector>
#include <cstdint>
#include <cstring>
#include <memory>
#include <cctype>
#include <sys/mman.h>
#include <unistd.h>

// ----------------------------------------------------------------------------
// 1. Runtime helper – called by generated machine code
// ----------------------------------------------------------------------------
extern "C" void runtime_print(int64_t value) {
    std::cout << value << std::endl;
}

// ----------------------------------------------------------------------------
// 2. Lexer (tiny subset)
// ----------------------------------------------------------------------------
enum TokenType {
    TOK_EOF,
    TOK_NUMBER,
    TOK_PRINT,
    TOK_PLUS, TOK_MINUS, TOK_STAR, TOK_SLASH,
    TOK_LPAREN, TOK_RPAREN,
    TOK_SEMICOLON
};

struct Token {
    TokenType type;
    int64_t value; // for TOK_NUMBER
};

class Lexer {
    const char* src;
    size_t pos;
public:
    Lexer(const char* s) : src(s), pos(0) {}
    Token next() {
        while (src[pos] == ' ' || src[pos] == '\t' || src[pos] == '\n') pos++;
        if (src[pos] == '\0') return {TOK_EOF, 0};
        if (std::isdigit(src[pos])) {
            int64_t v = 0;
            while (std::isdigit(src[pos])) {
                v = v * 10 + (src[pos] - '0');
                pos++;
            }
            return {TOK_NUMBER, v};
        }
        // identifiers: only "print"
        if (std::isalpha(src[pos])) {
            if (strncmp(src + pos, "print", 5) == 0 && !std::isalnum(src[pos+5])) {
                pos += 5;
                return {TOK_PRINT, 0};
            }
            throw std::runtime_error("Unknown identifier");
        }
        char c = src[pos++];
        switch (c) {
            case '+': return {TOK_PLUS, 0};
            case '-': return {TOK_MINUS, 0};
            case '*': return {TOK_STAR, 0};
            case '/': return {TOK_SLASH, 0};
            case '(': return {TOK_LPAREN, 0};
            case ')': return {TOK_RPAREN, 0};
            case ';': return {TOK_SEMICOLON, 0};
            default: throw std::runtime_error(std::string("Unexpected char: ") + c);
        }
    }
};

// ----------------------------------------------------------------------------
// 3. Parser (recursive descent)
// ----------------------------------------------------------------------------
class Parser {
    Lexer lex;
    Token cur;
    void advance() { cur = lex.next(); }
    void expect(TokenType type) {
        if (cur.type != type) throw std::runtime_error("Syntax error");
        advance();
    }
public:
    Parser(const char* src) : lex(src) { advance(); }

    struct ExprAST {
        virtual ~ExprAST() = default;
        virtual int64_t eval() const = 0;
    };
    struct NumberExpr : ExprAST {
        int64_t val;
        NumberExpr(int64_t v) : val(v) {}
        int64_t eval() const override { return val; }
    };
    struct BinaryExpr : ExprAST {
        char op;
        std::unique_ptr<ExprAST> lhs, rhs;
        BinaryExpr(char o, std::unique_ptr<ExprAST> l, std::unique_ptr<ExprAST> r)
            : op(o), lhs(std::move(l)), rhs(std::move(r)) {}
        int64_t eval() const override {
            int64_t lv = lhs->eval(), rv = rhs->eval();
            switch (op) {
                case '+': return lv + rv;
                case '-': return lv - rv;
                case '*': return lv * rv;
                case '/': return lv / rv;
                default: return 0;
            }
        }
    };

    std::unique_ptr<ExprAST> parsePrimary() {
        if (cur.type == TOK_NUMBER) {
            int64_t v = cur.value;
            advance();
            return std::make_unique<NumberExpr>(v);
        }
        if (cur.type == TOK_LPAREN) {
            advance();
            auto expr = parseExpression();
            expect(TOK_RPAREN);
            return expr;
        }
        throw std::runtime_error("Expected number or '('");
    }

    std::unique_ptr<ExprAST> parseMulDiv() {
        auto lhs = parsePrimary();
        while (cur.type == TOK_STAR || cur.type == TOK_SLASH) {
            char op = (cur.type == TOK_STAR) ? '*' : '/';
            advance();
            auto rhs = parsePrimary();
            lhs = std::make_unique<BinaryExpr>(op, std::move(lhs), std::move(rhs));
        }
        return lhs;
    }

    std::unique_ptr<ExprAST> parseExpression() {
        auto lhs = parseMulDiv();
        while (cur.type == TOK_PLUS || cur.type == TOK_MINUS) {
            char op = (cur.type == TOK_PLUS) ? '+' : '-';
            advance();
            auto rhs = parseMulDiv();
            lhs = std::make_unique<BinaryExpr>(op, std::move(lhs), std::move(rhs));
        }
        return lhs;
    }

    void parseProgram(std::vector<std::unique_ptr<ExprAST>>& statements) {
        while (cur.type != TOK_EOF) {
            if (cur.type == TOK_PRINT) {
                advance();
                auto expr = parseExpression();
                expect(TOK_SEMICOLON);
                statements.push_back(std::move(expr));
            } else {
                throw std::runtime_error("Only 'print' statements are supported");
            }
        }
    }
};

// ----------------------------------------------------------------------------
// 4. x86‑64 code generator (JIT)
// ----------------------------------------------------------------------------
class X86JIT {
    std::vector<uint8_t> code;
    void emit_byte(uint8_t b) { code.push_back(b); }
    void emit_word(uint32_t w) {
        for (int i = 0; i < 4; ++i) emit_byte((w >> (i*8)) & 0xFF);
    }
    void emit_quad(uint64_t q) {
        for (int i = 0; i < 8; ++i) emit_byte((q >> (i*8)) & 0xFF);
    }
    void emit_rex(bool w, bool r, bool x, bool b) {
        uint8_t rex = 0x40;
        if (w) rex |= 0x08;
        if (r) rex |= 0x04;
        if (x) rex |= 0x02;
        if (b) rex |= 0x01;
        emit_byte(rex);
    }

public:
    // Compile an expression AST into machine code.
    // Generated code is a function with signature: int64_t (*)()
    // It computes the expression and returns the value.
    void compile_expr(Parser::ExprAST* ast) {
        if (auto num = dynamic_cast<Parser::NumberExpr*>(ast)) {
            // mov rax, imm64
            emit_byte(0x48);        // REX.W
            emit_byte(0xB8);        // mov rax, imm64
            emit_quad(num->val);
        } else if (auto bin = dynamic_cast<Parser::BinaryExpr*>(ast)) {
            // left into rax, push, right into rax, pop rbx, then operation
            compile_expr(bin->lhs.get());
            emit_byte(0x50);                 // push rax
            compile_expr(bin->rhs.get());
            emit_byte(0x5B);                 // pop rbx   (rbx = left)
            switch (bin->op) {
                case '+': // add rax, rbx
                    emit_byte(0x48); emit_byte(0x01); emit_byte(0xD8); // add rax, rbx
                    break;
                case '-': // rbx - rax -> rax
                    emit_byte(0x48); emit_byte(0x89); emit_byte(0xD9); // mov rcx, rbx
                    emit_byte(0x48); emit_byte(0x29); emit_byte(0xC1); // sub rcx, rax
                    emit_byte(0x48); emit_byte(0x89); emit_byte(0xC8); // mov rax, rcx
                    break;
                case '*': // imul rax, rbx
                    emit_byte(0x48); emit_byte(0x0F); emit_byte(0xAF); emit_byte(0xC3); // imul rax, rbx
                    break;
                case '/':
                    // left / right: left in rbx, right in rax
                    // mov rcx, rax   (right)
                    emit_byte(0x48); emit_byte(0x89); emit_byte(0xC1); // mov rcx, rax
                    // mov rax, rbx   (left)
                    emit_byte(0x48); emit_byte(0x89); emit_byte(0xD8); // mov rax, rbx
                    // xor rdx, rdx
                    emit_byte(0x48); emit_byte(0x31); emit_byte(0xD2); // xor rdx, rdx
                    // idiv rcx
                    emit_byte(0x48); emit_byte(0xF7); emit_byte(0xF9); // idiv rcx
                    break;
            }
        } else {
            throw std::runtime_error("Unsupported AST node");
        }
    }

    // Generate code that calls runtime_print with the computed value
    std::vector<uint8_t> compile_print(Parser::ExprAST* ast) {
        code.clear();
        // prologue
        emit_byte(0x55);                     // push rbp
        emit_byte(0x48); emit_byte(0x89); emit_byte(0xE5); // mov rbp, rsp

        compile_expr(ast);                   // rax = expression result

        // call runtime_print(rax) – first arg in rdi
        emit_byte(0x48); emit_byte(0x89); emit_byte(0xC7); // mov rdi, rax
        // movabs rcx, &runtime_print
        emit_byte(0x48); emit_byte(0xB9);
        emit_quad(reinterpret_cast<uint64_t>(runtime_print));
        emit_byte(0xFF); emit_byte(0xD1);    // call rcx

        // epilogue
        emit_byte(0x5D);                     // pop rbp
        emit_byte(0xC3);                     // ret

        return std::move(code);
    }
};

// ----------------------------------------------------------------------------
// 5. Main driver – compile and execute embedded source
// ----------------------------------------------------------------------------
int main() {
    // Example program: print (2+3)*4;
    const char* source = "print (2 + 3) * 4;";

    try {
        Parser parser(source);
        std::vector<std::unique_ptr<Parser::ExprAST>> statements;
        parser.parseProgram(statements);

        if (statements.empty()) {
            std::cerr << "No print statements found.\n";
            return 1;
        }

        X86JIT jit;
        std::vector<uint8_t> machine_code = jit.compile_print(statements[0].get());

        // Allocate executable memory
        void* exec = mmap(nullptr, machine_code.size(), PROT_READ | PROT_WRITE | PROT_EXEC,
                          MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (exec == MAP_FAILED) {
            perror("mmap");
            return 1;
        }
        memcpy(exec, machine_code.data(), machine_code.size());

        // Cast to function pointer and call it
        void (*func)() = reinterpret_cast<void (*)()>(exec);
        func();

        munmap(exec, machine_code.size());
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}