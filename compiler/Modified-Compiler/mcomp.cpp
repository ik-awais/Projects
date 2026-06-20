// mcomp_fixed.cpp - Fixed Multi-condition switch-case compiler wrapper
// Build: g++ -O2 -std=c++17 mcomp_fixed.cpp -o mcomp

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <cstdlib>
#include <cstdio>
#include <unistd.h>
#include <set>
#include <algorithm>

// Advanced transformer with fixed case duplication bug
class SwitchTransformer {
private:
    std::string src;
    size_t pos;
    size_t len;
    std::string output;
    int currentLine;
    
public:
    SwitchTransformer(const std::string& source) : src(source), pos(0), len(source.size()), currentLine(1) {
        output.reserve(source.size() * 1.2);
    }
    
    std::string transform() {
        while (pos < len) {
            char c = src[pos];
            
            // Track line numbers
            if (c == '\n') {
                currentLine++;
                output += c;
                pos++;
                continue;
            }
            
            // Skip string literals
            if (c == '"' || c == '\'') {
                handleStringLiteral();
                continue;
            }
            
            // Skip comments
            if (c == '/' && pos + 1 < len) {
                if (src[pos + 1] == '/') {
                    handleLineComment();
                    continue;
                } else if (src[pos + 1] == '*') {
                    handleBlockComment();
                    continue;
                }
            }
            
            // Look for case statement
            if (c == 'c' && tryMatchKeyword("case")) {
                handleCaseStatement();
                continue;
            }
            
            output += c;
            pos++;
        }
        
        return output;
    }
    
private:
    bool tryMatchKeyword(const std::string& keyword) {
        if (pos + keyword.size() > len) return false;
        
        // Check if it's a whole word
        if (pos > 0 && (isalnum(src[pos-1]) || src[pos-1] == '_')) return false;
        
        for (size_t i = 0; i < keyword.size(); i++) {
            if (src[pos + i] != keyword[i]) return false;
        }
        
        // Check next character is not part of word
        size_t nextPos = pos + keyword.size();
        if (nextPos < len && (isalnum(src[nextPos]) || src[nextPos] == '_')) return false;
        
        return true;
    }
    
    void handleStringLiteral() {
        char quote = src[pos];
        output += quote;
        pos++;
        
        while (pos < len) {
            if (src[pos] == '\\' && pos + 1 < len) {
                output += src[pos++];
                output += src[pos++];
                continue;
            }
            if (src[pos] == quote) {
                output += src[pos++];
                break;
            }
            output += src[pos++];
        }
    }
    
    void handleLineComment() {
        while (pos < len && src[pos] != '\n') {
            output += src[pos++];
        }
    }
    
    void handleBlockComment() {
        output += src[pos++]; // '/'
        output += src[pos++]; // '*'
        
        while (pos + 1 < len) {
            if (src[pos] == '*' && src[pos + 1] == '/') {
                output += src[pos++];
                output += src[pos++];
                break;
            }
            output += src[pos++];
        }
    }
    
    void handleCaseStatement() {
        size_t startPos = pos;
        
        // Don't output "case" yet - we'll handle it in the transformation
        pos += 4; // Skip "case"
        
        // Skip whitespace
        skipWhitespaceForParsing();
        
        // Check for '('
        if (pos >= len || src[pos] != '(') {
            // Normal case statement - output "case" and rest
            output += "case";
            while (pos < len && src[pos] != ':') {
                output += src[pos++];
            }
            if (pos < len) output += src[pos++];
            return;
        }
        
        // We have a special case with parentheses
        size_t openParen = pos;
        pos++; // Skip '('
        
        // Find matching ')' with nested parentheses support
        int depth = 1;
        size_t closeParen = pos;
        while (closeParen < len && depth > 0) {
            if (src[closeParen] == '(') depth++;
            else if (src[closeParen] == ')') depth--;
            if (depth > 0) closeParen++;
        }
        
        if (closeParen >= len) {
            // No closing paren, treat as normal case
            output += "case";
            pos = startPos + 4;
            while (pos < len && src[pos] != ':') {
                output += src[pos++];
            }
            if (pos < len) output += src[pos++];
            return;
        }
        
        std::string inside = src.substr(openParen + 1, closeParen - openParen - 1);
        
        // Check if this is actually a special case with our operators
        bool hasPipe = inside.find('|') != std::string::npos;
        bool hasRange = inside.find("..") != std::string::npos;
        
        if (!hasPipe && !hasRange) {
            // Normal case with parentheses, keep as is
            output += "case (";
            output += inside;
            output += ")";
            pos = closeParen + 1;
            
            // Skip to colon
            skipWhitespaceForParsing();
            if (pos < len && src[pos] == ':') {
                output += src[pos++];
            }
            return;
        }
        
        // Process the special case - output transformed cases without extra "case"
        std::string replacement = processSpecialCase(inside);
        
        // Skip to colon
        pos = closeParen + 1;
        skipWhitespaceForParsing();
        if (pos < len && src[pos] == ':') {
            pos++; // Skip colon
        }
        
        // Add the replacement (it already contains "case" keywords)
        output += replacement;
    }
    
    std::string processSpecialCase(const std::string& inside) {
        std::vector<std::string> segments;
        std::string current;
        int parenDepth = 0;
        
        for (char c : inside) {
            if (c == '(') parenDepth++;
            else if (c == ')') parenDepth--;
            
            if (c == '|' && parenDepth == 0) {
                if (!current.empty()) {
                    segments.push_back(trim(current));
                }
                current.clear();
            } else {
                current += c;
            }
        }
        if (!current.empty()) {
            segments.push_back(trim(current));
        }
        
        std::string result;
        bool first = true;
        for (const std::string& seg : segments) {
            if (seg.empty()) continue;
            
            size_t dotdot = seg.find("..");
            if (dotdot != std::string::npos) {
                // Range: a..b -> case a ... b:
                std::string left = trim(seg.substr(0, dotdot));
                std::string right = trim(seg.substr(dotdot + 2));
                if (!left.empty() && !right.empty()) {
                    if (!first) result += " ";
                    result += "case " + left + " ... " + right + ":";
                    first = false;
                }
            } else {
                // Single value: a -> case a:
                if (!first) result += " ";
                result += "case " + seg + ":";
                first = false;
            }
        }
        
        return result + " ";
    }
    
    void skipWhitespaceForParsing() {
        while (pos < len && (src[pos] == ' ' || src[pos] == '\t' || src[pos] == '\n' || src[pos] == '\r')) {
            if (src[pos] == '\n') currentLine++;
            pos++;
        }
    }
    
    std::string trim(const std::string& s) const {
        size_t start = s.find_first_not_of(" \t\n\r");
        if (start == std::string::npos) return "";
        size_t end = s.find_last_not_of(" \t\n\r");
        return s.substr(start, end - start + 1);
    }
};

std::string transformSource(const std::string& src) {
    SwitchTransformer transformer(src);
    return transformer.transform();
}

// Usage message
void printUsage(const std::string& program) {
    std::cerr << "mcomp - Advanced C/C++ Compiler with Multi-Condition Switch\n";
    std::cerr << "\nUsage:\n";
    std::cerr << "  mcomp [compiler] source_file [options]\n";
    std::cerr << "  mcomp source_file [options]              (defaults to g++)\n";
    std::cerr << "\nCompiler options:\n";
    std::cerr << "  g++, gcc, clang, clang++                  Specify backend compiler\n";
    std::cerr << "\nExamples:\n";
    std::cerr << "  mcomp g++ test.cpp -o a.out\n";
    std::cerr << "  mcomp gcc test.c -o program\n";
    std::cerr << "  mcomp test.cpp -O2 -o optimized\n";
    std::cerr << "\nSupported switch syntax:\n";
    std::cerr << "  case (1 | 5 | 9):          // Multiple values\n";
    std::cerr << "  case (2..4):               // Range (inclusive)\n";
    std::cerr << "  case (10 | 20..25 | 30):   // Mixed\n";
    std::cerr << "  case (1 | 2 | 3..5 | 10):  // Complex expressions\n";
}

int main(int argc, char** argv) {
    if (argc < 2) {
        printUsage(argv[0]);
        return 1;
    }
    
    std::vector<std::string> args;
    for (int i = 1; i < argc; ++i) {
        args.push_back(argv[i]);
    }
    
    // Determine backend compiler
    std::string backend = "g++";
    size_t startIdx = 0;
    
    std::set<std::string> compilers = {"g++", "gcc", "clang", "clang++", "cc", "c++"};
    if (compilers.find(args[0]) != compilers.end()) {
        backend = args[0];
        startIdx = 1;
    }
    
    // Collect source files and other arguments
    std::vector<std::string> finalArgs;
    std::vector<std::string> tempFiles;
    std::vector<std::string> sourceFiles;
    
    auto isSourceFile = [](const std::string& f) {
        static std::set<std::string> extensions = {".c", ".cpp", ".cc", ".cxx", ".c++", ".cp", ".C"};
        for (const auto& ext : extensions) {
            if (f.size() >= ext.size() && 
                f.compare(f.size() - ext.size(), ext.size(), ext) == 0) {
                return true;
            }
        }
        return false;
    };
    
    // Parse arguments
    bool hasStd = false;
    bool isC = false;
    
    for (size_t i = startIdx; i < args.size(); ++i) {
        const std::string& arg = args[i];
        
        // Skip our marker if present
        if (arg == "-mcomp" || arg == "<mcomp>") continue;
        
        // Check for standard flag
        if (arg.rfind("-std=", 0) == 0) {
            hasStd = true;
            finalArgs.push_back(arg);
            continue;
        }
        
        // Handle source files
        if (!arg.empty() && arg[0] != '-' && isSourceFile(arg)) {
            sourceFiles.push_back(arg);
            
            // Determine if C or C++
            if (arg.size() >= 2 && arg.compare(arg.size()-2, 2, ".c") == 0) {
                isC = true;
            }
            
            // Process source file
            std::ifstream in(arg, std::ios::binary);
            if (!in) {
                std::cerr << "mcomp: error: cannot open " << arg << std::endl;
                return 1;
            }
            
            std::stringstream ss;
            ss << in.rdbuf();
            std::string transformed = transformSource(ss.str());
            in.close();
            
            // Create temporary file
            std::string tmpFile = "/tmp/mcomp_" + std::to_string(getpid()) + 
                                 "_" + std::to_string(i) + 
                                 (isC ? ".c" : ".cpp");
            std::ofstream out(tmpFile, std::ios::binary);
            if (!out) {
                std::cerr << "mcomp: error: cannot create temp file " << tmpFile << std::endl;
                return 1;
            }
            out << transformed;
            out.close();
            
            tempFiles.push_back(tmpFile);
            finalArgs.push_back(tmpFile);
        } else {
            finalArgs.push_back(arg);
        }
    }
    
    // Add default standard if not specified
    if (!hasStd && !sourceFiles.empty()) {
        if (backend == "gcc" || backend == "cc") {
            finalArgs.insert(finalArgs.begin() + startIdx, "-std=c11");
        } else {
            finalArgs.insert(finalArgs.begin() + startIdx, "-std=c++17");
        }
    }
    
    // Build the command
    std::string cmd = backend;
    for (const auto& arg : finalArgs) {
        cmd += " " + arg;
    }
    
    // Execute the compiler
    int rc = std::system(cmd.c_str());
    
    // Cleanup temporary files
    for (const auto& tmp : tempFiles) {
        std::remove(tmp.c_str());
    }
    
    // Handle errors
    if (rc != 0) {
        std::cerr << "mcomp: compilation failed with code " << rc << std::endl;
        return rc >> 8;
    }
    
    return 0;
}
