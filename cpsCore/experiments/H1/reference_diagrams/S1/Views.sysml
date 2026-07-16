// Views for H1 ground-truth diagrams — S1: Aggregator notification chain
// Exposes structural.sysml and sequence.sysml so the SysML v2 tool can render them.

package 'S1-Views' {
     import 'S1-Structural'::*;
     import 'S1-Sequence'::*;

    view s1Structure : GeneralView {
        expose 'S1-Structural'::*;
    }

    view s1Connections : InterconnectionView {
        expose 'S1-Structural'::*;
    }

    view s1Sequence : SequenceView {
        expose 'S1-Sequence'::*;
    }
}
