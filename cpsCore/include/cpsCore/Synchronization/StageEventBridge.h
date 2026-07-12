////////////////////////////////////////////////////////////////////////////////
// StageEventBridge.h
//
// Added for H1 scenario S4 (see experiments/scenarios/S4/definition.md).
//
// Purpose: demonstrate a genuinely cross-component publish/subscribe
// interaction (Synchronization -> Aggregation) whose delivery edge is
// observable only at RUNTIME, combined with a fault-path log edge that is
// observable only STATICALLY (suppressible via LogLevel::NONE). Together
// these two properties make it possible for C4 (static+dynamic) to strictly
// outperform BOTH C2 (static-only) and C3 (dynamic-only) on the same
// scenario -- something no other scenario (S1-S3) in this experiment set
// demonstrates, because in all of them the dynamic trace is always a subset
// of what static analysis already finds.
//
// This mirrors the IDC/Redis publish-subscribe indirection discussed in the
// thesis ("Macro Resolution for Publish-Subscribe Systems"), but is
// intentionally minimal and self-contained (no live Redis / IPC transport
// required), so it is deterministically testable in a single-process unit
// test.
////////////////////////////////////////////////////////////////////////////////
#ifndef CPSCORE_SYNCHRONIZATION_STAGEEVENTBRIDGE_H_
#define CPSCORE_SYNCHRONIZATION_STAGEEVENTBRIDGE_H_

#include "cpsCore/Synchronization/IRunnableObject.h"
#include <boost/signals2.hpp>

/**
 * @brief Publishes RunStage completion events to any subscribed listener via
 * a boost::signals2 signal.
 *
 * The source (Synchronization) component that emits the signal never
 * directly calls the slot function of the subscribing component -- the two
 * are connected only via boost::signals2::connect() at runtime, so a static
 * call graph cannot link a specific publishStage() call site to a specific
 * slot function. Only a runtime trace observing the slot actually executing
 * can recover this edge.
 */
class StageEventBridge
{
public:
	using OnStageComplete = boost::signals2::signal<void(RunStage)>;

	/**
	 * @brief Publish a stage-completion event to all connected listeners.
	 *
	 * If no listener is connected when this is called, an error is logged
	 * (source-visible fault path). This branch is intentionally suppressible
	 * via CPSLogger::LogLevelScope(LogLevel::NONE) at test time, so a
	 * runtime trace recorded during that suppressed window will NOT observe
	 * this edge even though it is present in source -- the LogLevel::NONE
	 * suppression mechanism that makes the fault-path edge static-only.
	 */
	void
	publishStage(RunStage stage);

	/**
	 * @brief Connect a listener slot to the stage-completion signal.
	 * @return the boost::signals2::connection, so the caller can disconnect.
	 */
	boost::signals2::connection
	subscribeStage(const OnStageComplete::slot_type& slot);

private:
	OnStageComplete stageComplete_;
};

#endif /* CPSCORE_SYNCHRONIZATION_STAGEEVENTBRIDGE_H_ */
