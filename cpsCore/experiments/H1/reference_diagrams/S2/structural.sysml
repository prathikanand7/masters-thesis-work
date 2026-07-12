// H1 ground-truth structural diagram — S2: Configuration property mapping
// Derived from CPSCore source + validated against runtime_traces.txt
//
// S2 is the simplest scenario: PropertyMapper calls CPSLOG_TRACE (→ RAIILogStream)
// on every property read. Single directed dependency Configuration → Logging.

package 'S2-Structural' {

    // ── Components ──────────────────────────────────────────────────────────
    part def Configuration {
        part propertyMapper : PropertyMapper;
    }

    part def Logging {
        part raiiLogStream : RAIILogStream;
    }

    // ── Interface ───────────────────────────────────────────────────────────
    interface def IRAIILogStream {
        in feature stream : 'stream';
    }

    // ── Connection ──────────────────────────────────────────────────────────
    // Every PropertyMapper method (add, addVector, addEnum, addEigen,
    // getChild, mandatoryCheck) calls CPSLOG_TRACE which writes to RAIILogStream.
    connection : IRAIILogStream
        connect Configuration::propertyMapper to Logging::raiiLogStream;
}
