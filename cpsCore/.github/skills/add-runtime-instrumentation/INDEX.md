# add-runtime-instrumentation Skill - Complete Index

## What This Skill Does

The **add-runtime-instrumentation** skill integrates the **renaissance_clang DSL tool** into cpsCore to enable automated code instrumentation and runtime tracing. It allows you to:

- **Inject trace points** into function calls and logging operations automatically
- **Match complex patterns** using a domain-specific language (csp_matcher)
- **Capture runtime metadata** (timestamp, caller, component, location) with minimal code coupling
- **Apply and remove instrumentation** reversibly without permanent source modifications

## Directory Structure

```
.github/skills/add-runtime-instrumentation/
├── INSTALLATION.md          ← Start here for setup
├── README.md                ← Quick start guide  
├── SKILL.md                 ← Comprehensive documentation
├── CONFIGURATION.md         ← How to customize the tool
├── EXAMPLES.md              ← Practical usage examples
├── package.json             ← Skill metadata
└── scripts/
    ├── apply_tracing.ps1           ← Apply instrumentation
    ├── remove_tracing.ps1          ← Remove instrumentation
    ├── invoke_instrumentation.py   ← Python wrapper for agents
    ├── add_tracing.txt             ← Pattern matching rules
    ├── remove_tracing.txt          ← Rules to undo instrumentation
    ├── tracing_filters.cpp         ← Custom C++ filter logic
    └── csp_trace.h                 ← Trace helper functions
```

## File Guide

### Documentation Files

| File | Purpose | Audience | Read Time |
|------|---------|----------|-----------|
| [INSTALLATION.md](INSTALLATION.md) | Setup, prerequisites, verification | DevOps, First-time users | 15 min |
| [README.md](README.md) | Quick start (5-10 minute walkthrough) | New users | 5 min |
| [SKILL.md](SKILL.md) | Complete technical documentation | Power users, architects | 30 min |
| [CONFIGURATION.md](CONFIGURATION.md) | Customization options and paths | Advanced users | 15 min |
| [EXAMPLES.md](EXAMPLES.md) | Real-world usage patterns | Developers, analysts | 20 min |

### Script Files

| File | Purpose | Language | Inputs | Outputs |
|------|---------|----------|--------|---------|
| [apply_tracing.ps1](scripts/apply_tracing.ps1) | Apply instrumentation | PowerShell | Paths, options | Modified `.cpp` files, log |
| [remove_tracing.ps1](scripts/remove_tracing.ps1) | Remove instrumentation | PowerShell | Paths | Restored `.cpp` files |
| [invoke_instrumentation.py](scripts/invoke_instrumentation.py) | Agent wrapper | Python | Action, options | Exit code, console output |

### Configuration Files

| File | Purpose | Content | Editable |
|------|---------|---------|----------|
| [add_tracing.txt](scripts/add_tracing.txt) | Pattern rules to apply | Pattern matching DSL | ✅ Yes |
| [remove_tracing.txt](scripts/remove_tracing.txt) | Rules to strip traces | Pattern matching DSL | ⚠️ Usually no |
| [tracing_filters.cpp](scripts/tracing_filters.cpp) | Custom filter functions | C++ code | ✅ Yes |

### Support Files

| File | Purpose | Role |
|------|---------|------|
| [csp_trace.h](scripts/csp_trace.h) | Trace helper functions | Injected into instrumented source |
| [package.json](package.json) | Skill metadata | NPM/project metadata |

## Quick Navigation

### I want to...

**Get started quickly**
→ Read [README.md](README.md) (5 min)

**Install and verify setup**
→ Follow [INSTALLATION.md](INSTALLATION.md) (15 min)

**Use the tool**
→ Copy example from [EXAMPLES.md](EXAMPLES.md) (↵5 min)

**Customize tracing rules**
→ See [CONFIGURATION.md](CONFIGURATION.md) (10 min)

**Understand the architecture**
→ Read [SKILL.md](SKILL.md) (30 min)

**Troubleshoot issues**
→ Check Troubleshooting sections in relevant docs

**Analyze collected traces**
→ See "Trace Analysis" section in [EXAMPLES.md](EXAMPLES.md)

**Integrate with CI/CD**
→ See "Integration with CI/CD" in [EXAMPLES.md](EXAMPLES.md)

## Key Concepts

### Trace Format

```
[TRACE] HH:MM:SS.mmm, caller_func, caller_component, Callee.method, callee_component, caller_class, file:line
```

**Example:**
```
[TRACE] 14:23:45.832, runStage, Synchronization, Aggregator.getAll, Aggregation, SimpleRunner, SimpleRunner.cpp:67
```

### Two-Phase Approach

1. **Pattern Matching (via csp_matcher)**: Find and replace function calls with trace wrappers
2. **Macro Patching**: Update CPSLOG macro to emit traces on logging calls

### Key Files Modified

- `.cpp` files in `src/` and `tests/`: Trace injections added (reversible)
- `CPSLogger.h`: CPSLOG macro modified (reversible)

## Typical Workflow

```
┌─────────────────────────────────────────┐
│ 1. Apply Instrumentation                │
│ $ .\apply_tracing.ps1                   │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 2. Rebuild cpsCore                      │
│ $ cmake --build ... --target all        │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 3. Run Tests & Collect Traces           │
│ $ ./tests -d yes 2>&1 | tee trace.txt   │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 4. Analyze Traces                       │
│ $ grep "\[TRACE\]" trace.txt | ...      │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│ 5. Remove Instrumentation (Optional)    │
│ $ .\remove_tracing.ps1                  │
└─────────────────────────────────────────┘
```

## Integration Points

### With Other cpsCore Skills

- **draw-sequential-mermaid-general**: Process traces → visualization
- **get-interface-dependency-table**: Document runtime interactions
- **draw-sysml-sequence-model**: Generate formal SysML from traces

### With Development Tools

- VS Code: Launch as task via `.vscode/tasks.json`
- PowerShell: Direct invocation with aliases
- Python: Agent-based automation via `invoke_instrumentation.py`
- CI/CD: GitHub Actions, Jenkins, etc.

## Prerequisite Checklist

- [ ] Renaissance Clang project built (csp_matcher.exe exists)
- [ ] cpsCore configured with CMake (compile_commands.json exists)
- [ ] PowerShell 5.0+ available
- [ ] MSys64/MinGW64 in PATH
- [ ] cpsCore source accessible and writable
- [ ] Read [INSTALLATION.md](INSTALLATION.md)

## Support Resources

| Issue | Resource |
|-------|----------|
| Setup help | [INSTALLATION.md](INSTALLATION.md) |
| First run | [README.md](README.md) |
| Examples | [EXAMPLES.md](EXAMPLES.md) |
| Customization | [CONFIGURATION.md](CONFIGURATION.md) |
| Architecture | [SKILL.md](SKILL.md) |
| Troubleshooting | Troubleshooting sections in docs |

## Version History

- **v1.0.0** (Current): Initial release with core functionality
  - Pattern-based code instrumentation
  - Reversible trace injection
  - Macro-level CPSLOG patching
  - Python agent wrapper

## Technical Specifications

| Aspect | Details |
|--------|---------|
| Language Support | C++ (C++17) |
| Pattern Syntax | renaissance_clang DSL |
| Trace Output | stderr, line-based format |
| Reversibility | Fully reversible (remove_tracing.ps1) |
| Code Coupling | Minimal (conditional includes, macros) |
| Platform | Windows (via PowerShell) + Linux rebuild |

## Notes for Developers

### When to Use This Skill

✅ **Good for:**
- Understanding call flow and component interactions
- Performance analysis and bottleneck identification
- Runtime validation of design assumptions
- Testing distributed system coordination
- Tracing specific code paths

❌ **Not ideal for:**
- Debugging (prefer debugger for stepping)
- Production instrumentation (design for production-ready logging)
- Performance optimization (requires removal for baseline tests)

### Best Practices

1. **Start small**: Use `-ExcludeTests` for quick iteration
2. **Commit first**: Ensure clean git state before applying
3. **Test both**: Verify traces work with and without instrumentation
4. **Document custom rules**: Add comments to `add_tracing.txt` for team understanding
5. **Use filters**: Custom C++ filters reduce spurious matches
6. **Analyze systematically**: Don't rely on visual inspection alone

### Known Limitations

- Requires Windows machine with csp_matcher for applying
- Rebuild required after instrumentation
- Some complex template patterns may not match
- Large traces may consume disk space

## Getting Help

1. **Check appropriate documentation** in this directory
2. **Review troubleshooting sections** (all docs have them)
3. **Try EXAMPLES.md** for your specific use case
4. **Consult INSTALLATION.md** if prerequisites issue
5. **Check apply_log.txt** for pattern matching diagnostics

## Contributors & Attribution

This skill integrates the **renaissance_clang** DSL tool:
- Original tool: C++ pattern matching via Clang libtooling
- Skill adaptation: cpsCore team

## License

[Match cpsCore project license]

---

**Last Updated:** July 2026  
**Skill Version:** 1.0.0  
**Status:** Ready for production use
