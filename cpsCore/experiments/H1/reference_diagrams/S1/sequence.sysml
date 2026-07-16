// H1 ground-truth sequence diagram — S1: Aggregator notification chain
// Derived from CPSCore source + validated against runtime_traces.txt

package 'S1Sequence' {

    // Participants
    part sync  : Synchronization;
    part agg   : Aggregation;
    part log   : Logging;

    // ── Sequence ─────────────────────────────────────────────────────────────
    // 1. SynchronizedRunnerMaster constructor logs init
    message m1 from sync.syncRunnerMaster to log.raiiLogStream
        : 'RAIILogStream.stream';

    // 2. SynchronizedRunner.runSynchronized fetches runnable objects
    message m2 from sync.synchronizedRunner to agg.aggregator
        : 'Aggregator.getAll';

    // 3. SynchronizedRunner.runSynchronized flushes + reads logger instance
    message m3 from sync.synchronizedRunner to log.cpsLogger
        : 'CPSLogger.flush';
    message m4 from sync.synchronizedRunner to log.cpsLogger
        : 'CPSLogger.instance';

    // 4. AggregatableRunner.notifyAggregationOnUpdate fetches runnable objects
    message m5 from sync.aggregatableRunner to agg.aggregator
        : 'Aggregator.getAll';

    // 5. SimpleRunner.runStage fetches objects + logs stage
    message m6 from sync.simpleRunner to agg.aggregator
        : 'Aggregator.getAll';
    message m7 from sync.simpleRunner to log.raiiLogStream
        : 'RAIILogStream.stream';

    // 6. SimpleRunner.runStages logs each stage transition
    message m8 from sync.simpleRunner to log.raiiLogStream
        : 'RAIILogStream.stream';

    // 7. SimpleRunner.runAllStages logs init/normal/final stages
    message m9 from sync.simpleRunner to log.raiiLogStream
        : 'RAIILogStream.stream';

    // 8. SynchronizedRunnerMaster.runAllStages + runStage log
    message m10 from sync.syncRunnerMaster to log.raiiLogStream
        : 'RAIILogStream.stream';
    message m11 from sync.syncRunnerMaster to log.raiiLogStream
        : 'RAIILogStream.stream';
}
