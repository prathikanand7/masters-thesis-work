// Views for H1 ground-truth diagrams — S3: Multi-component runner orchestration
// Exposes structural.sysml and sequence.sysml so the SysML v2 tool can render them.

package 'S3-Views' {
     import 'S3-Structural'::*;
     import 'S3-Sequence'::*;

    view s3Structure : GeneralView {
        expose 'S3-Structural'::*;
    }

    view s3Connections : InterconnectionView {
        expose 'S3-Structural'::*;
    }

    view s3Sequence : SequenceView {
        expose 'S3-Sequence'::*;
    }
}
