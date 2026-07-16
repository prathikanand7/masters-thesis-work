// H1 ground-truth structural diagram — S4: Stage event bridge pub-sub routing (constructed scenario)
// Derived from CPSCore source (StageEventBridge/StageEventListener) + validated
// against tests/Synchronization/StageEventBridgeTest.cpp
//
// Constructed to combine a suppressed fault-path log call (static-only-visible)
// with a boost::signals2 dispatch that has no static call edge (dynamic-only-visible),
// so C4 (static+dynamic) is the only condition that recovers both interactions.

package 'S4-Structural' {

    // ── Components ──────────────────────────────────────────────────────────
    part def Synchronization {
        part stageEventBridge : StageEventBridge;
    }

    part def Aggregation {
        part stageEventListener : StageEventListener;
    }

    part def Logging {
        part raiiLogStream : RAIILogStream;
    }

    // ── Interfaces ──────────────────────────────────────────────────────────
    interface def IStageEventListener {
        in feature onStageEvent : 'onStageEvent';
    }

    interface def IRAIILogStream {
        in feature stream : 'stream';
    }

    // ── Connections ─────────────────────────────────────────────────────────
    // Fault path: publishStage() with no listener connected logs CPSLOG_ERROR.
    // Source-visible unconditionally; suppressed at runtime by LogLevel::NONE
    // during the test's first publishStage() call, so a runtime trace of that
    // window will NOT observe this edge -- STATIC-ONLY-VISIBLE.
    connection : IRAIILogStream
        connect Synchronization::stageEventBridge to Logging::raiiLogStream;

    // Dynamic path: publishStage() invokes its boost::signals2 signal, which
    // dispatches to the connected slot. No static call edge links
    // StageEventBridge::publishStage to StageEventListener::onStageEvent --
    // only a runtime trace observing the slot firing recovers this edge --
    // DYNAMIC-ONLY-VISIBLE.
    connection : IStageEventListener
        connect Synchronization::stageEventBridge to Aggregation::stageEventListener;

    // Note (not scored, not in elements.json): StageEventListener::attachTo()
    // calls StageEventBridge::subscribeStage() to wire the connection itself.
    // This is a static call edge (attachTo -> subscribeStage), distinct from
    // the delivery edge above -- it only proves a subscription was set up,
    // not that a stage event was ever dispatched through it.
}
