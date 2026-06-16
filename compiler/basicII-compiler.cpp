#include <iostream>
#include <vector>
#include <memory>
#include <cctype>
#include <unordered_map>
#include <string>

// ----------------------------------------------------------------------------
// Runtime symbol table
// ----------------------------------------------------------------------------
std::unordered_map<std::string, int64_t> globals;

// ----------------------------------------------------------------------------
// Lexer
// ----------------------------------------------------------------------------
enum TokenType {
    TOK_EOF, TOK_NUMBER, TOK_IDENTIFIER, TOK_PRINT,
    TOK_PLUS, TOK_MINUS, TOK_STAR, TOK_SLASH,
    TOK_LPAREN, TOK_RPAREN, TOK_ASSIGN, TOK_SEMICOLON
};

struct Token {
    TokenType type;
    int64_t num_value;
    std::string ident;
};

class Lexer {
    const char* src;
    size_t pos;
public:
    Lexer(const char* s) : src(s), pos(0) {}
    Token next() {
        while (src[pos] == ' ' || src[pos] == '\t' || src[pos] == '\n') pos++;
        if (src[pos] == '\0') return {TOK_EOF, 0, ""};
        if (std::isdigit(src[pos])) {
            int64_t v = 0;
            while (std::isdigit(src[pos])) v = v * 10 + (src[pos++] - '0');
            return {TOK_NUMBER, v, ""};
        }
        if (std::isalpha(src[pos])) {
            std::string id;
            while (std::isalnum(src[pos])) id.push_back(src[pos++]);
            if (id == "print") return {TOK_PRINT, 0, ""};
            return {TOK_IDENTIFIER, 0, id};
        }
        char c = src[pos++];
        switch (c) {
            case '+': return {TOK_PLUS, 0, ""};
            case '-': return {TOK_MINUS, 0, ""};
            case '*': return {TOK_STAR, 0, ""};
            case '/': return {TOK_SLASH, 0, ""};
            case '(': return {TOK_LPAREN, 0, ""};
            case ')': return {TOK_RPAREN, 0, ""};
            case '=': return {TOK_ASSIGN, 0, ""};
            case ';': return {TOK_SEMICOLON, 0, ""};
            default: throw std::runtime_error(std::string("Unexpected char: ") + c);
        }
    }
};

// ----------------------------------------------------------------------------
// AST nodes
// ----------------------------------------------------------------------------
class ExprAST {
public:
    virtual ~ExprAST() = default;
    virtual int64_t eval() = 0;
};

class NumberExpr : public ExprAST {
    int64_t val;
public:
    NumberExpr(int64_t v) : val(v) {}
    int64_t eval() override { return val; }
};

class VariableExpr : public ExprAST {
    std::string name;
public:
    VariableExpr(const std::string& n) : name(n) {}
    int64_t eval() override { return globals[name]; }
};

class BinaryExpr : public ExprAST {
    char op;
    std::unique_ptr<ExprAST> lhs, rhs;
public:
    BinaryExpr(char o, std::unique_ptr<ExprAST> l, std::unique_ptr<ExprAST> r)
        : op(o), lhs(std::move(l)), rhs(std::move(r)) {}
    int64_t eval() override {
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

class AssignAST : public ExprAST {
    std::string name;
    std::unique_ptr<ExprAST> value;
public:
    AssignAST(const std::string& n, std::unique_ptr<ExprAST> v)
        : name(n), value(std::move(v)) {}
    int64_t eval() override {
        int64_t v = value->eval();
        globals[name] = v;
        return v;
    }
};

class PrintAST : public ExprAST {
    std::unique_ptr<ExprAST> expr;
public:
    PrintAST(std::unique_ptr<ExprAST> e) : expr(std::move(e)) {}
    int64_t eval() override {
        int64_t v = expr->eval();
        std::cout << v << std::endl;
        return v;
    }
};

// ----------------------------------------------------------------------------
// Parser
// ----------------------------------------------------------------------------
class Parser {
    Lexer lex;
    Token cur;
    void advance() { cur = lex.next(); }
    void expect(TokenType type) {
        if (cur.type != type) throw std::runtime_error("Syntax error");
        advance();
    }

    std::unique_ptr<ExprAST> parsePrimary() {
        if (cur.type == TOK_NUMBER) {
            auto n = std::make_unique<NumberExpr>(cur.num_value);
            advance();
            return n;
        }
        if (cur.type == TOK_IDENTIFIER) {
            auto v = std::make_unique<VariableExpr>(cur.ident);
            advance();
            return v;
        }
        if (cur.type == TOK_LPAREN) {
            advance();
            auto e = parseExpression();
            expect(TOK_RPAREN);
            return e;
        }
        throw std::runtime_error("Expected number, identifier, or '('");
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

public:
    Parser(const char* src) : lex(src) { advance(); }

    std::unique_ptr<ExprAST> parseStatement() {
        if (cur.type == TOK_PRINT) {
            advance();
            auto e = parseExpression();
            expect(TOK_SEMICOLON);
            return std::make_unique<PrintAST>(std::move(e));
        }
        else if (cur.type == TOK_IDENTIFIER) {
            std::string name = cur.ident;
            advance();
            expect(TOK_ASSIGN);
            auto e = parseExpression();
            expect(TOK_SEMICOLON);
            return std::make_unique<AssignAST>(name, std::move(e));
        }
        else {
            throw std::runtime_error("Expected 'print' or assignment");
        }
    }

    std::vector<std::unique_ptr<ExprAST>> parseProgram() {
        std::vector<std::unique_ptr<ExprAST>> stmts;
        while (cur.type != TOK_EOF) {
            stmts.push_back(parseStatement());
        }
        return stmts;
    }
};

// ----------------------------------------------------------------------------
// Main – compile and run any program
// ----------------------------------------------------------------------------
int main() {
    // Example program: variables, arithmetic, multiple statements
    const char* source = R"(
        x = 10;
        y = 20;
        z = x + y;
        print z;
        print x * y;
    )";

    try {
        Parser parser(source);
        auto statements = parser.parseProgram();

        for (auto& stmt : statements) {
            stmt->eval();
        }
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}