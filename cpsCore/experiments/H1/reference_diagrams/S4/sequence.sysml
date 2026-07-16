// H1 ground-truth sequence diagram — S4: Stage event bridge pub-sub routing (constructed scenario)
// Derived from CPSCore source + validated against
// tests/Synchronization/StageEventBridgeTest.cpp ("Stage Event Bridge Pub-Sub Routing")

package 'S4-Sequence' {

    // Participants
    part sync : Synchronization;
    part agg  : Aggregation;
    part log  : Logging;

    // ── Sequence (test order: fault path first, then dynamic path) ───────────

    // 1. publishStage(INIT) called before any listener is attached, wrapped in
    //    CPSLogger::LogLevelScope(LogLevel::NONE). CPSLOG_ERROR fires as a real
    //    call (static-visible) but produces no output at this log level, so it
    //    is absent from a runtime trace of this call -- STATIC-ONLY-VISIBLE.
    message m1 from sync.stageEventBridge to log.raiiLogStream
        : 'RAIILogStream.stream';

    // 2. listener.attachTo(bridge) connects the slot (static call edge,
    //    not part of the scored ground truth -- see structural.sysml note).

    // 3. publishStage(NORMAL) called after attachTo(); the boost::signals2
    //    signal dispatches to the connected slot. No static call edge exists
    //    from publishStage to onStageEvent -- DYNAMIC-ONLY-VISIBLE.
    message m2 from sync.stageEventBridge to agg.stageEventListener
        : 'StageEventListener.onStageEvent';
}
