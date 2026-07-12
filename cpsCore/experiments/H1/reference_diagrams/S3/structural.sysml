// H1 ground-truth structural diagram — S3: Multi-component runner orchestration
// Derived from CPSCore source + validated against runtime_traces.txt
//
// Fan-out pattern: SimpleRunner dispatches to Aggregation + Utilities + Logging
// simultaneously within each runStage() call.

package 'S3-Structural' {

    // ── Components ──────────────────────────────────────────────────────────
    part def Synchronization {
        part simpleRunner    : SimpleRunner;
        part syncMaster      : SynchronizedRunnerMaster;
    }

    part def Aggregation {
        part aggregator : Aggregator;
    }

    part def Utilities {
        part enumMap : EnumMap;
    }

    part def Logging {
        part raiiLogStream : RAIILogStream;
    }

    // ── Interfaces ──────────────────────────────────────────────────────────
    interface def IAggregator {
        in  feature request  : 'getAll';
        out feature response : 'ObjectList';
    }

    interface def IEnumMap {
        in  feature convert : 'convert';
        out feature label   : 'string';
    }

    interface def IRAIILogStream {
        in feature stream : 'stream';
    }

    // ── Connections ─────────────────────────────────────────────────────────
    // SimpleRunner.runStage → all three targets (fan-out)
    connection : IAggregator
        connect Synchronization::simpleRunner to Aggregation::aggregator;
    connection : IEnumMap
        connect Synchronization::simpleRunner to Utilities::enumMap;
    connection : IRAIILogStream
        connect Synchronization::simpleRunner to Logging::raiiLogStream;

    // SynchronizedRunnerMaster.runAllStages → Logging only
    connection : IRAIILogStream
        connect Synchronization::syncMaster to Logging::raiiLogStream;
}
