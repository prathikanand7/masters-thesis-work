// Views for H1 ground-truth diagrams — S2: Configuration property mapping
// Exposes structural.sysml and sequence.sysml so the SysML v2 tool can render them.

package 'S2-Views' {
     import 'S2-Structural'::*;
     import 'S2-Sequence'::*;

    view s2Structure : GeneralView {
        expose 'S2-Structural'::*;
    }

    view s2Connections : InterconnectionView {
        expose 'S2-Structural'::*;
    }

    view s2Sequence : SequenceView {
        expose 'S2-Sequence'::*;
    }
}
