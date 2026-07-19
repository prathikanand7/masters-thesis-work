package Views {
    import ComponentModel_S4::*;
    import CPScoreInteractionModels_S4::*;

    view s4structure : GeneralView {
        expose ComponentModel_S4::s4System;
    }

    view s4connections : InterconnectionView {
        expose ComponentModel_S4::s4System;
    }

    view s4Flow : SequenceView {
        expose CPScoreInteractionModels_S4::S4Scenario;
    }
}
