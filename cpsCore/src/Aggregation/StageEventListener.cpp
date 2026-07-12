/*
 * StageEventListener.cpp
 *
 * See include/cpsCore/Aggregation/StageEventListener.h for design rationale.
 */

#include "cpsCore/Aggregation/StageEventListener.h"
#include "cpsCore/Synchronization/StageEventBridge.h"
#include "cpsCore/Logging/CPSLogger.h"

#include <functional>

// --- TEMPORARY H1/S4 trace instrumentation --------------------------------
// See src/Synchronization/StageEventBridge.cpp for rationale. This edge
// (signal -> slot delivery) has no suppression mechanism, so it is traced
// unconditionally whenever the slot actually executes.
#include <chrono>
#include <cstdio>
namespace
{
std::string
s4TraceTimestampListener()
{
	using namespace std::chrono;
	auto now = system_clock::now();
	auto us  = duration_cast<microseconds>(now.time_since_epoch()).count() % 1000000;
	std::time_t t = system_clock::to_time_t(now);
	char buf[32];
	std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%S", std::gmtime(&t));
	char out[48];
	std::snprintf(out, sizeof(out), "%s.%06lldZ", buf, (long long) us);
	return out;
}
}
// --- end temporary instrumentation header ---------------------------------

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
	std::fprintf(stderr, "[S4TRACE]%s|StageEventListener.onStageEvent|Synchronization|"
				 "StageEventBridge.publishStage|Aggregation|StageEventListener.onStageEvent|Command|StageEventListener\n",
				 s4TraceTimestampListener().c_str());
	CPSLOG_DEBUG << "StageEventListener received stage " << EnumMap<RunStage>::convert(stage);
}

