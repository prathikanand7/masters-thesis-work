package Views {
    import ComponentModel_S2::*;
    import CPScoreInteractionModels_S2::*;

    view s2structure : GeneralView {
        expose ComponentModel_S2::System;
    }

    view s2connections : InterconnectionView {
        expose ComponentModel_S2::System;
    }

    view s2Flow : SequenceView {
        expose CPScoreInteractionModels_S2::S2Scenario;
    }
}
