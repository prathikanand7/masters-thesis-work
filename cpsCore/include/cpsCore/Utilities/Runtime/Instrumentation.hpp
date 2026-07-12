#ifndef CPS_CORE_UTILITIES_RUNTIME_INSTRUMENTATION_HPP
#define CPS_CORE_UTILITIES_RUNTIME_INSTRUMENTATION_HPP

#include <chrono>
#include <iostream>
#include <mutex>

namespace cps::instrumentation {

class RuntimeTracer {
private:
    static std::mutex& traceMutex()
    {
        static std::mutex mutex;
        return mutex;
    }

public:
    static void trace_enter(const char* component, const char* function)
    {
        std::lock_guard<std::mutex> lock(traceMutex());
        const auto now = std::chrono::system_clock::now();
        const auto ms = std::chrono::time_point_cast<std::chrono::milliseconds>(now);
        const auto timestamp = ms.time_since_epoch().count();
        std::cerr << "[TRACE_ENTER] " << timestamp << " | " << component << "::" << function << "\n";
    }

    static void trace_exit(const char* component, const char* function)
    {
        std::lock_guard<std::mutex> lock(traceMutex());
        const auto now = std::chrono::system_clock::now();
        const auto ms = std::chrono::time_point_cast<std::chrono::milliseconds>(now);
        const auto timestamp = ms.time_since_epoch().count();
        std::cerr << "[TRACE_EXIT] " << timestamp << " | " << component << "::" << function << "\n";
    }

    static void trace_call(
        const char* callerComponent,
        const char* callerFunction,
        const char* calleeComponent,
        const char* calleeFunction)
    {
        std::lock_guard<std::mutex> lock(traceMutex());
        const auto now = std::chrono::system_clock::now();
        const auto ms = std::chrono::time_point_cast<std::chrono::milliseconds>(now);
        const auto timestamp = ms.time_since_epoch().count();
        std::cerr << "[TRACE_CALL] " << timestamp << " | "
                  << callerComponent << "::" << callerFunction << " -> "
                  << calleeComponent << "::" << calleeFunction << "\n";
    }
};

class ScopeTracer {
private:
    const char* component_;
    const char* function_;

public:
    ScopeTracer(const char* component, const char* function)
        : component_(component)
        , function_(function)
    {
        RuntimeTracer::trace_enter(component_, function_);
    }

    ~ScopeTracer()
    {
        RuntimeTracer::trace_exit(component_, function_);
    }
};

} // namespace cps::instrumentation

#define TRACE_COMPONENT(comp) comp

#define CPS_TRACE_CONCAT_INNER(a, b) a##b
#define CPS_TRACE_CONCAT(a, b) CPS_TRACE_CONCAT_INNER(a, b)
#define CPS_TRACE_UNIQUE_NAME(base) CPS_TRACE_CONCAT(base, __COUNTER__)

#define TRACE_FUNCTION_SCOPE(component, function) \
    cps::instrumentation::ScopeTracer CPS_TRACE_UNIQUE_NAME(__scope_tracer_)(component, function)

#define TRACE_ENTER(component, function) \
    cps::instrumentation::RuntimeTracer::trace_enter(component, function)

#define TRACE_EXIT(component, function) \
    cps::instrumentation::RuntimeTracer::trace_exit(component, function)

#define TRACE_CALL(callerComp, callerFunc, calleeComp, calleeFunc) \
    cps::instrumentation::RuntimeTracer::trace_call(callerComp, callerFunc, calleeComp, calleeFunc)

#endif // CPS_CORE_UTILITIES_RUNTIME_INSTRUMENTATION_HPP
