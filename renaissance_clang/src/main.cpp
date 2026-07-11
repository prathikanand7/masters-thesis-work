// csp_matcher — AST-pattern search/replace tool using Clang C++ API
// (LibTooling + ASTMatchers dynamic parser + Rewriter)
//
// ═══════════════════════════════════════════════════════════════════════════════
// ARCHITECTURE OVERVIEW
// ═══════════════════════════════════════════════════════════════════════════════
//
// The tool takes a C++-like pattern string (e.g. "if ( $cond ) { $$body }"),
// compiles it into a Clang ASTMatcher, runs that matcher against one or more
// target source files, and optionally rewrites matches using a template string.
//
// Pipeline (one pattern, one target file):
//
//   User pattern string  (e.g. "if ( $cond ) { $$body }")
//        │
//        ▼  [Pattern rewrite]
//   Valid C++ with csp_hole_ placeholders  (e.g. "if (csp_hole_cond) { ... }")
//        │
//        ▼  [Synthetic TU parsing]
//   clang::ASTUnit   (parsed in-memory; never written to disk)
//        │
//        ▼  [DSL emitter]
//   ASTMatcher DSL string  (e.g. "ifStmt(hasCondition(expr().bind(\"cond\")))...")
//        │
//        ▼  [Dynamic matcher creation]
//   clang::ast_matchers::internal::DynTypedMatcher   (runtime matcher object)
//        │
//        ▼  [File processing — findMatchesInFile]
//   Parse target .cpp  →  run MatchFinder  →  collect MatchResult list
//        │
//        ▼  [Apply replacements — applyReplacements]
//   Rewritten source text written back to the target file
//
// Key data types:
//   PatternRewrite    — result of $-hole rewriting; holds hole→placeholder map
//   SyntheticSource   — the complete in-memory C++ TU fed to Clang
//   HoleBindings      — per-match map of hole name → captured source text
//   MatchResult       — one match: byte range, raw text, bindings, replacement
//   PatternReplacement— compiled matcher + replacement template + optional filter
//   CspReplPair       — one parsed rule from a rules file (find/replace/filter)
//   CompiledFilter    — runtime-loaded DLL wrapping a user-supplied filter fn
//
// Filter DLL protocol:
//   The user writes a plain C++ function:
//     bool my_filter(int count, const char * const *names,
//                               const char * const *values);
//   csp_matcher compiles it to a shared library at runtime (via MSYS2 g++)
//   and calls it for every candidate match.  No Clang headers are needed
//   inside the filter source file.
//
// ═══════════════════════════════════════════════════════════════════════════════

// ── Includes ─────────────────────────────────────────────────────────────────
#include "clang/AST/ASTContext.h"
#include "clang/AST/Decl.h"
#include "clang/AST/DeclBase.h"
#include "clang/AST/Expr.h"
#include "clang/AST/ExprCXX.h"
#include "clang/AST/Stmt.h"
#include "clang/AST/Type.h"
#include "clang/ASTMatchers/ASTMatchFinder.h"
#include "clang/ASTMatchers/ASTMatchers.h"
#include "clang/ASTMatchers/Dynamic/Diagnostics.h"
#include "clang/ASTMatchers/Dynamic/Parser.h"
#include "clang/ASTMatchers/Dynamic/VariantValue.h"
#include "clang/Basic/Diagnostic.h"
#include "clang/Basic/LangOptions.h"
#include "clang/Basic/SourceLocation.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Frontend/ASTUnit.h"
#include "clang/Lex/Lexer.h"
#include "clang/Rewrite/Core/Rewriter.h"
#include "clang/Tooling/Tooling.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Support/raw_ostream.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iostream>
#include <memory>
#include <optional>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace {

// ── String utilities ─────────────────────────────────────────────────────────
//
// Standalone helpers with no Clang dependency.  All operate on std::string and
// std::optional; none of them include or reference any Clang header.

/* The above code is a comment in C++ that mentions stripping leading and trailing ASCII whitespace. It
seems like it is describing the purpose or functionality of a piece of code that is not shown in the
comment itself. */
// Strip leading and trailing ASCII whitespace.
static std::string trim(const std::string &s) {
  size_t b = 0;
  while (b < s.size() && std::isspace(static_cast<unsigned char>(s[b])))
    ++b;
  size_t e = s.size();
  while (e > b && std::isspace(static_cast<unsigned char>(s[e - 1])))
    --e;
  return s.substr(b, e - b);
}

static bool startsWith(const std::string &s, const std::string &prefix) {
  return s.rfind(prefix, 0) == 0;
}

// Reads an entire file into a string. Returns nullopt if the file cannot be opened.
static std::optional<std::string> readFileContent(const std::string &filePath) {
  std::ifstream in(filePath, std::ios::binary);
  if (!in)
    return std::nullopt;
  std::ostringstream buf;
  buf << in.rdbuf();
  return buf.str();
}

// Escapes backslash, double-quote, and common control characters (\n \r \t)
// so s can be safely printed as a quoted string.
static std::string escapeForPrint(const std::string &s) {
  std::string out;
  out.reserve(s.size() + 8);
  for (char c : s) {
    switch (c) {
    case '\\': out += "\\\\"; break;
    case '"':  out += "\\\""; break;
    case '\n': out += "\\n";  break;
    case '\r': out += "\\r";  break;
    case '\t': out += "\\t";  break;
    default:   out.push_back(c);
    }
  }
  return out;
}

// ── Pattern rewrite ($ → csp_hole_) ──────────────────────────────────────────
//
// Converts the user-written $-hole pattern into valid C++ that Clang can parse.
//
// $name holes become csp_hole_* typed placeholders; $$name holes become
// csp_list_hole_* / csp_param_hole_* sentinels.  The rewritten code is then
// wrapped in a synthetic TU and fed to Clang to produce the AST that the
// DSL emitter traverses.
//
// Key types:
//   PatternRewrite  — rewritten source string + hole-name lists by kind.
//   SyntheticSource — the complete in-memory TU code + patternStartLine offset.

// Reads a C identifier starting at start in pattern; advances end past the last
// character and sets name.  Returns false if no valid identifier is found.
static bool parseHoleIdentifier(const std::string &pattern, size_t start,
                                size_t &end, std::string &name) {
  if (start >= pattern.size())
    return false;
  unsigned char first = static_cast<unsigned char>(pattern[start]);
  if (!std::isalpha(first) && first != '_')
    return false;
  size_t i = start + 1;
  while (i < pattern.size()) {
    unsigned char c = static_cast<unsigned char>(pattern[i]);
    if (!std::isalnum(c) && c != '_')
      break;
    ++i;
  }
  std::string candidate = pattern.substr(start, i - start);
  if (candidate.empty())
    return false;
  name = std::move(candidate);
  end = i;
  return true;
}

static bool isNameLead(char c) {
  unsigned char u = static_cast<unsigned char>(c);
  return std::isalpha(u) || c == '_';
}
static char prevNonSpace(const std::string &s, size_t i) {
  while (i > 0) {
    --i;
    if (!std::isspace(static_cast<unsigned char>(s[i])))
      return s[i];
  }
  return '\0';
}
static char nextNonSpace(const std::string &s, size_t i) {
  while (i < s.size()) {
    if (!std::isspace(static_cast<unsigned char>(s[i])))
      return s[i];
    ++i;
  }
  return '\0';
}

struct PatternRewrite {
  std::string rewritten;
  std::vector<std::string> exprHoles;
  std::vector<std::string> typeHoles;
  std::vector<std::string> functionHoles;
  std::vector<std::string> stmtListHoles;
  std::vector<std::string> paramListHoles;
  std::vector<std::string> unknownCalls; // non-csp_ identifiers used as call targets
};

struct SyntheticSource {
  std::string code;
  unsigned patternStartLine = 1;
};

static std::string rewriteDescDirectives(const std::string &raw) {
  std::string out;
  out.reserve(raw.size() + 128);
  size_t i = 0;
  while (i < raw.size()) {
    size_t lineEnd = raw.find('\n', i);
    if (lineEnd == std::string::npos)
      lineEnd = raw.size();
    std::string line = raw.substr(i, lineEnd - i);
    size_t cpos = line.find("//");
    bool handled = false;
    if (cpos != std::string::npos) {
      std::string code = line.substr(0, cpos);
      std::string body = trim(line.substr(cpos + 2));
      if (!body.empty() && body.front() == '<') {
        out.append(code);
        if (!trim(code).empty()) out.push_back('\n');
        out.append("csp_desc_begin();");
        handled = true;
      } else if (!body.empty() && body.back() == '>') {
        out.append(code);
        if (!trim(code).empty()) out.push_back('\n');
        out.append("csp_desc_end();");
        handled = true;
      }
    }
    if (!handled)
      out.append(line);
    if (lineEnd < raw.size())
      out.push_back('\n');
    i = (lineEnd < raw.size()) ? lineEnd + 1 : lineEnd;
  }
  return out;
}

// Scans the raw pattern for $name / $$name holes, replaces them with typed
// csp_hole_* / csp_list_hole_* / csp_param_hole_* / csp_fn_hole_* placeholders,
// records each hole name and its kind in the returned PatternRewrite struct.
// Calls rewriteDescDirectives first to translate descendant-directive comments.
static PatternRewrite rewritePattern(const std::string &raw) {
  std::string normalized = rewriteDescDirectives(raw);
  PatternRewrite out;
  out.rewritten.reserve(normalized.size() + 128);
  std::unordered_set<std::string> seenExpr, seenType, seenFn, seenStmtList, seenParamList;

  size_t i = 0;
  while (i < normalized.size()) {
    if (normalized[i] != '$') {
      out.rewritten.push_back(normalized[i++]);
      continue;
    }
    bool isList = (i + 1 < normalized.size() && normalized[i + 1] == '$');
    size_t idStart = i + (isList ? 2u : 1u);
    size_t idEnd = idStart;
    std::string name;
    if (!parseHoleIdentifier(normalized, idStart, idEnd, name)) {
      out.rewritten.push_back(normalized[i++]);
      continue;
    }
    if (isList) {
      char prev = prevNonSpace(normalized, i);
      if (prev == '(') {
        if (seenParamList.insert(name).second)
          out.paramListHoles.push_back(name);
        out.rewritten.append("int csp_param_hole_");
        out.rewritten.append(name);
      } else {
        if (seenStmtList.insert(name).second)
          out.stmtListHoles.push_back(name);
        out.rewritten.append("csp_list_hole_");
        out.rewritten.append(name);
        out.rewritten.append("();");
      }
    } else {
      char next = nextNonSpace(normalized, idEnd);
      if (next == '(') {
        if (seenFn.insert(name).second)
          out.functionHoles.push_back(name);
        out.rewritten.append("csp_fn_hole_");
        out.rewritten.append(name);
      } else {
        char prev = prevNonSpace(normalized, i);
        // Convention: a single uppercase letter (T, U, V, …) is always a
        // type hole — consistent with C++ template-parameter naming.
        bool isUpperSingle = (name.size() == 1 &&
                              std::isupper(static_cast<unsigned char>(name[0])));
        bool couldBeTypePos = isUpperSingle ||
                              (prev == '\0' || prev == '{' || prev == ';' ||
                               prev == '}' || prev == ')');
        bool typeFollower = isUpperSingle ||
                            (next == '$' || isNameLead(next));
        if (couldBeTypePos && typeFollower) {
          if (seenType.insert(name).second)
            out.typeHoles.push_back(name);
          out.rewritten.append("csp_type_hole_");
          out.rewritten.append(name);
        } else {
          if (seenExpr.insert(name).second)
            out.exprHoles.push_back(name);
          out.rewritten.append("csp_hole_");
          out.rewritten.append(name);
        }
      }
    }
    i = idEnd;
  }

  // Scan rewritten pattern for non-csp_ identifiers used as call targets
  // (e.g. "foo(" in "foo(csp_hole_x)") so we can forward-declare them.
  {
    std::unordered_set<std::string> seenUnknown;
    const std::string &rw = out.rewritten;
    size_t j = 0;
    while (j < rw.size()) {
      // Skip non-identifier characters
      if (!isNameLead(rw[j])) { ++j; continue; }
      // Read identifier
      size_t start = j;
      while (j < rw.size() && (std::isalnum((unsigned char)rw[j]) || rw[j] == '_'))
        ++j;
      std::string id = rw.substr(start, j - start);
      // Skip whitespace
      size_t k = j;
      while (k < rw.size() && rw[k] == ' ') ++k;
      // Check if followed by '('
      if (k < rw.size() && rw[k] == '(') {
        // Only register if not a csp_ internal name and not a C++ keyword
        static const std::unordered_set<std::string> cppKeywords{
          "if","else","for","while","do","switch","case","return","break",
          "continue","goto","try","catch","throw","new","delete","sizeof",
          "alignof","decltype","noexcept","static_assert","typeid","nullptr"
        };
        if (id.substr(0, 4) != "csp_" && cppKeywords.find(id) == cppKeywords.end()
            && seenUnknown.insert(id).second)
          out.unknownCalls.push_back(id);
      }
    }
  }

  return out;
}

// Returns 1 + the number of '\n' characters in s (i.e. the number of lines).
static unsigned countLines(const std::string &s) {
  return static_cast<unsigned>(1 + std::count(s.begin(), s.end(), '\n'));
}

// Generates forward-declarations for all hole-placeholder identifiers so the
// synthetic TU compiles without errors.  Skips any name already present in
// preamble to avoid redefinition conflicts with user-supplied typed declarations.
static std::string buildPrelude(const PatternRewrite &r,
                                const std::string &preamble = "") {
  std::string code;
  code.append("void csp_desc_begin();\n");
  code.append("void csp_desc_end();\n");
  for (const std::string &h : r.exprHoles) {
    if (!preamble.empty() &&
        preamble.find("csp_hole_" + h) != std::string::npos)
      continue; // preamble provides a typed declaration
    code.append("int csp_hole_"); code.append(h); code.append(" = 0;\n");
  }
  for (const std::string &h : r.typeHoles) {
    if (!preamble.empty() &&
        preamble.find("csp_type_hole_" + h) != std::string::npos)
      continue; // preamble provides a typed declaration
    code.append("using csp_type_hole_"); code.append(h); code.append(" = void;\n");
  }
  for (const std::string &h : r.stmtListHoles) {
    code.append("void csp_list_hole_"); code.append(h); code.append("();\n");
  }
  // Declare fn holes as C-style variadic so calls to them compile
  for (const std::string &h : r.functionHoles) {
    code.append("int csp_fn_hole_"); code.append(h); code.append("(...);\n");
  }
  // Forward-declare any unknown function call targets so Clang produces proper
  // CallExpr nodes (rather than RecoveryExpr from error recovery).
  for (const std::string &fn : r.unknownCalls) {
    code.append("int "); code.append(fn); code.append("(...);\n");
  }
  return code;
}

// Wraps the rewritten pattern in a synthetic function body: the primary parse
// strategy for statement-level patterns (if-stmts, return, expressions, etc.).
static SyntheticSource buildStatementTU(const PatternRewrite &r,
                                        const std::string &preamble = "") {
  SyntheticSource out;
  if (!preamble.empty()) { out.code = preamble; out.code.push_back('\n'); }
  out.code += buildPrelude(r, preamble);
  out.patternStartLine = countLines(out.code) + 1;
  out.code.append("void __csp_pattern_fn() {\n");
  out.code.append(r.rewritten);
  // Ensure the pattern body ends with a semicolon so Clang parses it cleanly
  // (single-expression patterns like "foo($x)" have no trailing ';').
  const std::string &rw = r.rewritten;
  if (!rw.empty() && rw.back() != ';' && rw.back() != '}')
    out.code.append(";");
  out.code.append("\n}\n");
  return out;
}

// Wraps the rewritten pattern as a top-level declaration.  Used as a fallback
// when the statement-level parse yields no AST roots (e.g. function-decl patterns).
static SyntheticSource buildDeclTU(const PatternRewrite &r,
                                   const std::string &preamble = "") {
  SyntheticSource out;
  if (!preamble.empty()) { out.code = preamble; out.code.push_back('\n'); }
  out.code += buildPrelude(r, preamble);
  out.patternStartLine = countLines(out.code);
  out.code.append(r.rewritten);
  out.code.append("\n");
  return out;
}

// ── Synthetic TU parsing (Clang C++ API) ─────────────────────────────────────
//
// parseSyntheticTU() — feeds a SyntheticSource to
// clang::tooling::buildASTFromCodeWithArgs with "-xc++ -std=c++17 -w".
// The result is an in-memory ASTUnit; no file is written to disk.
// Extra compiler flags (--pattern-flags / --pattern-preamble) are forwarded
// here so the pattern sees the same types as the target file.

static std::unique_ptr<clang::ASTUnit>
parseSyntheticTU(const SyntheticSource &src,
                 const std::vector<std::string> &extraArgs = {}) {
  std::vector<std::string> args = {"-xc++", "-std=c++17", "-w"};
  args.insert(args.end(), extraArgs.begin(), extraArgs.end());
  return clang::tooling::buildASTFromCodeWithArgs(src.code, args,
                                                  "csp_pattern.cpp");
}

// ── DSL emitter (Clang C++ AST → matcher DSL string) ─────────────────────────
//
// DslEmitter traverses the AST of the synthetic TU produced in the pattern-rewrite
// stage and produces an ASTMatcher DSL string (e.g.
//   "ifStmt(hasCondition(expr().bind(\"cond\"))).bind(\"__csp_root__\")").
//
// csp_hole_* placeholders are recognised by name and translated to
// expr().bind() / stmt().bind() / parmVarDecl().bind() etc.  For every node
// kind that has a dedicated handler the matcher is structural; unrecognised
// nodes fall back to a hasDescendant() chain so child holes are still captured.
//
// emitStmt() / emitDecl() are the public entry points.  Private helpers cover
// individual node kinds; emitGenericStmt() is the catch-all fallback.

// Strip implicit casts, parens, cleanups, and trivial single-arg copy/move
// constructions to reach the semantically meaningful core expression.
static const clang::Expr *stripExpr(const clang::Expr *e) {
  while (e) {
    if (auto *ice = clang::dyn_cast<clang::ImplicitCastExpr>(e))
      e = ice->getSubExpr();
    else if (auto *pe = clang::dyn_cast<clang::ParenExpr>(e))
      e = pe->getSubExpr();
    else if (auto *ewc = clang::dyn_cast<clang::ExprWithCleanups>(e))
      e = ewc->getSubExpr();
    else if (auto *bt = clang::dyn_cast<clang::CXXBindTemporaryExpr>(e))
      e = bt->getSubExpr();
    else if (auto *ce = clang::dyn_cast<clang::CXXConstructExpr>(e)) {
      // Strip trivial single-arg copy/move constructor wrapping that Clang
      // inserts for by-value arguments (e.g. shared_ptr copy-construction).
      if (ce->getNumArgs() == 1 &&
          !clang::isa<clang::CXXDefaultArgExpr>(ce->getArg(0)))
        e = ce->getArg(0);
      else
        break;
    }
    else
      break;
  }
  return e;
}

// Resolves a (possibly cast-wrapped) DeclRefExpr to its NamedDecl.
static const clang::NamedDecl *getRefDecl(const clang::Expr *e) {
  e = stripExpr(e);
  if (!e) return nullptr;
  auto *ref = clang::dyn_cast<clang::DeclRefExpr>(e);
  if (!ref) return nullptr;
  return clang::dyn_cast_or_null<clang::NamedDecl>(ref->getDecl());
}

// Resolves the callee of a CallExpr to its NamedDecl (direct call or member).
static const clang::NamedDecl *getCalleeDecl(const clang::CallExpr *call) {
  if (auto *decl = call->getCalleeDecl())
    return clang::dyn_cast<clang::NamedDecl>(decl);
  const clang::Expr *callee = stripExpr(call->getCallee());
  if (!callee) return nullptr;
  if (auto *mem = clang::dyn_cast<clang::MemberExpr>(callee))
    return mem->getMemberDecl();
  return getRefDecl(callee);
}

// Walks the synthetic-TU AST and emits an ASTMatcher DSL string.
// emitStmt() dispatches on Stmt subtypes; emitDecl() on Decl subtypes.
// Private helpers handle each recognised node kind; emitGenericStmt() is the
// catch-all fallback that emits hasDescendant() chains for unrecognised nodes.
class DslEmitter {
public:
  std::string emitStmt(const clang::Stmt *stmt) const {
    if (!stmt) return "stmt()";

    // Expr hole detection before dispatching
    if (auto *e = clang::dyn_cast<clang::Expr>(stmt)) {
      std::string hole;
      if (isExprHole(e, &hole))
        return "expr().bind(\"" + hole + "\")";
    }

    // Strip C++ expression wrappers (destructor-cleanup, temporary-binding,
    // copy/move construction, and plain parentheses). These are generated by
    // Clang around STL type usage or as syntactic grouping; they should not
    // affect the matcher DSL.
    if (auto *pe = clang::dyn_cast<clang::ParenExpr>(stmt))
      return "parenExpr(has(" + emitStmt(pe->getSubExpr()) + "))";
    if (auto *ewc = clang::dyn_cast<clang::ExprWithCleanups>(stmt))
      return emitStmt(ewc->getSubExpr());
    if (auto *bt = clang::dyn_cast<clang::CXXBindTemporaryExpr>(stmt))
      return emitStmt(bt->getSubExpr());
    if (auto *ce = clang::dyn_cast<clang::CXXConstructExpr>(stmt)) {
      if (ce->getNumArgs() == 1 &&
          !clang::isa<clang::CXXDefaultArgExpr>(ce->getArg(0)))
        return emitStmt(ce->getArg(0));
      return emitGenericStmt(stmt);
    }

    if (auto *call = clang::dyn_cast<clang::CallExpr>(stmt))
      return emitCallExpr(call);
    if (auto *bin = clang::dyn_cast<clang::BinaryOperator>(stmt))
      return emitBinaryOp(bin);
    if (auto *un = clang::dyn_cast<clang::UnaryOperator>(stmt))
      return emitUnaryOp(un);
    if (auto *ref = clang::dyn_cast<clang::DeclRefExpr>(stmt))
      return emitDeclRefExpr(ref);
    if (auto *mem = clang::dyn_cast<clang::MemberExpr>(stmt))
      return emitMemberExpr(mem);
    if (auto *compound = clang::dyn_cast<clang::CompoundStmt>(stmt))
      return emitCompoundStmt(compound);
    if (auto *ifst = clang::dyn_cast<clang::IfStmt>(stmt))
      return emitIfStmt(ifst);
    if (clang::isa<clang::IntegerLiteral>(stmt))
      return "integerLiteral()";
    if (clang::isa<clang::FloatingLiteral>(stmt))
      return "floatLiteral()";
    if (auto *ret = clang::dyn_cast<clang::ReturnStmt>(stmt)) {
      if (const clang::Expr *val = ret->getRetValue()) {
        std::string inner = emitStmt(val);
        return "returnStmt(has(" + inner + "))";
      }
      return "returnStmt()";
    }

    return emitGenericStmt(stmt);
  }

  std::string emitDecl(const clang::Decl *decl) const {
    if (!decl) return "decl()";
    if (auto *fn = clang::dyn_cast<clang::FunctionDecl>(decl))
      return emitFunctionDecl(fn);
    if (auto *parm = clang::dyn_cast<clang::ParmVarDecl>(decl))
      return emitParmVarDecl(parm);
    return "decl()";
  }

private:
  // ── hole detection ────────────────────────────────────────────────────────
  bool isExprHole(const clang::Expr *e, std::string *name = nullptr) const {
    const clang::NamedDecl *nd = getRefDecl(e);
    if (!nd) return false;
    llvm::StringRef n = nd->getName();
    if (!n.starts_with("csp_hole_")) return false;
    if (name) *name = n.drop_front(9).str();
    return true;
  }

  bool isListHole(const clang::CallExpr *call, std::string *name = nullptr) const {
    const clang::NamedDecl *nd = getCalleeDecl(call);
    if (!nd) return false;
    llvm::StringRef n = nd->getName();
    if (!n.starts_with("csp_list_hole_")) return false;
    if (name) *name = n.drop_front(14).str();
    return true;
  }

  bool isFnHole(const clang::CallExpr *call, std::string *name = nullptr) const {
    const clang::NamedDecl *nd = getCalleeDecl(call);
    if (!nd) return false;
    llvm::StringRef n = nd->getName();
    if (!n.starts_with("csp_fn_hole_")) return false;
    if (name) *name = n.drop_front(12).str();
    return true;
  }

  static bool isSpecialCall(const clang::Stmt *stmt, llvm::StringRef fname) {
    const clang::CallExpr *call = clang::dyn_cast<clang::CallExpr>(stmt);
    if (!call) {
      if (auto *ewc = clang::dyn_cast<clang::ExprWithCleanups>(stmt))
        call = clang::dyn_cast<clang::CallExpr>(ewc->getSubExpr());
    }
    if (!call) return false;
    const clang::NamedDecl *nd = getCalleeDecl(call);
    return nd && nd->getName() == fname;
  }

  // ── CallExpr ──────────────────────────────────────────────────────────────
  std::string emitCallExpr(const clang::CallExpr *call) const {
    // List hole: csp_list_hole_X()
    {
      std::string hole;
      if (isListHole(call, &hole))
        return "stmt().bind(\"" + hole + "\")";
    }

    // Fn hole: csp_fn_hole_f(args) — match any call, bind callee functionDecl
    {
      std::string hole;
      if (isFnHole(call, &hole)) {
        std::vector<std::string> parts;
        for (unsigned i = 0; i < call->getNumArgs(); ++i) {
          const clang::Expr *arg = stripExpr(call->getArg(i));
          if (!arg) continue;
          std::string s = emitStmt(arg);
          if (s != "expr()" && s != "stmt()")
            parts.push_back("hasArgument(" + std::to_string(i) + ", " + s + ")");
        }
        parts.push_back("callee(functionDecl().bind(\"" + hole + "\"))");
        std::string dsl = "callExpr(";
        for (size_t k = 0; k < parts.size(); ++k) {
          if (k) dsl += ", ";
          dsl += parts[k];
        }
        return dsl + ")";
      }
    }

    // Regular call
    std::vector<std::string> parts;

    // Callee constraint
    const clang::Expr *calleeExpr = stripExpr(call->getCallee());
    if (calleeExpr) {
      if (auto *mem = clang::dyn_cast<clang::MemberExpr>(calleeExpr)) {
        std::string n = mem->getMemberNameInfo().getAsString();
        if (!n.empty() && !startsWith(n, "csp_fn_hole_")) {
          // Include the class name so "flush" on CPSLogger != "flush" on ostream
          std::string methodMatcher = "cxxMethodDecl(hasName(\"" + n + "\")";
          if (auto *method =
                  clang::dyn_cast_or_null<clang::CXXMethodDecl>(mem->getMemberDecl())) {
            if (auto *cls = method->getParent())
              methodMatcher += ", ofClass(hasName(\"" + cls->getName().str() + "\"))";
          }
          methodMatcher += ")";
          parts.push_back("callee(" + methodMatcher + ")");

          // Add receiver binding when the implicit object IS an expr hole.
          // This lets $agg in "$agg.method()" be captured for replacement.
          // For non-hole (concrete) receivers we deliberately omit on() to
          // avoid missed matches in TUs with unresolved include errors.
          if (auto *memberCall = clang::dyn_cast<clang::CXXMemberCallExpr>(call)) {
            const clang::Expr *obj =
                stripExpr(memberCall->getImplicitObjectArgument());
            std::string recvHole;
            if (obj && isExprHole(obj, &recvHole))
              parts.push_back("on(expr().bind(\"" + recvHole + "\"))");
          }
        }
      } else {
        const clang::NamedDecl *nd = getRefDecl(calleeExpr);
        if (nd) {
          llvm::StringRef n = nd->getName();
          if (!n.starts_with("csp_fn_hole_") && !n.empty()) {
            // Use cxxMethodDecl when the function is a class member because
            // ofClass() is Matcher<CXXMethodDecl> and is rejected by functionDecl().
            bool isMember = clang::isa<clang::CXXMethodDecl>(nd);
            std::string funcMatcher =
                (isMember ? "cxxMethodDecl" : "functionDecl");
            funcMatcher += "(hasName(\"" + n.str() + "\")";
            if (auto *fn = clang::dyn_cast<clang::FunctionDecl>(nd)) {
              if (auto *cls =
                      clang::dyn_cast<clang::CXXRecordDecl>(fn->getDeclContext()))
                funcMatcher += ", ofClass(hasName(\"" + cls->getName().str() + "\"))";
            }
            funcMatcher += ")";
            parts.push_back("callee(" + funcMatcher + ")");
          }
        }
      }
    }

    // Argument constraints
    for (unsigned i = 0; i < call->getNumArgs(); ++i) {
      const clang::Expr *arg = stripExpr(call->getArg(i));
      if (!arg) continue;
      std::string s = emitStmt(arg);
      if (s != "expr()" && s != "stmt()")
        parts.push_back("hasArgument(" + std::to_string(i) + ", " + s + ")");
    }

    if (parts.empty()) return "callExpr()";
    // Use cxxMemberCallExpr for member calls — required when on() is present
    // (on() is defined for CXXMemberCallExpr, not the base CallExpr).
    bool isMemberCall = clang::isa<clang::CXXMemberCallExpr>(call);
    std::string dsl = isMemberCall ? "cxxMemberCallExpr(" : "callExpr(";
    for (size_t k = 0; k < parts.size(); ++k) {
      if (k) dsl += ", ";
      dsl += parts[k];
    }
    return dsl + ")";
  }

  // ── BinaryOperator ────────────────────────────────────────────────────────
  std::string emitBinaryOp(const clang::BinaryOperator *bin) const {
    std::string op = clang::BinaryOperator::getOpcodeStr(bin->getOpcode()).str();
    std::string lhs = emitStmt(bin->getLHS());
    std::string rhs = emitStmt(bin->getRHS());
    std::string dsl = "binaryOperator(";
    if (!op.empty()) dsl += "hasOperatorName(\"" + op + "\"), ";
    dsl += "hasLHS(" + lhs + "), hasRHS(" + rhs + "))";
    return dsl;
  }

  // ── UnaryOperator ─────────────────────────────────────────────────────────
  std::string emitUnaryOp(const clang::UnaryOperator *un) const {
    std::string op = clang::UnaryOperator::getOpcodeStr(un->getOpcode()).str();
    std::string operand = emitStmt(un->getSubExpr());
    std::string dsl = "unaryOperator(";
    if (!op.empty()) dsl += "hasOperatorName(\"" + op + "\"), ";
    dsl += "hasUnaryOperand(" + operand + "))";
    return dsl;
  }

  // ── DeclRefExpr ───────────────────────────────────────────────────────────
  std::string emitDeclRefExpr(const clang::DeclRefExpr *ref) const {
    std::string hole;
    if (isExprHole(ref, &hole))
      return "expr().bind(\"" + hole + "\")";
    llvm::StringRef n = ref->getDecl() ? ref->getDecl()->getName() : llvm::StringRef{};
    if (n.empty()) return "declRefExpr()";
    return "declRefExpr(to(namedDecl(hasName(\"" + n.str() + "\"))))";
  }

  // ── MemberExpr ────────────────────────────────────────────────────────────
  std::string emitMemberExpr(const clang::MemberExpr *mem) const {
    std::string name = mem->getMemberNameInfo().getAsString();
    if (name.empty() || startsWith(name, "csp_fn_hole_"))
      return "memberExpr()";
    return "memberExpr(member(hasName(\"" + name + "\")))";
  }

  // ── CompoundStmt ──────────────────────────────────────────────────────────
  std::string emitCompoundStmt(const clang::CompoundStmt *cs) const {
    std::vector<std::string> parts;
    std::string listHoleName; // non-desc list hole → bind compoundStmt itself
    bool descMode = false;
    for (const clang::Stmt *s : cs->body()) {
      if (isSpecialCall(s, "csp_desc_begin")) { descMode = true;  continue; }
      if (isSpecialCall(s, "csp_desc_end"))   { descMode = false; continue; }

      if (auto *call = clang::dyn_cast<clang::CallExpr>(s)) {
        std::string hole;
        if (isListHole(call, &hole)) {
          if (descMode) {
            parts.push_back("hasDescendant(stmt().bind(\"" + hole + "\"))");
          } else {
            // Capture entire compound-stmt body: bind the compoundStmt node
            listHoleName = hole;
          }
          continue;
        }
      }

      std::string inner = emitStmt(s);
      parts.push_back(descMode ? "hasDescendant(" + inner + ")"
                                : "hasAnySubstatement(" + inner + ")");
    }
    std::string dsl;
    if (parts.empty()) {
      dsl = "compoundStmt()";
    } else {
      dsl = "compoundStmt(";
      for (size_t k = 0; k < parts.size(); ++k) {
        if (k) dsl += ", ";
        dsl += parts[k];
      }
      dsl += ")";
    }
    // Bind the whole compoundStmt so MatchCollector can extract the body text
    if (!listHoleName.empty())
      dsl += ".bind(\"__cs__" + listHoleName + "\")";
    return dsl;
  }

  // ── IfStmt ────────────────────────────────────────────────────────────────
  std::string emitIfStmt(const clang::IfStmt *ifst) const {
    std::string cond = ifst->getCond() ? emitStmt(ifst->getCond()) : "expr()";
    std::string then = ifst->getThen() ? emitStmt(ifst->getThen()) : "stmt()";
    std::string dsl = "ifStmt(hasCondition(" + cond + "), hasThen(" + then + ")";
    if (const clang::Stmt *el = ifst->getElse())
      dsl += ", hasElse(" + emitStmt(el) + ")";
    return dsl + ")";
  }

  // ── FunctionDecl ──────────────────────────────────────────────────────────
  std::string emitFunctionDecl(const clang::FunctionDecl *fn) const {
    std::vector<std::string> parts;

    llvm::StringRef fnName = fn->getName();
    bool isFnHoleName = fnName.starts_with("csp_fn_hole_");
    if (!isFnHoleName && !fnName.empty()) {
      parts.push_back("hasName(\"" + fnName.str() + "\")");
    }

    // Note: returns(qualType().bind(...)) is NOT supported in the dynamic
    // matcher registry — QualType cannot be bound. Type holes are extracted
    // post-match from the root FunctionDecl.
    std::string retType = fn->getReturnType().getAsString();
    bool isTypeHole = startsWith(retType, "csp_type_hole_");
    if (!isTypeHole && !retType.empty() && retType != "void") {
      // Concrete return type: add hasName constraint only for non-hole cases
      // (skip return type constraint — too complex to express generically)
    }

    // Require a body (pattern has { ... })
    if (fn->hasBody())
      parts.push_back("isDefinition()");

    std::string dsl;
    if (parts.empty()) {
      dsl = "functionDecl()";
    } else {
      dsl = "functionDecl(";
      for (size_t k = 0; k < parts.size(); ++k) {
        if (k) dsl += ", ";
        dsl += parts[k];
      }
      dsl += ")";
    }

    // NOTE: do NOT add .bind(fnHoleName) here — the caller (emitDeclPatternDsl)
    // adds .bind("__csp_root__") on the outside.  Function-name bindings are
    // extracted post-match from the root FunctionDecl (see MatchCollector::run).
    return dsl;
  }

  // ── ParmVarDecl ───────────────────────────────────────────────────────────
  std::string emitParmVarDecl(const clang::ParmVarDecl *parm) const {
    llvm::StringRef n = parm->getName();
    if (n.starts_with("csp_param_hole_"))
      return "parmVarDecl().bind(\"" + n.drop_front(15).str() + "\")";
    if (n.empty()) return "parmVarDecl()";
    return "parmVarDecl(hasName(\"" + n.str() + "\"))";
  }

  // ── Generic fallback ──────────────────────────────────────────────────────
  std::string emitGenericStmt(const clang::Stmt *stmt) const {
    std::vector<std::string> parts;
    for (const clang::Stmt *child : stmt->children()) {
      if (!child) continue;
      std::string s = emitStmt(child);
      if (s != "stmt()" && s != "expr()")
        parts.push_back("hasDescendant(" + s + ")");
    }
    if (parts.empty()) return "stmt()";
    std::string dsl = "stmt(";
    for (size_t k = 0; k < parts.size(); ++k) {
      if (k) dsl += ", ";
      dsl += parts[k];
    }
    return dsl + ")";
  }
};

// ── Pattern → DSL string ──────────────────────────────────────────────────────
//
// Drives the full pipeline from a parsed synthetic-TU ASTUnit to a
// DynTypedMatcher DSL string.  The three stages are:
//   1. Extract AST roots from the synthetic TU.
//   2. Walk the roots with DslEmitter to emit the DSL string.
//   3. Append .bind("__csp_root__") so MatchCollector can find the root node.
//
// Bare-expression-hole roots ($any as the sole pattern) are handled specially:
// re-binding an already-bound expr() is invalid DSL, so the original hole name
// is saved in rootHoleName and the node is rebound as "__csp_root__".

// Returns the body statements of __csp_pattern_fn from the synthetic TU.
static std::vector<const clang::Stmt *>
extractStmtRoots(const clang::ASTUnit &ast) {
  std::vector<const clang::Stmt *> out;
  const clang::TranslationUnitDecl *tu =
      ast.getASTContext().getTranslationUnitDecl();
  for (const clang::Decl *d : tu->decls()) {
    if (auto *fn = clang::dyn_cast<clang::FunctionDecl>(d)) {
      if (fn->getName() == "__csp_pattern_fn" && fn->hasBody()) {
        auto *body = clang::cast<clang::CompoundStmt>(fn->getBody());
        for (const clang::Stmt *s : body->body())
          out.push_back(s);
        return out;
      }
    }
  }
  return out;
}

// Returns top-level decls in csp_pattern.cpp at or after patternStartLine.
// Fallback for when the statement-level parse yields no roots (e.g. function-decl patterns).
static std::vector<const clang::Decl *>
extractDeclRoots(const clang::ASTUnit &ast, unsigned patternStartLine) {
  std::vector<const clang::Decl *> out;
  const clang::TranslationUnitDecl *tu =
      ast.getASTContext().getTranslationUnitDecl();
  const clang::SourceManager &sm = ast.getSourceManager();
  for (const clang::Decl *d : tu->decls()) {
    clang::SourceLocation loc = d->getLocation();
    if (loc.isInvalid()) continue;
    clang::PresumedLoc pl = sm.getPresumedLoc(loc);
    if (pl.isInvalid()) continue;
    std::string fname = pl.getFilename();
    if (fname.find("csp_pattern.cpp") == std::string::npos) continue;
    if (pl.getLine() < patternStartLine) continue;
    out.push_back(d);
  }
  return out;
}

// Emits the ASTMatcher DSL string for statement roots, appending
// .bind("__csp_root__").  For a sole bare-expression-hole root, saves the
// original hole name in *rootHoleName and re-binds the node as "__csp_root__".
static std::string emitPatternDsl(const std::vector<const clang::Stmt *> &roots,
                                   std::string *rootHoleName = nullptr) {
  if (roots.empty()) return "";
  DslEmitter emitter;
  if (roots.size() == 1) {
    std::string dsl = emitter.emitStmt(roots[0]);
    // Detect bare expression hole (e.g. $any → expr().bind("any")).
    // Chaining a second .bind("__csp_root__") produces invalid DSL, so
    // re-bind it as __csp_root__ and record the original hole name.
    const char *exprBindPrefix = "expr().bind(\"";
    if (dsl.rfind(exprBindPrefix, 0) == 0) {
      size_t nameStart = strlen(exprBindPrefix);
      size_t nameEnd   = dsl.find('"', nameStart);
      if (nameEnd != std::string::npos) {
        if (rootHoleName)
          *rootHoleName = dsl.substr(nameStart, nameEnd - nameStart);
        return "expr().bind(\"__csp_root__\")";
      }
    }
    return dsl + ".bind(\"__csp_root__\")";
  }
  // Multiple stmts: require all inside a compound
  std::string dsl = "compoundStmt(";
  for (size_t i = 0; i < roots.size(); ++i) {
    if (i) dsl += ", ";
    dsl += "hasAnySubstatement(" + emitter.emitStmt(roots[i]) + ")";
  }
  return dsl + ").bind(\"__csp_root__\")";
}

// Emits the ASTMatcher DSL string for declaration roots (e.g. function-decl patterns).
static std::string emitDeclPatternDsl(const std::vector<const clang::Decl *> &roots) {
  if (roots.empty()) return "";
  DslEmitter emitter;
  // Use first decl root (multiple decl patterns are rare)
  return emitter.emitDecl(roots[0]) + ".bind(\"__csp_root__\")";
}

// ── Dynamic matcher creation ──────────────────────────────────────────────────
//
// parseDsl() — feeds the emitted DSL string into
// clang::ast_matchers::dynamic::Parser::parseMatcherExpression().
// Returns a DynTypedMatcher on success, or prints a diagnostic and returns
// nullopt on failure (unless --strict is set, which makes main() abort).

static std::optional<clang::ast_matchers::internal::DynTypedMatcher>
parseDsl(const std::string &dsl) {
  if (dsl.empty()) return std::nullopt;
  clang::ast_matchers::dynamic::Diagnostics diag;
  llvm::StringRef code(dsl);
  auto result =
      clang::ast_matchers::dynamic::Parser::parseMatcherExpression(code, &diag);
  if (!result) {
    std::cerr << "DSL parse error for: " << dsl << "\n";
    std::cerr << "  " << diag.toString() << "\n";
    return std::nullopt;
  }
  return result;
}

// ── Source text extraction ────────────────────────────────────────────────────
//
// extractSourceText() — given a SourceRange from a MatchResult, returns the
// verbatim source characters from the SourceManager.  Uses
// Lexer::getLocForEndOfToken to include the final token.

static std::string extractSourceText(clang::SourceRange range,
                                     const clang::SourceManager &sm,
                                     const clang::LangOptions &lo) {
  if (range.isInvalid()) return "";
  clang::SourceLocation start = sm.getSpellingLoc(range.getBegin());
  clang::SourceLocation end =
      clang::Lexer::getLocForEndOfToken(sm.getSpellingLoc(range.getEnd()), 0, sm, lo);
  if (start.isInvalid() || end.isInvalid()) return "";
  bool invalid = false;
  const char *data = sm.getCharacterData(start, &invalid);
  if (invalid || !data) return "";
  unsigned startOff = sm.getFileOffset(start);
  unsigned endOff   = sm.getFileOffset(end);
  if (endOff <= startOff) return "";
  return std::string(data, endOff - startOff);
}

// ── HoleBindings and MatchResult ──────────────────────────────────────────────
//
// Per-match data produced by MatchCollector::run() and consumed by
// applyReplacements() and the output-printing loop.
//
// Two types carry the data for one match:
//   HoleBindings — maps hole names to captured source text.  'single' holds
//                  expressions and named entities; 'list' holds stmt-lists
//                  and param-lists (bound as compound-stmt bodies).
//   MatchResult  — byte range in the file, raw text, bindings, and the
//                  replacement string computed from the template (if any).
//
// applyReplacementTemplate() performs the $name / $$name substitution and
// handles the empty-receiver '.' elision for implicit-this member calls.

// Maps hole names to captured source text.
// 'single': expressions and named entities.  'list': stmt-lists, param-lists.
struct HoleBindings {
  std::unordered_map<std::string, std::string> single;
  std::unordered_map<std::string, std::string> list;
};

// One match: byte range in the target file, raw source text, hole bindings,
// and the replacement string (if --replace / --remove was requested).
struct MatchResult {
  unsigned start = 0;
  unsigned end   = 0;
  std::string raw;
  HoleBindings bindings;
  std::string replacementText;
  bool hasReplacement = false; // true if replace/remove was requested
  bool isRemoval = false;      // true if this is a --remove match
  size_t patternIndex = 0;
};

// Substitutes every $name / $$name reference in the replacement template with
// its captured text from bindings.  Elides a trailing '.' when the receiver
// hole expanded to "" (implicit-this member-call pattern).
static std::string applyReplacementTemplate(const std::string &replacement,
                                            const HoleBindings &bindings) {
  std::string out;
  out.reserve(replacement.size() + 32);
  size_t i = 0;
  while (i < replacement.size()) {
    if (replacement[i] != '$') { out.push_back(replacement[i++]); continue; }
    bool isList = (i + 1 < replacement.size() && replacement[i + 1] == '$');
    size_t start = i + (isList ? 2 : 1);
    size_t end = start;
    std::string holeName;
    if (!parseHoleIdentifier(replacement, start, end, holeName)) {
      out.push_back(replacement[i++]);
      continue;
    }
    if (isList) {
      auto it = bindings.list.find(holeName);
      if (it != bindings.list.end()) out.append(it->second);
    } else {
      auto it = bindings.single.find(holeName);
      std::string subst;
      if (it != bindings.single.end()) {
        subst = it->second;
      } else {
        auto it2 = bindings.list.find(holeName);
        if (it2 != bindings.list.end()) subst = it2->second;
      }
      out.append(subst);
      // If an implicit-receiver hole expanded to "", skip the following '.'
      // so "$agg.method($arg)" becomes "method($arg)" not ".method($arg)".
      if (subst.empty() && end < replacement.size() && replacement[end] == '.')
        ++end;
    }
    i = end;
  }
  return out;
}

// ── Match collector (MatchFinder callback) ────────────────────────────────────
//
// MatchCollector is the MatchFinder::MatchCallback that bridges the Clang
// matching machinery and the tool's result model.  One collector instance is
// created per pattern per target file.
//
// PatternSpec is a lightweight, non-owning view of a compiled pattern:
// it carries the matcher pointer, replacement template, and a type-erased
// filter lambda so MatchCollector does not need CompiledFilter to be complete.

// Forward declarations so PatternReplacement can hold a filter pointer.
struct CompiledFilter;
using CompiledFilterPtr = std::shared_ptr<CompiledFilter>;

// Lightweight, non-owning view of a compiled pattern passed into MatchCollector.
struct PatternSpec {
  const clang::ast_matchers::internal::DynTypedMatcher *matcher;
  std::string replacementTemplate;
  bool remove = false;
  size_t index = 0;
  // Type-erased filter function — avoids depending on CompiledFilter being
  // complete at this point (it is defined later).
  std::function<bool(const HoleBindings &)> filterFn;
  // Hole names for post-match FunctionDecl binding extraction
  std::vector<std::string> typeHoles;
  std::vector<std::string> functionHoles;
  std::vector<std::string> paramListHoles;
  std::vector<std::string> stmtListHoles;
  // When the root is a bare expression hole ($any etc.), the hole name is
  // stored here so MatchCollector can populate it from the root node.
  std::string rootExprHoleName;
};

// MatchFinder::MatchCallback implementation.  For each matched AST node, run():
//   1. Extracts the source range and raw text from SourceManager.
//   2. Populates HoleBindings from the BoundNodes map.
//   3. Handles bare-expression-root patterns via rootExprHoleName.
//   4. Extracts template type arguments ($T holes) from CallExpr specialisation.
//   5. Injects $callerFunc / $callerClass by walking the AST parent chain.
//   6. Calls the optional filter lambda; discards the match on rejection.
//   7. Applies the replacement template and appends the MatchResult.
class MatchCollector : public clang::ast_matchers::MatchFinder::MatchCallback {
public:
  MatchCollector(const PatternSpec &spec, const std::string &sourceText)
      : spec_(spec), sourceText_(sourceText) {}

  void run(const clang::ast_matchers::MatchFinder::MatchResult &result) override {
    const auto &nodeMap = result.Nodes.getMap();
    auto rootIt = nodeMap.find("__csp_root__");
    if (rootIt == nodeMap.end()) return;

    const clang::DynTypedNode &rootNode = rootIt->second;
    clang::SourceRange range = rootNode.getSourceRange();
    if (range.isInvalid()) return;

    clang::SourceLocation startLoc =
        result.SourceManager->getSpellingLoc(range.getBegin());
    if (!result.SourceManager->isInMainFile(startLoc)) return;

    unsigned startOff = result.SourceManager->getFileOffset(startLoc);
    clang::SourceLocation endLoc = clang::Lexer::getLocForEndOfToken(
        result.SourceManager->getSpellingLoc(range.getEnd()), 0,
        *result.SourceManager, result.Context->getLangOpts());
    unsigned endOff = result.SourceManager->getFileOffset(endLoc);
    if (endOff < startOff) return;

    // Collect hole bindings
    HoleBindings bindings;
    for (const auto &kv : nodeMap) {
      if (kv.first == "__csp_root__") continue;

      // Compound-stmt body hole: key is "__cs__holeName"
      // The compoundStmt was bound so we can extract its body text
      if (kv.first.size() > 6 && kv.first.substr(0, 6) == "__cs__") {
        std::string holeName = kv.first.substr(6);
        if (auto *cs = kv.second.get<clang::CompoundStmt>()) {
          unsigned lOff =
              result.SourceManager->getFileOffset(cs->getLBracLoc()) + 1;
          unsigned rOff =
              result.SourceManager->getFileOffset(cs->getRBracLoc());
          std::string bodyText;
          if (rOff > lOff && rOff <= sourceText_.size()) {
            bodyText = sourceText_.substr(lOff, rOff - lOff);
            // Trim leading/trailing whitespace
            size_t s = bodyText.find_first_not_of(" \t\n\r");
            size_t e = bodyText.find_last_not_of(" \t\n\r");
            bodyText = (s != std::string::npos) ? bodyText.substr(s, e - s + 1)
                                                : "";
          }
          bindings.list[holeName] = bodyText;
        }
        continue;
      }

      if (auto *expr = kv.second.get<clang::Expr>()) {
        // CXXThisExpr with implicit 'this' (e.g. unqualified member call
        // "add(x)") has a source range pointing at the member name, not at
        // "this". Detect by extracting text and checking it isn't "this";
        // in that case store "" so applyReplacementTemplate drops the '.'.
        std::string exprText =
            extractSourceText(expr->getSourceRange(), *result.SourceManager,
                              result.Context->getLangOpts());
        if (clang::isa<clang::CXXThisExpr>(expr) && exprText != "this")
          exprText = "";
        bindings.single[kv.first] = exprText;
      } else if (auto *fn = kv.second.get<clang::FunctionDecl>()) {
        bindings.single[kv.first] = fn->getNameAsString();
      } else if (auto *nd = kv.second.get<clang::NamedDecl>()) {
        bindings.single[kv.first] = nd->getNameAsString();
      } else {
        clang::SourceRange hr = kv.second.getSourceRange();
        if (hr.isValid())
          bindings.single[kv.first] = extractSourceText(
              hr, *result.SourceManager, result.Context->getLangOpts());
      }
    }

    // For FunctionDecl roots, extract hole bindings that can't be bound
    // via the dynamic matcher (type holes, function-name holes, param lists)
    if (auto *fn = rootIt->second.get<clang::FunctionDecl>()) {
      for (const auto &h : spec_.typeHoles)
        bindings.single[h] = fn->getReturnType().getAsString();

      for (const auto &h : spec_.functionHoles)
        bindings.single[h] = fn->getNameAsString();

      if (!spec_.paramListHoles.empty()) {
        std::string paramText;
        bool first = true;
        for (const clang::ParmVarDecl *parm : fn->parameters()) {
          if (!first) paramText += ", ";
          paramText += parm->getType().getAsString();
          if (!parm->getName().empty())
            paramText += " " + parm->getNameAsString();
          first = false;
        }
        for (const auto &h : spec_.paramListHoles)
          bindings.list[h] = paramText;
      }

      if (!spec_.stmtListHoles.empty() && fn->getBody()) {
        if (auto *cs = clang::dyn_cast<clang::CompoundStmt>(fn->getBody())) {
          std::string bodyText;
          for (const clang::Stmt *s : cs->body()) {
            std::string st = extractSourceText(
                s->getSourceRange(), *result.SourceManager,
                result.Context->getLangOpts());
            if (!bodyText.empty()) bodyText += "\n  ";
            bodyText += st;
          }
          for (const auto &h : spec_.stmtListHoles)
            bindings.list[h] = bodyText;
        }
      }
    }

    // For CXXMemberCallExpr roots: extract template specialisation type-args
    // in declaration order and map them to unbound type holes (e.g. $T).
    // This lets replacement templates like "$agg.getAll<$T>()" reconstruct
    // the original template argument even though type args can't be bound
    // via the dynamic-matcher expression-binding mechanism.
    if (!spec_.typeHoles.empty()) {
      if (auto *call = rootIt->second.get<clang::CXXMemberCallExpr>()) {
        if (auto *method = call->getMethodDecl()) {
          if (const auto *specArgs =
                  method->getTemplateSpecializationArgs()) {
            unsigned argIdx = 0;
            for (const auto &h : spec_.typeHoles) {
              if (bindings.single.count(h) != 0) { ++argIdx; continue; }
              if (argIdx >= specArgs->size()) break;
              const clang::TemplateArgument &targ = specArgs->get(argIdx++);
              if (targ.getKind() == clang::TemplateArgument::Type) {
                std::string ts =
                    targ.getAsType().getUnqualifiedType().getAsString();
                // Strip elaborated-type prefix ("struct ", "class ", etc.)
                for (const char *pfx : {"struct ", "class ", "enum "}) {
                  std::string p(pfx);
                  if (ts.size() > p.size() &&
                      ts.substr(0, p.size()) == p)
                    ts = ts.substr(p.size());
                }
                bindings.single[h] = ts;
              }
            }
          }
        }
      }
    }

    // When the root is a bare expression hole (e.g. $any), populate the hole
    // binding from the root node's source text so replacement templates work.
    if (!spec_.rootExprHoleName.empty()) {
      clang::SourceRange hr = rootIt->second.getSourceRange();
      if (hr.isValid())
        bindings.single[spec_.rootExprHoleName] =
            extractSourceText(hr, *result.SourceManager,
                              result.Context->getLangOpts());
    }

    // Inject $callerFunc and $callerClass by walking AST parents to find the
    // enclosing function/method.  This lets replacement templates embed them
    // as compile-time string literals instead of parsing __PRETTY_FUNCTION__.
    {
      clang::DynTypedNode cur = rootNode;
      for (int depth = 0; depth < 30; ++depth) {
        auto parents = result.Context->getParents(cur);
        if (parents.empty()) break;
        cur = parents[0];
        if (auto *fn = cur.get<clang::FunctionDecl>()) {
          bindings.single["callerFunc"] = fn->getNameAsString();
          if (auto *rec = clang::dyn_cast_or_null<clang::CXXRecordDecl>(
                  fn->getDeclContext()))
            bindings.single["callerClass"] = rec->getNameAsString();
          else
            bindings.single["callerClass"] = "";
          break;
        }
      }
    }

    MatchResult m;
    m.start = startOff;
    m.end   = endOff;
    m.patternIndex = spec_.index;
    if (endOff >= startOff && endOff <= sourceText_.size())
      m.raw = sourceText_.substr(startOff, endOff - startOff);
    m.bindings = std::move(bindings);

    if (spec_.remove) {
      m.hasReplacement = true;
      m.isRemoval = true;
      m.replacementText = "";
    } else if (!spec_.replacementTemplate.empty()) {
      m.hasReplacement = true;
      m.replacementText =
          applyReplacementTemplate(spec_.replacementTemplate, m.bindings);
    }

    // Apply per-pattern filter (if any) before recording the match.
    if (spec_.filterFn && !spec_.filterFn(m.bindings))
      return;

    results_.push_back(std::move(m));
  }

  std::vector<MatchResult> &results() { return results_; }

private:
  const PatternSpec &spec_;
  const std::string &sourceText_;
  std::vector<MatchResult> results_;
};

// ── Filter compilation ────────────────────────────────────────────────────────
//
// User-written filter functions are compiled into a shared library at runtime
// (via MSYS2 g++) and loaded via LoadLibrary / dlopen.  The DLL exports a
// single C trampoline that csp_matcher calls for every candidate match.
//
// The filter DLL API requires no Clang headers:
//   extern "C" int csp_filter_fn(int count,
//                                const char * const *names,
//                                const char * const *values);
//
// buildFilterSource() generates the trampoline source.  compileFilter() invokes
// the compiler, loads the DLL, and wraps it in a CompiledFilter RAII handle.

// Generates the complete DLL source: #includes the user definitions file and
// emits an exported C trampoline that calls the user function with the captured
// hole values.  Extra literal args in callExpr are re-quoted as needed.
static std::string buildFilterSource(const std::string &callExpr,
                                     const std::string &defsFilePath) {
  std::string funcName, extraArgs;
  auto parenPos = callExpr.find('(');
  if (parenPos == std::string::npos) {
    funcName = trim(callExpr);
  } else {
    funcName = trim(callExpr.substr(0, parenPos));
    auto lastParen = callExpr.rfind(')');
    if (lastParen != std::string::npos && lastParen > parenPos)
      extraArgs = callExpr.substr(parenPos + 1, lastParen - parenPos - 1);
    else
      extraArgs = callExpr.substr(parenPos + 1);
    extraArgs = trim(extraArgs);
  }

  // On Windows, the shell strips double-quotes from arguments, so a user's
  // `cond_equals("x")` may arrive as `cond_equals(x)`.  Re-quote any bare
  // identifiers in extraArgs so the generated C++ code is valid.
  auto quoteExtraArgs = [](const std::string &args) -> std::string {
    std::string out;
    size_t i = 0;
    while (i < args.size()) {
      char c = args[i];
      if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_') {
        size_t start = i;
        while (i < args.size() &&
               (std::isalnum((unsigned char)args[i]) || args[i] == '_'))
          ++i;
        std::string ident = args.substr(start, i - start);
        // Check if followed by '(' — if so, it's a function call, not a string
        size_t j = i;
        while (j < args.size() && args[j] == ' ') ++j;
        if (j < args.size() && args[j] == '(')
          out += ident;       // function call: leave as-is
        else
          out += '"' + ident + '"'; // bare word: re-quote as string literal
      } else {
        out += c;
        ++i;
      }
    }
    return out;
  };

  // Build the call: funcName(count, names, values [, extraArgs])
  std::string callStr = funcName + "(count, names, values";
  if (!extraArgs.empty()) callStr += ", " + quoteExtraArgs(extraArgs);
  callStr += ")";

  std::string defsIncludePath = defsFilePath;
  for (char &c : defsIncludePath) if (c == '\\') c = '/';

  std::string src;
  if (!defsIncludePath.empty())
    src += "#include \"" + defsIncludePath + "\"\n\n";
  src += "#ifdef _WIN32\n"
         "extern \"C\" __declspec(dllexport)\n"
         "#else\n"
         "extern \"C\" __attribute__((visibility(\"default\")))\n"
         "#endif\n";
  src += "int csp_filter_fn(int count,\n"
         "                  const char * const * names,\n"
         "                  const char * const * values)\n"
         "{\n"
         "    return " + callStr + " ? 1 : 0;\n"
         "}\n";
  return src;
}

// Exported DLL function signature (parallel name/value arrays of hole text).
using FilterFn = int (*)(int, const char * const *, const char * const *);

// RAII handle for the compiled filter DLL.  Destructor unloads the library
// and deletes the temporary .dll file from disk.
struct CompiledFilter {
  FilterFn fn = nullptr;
#ifdef _WIN32
  HMODULE handle = nullptr;
  std::string dllPath;
#endif
  CompiledFilter() = default;
  CompiledFilter(const CompiledFilter &) = delete;
  CompiledFilter &operator=(const CompiledFilter &) = delete;
  ~CompiledFilter() {
    fn = nullptr;
#ifdef _WIN32
    if (handle) { FreeLibrary(handle); handle = nullptr; }
    if (!dllPath.empty()) { DeleteFileA(dllPath.c_str()); }
#endif
  }
  bool apply(const HoleBindings &bindings) const {
    if (!fn) return true;
    std::vector<const char *> names, vals;
    names.reserve(bindings.single.size());
    vals.reserve(bindings.single.size());
    for (const auto &kv : bindings.single) {
      names.push_back(kv.first.c_str());
      vals.push_back(kv.second.c_str());
    }
    return fn(static_cast<int>(names.size()), names.data(), vals.data()) != 0;
  }
};
// CompiledFilterPtr already forward-declared above PatternSpec.

// Compiles callExpr's filter DLL via MSYS2 g++, loads it, and resolves
// csp_filter_fn.  Returns a shared CompiledFilter on success;
// sets outError and returns nullopt on any failure.
static std::optional<CompiledFilterPtr>
compileFilter(const std::string &callExpr,
              const std::string &defsFilePath,
              const std::string &mingwRoot,
              std::string &outError) {
#ifdef _WIN32
  char tmpBuf[MAX_PATH + 1] = {};
  if (GetTempPathA(MAX_PATH, tmpBuf) == 0) {
    outError = "GetTempPath failed";
    return std::nullopt;
  }
  static int seq = 0;
  std::string stem = std::string(tmpBuf) + "csp_flt_"
      + std::to_string(static_cast<unsigned long>(GetCurrentProcessId()))
      + "_" + std::to_string(++seq);
  std::string srcPath = stem + ".cpp";
  std::string dllPath = stem + ".dll";
  std::string logPath = stem + ".log";

  {
    std::string absDefsFilePath = defsFilePath;
    if (!defsFilePath.empty()) {
      char absBuf[MAX_PATH + 1] = {};
      if (GetFullPathNameA(defsFilePath.c_str(), MAX_PATH, absBuf, nullptr) != 0)
        absDefsFilePath = absBuf;
    }
    std::ofstream out(srcPath, std::ios::trunc);
    if (!out) {
      outError = "Cannot write filter source: " + srcPath;
      return std::nullopt;
    }
    out << buildFilterSource(callExpr, absDefsFilePath);
  }

  // Compiler: always use MSYS2/MinGW g++ for ABI compatibility with the main binary.
  // The filter DLL uses only C standard library — no Clang/LLVM headers needed.
  std::string compiler = mingwRoot + "/bin/g++";

  std::string cmd =
      "\"" + compiler + "\""
      " -std=c++17 -shared -w"
      " \"" + srcPath + "\""
      " -o \"" + dllPath + "\""
      " > \"" + logPath + "\" 2>&1";
  // On Windows, cmd.exe /c requires extra outer quotes when the command
  // string itself starts with a quoted token (path with spaces).
  cmd = "\"" + cmd + "\"";

  int rc = std::system(cmd.c_str());
  DeleteFileA(srcPath.c_str());

  if (rc != 0) {
    std::ifstream log(logPath);
    std::string logText((std::istreambuf_iterator<char>(log)),
                        std::istreambuf_iterator<char>());
    DeleteFileA(logPath.c_str());
    outError = "Filter compilation failed:\n" + logText;
    return std::nullopt;
  }
  DeleteFileA(logPath.c_str());

  if (GetFileAttributesA(dllPath.c_str()) == INVALID_FILE_ATTRIBUTES) {
    outError = "Filter compiler produced no DLL at: " + dllPath;
    return std::nullopt;
  }

  HMODULE dll = LoadLibraryA(dllPath.c_str());
  if (!dll) {
    outError = "LoadLibrary failed (" + std::to_string(GetLastError()) + "): " + dllPath;
    DeleteFileA(dllPath.c_str());
    return std::nullopt;
  }

  auto fn = reinterpret_cast<FilterFn>(GetProcAddress(dll, "csp_filter_fn"));
  if (!fn) {
    outError = "csp_filter_fn not found in filter DLL";
    FreeLibrary(dll);
    DeleteFileA(dllPath.c_str());
    return std::nullopt;
  }

  auto cf     = std::make_shared<CompiledFilter>();
  cf->fn      = fn;
  cf->handle  = dll;
  cf->dllPath = dllPath;
  return cf;
#else
  (void)callExpr; (void)defsFilePath; (void)mingwRoot;
  outError = "--filter is not supported on this platform.";
  return std::nullopt;
#endif
}

// ── File processing ───────────────────────────────────────────────────────────
//
// Two functions drive the per-file work:
//   findMatchesInFile()  — parses the target file, registers one MatchCollector
//                          per pattern, runs MatchFinder, and returns a
//                          deduplicated MatchResult list.
//   applyReplacements()  — re-parses the file, applies all replacement/removal
//                          edits via clang::Rewriter (outer-match-wins for
//                          overlaps), and returns the modified source text.
//
// PatternReplacement is the fully compiled counterpart to CspReplPair: it owns
// the DynTypedMatcher, replacement template, optional CompiledFilter pointer,
// and hole-kind metadata used by MatchCollector.

// Fully compiled counterpart to CspReplPair: holds the DynTypedMatcher,
// replacement template, optional CompiledFilter, and hole-kind metadata.
struct PatternReplacement {
  std::optional<clang::ast_matchers::internal::DynTypedMatcher> matcher;
  std::string replacementTemplate;
  CompiledFilterPtr filterPtr;
  bool remove = false;
  size_t index = 0;
  // Hole names for post-match FunctionDecl binding extraction
  std::vector<std::string> typeHoles;
  std::vector<std::string> functionHoles;
  std::vector<std::string> paramListHoles;
  std::vector<std::string> stmtListHoles;
  // Non-empty when root is a bare expression hole — the original hole name.
  std::string rootExprHoleName;
};

// Parses targetPath as an ASTUnit, registers one MatchCollector per pattern
// with a MatchFinder, runs the finder, and returns a deduplicated MatchResult list.
static std::vector<MatchResult>
findMatchesInFile(const std::string &targetPath,
                  const std::string &sourceText,
                  const std::vector<std::string> &extraArgs,
                  const std::vector<PatternReplacement> &patterns) {
  std::vector<MatchResult> allResults;

  // Parse the target file as an ASTUnit
  std::vector<std::string> args = {"-xc++", "-std=c++17", "-w"};
  args.insert(args.end(), extraArgs.begin(), extraArgs.end());

  auto ast = clang::tooling::buildASTFromCodeWithArgs(sourceText, args, targetPath);
  if (!ast) {
    std::cerr << "Failed to parse: " << targetPath << "\n";
    return allResults;
  }

  for (const PatternReplacement &pr : patterns) {
    PatternSpec spec;
    spec.matcher             = &*pr.matcher;
    spec.replacementTemplate = pr.replacementTemplate;
    spec.remove              = pr.remove;
    spec.index               = pr.index;
    if (pr.filterPtr) {
      auto fp = pr.filterPtr;
      spec.filterFn = [fp](const HoleBindings &b) { return fp->apply(b); };
    }
    spec.typeHoles        = pr.typeHoles;
    spec.functionHoles    = pr.functionHoles;
    spec.paramListHoles   = pr.paramListHoles;
    spec.stmtListHoles    = pr.stmtListHoles;
    spec.rootExprHoleName = pr.rootExprHoleName;
    MatchCollector collector(spec, sourceText);

    clang::ast_matchers::MatchFinder finder;
    if (!finder.addDynamicMatcher(*pr.matcher, &collector)) {
      std::cerr << "Cannot add matcher for pattern " << pr.index << "\n";
      continue;
    }
    finder.matchAST(ast->getASTContext());

    // Filter is applied inside MatchCollector::run(); just collect results.
    for (MatchResult &m : collector.results())
      allResults.push_back(std::move(m));
  }

  // Deduplicate same-range same-pattern matches
  std::sort(allResults.begin(), allResults.end(),
            [](const MatchResult &a, const MatchResult &b) {
              return a.start < b.start ||
                     (a.start == b.start && a.end > b.end);
            });
  allResults.erase(
      std::unique(allResults.begin(), allResults.end(),
                  [](const MatchResult &a, const MatchResult &b) {
                    return a.start == b.start && a.end == b.end &&
                           a.patternIndex == b.patternIndex;
                  }),
      allResults.end());

  return allResults;
}

// ── Apply replacements via Rewriter ──────────────────────────────────────────

static std::string applyReplacements(const std::string &targetPath,
                                     const std::string &sourceText,
                                     const std::vector<std::string> &extraArgs,
                                     const std::vector<MatchResult> &matches) {
  // Only process matches that have a replacement
  std::vector<const MatchResult *> toReplace;
  for (const auto &m : matches)
    if (m.hasReplacement)
      toReplace.push_back(&m);

  if (toReplace.empty()) return sourceText;

  std::vector<std::string> args = {"-xc++", "-std=c++17", "-w"};
  args.insert(args.end(), extraArgs.begin(), extraArgs.end());

  auto ast = clang::tooling::buildASTFromCodeWithArgs(sourceText, args, targetPath);
  if (!ast) return sourceText;

  clang::SourceManager &sm = ast->getSourceManager();
  clang::Rewriter rewriter(sm, ast->getASTContext().getLangOpts());
  clang::FileID mainFID = sm.getMainFileID();

  // When two matches overlap, keep the LONGER one (outer expression takes
  // priority over inner sub-expression).  Sort by span length descending and
  // greedily select non-overlapping matches.
  std::sort(toReplace.begin(), toReplace.end(),
            [](const MatchResult *a, const MatchResult *b) {
              unsigned la = a->end - a->start;
              unsigned lb = b->end - b->start;
              return la > lb;
            });

  std::vector<const MatchResult *> selected;
  for (const MatchResult *m : toReplace) {
    bool overlaps = false;
    for (const MatchResult *s : selected) {
      if (std::max(m->start, s->start) < std::min(m->end, s->end)) {
        overlaps = true;
        break;
      }
    }
    if (!overlaps) selected.push_back(m);
  }

  // Apply selected replacements back-to-front to preserve byte offsets.
  std::sort(selected.begin(), selected.end(),
            [](const MatchResult *a, const MatchResult *b) {
              return a->start > b->start;
            });

  for (const MatchResult *m : selected) {
    clang::SourceLocation startLoc =
        sm.getLocForStartOfFile(mainFID).getLocWithOffset(
            static_cast<int>(m->start));
    clang::SourceLocation endLoc =
        sm.getLocForStartOfFile(mainFID).getLocWithOffset(
            static_cast<int>(m->end));
    clang::CharSourceRange charRange =
        clang::CharSourceRange::getCharRange(startLoc, endLoc);
    rewriter.ReplaceText(charRange, m->replacementText);
  }

  const llvm::RewriteBuffer *buf = rewriter.getRewriteBufferFor(mainFID);
  if (!buf) return sourceText;
  return std::string(buf->begin(), buf->end());
}

// ── Compilation-database helpers ─────────────────────────────────────────────
//
// Minimal hand-rolled JSON parser for compile_commands.json.
// extractJsonString() / loadCompileDb() — extract the list of 'file' values
// and deduplicate them.  Does not depend on any JSON library.

static std::string extractJsonString(const std::string &json, size_t &pos) {
  ++pos;
  std::string result;
  while (pos < json.size() && json[pos] != '"') {
    if (json[pos] == '\\' && pos + 1 < json.size()) {
      ++pos;
      switch (json[pos]) {
      case '"':  result += '"';  break;
      case '\\': result += '\\'; break;
      case '/':  result += '/';  break;
      case 'n':  result += '\n'; break;
      case 'r':  result += '\r'; break;
      case 't':  result += '\t'; break;
      default:   result += json[pos]; break;
      }
    } else {
      result += json[pos];
    }
    ++pos;
  }
  if (pos < json.size()) ++pos;
  return result;
}

// Extracts and deduplicates the 'file' fields from every object in the array,
// resolving relative paths against the corresponding 'directory' field.
static std::vector<std::string>
parseCompileCommandsFiles(const std::string &json) {
  std::vector<std::string> result;
  std::unordered_set<std::string> seen;
  size_t pos = 0;
  while (pos < json.size()) {
    size_t objStart = json.find('{', pos);
    if (objStart == std::string::npos) break;
    pos = objStart + 1;
    std::string fileVal, dirVal;
    int depth = 1;
    while (pos < json.size() && depth > 0) {
      const char c = json[pos];
      if (c == '{')      { ++depth; ++pos; }
      else if (c == '}') { --depth; ++pos; }
      else if (c == '"') {
        std::string key = extractJsonString(json, pos);
        while (pos < json.size() && std::isspace((unsigned char)json[pos])) ++pos;
        if (pos < json.size() && json[pos] == ':') {
          ++pos;
          while (pos < json.size() && std::isspace((unsigned char)json[pos])) ++pos;
          if (pos < json.size() && json[pos] == '"') {
            std::string val = extractJsonString(json, pos);
            if (key == "file")           fileVal = std::move(val);
            else if (key == "directory") dirVal  = std::move(val);
          }
        }
      } else { ++pos; }
    }
    if (fileVal.empty()) continue;
    for (auto &ch : fileVal) if (ch == '\\') ch = '/';
    for (auto &ch : dirVal)  if (ch == '\\') ch = '/';
    bool isAbsolute = (!fileVal.empty() && fileVal[0] == '/') ||
                      (fileVal.size() >= 2 &&
                       std::isalpha((unsigned char)fileVal[0]) && fileVal[1] == ':');
    if (!isAbsolute && !dirVal.empty()) {
      if (dirVal.back() != '/') dirVal += '/';
      fileVal = dirVal + fileVal;
    }
    if (seen.insert(fileVal).second)
      result.push_back(std::move(fileVal));
  }
  return result;
}

// ── Rules file ────────────────────────────────────────────────────────────────
//
// Parses the text-based find:/replace:/remove:/filter: DSL into a list of
// CspReplPair structs.  The rules file format is line-oriented:
//   find: <pattern>     — starts a new rule (required)
//   replace: <tmpl>     — replacement template (optional)
//   remove:             — delete the match; mutually exclusive with replace:
//   filter: <callexpr>  — filter function for the preceding find: (optional)
//   Blank lines and lines starting with '#' are ignored.

// One rule parsed from a rules file.
struct CspReplPair {
  std::string pattern;
  std::string replacement;
  std::string filter;
  bool remove = false;
};

// Line-by-line parser for rules files.  Recognises find: / replace: / remove: /
// filter: directives; ignores blank lines and lines beginning with '#'.
// Returns nullopt and prints a diagnostic on any parse error.
static std::optional<std::vector<CspReplPair>>
parseRulesFile(const std::string &filePath) {
  std::ifstream in(filePath);
  if (!in) {
    std::cerr << "Cannot open rules file: " << filePath << "\n";
    return std::nullopt;
  }
  std::vector<CspReplPair> pairs;
  std::string line;
  int lineNum = 0;
  while (std::getline(in, line)) {
    ++lineNum;
    std::string t = trim(line);
    if (t.empty() || t[0] == '#') continue;
    if (startsWith(t, "find:")) {
      std::string pattern = trim(t.substr(5));
      if (pattern.empty()) {
        std::cout << filePath << ":" << lineNum << ": empty pattern after 'find:'\n";
        return std::nullopt;
      }
      pairs.push_back({pattern, "", "", false});
    } else if (startsWith(t, "replace:")) {
      if (pairs.empty()) {
        std::cout << filePath << ":" << lineNum << ": 'replace:' without a preceding 'find:'\n";
        return std::nullopt;
      }
      pairs.back().replacement = trim(t.substr(8));
      pairs.back().remove = false;
    } else if (startsWith(t, "remove:")) {
      if (pairs.empty()) {
        std::cerr << filePath << ":" << lineNum << ": 'remove:' without a preceding 'find:'\n";
        return std::nullopt;
      }
      pairs.back().remove = true;
      pairs.back().replacement = "";
    } else if (startsWith(t, "filter:")) {
      std::string filterStr = trim(t.substr(7));
      if (filterStr.empty()) {
        std::cout << filePath << ":" << lineNum << ": empty expression after 'filter:'\n";
        return std::nullopt;
      }
      if (pairs.empty()) {
        std::cout << filePath << ":" << lineNum << ": 'filter:' without a preceding 'find:'\n";
        return std::nullopt;
      }
      pairs.back().filter = filterStr;
    } else {
      std::cerr << filePath << ":" << lineNum
                << ": unrecognised line (expected 'find:', 'replace:', 'remove:', or 'filter:')\n";
      return std::nullopt;
    }
  }
  if (pairs.empty()) {
    std::cerr << "Rules file contains no 'find:' entries: " << filePath << "\n";
    return std::nullopt;
  }
  return pairs;
}

// ── Output modes ─────────────────────────────────────────────────────────────
//
// parseOutputModes() — parses the --output flag value (comma/pipe-separated
// list of "count", "offset", "raw") into a bitmask.  Used by main() to
// control what is printed for each match.

enum OutputMode : unsigned {
  OutputCount  = 1u << 0,
  OutputOffset = 1u << 1,
  OutputRaw    = 1u << 2,
};

static std::optional<unsigned> parseOutputModes(const std::string &value) {
  unsigned mode = 0;
  size_t start = 0;
  while (start <= value.size()) {
    size_t end = value.find_first_of(",|", start);
    std::string token = trim(value.substr(
        start, end == std::string::npos ? std::string::npos : end - start));
    if (!token.empty()) {
      if (token == "count")                             mode |= OutputCount;
      else if (token == "offset" || token == "offsets") mode |= OutputOffset;
      else if (token == "raw" || token == "signature")  mode |= OutputRaw;
      else return std::nullopt;
    }
    if (end == std::string::npos) break;
    start = end + 1;
  }
  if (mode == 0) return std::nullopt;
  return mode;
}

// ── Usage ─────────────────────────────────────────────────────────────────────
//
// printUsage() — prints the full CLI reference to stdout.

static void printUsage() {
  std::cerr
      << "Usage: csp_matcher --csp \"pattern\" [--replace \"tmpl\" | --remove] "
         "[--filter \"call\"] [--csp \"pattern2\"] ...\n"
      << "                   [--filter-defs <filters.cpp>] [--rules <rules.txt>]\n"
      << "                   [--strict] [--find <file.cpp>]... [--db <compile_commands.json>]\n"
      << "                   [--output <modes>] [--max-matches <N>]\n"
      << "\n"
      << "Pattern flags (can be repeated):\n"
      << "  --csp <pattern>      AST match pattern. $hole for exprs/names, $$hole for "
         "stmt/param lists.\n"
      << "  --replace <tmpl>     Replacement template for the preceding --csp.\n"
      << "  --remove             Remove each match of the preceding --csp.\n"
      << "  --filter <call>      Filter function for the preceding --csp.\n"
      << "                       Signature: bool f(const clang::ast_matchers::MatchFinder::MatchResult&)\n"
      << "  --filter-defs <cpp>  File containing filter function definitions.\n"
      << "                       Compiled with MSYS2 g++ against libclang-cpp.\n"
      << "                       Set CSP_CXX or CXX env var to override the compiler.\n"
      << "                       Set MINGW_ROOT env var to override the MSYS2 path.\n"
      << "  --pattern-preamble <code>  Prepend code to every pattern TU.\n"
      << "  --pattern-flags <flag>     Add a compiler flag when parsing patterns.\n"
      << "  --rules <file>       Load find:/replace:/filter: pairs from a rules file.\n"
      << "\n"
      << "Target flags:\n"
      << "  --find <path>        Parse and match in a C++ source file.\n"
      << "  --db <path>          Load source files from a compile_commands.json.\n"
      << "  --find-flags <flag>  Add a compiler flag when parsing target files.\n"
      << "  --strict             Treat pattern parse errors as fatal.\n"
      << "\n"
      << "Output flags:\n"
      << "  --output <modes>     Comma/pipe-separated: count, offset, raw.\n"
      << "  --max-matches <N>    Limit printed match rows per file.\n"
      << "\n"
      << "Rules file format:\n"
      << "  find: <pattern>    replace: <tmpl>    remove:    filter: <call>\n"
      << "  Lines starting with # and blank lines are ignored.\n";
}

} // namespace

// ── main ─────────────────────────────────────────────────────────────────────
//
// Parses CLI arguments into a list of PatternReplacement objects (from
// --csp/--replace/--remove/--filter and --rules), resolves the target file
// list (from --find and --db), compiles any --filter-defs shared library,
// then drives the per-file loop:
//   for each file → findMatchesInFile → print output → applyReplacements.

int main(int argc, char **argv) {
  if (argc < 3) {
    printUsage();
    return 1;
  }

  std::vector<CspReplPair> cspPairs;
  std::vector<std::string> findPaths;
  bool strictMode = false;
  unsigned outputMode = OutputCount | OutputOffset;
  size_t maxPrintedMatchesPerFile = static_cast<size_t>(-1);
  std::string filterDefsPath;
  std::string patternPreamble;
  std::vector<std::string> patternExtraArgs;
  std::vector<std::string> findExtraArgs;

  // MINGW_ROOT: runtime env var overrides compile-time CMake default
  const char *mingwRootEnv = std::getenv("MINGW_ROOT");
  std::string mingwRoot = (mingwRootEnv && mingwRootEnv[0])
                              ? mingwRootEnv
                              : CSP_MINGW_ROOT;

  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
#define REQUIRE_NEXT(flag)                                          \
    if (i + 1 >= argc) {                                            \
      std::cerr << "Missing value for " flag "\n"; return 1;      \
    }
    if (a == "--csp") {
      REQUIRE_NEXT("--csp")
      cspPairs.push_back({argv[++i], "", "", false});
    } else if (a == "--strict") {
      strictMode = true;
    } else if (a == "--find") {
      REQUIRE_NEXT("--find")
      findPaths.push_back(argv[++i]);
    } else if (a == "--db") {
      REQUIRE_NEXT("--db")
      std::string dbPath = argv[++i];
      std::ifstream dbFile(dbPath);
      if (!dbFile) {
        std::cerr << "Cannot open compilation database: " << dbPath << "\n";
        return 1;
      }
      std::string dbContent((std::istreambuf_iterator<char>(dbFile)),
                             std::istreambuf_iterator<char>());
      for (std::string &f : parseCompileCommandsFiles(dbContent))
        findPaths.push_back(std::move(f));
    } else if (a == "--output") {
      REQUIRE_NEXT("--output")
      auto parsed = parseOutputModes(argv[++i]);
      if (!parsed) {
        std::cerr << "Invalid --output value. Use: count, offset, raw\n";
        return 1;
      }
      outputMode = *parsed;
    } else if (a == "--max-matches") {
      REQUIRE_NEXT("--max-matches")
      std::string v = argv[++i];
      size_t pos = 0;
      unsigned long long pv = 0;
      try { pv = std::stoull(v, &pos, 10); } catch (...) { pos = 0; }
      if (pos != v.size()) {
        std::cerr << "Invalid --max-matches value: " << v << "\n";
        return 1;
      }
      maxPrintedMatchesPerFile = static_cast<size_t>(pv);
    } else if (a == "--replace") {
      REQUIRE_NEXT("--replace")
      if (cspPairs.empty()) { std::cerr << "--replace must follow a --csp\n"; return 1; }
      cspPairs.back().replacement = argv[++i];
      cspPairs.back().remove = false;
    } else if (a == "--filter") {
      REQUIRE_NEXT("--filter")
      if (cspPairs.empty()) { std::cerr << "--filter must follow a --csp\n"; return 1; }
      cspPairs.back().filter = argv[++i];
    } else if (a == "--remove") {
      if (cspPairs.empty()) { std::cerr << "--remove must follow a --csp\n"; return 1; }
      cspPairs.back().remove = true;
      cspPairs.back().replacement = "";
    } else if (a == "--filter-defs") {
      REQUIRE_NEXT("--filter-defs")
      filterDefsPath = argv[++i];
    } else if (a == "--pattern-preamble") {
      REQUIRE_NEXT("--pattern-preamble")
      patternPreamble = argv[++i];
    } else if (a == "--pattern-flags") {
      REQUIRE_NEXT("--pattern-flags")
      patternExtraArgs.push_back(argv[++i]);
    } else if (a == "--find-flags") {
      REQUIRE_NEXT("--find-flags")
      findExtraArgs.push_back(argv[++i]);
    } else if (a == "--rules") {
      REQUIRE_NEXT("--rules")
      auto loaded = parseRulesFile(argv[++i]);
      if (!loaded) return 1;
      for (CspReplPair &p : *loaded)
        cspPairs.push_back(std::move(p));
    } else {
      std::cerr << "Unknown argument: " << a << "\n";
      printUsage();
      return 1;
    }
#undef REQUIRE_NEXT
  }

  if (cspPairs.empty()) {
    std::cerr << "At least one --csp is required\n";
    return 1;
  }

  bool anyReplacement = false;
  for (const auto &cp : cspPairs)
    if (!cp.replacement.empty() || cp.remove) { anyReplacement = true; break; }
  if (anyReplacement && findPaths.empty()) {
    std::cerr << "--replace/--remove requires at least one --find target file\n";
    return 1;
  }

  // ── Compile all patterns → DynTypedMatcher ────────────────────────────────
  std::vector<PatternReplacement> compiledPairs;
  int parseExitCode = 0;

  for (size_t pi = 0; pi < cspPairs.size() && parseExitCode == 0; ++pi) {
    const std::string &pat = cspPairs[pi].pattern;
    PatternRewrite rewrite = rewritePattern(pat);

    // Try statement TU first
    SyntheticSource stmtSrc = buildStatementTU(rewrite, patternPreamble);
    auto stmtAST = parseSyntheticTU(stmtSrc, patternExtraArgs);
    std::string dsl;
    std::string rootHoleName;

    if (stmtAST) {
      auto roots = extractStmtRoots(*stmtAST);
      if (!roots.empty()) {
        if (strictMode && stmtAST->getDiagnostics().hasErrorOccurred()) {
          std::cerr << "Pattern[" << pi << "] parse error: pattern has syntax errors\n";
          parseExitCode = 5;
        } else {
          dsl = emitPatternDsl(roots, &rootHoleName);
        }
      }
    }

    if (parseExitCode != 0) continue;

    if (dsl.empty()) {
      // Fallback to declaration TU
      SyntheticSource declSrc = buildDeclTU(rewrite, patternPreamble);
      auto declAST = parseSyntheticTU(declSrc, patternExtraArgs);
      if (declAST) {
        auto roots = extractDeclRoots(*declAST, declSrc.patternStartLine);
        if (!roots.empty()) {
          if (strictMode && declAST->getDiagnostics().hasErrorOccurred()) {
            std::cerr << "Pattern[" << pi << "] parse error: pattern has syntax errors\n";
            parseExitCode = 5;
          } else {
            dsl = emitDeclPatternDsl(roots);
          }
        }
      }
    }

    if (parseExitCode != 0) continue;

    if (dsl.empty()) {
      std::cerr << "Pattern[" << pi << "] parse error: no AST roots extracted\n";
      if (strictMode) { parseExitCode = 5; continue; }
      continue;
    }

    // Print DSL when no target files (diagnostic mode)
    if (findPaths.empty())
      std::cout << "pattern[" << pi << "] DSL: " << dsl << "\n";

    auto matcher = parseDsl(dsl);
    if (!matcher) {
      std::cerr << "Pattern[" << pi << "]: DSL parse failed: " << dsl << "\n";
      if (strictMode) { parseExitCode = 1; continue; }
      continue;
    }

    // Compile filter if requested
    CompiledFilterPtr filterPtr;
    if (!cspPairs[pi].filter.empty()) {
      std::string err;
      auto cf = compileFilter(cspPairs[pi].filter, filterDefsPath, mingwRoot, err);
      if (!cf) {
        std::cout << "Pattern[" << pi << "]: filter compile error: " << err << "\n";
        parseExitCode = 3;
        continue;
      }
      filterPtr = *cf;
    }

    PatternReplacement pr;
    pr.matcher             = matcher;
    pr.replacementTemplate = cspPairs[pi].replacement;
    pr.remove              = cspPairs[pi].remove;
    pr.filterPtr           = std::move(filterPtr);
    pr.index               = pi;
    pr.typeHoles           = rewrite.typeHoles;
    pr.functionHoles       = rewrite.functionHoles;
    pr.paramListHoles      = rewrite.paramListHoles;
    pr.stmtListHoles       = rewrite.stmtListHoles;
    pr.rootExprHoleName    = rootHoleName;
    compiledPairs.push_back(std::move(pr));
  }

  if (parseExitCode != 0) return parseExitCode;
  if (compiledPairs.empty()) {
    if (!findPaths.empty()) {
      std::cerr << "No valid patterns compiled\n";
      return 1;
    }
    return 0; // DSL-only mode already printed
  }
  if (findPaths.empty()) return 0;

  // ── Process target files ──────────────────────────────────────────────────
  unsigned long long grandTotal = 0;
  int exitCode = 0;

  for (const std::string &targetPath : findPaths) {
    auto srcOpt = readFileContent(targetPath);
    if (!srcOpt) {
      std::cerr << "Cannot read file: " << targetPath << "\n";
      exitCode = 1;
      continue;
    }
    const std::string &sourceText = *srcOpt;

    std::vector<MatchResult> matches =
        findMatchesInFile(targetPath, sourceText, findExtraArgs, compiledPairs);

    unsigned long long fileCount = matches.size();
    grandTotal += fileCount;

    // ── Count replacements / removals ───────────────────────────────────
    unsigned long long numReplaced = 0, numRemoved = 0;
    for (const MatchResult &m : matches) {
      if (m.hasReplacement) {
        if (m.isRemoval) ++numRemoved;
        else ++numReplaced;
      }
    }
    bool hasAnyMod = (numReplaced + numRemoved) > 0;

    // ── Apply replacements to file ────────────────────────────────────────
    if (hasAnyMod) {
      std::string modified =
          applyReplacements(targetPath, sourceText, findExtraArgs, matches);
      std::ofstream out(targetPath, std::ios::binary | std::ios::trunc);
      if (!out) {
        std::cerr << "Cannot write: " << targetPath << "\n";
        exitCode = 1;
        continue;
      }
      out << modified;
    }

    // ── Determine how many match lines to print ───────────────────────────
    size_t numPrinted = (maxPrintedMatchesPerFile < static_cast<size_t>(fileCount))
                            ? maxPrintedMatchesPerFile
                            : static_cast<size_t>(fileCount);
    bool truncated = (numPrinted < static_cast<size_t>(fileCount));

    // ── File summary line (count mode) ────────────────────────────────────
    if (outputMode & OutputCount) {
      if (hasAnyMod) {
        // Replacement/removal summary on its own line
        std::cout << "file=" << targetPath;
        if (numRemoved > 0)
          std::cout << " replacements=" << numReplaced
                    << " removals=" << numRemoved << " conflicts=0";
        else
          std::cout << " replacements=" << numReplaced;
        std::cout << "\n";
      }
      // Match count on its own line
      std::cout << "file=" << targetPath << " matches=" << fileCount << "\n";
    }

    // ── Per-match detail lines ─────────────────────────────────────────────
    if (outputMode & (OutputOffset | OutputRaw)) {
      for (size_t i = 0; i < numPrinted; ++i) {
        const MatchResult &m = matches[i];
        std::cout << "match[" << i << "]";
        if (outputMode & OutputOffset)
          std::cout << " start=" << m.start << " end=" << m.end;
        if (outputMode & OutputRaw)
          std::cout << " raw=\"" << escapeForPrint(m.raw) << "\"";
        std::cout << "\n";
      }
    }

    // ── Truncation notice (separate line after match lines) ───────────────
    if (truncated && (outputMode & OutputCount))
      std::cout << "file=" << targetPath
                << " printed=" << numPrinted << " of " << fileCount << " matches\n";
  }

  // ── Grand total (multi-file + count mode) ─────────────────────────────────
  if ((outputMode & OutputCount) && findPaths.size() > 1)
    std::cout << "total_matches=" << grandTotal << "\n";

  return exitCode;
}
