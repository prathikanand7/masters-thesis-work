/*
 * StageEventListener.cpp
 *
 * See include/cpsCore/Aggregation/StageEventListener.h for design rationale.
 */

#ifdef __linux__
#  include "/mnt/c/Code/clang-exp/examples/cpscore_tracing/csp_trace.h"
#else
#  include "csp_trace.h"
#endif
#include "cpsCore/Aggregation/StageEventListener.h"
#include "cpsCore/Synchronization/StageEventBridge.h"
#include "cpsCore/Logging/CPSLogger.h"

#include <functional>


void
StageEventListener::attachTo(StageEventBridge& bridge)
{
	connection_ = bridge.subscribeStage(
			std::bind(&StageEventListener::onStageEvent, this, std::placeholders::_1));
}

void
StageEventListener::onStageEvent(RunStage stage)
{
	lastStage_ = stage;
	CPSLOG_DEBUG << "StageEventListener received stage " << (std::fprintf(stderr, "[TRACE] %s, onStageEvent, %s, EnumMap.convert, Utilities, StageEventListener, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), EnumMap<RunStage>::convert(stage));
}
