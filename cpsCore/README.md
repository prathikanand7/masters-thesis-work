# cpsCore

## Dependencies

This project has some dependencies for various functionality. The dependencies are as follows:

```
Prerequisites:
- Eigen3 [header only] (http://eigen.tuxfamily.org)
- Boost [Component: system] (https://www.boost.org/)

Submodules:
- cpp_redis (https://github.com/cpp-redis/cpp_redis)
- Catch2 (https://github.com/catchorg/Catch2)
```

## Cloning and Compiling


```shell script
git clone --recurse-submodules https://github.com/theilem/cpsCore.git 

cd cpsCore
mkdir -p bld/release && cd bld/release

cmake -DCMAKE_BUILD_TYPE=Release ../../
make
make install
```



## Components

### Aggregation

Aggregation defines how objects are aggregated together and contains all the aggregation logic. Check the [aggregation tests](https://github.com/theilem/cpsCore/blob/master/tests/Aggregation/AggregatableObjectTest.cpp) for an example of how Aggregation is done.
    
### Configuration
Configuration defines how configurable objects are made and contains all the configuration logic. Check the [configuration tests](https://github.com/theilem/cpsCore/blob/master/tests/Configuration/ConfigurableObjectTest.cpp) for an example of how Configuration is done.

### Synchronization
Synchronization defines all the runnable objects and contains all the synchronization and run stage logic. Check the [synchronization tests](https://github.com/theilem/cpsCore/blob/master/tests/Synchronization/RunnerTest.cpp) for an example of how Synchronization is done.

### Logger
This contains the logic for the CPSLogger, the logger used in this project.

### Utilities
Utilities contain all helper classes which can be Aggregatable, Configurable, and Runnable. This is a catchall directory for components

## References
Theile, M., Dantsker, O., Nai, R., Caccamo, M., & Yu, S. (2020). uavAP: A Modular Autopilot Framework for UAVs. In AIAA AVIATION 2020 FORUM (p. 3268).

---

## Architectural Communication Analysis (Renaissance + clang-exp)

CPSCore uses a two-stage static+dynamic analysis pipeline to extract and instrument
architectural communications between components.

### Stage 1 — Renaissance: extract cross-component call pairs from the Neo4j graph

The following Cypher query extracts all direct cross-component function calls from the
Renaissance graph. It returns every caller→callee pair where caller and callee belong to
different top-level CPSCore components, excluding test code.

Output: `interface_dependency_table.csv` — one row per unique cross-component call.

```cypher
WITH ['Aggregation', 'Configuration', 'Synchronization', 'Logging', 'Utilities', 'Framework'] AS validComponents

MATCH (callerFunc)-[:Source]->(callerFile)-[:ParentFolder]->(callerFolder)
MATCH (calleeFile)-[:ParentFolder]->(calleeFolder)
MATCH (callerFunc)-[:CppCalls]->(calleeDecl)
MATCH (calleeDecl)-[:Source]->(calleeFile)

WHERE last(split(callerFolder.name, '/')) IN validComponents
  AND last(split(calleeFolder.name, '/')) IN validComponents
  AND last(split(callerFolder.name, '/')) <> last(split(calleeFolder.name, '/'))
  AND NOT toLower(callerFolder.name) CONTAINS 'test'
  AND NOT toLower(calleeFolder.name) CONTAINS 'test'

WITH callerFunc,
     last(split(callerFolder.name, '/')) AS callerComponent,
     calleeDecl.name AS calleeFunction,
     last(split(calleeFolder.name, '/')) AS calleeComponent,
     split(last(split(calleeDecl.name, '/')), '.')[0] AS interface

RETURN DISTINCT last(split(callerFunc.name, '/')) AS `Caller Function`,
                callerComponent AS `Client`,
                last(split(calleeFunction, '/')) AS `Callee Function`,
                interface AS `Interface`,
                calleeComponent AS `Server`
ORDER BY callerComponent, `Caller Function`
```

The input rows have the format:

```
callerFunc.name,                                                                          callerFolder,   calleeFunction,                                                                calleeFolder
"cpp_funcdef//src/Synchronization/SynchronizedRunner.cpp/SynchronizedRunner.runSynchronized", "Synchronization", "cpp_funcdec//include/cpsCore/Aggregation/Aggregator.h/Aggregator.getAll", "Aggregation"
```

### Stage 2 — clang-exp: generate guided instrumentation

`clang-exp` (at `C:\Code\clang-exp`) takes `interface_dependency_table.csv` as input,
generates concrete syntax patterns for each caller→callee pair, locates the matching
call sites in the source using static analysis, and instruments only those sites.

Running the instrumented binary against a specific test produces `trace_slice.txt`
(the **guided trace**) — events scoped to architecturally-relevant cross-component calls.

Running the binary with blanket instrumentation (e.g. LLVM XRay) against the same test
produces the **full trace** — all function calls, including intra-component and
non-architectural ones.

The H2 experiment compares these two instrumentation strategies on the same test runs.
See `experiments/H2/README.md` for the full comparison.
