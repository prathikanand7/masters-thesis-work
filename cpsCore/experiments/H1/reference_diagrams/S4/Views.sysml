// Views for H1 ground-truth diagrams — S4: Stage event bridge pub-sub routing (constructed scenario)
// Exposes structural.sysml and sequence.sysml so the SysML v2 tool can render them.

package 'S4-Views' {
     import 'S4-Structural'::*;
     import 'S4-Sequence'::*;

    view s4Structure : GeneralView {
        expose 'S4-Structural'::*;
    }

    view s4Connections : InterconnectionView {
        expose 'S4-Structural'::*;
    }

    view s4Sequence : SequenceView {
        expose 'S4-Sequence'::*;
    }
}
