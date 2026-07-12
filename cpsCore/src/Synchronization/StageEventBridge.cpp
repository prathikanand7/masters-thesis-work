/*
 * StageEventBridge.cpp
 *
 * See include/cpsCore/Synchronization/StageEventBridge.h for design rationale.
 */

#include "cpsCore/Synchronization/StageEventBridge.h"
#include "cpsCore/Logging/CPSLogger.h"

// --- TEMPORARY H1/S4 trace instrumentation -------------------------------
// Emits a pipe-delimited [TRACE] line matching the same format used by the
// csp_matcher-based instrumentation elsewhere in this thesis (see
// Methods, Stage 3: Runtime Trace Collection). Gated on the CURRENT log
// level exactly like the real CPSLOG_ERROR macro (CPSLogger::log() only
// returns the real sink when level >= setLevel_), so this probe reproduces
// the same LogLevel::NONE suppression mechanism as the real CPSLOG_ERROR
// macro rather than unconditionally tracing every call. Removed once
// trace_slice.txt for S4 has been captured
// (see experiments/scenarios/S4/definition.md).
#include <chrono>
#include <cstdio>
namespace
{
std::string
s4TraceTimestamp()
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
// --- end temporary instrumentation header --------------------------------

void
StageEventBridge::publishStage(RunStage stage)
{
	if (stageComplete_.num_slots() == 0)
	{
		if (LogLevel::ERROR >= CPSLogger::instance()->getLogLevel())
		{
			std::fprintf(stderr, "[S4TRACE]%s|RAIILogStream.stream|Synchronization|"
						 "StageEventBridge.publishStage|Logging|RAIILogStream.stream|Command|RAIILogStream\n",
						 s4TraceTimestamp().c_str());
		}
		CPSLOG_ERROR << "StageEventBridge: no listener connected for stage "
					 << EnumMap<RunStage>::convert(stage);
		return;
	}

	stageComplete_(stage);
}

boost::signals2::connection
StageEventBridge::subscribeStage(const OnStageComplete::slot_type& slot)
{
	return stageComplete_.connect(slot);
}
