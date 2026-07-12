////////////////////////////////////////////////////////////////////////////////
// StageEventListener.h
//
// Added for H1 scenario S4 (see experiments/scenarios/S4/definition.md).
//
// Aggregation-side counterpart of Synchronization::StageEventBridge. Attaches
// to a bridge's boost::signals2 signal and records the most recently
// observed RunStage. The interaction
// "StageEventBridge::publishStage -> StageEventListener::onStageEvent" is
// only observable at runtime (via the connected slot firing); it is NOT a
// direct call edge in the static call graph, since the bridge only ever
// invokes its own signal object (stageComplete_(stage)), never
// onStageEvent() directly.
////////////////////////////////////////////////////////////////////////////////
#ifndef CPSCORE_AGGREGATION_STAGEEVENTLISTENER_H_
#define CPSCORE_AGGREGATION_STAGEEVENTLISTENER_H_

#include "cpsCore/Synchronization/IRunnableObject.h"
#include <boost/signals2.hpp>

class StageEventBridge;

class StageEventListener
{
public:
	StageEventListener() = default;

	/// Connects this listener to the given bridge's stage-completion signal.
	void
	attachTo(StageEventBridge& bridge);

	/// Slot invoked by the connected signal when a stage completes.
	void
	onStageEvent(RunStage stage);

	RunStage
	getLastStage() const
	{
		return lastStage_;
	}

private:
	RunStage lastStage_ = RunStage::SYNCHRONIZE;
	boost::signals2::connection connection_;
};

#endif /* CPSCORE_AGGREGATION_STAGEEVENTLISTENER_H_ */
