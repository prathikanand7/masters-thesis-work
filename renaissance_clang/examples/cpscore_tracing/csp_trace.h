#pragma once
// ---------------------------------------------------------------------------
// csp_trace.h  –  helper functions included in instrumented cpsCore files.
//
// Trace format (written to stderr):
//   [TRACE] HH:MM:SS.mmm, callerFunc, callerComponent, Callee.method, calleeComponent, callerClass, file:line
//
// Helpers:
//   cspTraceTimestamp()         — wall-clock time as "HH:MM:SS.mmm" (local time, ms precision).
//   cspTraceCallerFunc()        — method name extracted from __PRETTY_FUNCTION__.
//   cspTraceCallerClass()       — class name extracted from __PRETTY_FUNCTION__ ("" for free functions).
//   cspTraceCallerComponent()   — component directory extracted from __FILE__ path.
//   cspTraceLocation()          — "filename:lineno" for the call site.
//   cspTraceSource()            — legacy: bare filename without extension.
// ---------------------------------------------------------------------------

#include <chrono>
#include <cstdio>
#include <ctime>
#include <string>

// Returns wall-clock time formatted as "HH:MM:SS.mmm".
inline std::string cspTraceTimestamp()
{
    using namespace std::chrono;
    auto now = system_clock::now();
    std::time_t t = system_clock::to_time_t(now);
    int ms = static_cast<int>(
        duration_cast<milliseconds>(now.time_since_epoch()).count() % 1000);
    struct tm tm_r;
    localtime_r(&t, &tm_r);
    char buf[16];
    std::snprintf(buf, sizeof(buf), "%02d:%02d:%02d.%03d",
                  tm_r.tm_hour, tm_r.tm_min, tm_r.tm_sec, ms);
    return buf;
}

// Returns "filename.ext:lineno" for the trace call site (e.g. "Aggregator.cpp:42").
inline std::string cspTraceLocation(const char* filepath, int line)
{
    const char* base = filepath;
    for (const char* p = filepath; *p; ++p)
        if (*p == '/' || *p == '\\') base = p + 1;
    char buf[128];
    std::snprintf(buf, sizeof(buf), "%s:%d", base, line);
    return buf;
}

// Returns the filename component of filepath with the extension stripped,
// giving the CSP component name (e.g. "AggregatableRunner.cpp" → "AggregatableRunner").
inline std::string cspTraceSource(const char* filepath)
{
    const char* base = filepath;
    for (const char* p = filepath; *p; ++p)
        if (*p == '/' || *p == '\\') base = p + 1;
    std::string s(base);
    std::string::size_type dot = s.rfind('.');
    if (dot != std::string::npos)
        s.erase(dot);
    return s;
}

// Returns the method/function name from __PRETTY_FUNCTION__.
// e.g. "void AggregatableRunner::notifyAggregationOnUpdate()" → "notifyAggregationOnUpdate"
inline std::string cspTraceCallerFunc(const char* pretty_func)
{
    std::string s(pretty_func);
    auto paren = s.find('(');
    if (paren != std::string::npos) s = s.substr(0, paren);
    auto space = s.rfind(' ');
    if (space != std::string::npos) s = s.substr(space + 1);
    auto colon = s.rfind("::");
    if (colon != std::string::npos) s = s.substr(colon + 2);
    return s;
}

// Returns the class name from __PRETTY_FUNCTION__, or "" for free functions.
// e.g. "void AggregatableRunner::notifyAggregationOnUpdate()" → "AggregatableRunner"
// Uses bracket-aware search so that spaces and '::' inside template argument
// lists (e.g. "StaticFactory<Base, Objects ...>::create") are not misidentified.
inline std::string cspTraceCallerClass(const char* pretty_func)
{
    std::string s(pretty_func);
    // Strip parameter list (and any trailing "[with ...]" GCC suffix).
    auto paren = s.find('(');
    if (paren != std::string::npos) s = s.substr(0, paren);

    // Find the last space OUTSIDE angle brackets — separates return type from
    // qualified function name.
    {
        int depth = 0, lastSpace = -1;
        for (int i = 0; i < (int)s.size(); ++i) {
            if      (s[i] == '<') ++depth;
            else if (s[i] == '>' && depth > 0) --depth;
            else if (s[i] == ' ' && depth == 0) lastSpace = i;
        }
        if (lastSpace >= 0) s = s.substr(lastSpace + 1);
    }

    // Find the last '::' OUTSIDE angle brackets — separates class from method.
    {
        int depth = 0;
        for (int i = (int)s.size() - 1; i >= 1; --i) {
            if      (s[i] == '>') ++depth;
            else if (s[i] == '<' && depth > 0) --depth;
            else if (depth == 0 && s[i] == ':' && s[i - 1] == ':')
                return s.substr(0, i - 1);
        }
    }
    return "";
}

// Returns the component directory from a file path.
// For src/tests: first directory after /src/ or /tests/.
//   e.g. ".../src/Synchronization/AggregatableRunner.cpp" → "Synchronization"
// For headers: first directory after /include/cpsCore/ (skips the cpsCore segment).
//   e.g. ".../include/cpsCore/Aggregation/Aggregator.h" → "Aggregation"
inline std::string cspTraceCallerComponent(const char* filepath)
{
    // helper: manual strstr returning pointer past the marker, or nullptr
    auto findMarker = [](const char* haystack, const char* needle) -> const char* {
        for (const char* pos = haystack; *pos; ++pos) {
            const char* p = pos, *m = needle;
            while (*p && *m && *p == *m) { ++p; ++m; }
            if (!*m) return p;
        }
        return nullptr;
    };
    auto takeComponent = [](const char* start) -> std::string {
        const char* end = start;
        while (*end && *end != '/' && *end != '\\') ++end;
        if (end > start) return std::string(start, end);
        return "";
    };

    // src / tests: take the first component directly after the marker
    for (auto marker : {"/src/", "\\src\\", "/tests/", "\\tests\\"}) {
        if (const char* p = findMarker(filepath, marker)) {
            auto s = takeComponent(p);
            if (!s.empty()) return s;
        }
    }
    // include/cpsCore/<component>/…: skip the cpsCore segment
    for (auto marker : {"/include/cpsCore/", "\\include\\cpsCore\\"}) {
        if (const char* p = findMarker(filepath, marker)) {
            auto s = takeComponent(p);
            if (!s.empty()) return s;
        }
    }
    return "Unknown";
}
