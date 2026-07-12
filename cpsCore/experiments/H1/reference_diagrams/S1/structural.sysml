// H1 ground-truth structural diagram — S1: Aggregator notification chain
// Derived from CPSCore source + validated against runtime_traces.txt

package 'S1-Structural' {

    // ── Components ──────────────────────────────────────────────────────────
    part def Synchronization {
        part aggregatableRunner : AggregatableRunner;
        part simpleRunner       : SimpleRunner;
        part synchronizedRunner : SynchronizedRunner;
        part syncRunnerMaster   : SynchronizedRunnerMaster;
    }

    part def Aggregation {
        part aggregator : Aggregator;
    }

    part def Logging {
        part cpsLogger     : CPSLogger;
        part raiiLogStream : RAIILogStream;
    }

    // ── Interfaces ──────────────────────────────────────────────────────────
    interface def IAggregator {
        in  feature request  : 'getAll';
        out feature response : 'ObjectList';
    }

    interface def ICPSLogger {
        in feature flush    : 'flush';
        in feature instance : 'instance';
    }

    interface def IRAIILogStream {
        in feature stream : 'stream';
    }

    // ── Connections ─────────────────────────────────────────────────────────
    // Synchronization → Aggregation
    connection : IAggregator
        connect Synchronization::aggregatableRunner to Aggregation::aggregator;
    connection : IAggregator
        connect Synchronization::simpleRunner       to Aggregation::aggregator;
    connection : IAggregator
        connect Synchronization::synchronizedRunner  to Aggregation::aggregator;

    // Synchronization → Logging (RAIILogStream)
    connection : IRAIILogStream
        connect Synchronization::simpleRunner        to Logging::raiiLogStream;
    connection : IRAIILogStream
        connect Synchronization::syncRunnerMaster    to Logging::raiiLogStream;

    // Synchronization → Logging (CPSLogger)
    connection : ICPSLogger
        connect Synchronization::synchronizedRunner  to Logging::cpsLogger;
}
