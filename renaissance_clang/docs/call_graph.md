# csp_matcher — function call graph

```mermaid
flowchart TD
    main(["main()"])

    %% ── CLI setup ──────────────────────────────────────────────────────────
    main -->|"--db"| parseCompileCommandsFiles["parseCompileCommandsFiles()"]
    main -->|"--output"| parseOutputModes["parseOutputModes()"]
    main -->|"--rules"| parseRulesFile["parseRulesFile()"]

    %% ── Pattern compilation loop (per pattern) ─────────────────────────────
    main -->|"per pattern"| rewritePattern["rewritePattern()"]
    rewritePattern --> rewriteDescDirectives["rewriteDescDirectives()"]

    rewritePattern --> buildStatementTU["buildStatementTU()"]
    buildStatementTU --> buildPrelude["buildPrelude()"]
    buildStatementTU --> parseSyntheticTU_s["parseSyntheticTU()"]
    parseSyntheticTU_s -->|"ASTUnit"| extractStmtRoots["extractStmtRoots()"]
    extractStmtRoots -->|"stmt roots"| emitPatternDsl["emitPatternDsl()"]
    emitPatternDsl --> DslEmitter["DslEmitter::emitStmt / emitDecl"]

    rewritePattern -->|"fallback: no stmt roots"| buildDeclTU["buildDeclTU()"]
    buildDeclTU --> buildPrelude
    buildDeclTU --> parseSyntheticTU_d["parseSyntheticTU()"]
    parseSyntheticTU_d -->|"ASTUnit"| extractDeclRoots["extractDeclRoots()"]
    extractDeclRoots -->|"decl roots"| emitDeclPatternDsl["emitDeclPatternDsl()"]
    emitDeclPatternDsl --> DslEmitter

    emitPatternDsl -->|"DSL string"| parseDsl["parseDsl()"]
    emitDeclPatternDsl -->|"DSL string"| parseDsl

    %% ── Filter compilation (optional) ──────────────────────────────────────
    main -->|"if --filter"| compileFilter["compileFilter()"]
    compileFilter --> buildFilterSource["buildFilterSource()"]
    compileFilter -->|"g++ + LoadLibrary"| CompiledFilter[["CompiledFilter (DLL)"]]

    %% ── Per-file loop ───────────────────────────────────────────────────────
    main -->|"per target file"| readFileContent["readFileContent()"]
    main -->|"per target file"| findMatchesInFile["findMatchesInFile()"]
    findMatchesInFile -->|"registers callback"| MatchCollector["MatchCollector::run()"]
    findMatchesInFile -->|"runs"| MatchFinder[["Clang MatchFinder"]]
    MatchFinder --> MatchCollector
    MatchCollector -->|"on each match"| applyReplacementTemplate["applyReplacementTemplate()"]
    MatchCollector -->|"if filter set"| CompiledFilter

    main -->|"if replacements"| applyReplacements["applyReplacements()"]
    applyReplacements -->|"edits source"| Rewriter[["Clang Rewriter"]]

    %% ── Styles ──────────────────────────────────────────────────────────────
    classDef clangApi fill:#dde8f5,stroke:#5588cc
    classDef external fill:#e8f5e9,stroke:#55aa55
    class MatchFinder,Rewriter clangApi
    class CompiledFilter external
```

## Notes

- **Fallback branch**: `buildDeclTU` / `extractDeclRoots` / `emitDeclPatternDsl` are only reached when `extractStmtRoots` returns no roots (e.g. function-declaration patterns).
- **Shared node**: both `buildStatementTU` and `buildDeclTU` call `buildPrelude`.
- **Clang API boundary** (blue): `MatchFinder` and `Rewriter` are Clang library objects, not functions defined in `main.cpp`.
- **DLL boundary** (green): `CompiledFilter` is a runtime-loaded shared library compiled from the user's filter definitions file.
- **`DslEmitter`** is not called directly by `main`; it is internal to `emitPatternDsl` / `emitDeclPatternDsl`.
- **`MatchCollector::run()`** is invoked by `MatchFinder` (Clang callback), not directly by `findMatchesInFile`.
