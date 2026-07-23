/*
 * StageEventBridgeTest.cpp
 *
 * Runtime driver for H1 scenario S4 (experiments/scenarios/S4/).
 *
 * This test exercises two distinct interactions in a single scenario:
 *
 *   1. FAULT PATH (static-only-visible):
 *      bridge.publishStage(RunStage::INIT) is called BEFORE any listener is
 *      attached, wrapped in CPSLogger::LogLevelScope(LogLevel::NONE). This
 *      triggers the "no listener connected" CPSLOG_ERROR branch in
 *      StageEventBridge::publishStage() -- source-visible (static analysis
 *      sees the CPSLOG_ERROR call site unconditionally), but the log is
 *      suppressed at runtime, so a trace recorded during this test will NOT
 *      observe the Synchronization -> Logging : stream edge.
 *
 *   2. DYNAMIC-ONLY PATH (dynamic-only-visible):
 *      after listener.attachTo(bridge), bridge.publishStage(RunStage::NORMAL)
 *      invokes the internal boost::signals2 signal, which in turn invokes
 *      listener.onStageEvent(). The static call graph shows publishStage()
 *      calling its own signal object and attachTo() calling subscribeStage(),
 *      but NO static edge connects publishStage() to onStageEvent() --
 *      that link exists only once the signal is actually emitted at runtime.
 *      So Synchronization -> Aggregation : onStageEvent is recoverable only
 *      from a runtime trace, not from static analysis.
 *
 * Reference (ground truth, source+behavior derived):
 *   Synchronization -> Logging     : stream        (fault path, #1)
 *   Synchronization -> Aggregation : onStageEvent   (dynamic path, #2)
 *
 * Expected condition scores (see experiments/scenarios/S4/definition.md):
 *   C2 static-only  : misses onStageEvent (no static edge exists)   -> FN=1
 *   C3 dynamic-only : misses stream (suppressed by LogLevel::NONE)  -> FN=1
 *   C4 static+dyn.  : recovers both                                 -> FN=0
 *   => F1(C4) > F1(C2) AND F1(C4) > F1(C3) on the same scenario.
 */

#include <cpsCore/Utilities/Test/TestInfo.h>
#include <cpsCore/Synchronization/StageEventBridge.h>
#include <cpsCore/Aggregation/StageEventListener.h>
#include <cpsCore/Logging/CPSLogger.h>

TEST_CASE("Stage Event Bridge Pub-Sub Routing")
{
	StageEventBridge bridge;

// --- Fault path: publish with no listener attached, log suppressed ---
        {
                CPSLogger::LogLevelScope log(LogLevel::NONE);
                bridge.publishStage(RunStage::INIT);
                // CPSLOG_ERROR "no listener connected" fires here but is suppressed;
                // source-visible (static, confirmed by Neo4j traversal), absent from trace.
        }

	// --- Dynamic-only path: attach listener, publish, cross-component delivery ---
	StageEventListener listener;
	listener.attachTo(bridge);

	bridge.publishStage(RunStage::NORMAL);

	CHECK(listener.getLastStage() == RunStage::NORMAL);
}
