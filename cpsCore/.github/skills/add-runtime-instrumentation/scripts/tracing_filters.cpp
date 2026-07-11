#include <cstring>

extern "C" {

static const char* get_hole(int n, const char* const* ns, const char* const* vs, const char* name) {
    for (int i = 0; i < n; ++i)
        if (strcmp(ns[i], name) == 0) return vs[i];
    return NULL;
}

// Accept ($any, $orig) comma expressions where $any contains our [TRACE] marker.
bool is_trace_remove(int n, const char* const* ns, const char* const* vs) {
    const char* text = get_hole(n, ns, vs, "any");
    return text != NULL && strstr(text, "[TRACE]") != NULL;
}

} // extern "C"
