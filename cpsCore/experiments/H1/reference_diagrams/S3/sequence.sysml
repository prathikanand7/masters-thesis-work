// H1 ground-truth sequence diagram — S3: Multi-component runner orchestration
// Derived from CPSCore source + validated against runtime_traces.txt

package 'S3-Sequence' {

    // Participants
    part sync : Synchronization;
    part agg  : Aggregation;
    part util : Utilities;
    part log  : Logging;

    // ── Sequence ─────────────────────────────────────────────────────────────
    // SimpleRunner.runStage — fan-out to all three subsystems
    message m1 from sync.simpleRunner to agg.aggregator
        : 'Aggregator.getAll';          // fetch runnable objects
    message m2 from sync.simpleRunner to util.enumMap
        : 'EnumMap.convert';            // convert RunStage enum to log string
    message m3 from sync.simpleRunner to log.raiiLogStream
        : 'RAIILogStream.stream';       // CPSLOG_DEBUG stage name

    // SimpleRunner.runStages — repeated for each stage in the vector
    message m4 from sync.simpleRunner to util.enumMap
        : 'EnumMap.convert';            // convert stage enum
    message m5 from sync.simpleRunner to log.raiiLogStream
        : 'RAIILogStream.stream';       // CPSLOG_DEBUG / CPSLOG_ERROR

    // SynchronizedRunnerMaster.runAllStages — logs progress
    message m6 from sync.syncMaster to log.raiiLogStream
        : 'RAIILogStream.stream';
}
