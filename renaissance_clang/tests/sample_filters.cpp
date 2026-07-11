// Sample filter definitions for csp_matcher
// Include this file via: --filter-defs tests/sample_filters.cpp
//
// Each filter function receives pre-extracted hole values as parallel arrays:
//   bool my_filter(int count,
//                  const char * const *names,
//                  const char * const *values [, extra_args...])
//
// No Clang/LLVM headers are required — only standard C headers.

#include <string.h>  // strcmp, strlen

// Helper: look up a hole value by name. Returns "" when not found.
static const char* csp_hole(int count,
                             const char * const *names,
                             const char * const *values,
                             const char *name) {
    for (int i = 0; i < count; i++)
        if (strcmp(names[i], name) == 0)
            return values[i];
    return "";
}

// Accept all matches (useful for smoke-testing that the filter pipeline runs).
bool accept_all(int, const char * const *, const char * const *) {
    return true;
}

// Reject all matches.
bool reject_all(int, const char * const *, const char * const *) {
    return false;
}

// Accept the match only when the condition hole equals the given string.
bool cond_equals(int count, const char * const *names, const char * const *values,
                 const char *expected) {
    return strcmp(csp_hole(count, names, values, "cond"), expected) == 0;
}

// Accept the match only when the condition hole is shorter than max_len characters.
bool cond_shorter_than(int count, const char * const *names, const char * const *values,
                       int max_len) {
    return (int)strlen(csp_hole(count, names, values, "cond")) < max_len;
}
