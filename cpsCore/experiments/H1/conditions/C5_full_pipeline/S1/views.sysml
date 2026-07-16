package Views {
    import ComponentModel_S1::*;
    import CPScoreInteractionModels_S1::*;

    view s1structure : GeneralView {
        expose ComponentModel_S1::System;
    }

    view s1connections : InterconnectionView {
        expose ComponentModel_S1::System;
    }

    view s1Flow : SequenceView {
        expose CPScoreInteractionModels_S1::S1Scenario;
    }
}
