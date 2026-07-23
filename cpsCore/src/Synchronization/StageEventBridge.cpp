/*
 * StageEventBridge.cpp
 *
 * See include/cpsCore/Synchronization/StageEventBridge.h for design rationale.
 */

#ifdef __linux__
#  include "/mnt/c/Code/clang-exp/examples/cpscore_tracing/csp_trace.h"
#else
#  include "csp_trace.h"
#endif
#include "cpsCore/Synchronization/StageEventBridge.h"
#include "cpsCore/Logging/CPSLogger.h"


void
StageEventBridge::publishStage(RunStage stage)
{
	if (stageComplete_.num_slots() == 0)
	{
		CPSLOG_ERROR << "StageEventBridge: no listener connected for stage "
					 << (std::fprintf(stderr, "[TRACE] %s, publishStage, %s, EnumMap.convert, Utilities, StageEventBridge, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), EnumMap<RunStage>::convert(stage));
		return;
	}

	stageComplete_(stage);
}

boost::signals2::connection
StageEventBridge::subscribeStage(const OnStageComplete::slot_type& slot)
{
	return stageComplete_.connect(slot);
}
