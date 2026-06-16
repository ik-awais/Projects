#include <iostream>
#include <vector>
#include <memory>
#include <unordered_map>
#include <string>
#include <cctype>
#include <stdexcept>

// ----------------------------------------------------------------------
// Forward declarations
// ----------------------------------------------------------------------
struct Object;
class Expr;
class Stmt;
class ASTFunction;

// ----------------------------------------------------------------------
// Value type (int or object)
// ----------------------------------------------------------------------
struct Value {
    enum Type { INT, OBJECT } type;
    int intVal;
    std::shared_ptr<Object> objVal;
    Value() : type(INT), intVal(0) {}
    Value(int v) : type(INT), intVal(v) {}
    Value(std::shared_ptr<Object> o) : type(OBJECT), intVal(0), objVal(std::move(o)) {}
};

// ----------------------------------------------------------------------
// Control-flow signal used to implement 'return'
// ----------------------------------------------------------------------
struct ReturnException {
    Value value;
    explicit ReturnException(Value v) : value(std::move(v)) {}
};

// ----------------------------------------------------------------------
// Class definition (must be complete before Object)
// ----------------------------------------------------------------------
struct ClassDef {
    std::string name;
    std::vector<std::string> memberNames;
    std::unordered_map<std::string, int> memberOffsets;
    std::unordered_map<std::string, ASTFunction*> methods;
};

// ----------------------------------------------------------------------
// Object instance
// ----------------------------------------------------------------------
struct Object {
    ClassDef* klass;
    std::vector<Value> members;
    Object(ClassDef* k) : klass(k), members(k->memberNames.size()) {}
};

// ----------------------------------------------------------------------
// Global symbol tables
// ----------------------------------------------------------------------
std::unordered_map<std::string, Value> globals;
std::unordered_map<std::string, ClassDef> classes;

// ----------------------------------------------------------------------
// Lexer
// ----------------------------------------------------------------------
enum TokenType {
    TOK_EOF, TOK_NUMBER, TOK_IDENTIFIER,
    TOK_INT, TOK_CLASS, TOK_VOID, TOK_RETURN,
    TOK_IF, TOK_ELSE, TOK_WHILE, TOK_PRINT,
    TOK_PLUS, TOK_MINUS, TOK_STAR, TOK_SLASH,
    TOK_LPAREN, TOK_RPAREN, TOK_LBRACE, TOK_RBRACE,
    TOK_LBRACKET, TOK_RBRACKET,
    TOK_ASSIGN, TOK_SEMICOLON, TOK_COMMA, TOK_DOT,
    TOK_EQ, TOK_NE, TOK_LT, TOK_LE, TOK_GT, TOK_GE
};

struct Token {
    TokenType type;
    int64_t numVal;
    std::string text;
    Token() : type(TOK_EOF), numVal(0) {}
    Token(TokenType t) : type(t), numVal(0) {}
    Token(TokenType t, const std::string& s) : type(t), numVal(0), text(s) {}
    Token(int64_t n) : type(TOK_NUMBER), numVal(n) {}
};

class Lexer {
    const char* src;
    size_t pos;
public:
    Lexer(const char* s) : src(s), pos(0) {}
    Token next() {
        while (src[pos] == ' ' || src[pos] == '\t' || src[pos] == '\n') pos++;
        if (src[pos] == '\0') return Token(TOK_EOF);
        if (std::isdigit(src[pos])) {
            int64_t v = 0;
            while (std::isdigit(src[pos])) v = v * 10 + (src[pos++] - '0');
            return Token(v);
        }
        if (std::isalpha(src[pos])) {
            std::string id;
            while (std::isalnum(src[pos])) id.push_back(src[pos++]);
            if (id == "int") return Token(TOK_INT, id);
            if (id == "class") return Token(TOK_CLASS, id);
            if (id == "void") return Token(TOK_VOID, id);
            if (id == "return") return Token(TOK_RETURN, id);
            if (id == "if") return Token(TOK_IF, id);
            if (id == "else") return Token(TOK_ELSE, id);
            if (id == "while") return Token(TOK_WHILE, id);
            if (id == "print") return Token(TOK_PRINT, id);
            return Token(TOK_IDENTIFIER, id);
        }
        char c = src[pos++];
        switch (c) {
            case '+': return Token(TOK_PLUS);
            case '-': return Token(TOK_MINUS);
            case '*': return Token(TOK_STAR);
            case '/': return Token(TOK_SLASH);
            case '(': return Token(TOK_LPAREN);
            case ')': return Token(TOK_RPAREN);
            case '{': return Token(TOK_LBRACE);
            case '}': return Token(TOK_RBRACE);
            case '[': return Token(TOK_LBRACKET);
            case ']': return Token(TOK_RBRACKET);
            case ';': return Token(TOK_SEMICOLON);
            case ',': return Token(TOK_COMMA);
            case '.': return Token(TOK_DOT);
            case '!':
                if (src[pos] == '=') { pos++; return Token(TOK_NE); }
                break;
            case '=':
                if (src[pos] == '=') { pos++; return Token(TOK_EQ); }
                else return Token(TOK_ASSIGN);
            case '<':
                if (src[pos] == '=') { pos++; return Token(TOK_LE); }
                else return Token(TOK_LT);
            case '>':
                if (src[pos] == '=') { pos++; return Token(TOK_GE); }
                else return Token(TOK_GT);
            default:
                throw std::runtime_error(std::string("Unexpected char: ") + c);
        }
        return Token(TOK_EOF);
    }
};

// ----------------------------------------------------------------------
// AST base classes
// ----------------------------------------------------------------------
class Expr {
public:
    virtual ~Expr() = default;
    virtual Value eval() = 0;
};

class Stmt {
public:
    virtual ~Stmt() = default;
    virtual void execute() = 0;
};

class ASTFunction {
public:
    std::string name;
    std::string returnType;   // "int" or "void"
    std::vector<std::string> params;
    std::vector<std::unique_ptr<Stmt>> body;
    ClassDef* ownerClass = nullptr;
};

// ----------------------------------------------------------------------
// Concrete expression nodes
// ----------------------------------------------------------------------
class NumberExpr : public Expr {
    int64_t val;
public:
    NumberExpr(int64_t v) : val(v) {}
    Value eval() override { return Value((int)val); }
};

class VarExpr : public Expr {
    std::string name;
public:
    VarExpr(const std::string& n) : name(n) {}
    Value eval() override {
        auto it = globals.find(name);
        if (it == globals.end()) throw std::runtime_error("Undefined variable: " + name);
        return it->second;
    }
};

class MemberVarExpr : public Expr {
    std::string objName;
    std::string memberName;
public:
    MemberVarExpr(const std::string& obj, const std::string& mem) : objName(obj), memberName(mem) {}
    Value eval() override {
        Value objVal = VarExpr(objName).eval();
        if (objVal.type != Value::OBJECT) throw std::runtime_error("Not an object");
        Object* obj = objVal.objVal.get();
        auto it = obj->klass->memberOffsets.find(memberName);
        if (it == obj->klass->memberOffsets.end())
            throw std::runtime_error("Unknown member: " + memberName);
        return obj->members[it->second];
    }
};

class ArrayElemExpr : public Expr {
    std::string arrayName;
    std::unique_ptr<Expr> index;
public:
    ArrayElemExpr(const std::string& arr, std::unique_ptr<Expr> idx)
        : arrayName(arr), index(std::move(idx)) {}
    Value eval() override {
        Value arrVal = VarExpr(arrayName).eval();
        if (arrVal.type != Value::OBJECT) throw std::runtime_error("Not an array");
        int idxVal = index->eval().intVal;
        if (idxVal < 0 || idxVal >= (int)arrVal.objVal->members.size())
            throw std::runtime_error("Array index out of bounds");
        return arrVal.objVal->members[idxVal];
    }
};

class BinaryExpr : public Expr {
    char op;
    std::unique_ptr<Expr> lhs, rhs;
public:
    BinaryExpr(char o, std::unique_ptr<Expr> l, std::unique_ptr<Expr> r)
        : op(o), lhs(std::move(l)), rhs(std::move(r)) {}
    Value eval() override {
        Value lv = lhs->eval();
        Value rv = rhs->eval();
        if (lv.type != Value::INT || rv.type != Value::INT)
            throw std::runtime_error("Arithmetic on non-int");
        int a = lv.intVal, b = rv.intVal;
        switch (op) {
            case '+': return Value(a + b);
            case '-': return Value(a - b);
            case '*': return Value(a * b);
            case '/': return Value(a / b);
            default: throw std::runtime_error("Unknown operator");
        }
    }
};

class RelationalExpr : public Expr {
    TokenType op;
    std::unique_ptr<Expr> lhs, rhs;
public:
    RelationalExpr(TokenType o, std::unique_ptr<Expr> l, std::unique_ptr<Expr> r)
        : op(o), lhs(std::move(l)), rhs(std::move(r)) {}
    Value eval() override {
        int a = lhs->eval().intVal;
        int b = rhs->eval().intVal;
        bool result;
        switch (op) {
            case TOK_EQ: result = (a == b); break;
            case TOK_NE: result = (a != b); break;
            case TOK_LT: result = (a < b); break;
            case TOK_LE: result = (a <= b); break;
            case TOK_GT: result = (a > b); break;
            case TOK_GE: result = (a >= b); break;
            default: throw std::runtime_error("Bad relational op");
        }
        return Value(result ? 1 : 0);
    }
};

class MethodCallExpr : public Expr {
    std::string objectName;
    std::string methodName;
    std::vector<std::unique_ptr<Expr>> arguments;
public:
    MethodCallExpr(const std::string& obj, const std::string& meth,
                   std::vector<std::unique_ptr<Expr>> args)
        : objectName(obj), methodName(meth), arguments(std::move(args)) {}
    Value eval() override {
        Value objVal = VarExpr(objectName).eval();
        if (objVal.type != Value::OBJECT) throw std::runtime_error("Not an object");
        Object* obj = objVal.objVal.get();
        ClassDef* klass = obj->klass;
        auto it = klass->methods.find(methodName);
        if (it == klass->methods.end()) throw std::runtime_error("Unknown method");
        ASTFunction* func = it->second;
        if (func->params.size() != arguments.size())
            throw std::runtime_error("Argument count mismatch");

        // Save current globals and create new frame
        std::unordered_map<std::string, Value> oldGlobals = globals;
        globals["this"] = objVal;

        // Bind member variables as globals (so method body can access them directly)
        for (const auto& member : klass->memberNames) {
            int offset = klass->memberOffsets[member];
            globals[member] = obj->members[offset];
        }
        // Bind parameters
        for (size_t i = 0; i < arguments.size(); ++i) {
            Value argVal = arguments[i]->eval();
            globals[func->params[i]] = argVal;
        }

        Value returnValue(0);
        try {
            for (auto& stmt : func->body) stmt->execute();
        } catch (ReturnException& ret) {
            returnValue = ret.value;
        } catch (...) {
            globals = oldGlobals;
            throw;
        }

        // Write back modified member variables from globals to object
        for (const auto& member : klass->memberNames) {
            int offset = klass->memberOffsets[member];
            obj->members[offset] = globals[member];
        }

        globals = oldGlobals;
        return returnValue;
    }
};

// ----------------------------------------------------------------------
// Concrete statement nodes
// ----------------------------------------------------------------------
class AssignStmt : public Stmt {
    std::string name;
    std::unique_ptr<Expr> value;
public:
    AssignStmt(const std::string& n, std::unique_ptr<Expr> v) : name(n), value(std::move(v)) {}
    void execute() override {
        Value v = value->eval();
        globals[name] = v;
    }
};

class MemberAssignStmt : public Stmt {
    std::string objName;
    std::string memberName;
    std::unique_ptr<Expr> value;
public:
    MemberAssignStmt(const std::string& obj, const std::string& mem, std::unique_ptr<Expr> val)
        : objName(obj), memberName(mem), value(std::move(val)) {}
    void execute() override {
        Value objVal = VarExpr(objName).eval();
        if (objVal.type != Value::OBJECT) throw std::runtime_error("Not an object");
        Object* obj = objVal.objVal.get();
        auto it = obj->klass->memberOffsets.find(memberName);
        if (it == obj->klass->memberOffsets.end())
            throw std::runtime_error("Unknown member: " + memberName);
        Value v = value->eval();
        obj->members[it->second] = v;
        // Also update the global copy in current frame (if any)
        if (globals.find(memberName) != globals.end())
            globals[memberName] = v;
    }
};

class ArrayAssignStmt : public Stmt {
    std::string arrayName;
    std::unique_ptr<Expr> index;
    std::unique_ptr<Expr> value;
public:
    ArrayAssignStmt(const std::string& arr, std::unique_ptr<Expr> idx, std::unique_ptr<Expr> val)
        : arrayName(arr), index(std::move(idx)), value(std::move(val)) {}
    void execute() override {
        Value arrVal = VarExpr(arrayName).eval();
        if (arrVal.type != Value::OBJECT) throw std::runtime_error("Not an array");
        int idxVal = index->eval().intVal;
        Value valVal = value->eval();
        if (idxVal < 0 || idxVal >= (int)arrVal.objVal->members.size())
            throw std::runtime_error("Array index out of bounds");
        arrVal.objVal->members[idxVal] = valVal;
    }
};

class VarDeclStmt : public Stmt {
    std::string name;
    std::unique_ptr<Expr> init;
public:
    VarDeclStmt(const std::string& n, std::unique_ptr<Expr> i) : name(n), init(std::move(i)) {}
    void execute() override {
        Value v = init ? init->eval() : Value(0);
        globals[name] = v;
    }
};

class ArrayDeclStmt : public Stmt {
    std::string name;
    int size;
public:
    ArrayDeclStmt(const std::string& n, int s) : name(n), size(s) {}
    void execute() override {
        ClassDef* arrayClass = new ClassDef();
        arrayClass->name = "__array";
        for (int i = 0; i < size; ++i) arrayClass->memberNames.push_back("");
        auto obj = std::make_shared<Object>(arrayClass);
        for (int i = 0; i < size; ++i) obj->members[i] = Value(0);
        globals[name] = Value(obj);
    }
};

class ObjectDeclStmt : public Stmt {
    std::string className;
    std::string varName;
public:
    ObjectDeclStmt(const std::string& cls, const std::string& var) : className(cls), varName(var) {}
    void execute() override {
        auto it = classes.find(className);
        if (it == classes.end()) throw std::runtime_error("Unknown class: " + className);
        auto obj = std::make_shared<Object>(&it->second);
        globals[varName] = Value(obj);
    }
};

class PrintStmt : public Stmt {
    std::unique_ptr<Expr> expr;
public:
    PrintStmt(std::unique_ptr<Expr> e) : expr(std::move(e)) {}
    void execute() override {
        Value v = expr->eval();
        if (v.type == Value::INT) std::cout << v.intVal << std::endl;
        else std::cout << "<object>" << std::endl;
    }
};

class ExprStmt : public Stmt {
    std::unique_ptr<Expr> expr;
public:
    ExprStmt(std::unique_ptr<Expr> e) : expr(std::move(e)) {}
    void execute() override { expr->eval(); }
};

class EmptyStmt : public Stmt {
public:
    void execute() override {}
};

class IfStmt : public Stmt {
    std::unique_ptr<Expr> cond;
    std::vector<std::unique_ptr<Stmt>> thenBlock;
    std::vector<std::unique_ptr<Stmt>> elseBlock;
public:
    IfStmt(std::unique_ptr<Expr> c, std::vector<std::unique_ptr<Stmt>> t,
           std::vector<std::unique_ptr<Stmt>> e)
        : cond(std::move(c)), thenBlock(std::move(t)), elseBlock(std::move(e)) {}
    void execute() override {
        if (cond->eval().intVal != 0) {
            for (auto& stmt : thenBlock) stmt->execute();
        } else if (!elseBlock.empty()) {
            for (auto& stmt : elseBlock) stmt->execute();
        }
    }
};

class WhileStmt : public Stmt {
    std::unique_ptr<Expr> cond;
    std::vector<std::unique_ptr<Stmt>> body;
public:
    WhileStmt(std::unique_ptr<Expr> c, std::vector<std::unique_ptr<Stmt>> b)
        : cond(std::move(c)), body(std::move(b)) {}
    void execute() override {
        while (cond->eval().intVal != 0) {
            for (auto& stmt : body) stmt->execute();
        }
    }
};

class ReturnStmt : public Stmt {
    std::unique_ptr<Expr> expr;
public:
    ReturnStmt(std::unique_ptr<Expr> e) : expr(std::move(e)) {}
    void execute() override {
        throw ReturnException(expr ? expr->eval() : Value(0));
    }
};

// ----------------------------------------------------------------------
// Parser
// ----------------------------------------------------------------------
class Parser {
    Lexer lex;
    Token cur;
    void advance() { cur = lex.next(); }
    void expect(TokenType t) {
        if (cur.type != t) throw std::runtime_error("Syntax error");
        advance();
    }
    bool isRelOp() {
        return cur.type == TOK_EQ || cur.type == TOK_NE ||
               cur.type == TOK_LT || cur.type == TOK_LE ||
               cur.type == TOK_GT || cur.type == TOK_GE;
    }

public:
    Parser(const char* src) : lex(src) { advance(); }

    std::unique_ptr<Expr> parseExpression();
    std::vector<std::unique_ptr<Stmt>> parseBlock();
    std::unique_ptr<Stmt> parseStatement();
    ClassDef parseClass();
    void parseTopLevel();

private:
    std::unique_ptr<Expr> parsePrimary();
    std::unique_ptr<Expr> parseMulDiv();
    std::unique_ptr<Expr> parseAddSub();
    std::unique_ptr<Expr> parseRelational();
};

std::unique_ptr<Expr> Parser::parsePrimary() {
    if (cur.type == TOK_NUMBER) {
        int64_t n = cur.numVal;
        advance();
        return std::make_unique<NumberExpr>(n);
    }
    else if (cur.type == TOK_IDENTIFIER) {
        std::string name = cur.text;
        advance();
        // array access: ident '[' expr ']'
        if (cur.type == TOK_LBRACKET) {
            advance();
            auto idx = parseExpression();
            expect(TOK_RBRACKET);
            return std::make_unique<ArrayElemExpr>(name, std::move(idx));
        }
        // method call: ident '.' ident '(' args ')'
        else if (cur.type == TOK_DOT) {
            advance();
            if (cur.type != TOK_IDENTIFIER) throw std::runtime_error("Expected member/method name");
            std::string member = cur.text;
            advance();
            if (cur.type == TOK_LPAREN) {
                // method call
                expect(TOK_LPAREN);
                std::vector<std::unique_ptr<Expr>> args;
                if (cur.type != TOK_RPAREN) {
                    args.push_back(parseExpression());
                    while (cur.type == TOK_COMMA) {
                        advance();
                        args.push_back(parseExpression());
                    }
                }
                expect(TOK_RPAREN);
                return std::make_unique<MethodCallExpr>(name, member, std::move(args));
            } else {
                // member variable access
                return std::make_unique<MemberVarExpr>(name, member);
            }
        }
        else {
            return std::make_unique<VarExpr>(name);
        }
    }
    else if (cur.type == TOK_LPAREN) {
        advance();
        auto e = parseExpression();
        expect(TOK_RPAREN);
        return e;
    }
    throw std::runtime_error("Expected primary expression");
}

std::unique_ptr<Expr> Parser::parseMulDiv() {
    auto lhs = parsePrimary();
    while (cur.type == TOK_STAR || cur.type == TOK_SLASH) {
        char op = (cur.type == TOK_STAR) ? '*' : '/';
        advance();
        auto rhs = parsePrimary();
        lhs = std::make_unique<BinaryExpr>(op, std::move(lhs), std::move(rhs));
    }
    return lhs;
}

std::unique_ptr<Expr> Parser::parseAddSub() {
    auto lhs = parseMulDiv();
    while (cur.type == TOK_PLUS || cur.type == TOK_MINUS) {
        char op = (cur.type == TOK_PLUS) ? '+' : '-';
        advance();
        auto rhs = parseMulDiv();
        lhs = std::make_unique<BinaryExpr>(op, std::move(lhs), std::move(rhs));
    }
    return lhs;
}

std::unique_ptr<Expr> Parser::parseRelational() {
    auto lhs = parseAddSub();
    if (isRelOp()) {
        TokenType op = cur.type;
        advance();
        auto rhs = parseAddSub();
        lhs = std::make_unique<RelationalExpr>(op, std::move(lhs), std::move(rhs));
    }
    return lhs;
}

std::unique_ptr<Expr> Parser::parseExpression() {
    return parseRelational();
}

std::vector<std::unique_ptr<Stmt>> Parser::parseBlock() {
    expect(TOK_LBRACE);
    std::vector<std::unique_ptr<Stmt>> stmts;
    while (cur.type != TOK_RBRACE && cur.type != TOK_EOF) {
        stmts.push_back(parseStatement());
    }
    expect(TOK_RBRACE);
    return stmts;
}

std::unique_ptr<Stmt> Parser::parseStatement() {
    if (cur.type == TOK_INT) {
        advance();
        if (cur.type != TOK_IDENTIFIER) throw std::runtime_error("Expected variable name");
        std::string name = cur.text;
        advance();
        // array declaration: int ident[constant];
        if (cur.type == TOK_LBRACKET) {
            advance();
            if (cur.type != TOK_NUMBER) throw std::runtime_error("Array size must be constant");
            int size = (int)cur.numVal;
            advance();
            expect(TOK_RBRACKET);
            expect(TOK_SEMICOLON);
            return std::make_unique<ArrayDeclStmt>(name, size);
        }
        else {
            std::unique_ptr<Expr> init = nullptr;
            if (cur.type == TOK_ASSIGN) {
                advance();
                init = parseExpression();
            }
            expect(TOK_SEMICOLON);
            return std::make_unique<VarDeclStmt>(name, std::move(init));
        }
    }
    else if (cur.type == TOK_IDENTIFIER) {
        std::string name = cur.text;
        advance();
        // check if it's a class name (object declaration)
        auto classIt = classes.find(name);
        if (classIt != classes.end()) {
            if (cur.type != TOK_IDENTIFIER) throw std::runtime_error("Expected variable name");
            std::string varName = cur.text;
            advance();
            expect(TOK_SEMICOLON);
            return std::make_unique<ObjectDeclStmt>(name, varName);
        }
        // assignment: ident = expr;
        if (cur.type == TOK_ASSIGN) {
            advance();
            auto expr = parseExpression();
            expect(TOK_SEMICOLON);
            return std::make_unique<AssignStmt>(name, std::move(expr));
        }
        // array assignment: ident[expr] = expr;
        else if (cur.type == TOK_LBRACKET) {
            advance();
            auto idx = parseExpression();
            expect(TOK_RBRACKET);
            expect(TOK_ASSIGN);
            auto val = parseExpression();
            expect(TOK_SEMICOLON);
            return std::make_unique<ArrayAssignStmt>(name, std::move(idx), std::move(val));
        }
        // dot: either method call or member assignment
        else if (cur.type == TOK_DOT) {
            advance();
            if (cur.type != TOK_IDENTIFIER) throw std::runtime_error("Expected member/method name");
            std::string member = cur.text;
            advance();
            if (cur.type == TOK_LPAREN) {
                // method call
                expect(TOK_LPAREN);
                std::vector<std::unique_ptr<Expr>> args;
                if (cur.type != TOK_RPAREN) {
                    args.push_back(parseExpression());
                    while (cur.type == TOK_COMMA) {
                        advance();
                        args.push_back(parseExpression());
                    }
                }
                expect(TOK_RPAREN);
                expect(TOK_SEMICOLON);
                auto expr = std::make_unique<MethodCallExpr>(name, member, std::move(args));
                return std::make_unique<ExprStmt>(std::move(expr));
            } else if (cur.type == TOK_ASSIGN) {
                // member assignment: obj.member = expr;
                advance();
                auto val = parseExpression();
                expect(TOK_SEMICOLON);
                return std::make_unique<MemberAssignStmt>(name, member, std::move(val));
            } else {
                throw std::runtime_error("Expected '(' or '=' after member name");
            }
        }
        else {
            throw std::runtime_error("Expected assignment or method call");
        }
    }
    else if (cur.type == TOK_PRINT) {
        advance();
        auto expr = parseExpression();
        expect(TOK_SEMICOLON);
        return std::make_unique<PrintStmt>(std::move(expr));
    }
    else if (cur.type == TOK_IF) {
        advance();
        expect(TOK_LPAREN);
        auto cond = parseExpression();
        expect(TOK_RPAREN);
        auto thenBlock = parseBlock();
        std::vector<std::unique_ptr<Stmt>> elseBlock;
        if (cur.type == TOK_ELSE) {
            advance();
            elseBlock = parseBlock();
        }
        return std::make_unique<IfStmt>(std::move(cond), std::move(thenBlock), std::move(elseBlock));
    }
    else if (cur.type == TOK_WHILE) {
        advance();
        expect(TOK_LPAREN);
        auto cond = parseExpression();
        expect(TOK_RPAREN);
        auto body = parseBlock();
        return std::make_unique<WhileStmt>(std::move(cond), std::move(body));
    }
    else if (cur.type == TOK_RETURN) {
        advance();
        std::unique_ptr<Expr> expr = nullptr;
        if (cur.type != TOK_SEMICOLON) {
            expr = parseExpression();
        }
        expect(TOK_SEMICOLON);
        return std::make_unique<ReturnStmt>(std::move(expr));
    }
    else if (cur.type == TOK_SEMICOLON) {
        advance();
        return std::make_unique<EmptyStmt>();
    }
    throw std::runtime_error("Unexpected statement");
}

ClassDef Parser::parseClass() {
    expect(TOK_CLASS);
    if (cur.type != TOK_IDENTIFIER) throw std::runtime_error("Expected class name");
    std::string className = cur.text;
    advance();
    expect(TOK_LBRACE);
    ClassDef klass;
    klass.name = className;
    while (cur.type != TOK_RBRACE && cur.type != TOK_EOF) {
        if (cur.type == TOK_INT || cur.type == TOK_VOID) {
            TokenType retType = cur.type;
            advance(); // consume int/void
            if (cur.type != TOK_IDENTIFIER) throw std::runtime_error("Expected member/method name");
            std::string name = cur.text;
            advance();
            // Check if it's a method (next token is '(')
            if (cur.type == TOK_LPAREN) {
                // Method
                auto method = std::make_unique<ASTFunction>();
                method->name = name;
                method->ownerClass = &klass;
                method->returnType = (retType == TOK_INT ? "int" : "void");
                expect(TOK_LPAREN);
                // Parse parameters
                if (cur.type == TOK_INT) {
                    advance();
                    if (cur.type != TOK_IDENTIFIER) throw std::runtime_error("Expected param name");
                    method->params.push_back(cur.text);
                    advance();
                    while (cur.type == TOK_COMMA) {
                        advance();
                        expect(TOK_INT);
                        if (cur.type != TOK_IDENTIFIER) throw std::runtime_error("Expected param name");
                        method->params.push_back(cur.text);
                        advance();
                    }
                }
                expect(TOK_RPAREN);
                method->body = parseBlock();
                ASTFunction* funcPtr = method.release();
                klass.methods[funcPtr->name] = funcPtr;
            } else {
                // Member variable
                expect(TOK_SEMICOLON);
                klass.memberNames.push_back(name);
                klass.memberOffsets[name] = klass.memberNames.size() - 1;
            }
        } else {
            throw std::runtime_error("Unexpected token in class body");
        }
    }
    expect(TOK_RBRACE);
    return klass;
}

void Parser::parseTopLevel() {
    while (cur.type != TOK_EOF) {
        if (cur.type == TOK_CLASS) {
            ClassDef c = parseClass();
            classes[c.name] = c;
        } else {
            auto stmt = parseStatement();
            stmt->execute();
        }
    }
}

// ----------------------------------------------------------------------
// Main
// ----------------------------------------------------------------------
int main() {
    const char* source = R"(
        class Counter {
            int value;
            void inc() {
                value = value + 1;
            }
            int get() {
                return value;
            }
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
    )";

    try {
        Parser parser(source);
        parser.parseTopLevel();
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}