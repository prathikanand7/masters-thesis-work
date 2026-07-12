// H1 ground-truth sequence diagram — S2: Configuration property mapping
// Derived from CPSCore source + validated against runtime_traces.txt

package 'S2-Sequence' {

    // Participants
    part cfg : Configuration;
    part log : Logging;

    // ── Sequence (in trace timestamp order) ──────────────────────────────────
    // Each PropertyMapper method emits a CPSLOG_TRACE → RAIILogStream.stream

    message m1 from cfg.propertyMapper to log.raiiLogStream
        : 'RAIILogStream.stream';   // PropertyMapper.add (string key)

    message m2 from cfg.propertyMapper to log.raiiLogStream
        : 'RAIILogStream.stream';   // PropertyMapper.add (second overload)

    message m3 from cfg.propertyMapper to log.raiiLogStream
        : 'RAIILogStream.stream';   // PropertyMapper.addEigen

    message m4 from cfg.propertyMapper to log.raiiLogStream
        : 'RAIILogStream.stream';   // PropertyMapper.addEnum

    message m5 from cfg.propertyMapper to log.raiiLogStream
        : 'RAIILogStream.stream';   // PropertyMapper.addVector

    message m6 from cfg.propertyMapper to log.raiiLogStream
        : 'RAIILogStream.stream';   // PropertyMapper.getChild

    message m7 from cfg.propertyMapper to log.raiiLogStream
        : 'RAIILogStream.stream';   // PropertyMapper.mandatoryCheck
}
