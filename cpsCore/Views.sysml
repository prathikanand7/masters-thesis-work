package Views {
    import ComponentModel1::*;
    import CPScoreInteractionModels::*;

    view structure : GeneralView {
        expose ComponentModel1::System;
    }

    view connections : InterconnectionView {
        expose ComponentModel1::System;
    }

    view redisFlow : SequenceView {
        expose CPScoreInteractionModels::RedisScenario;
    }

    view dataPresentationFlow : SequenceView {
        expose CPScoreInteractionModels::DataPresentationScenario;
    }

    view aggregationFlow : SequenceView {
        expose CPScoreInteractionModels::AggregationScenario;
    }

    view synchronizationFlow : SequenceView {
        expose CPScoreInteractionModels::SynchronizationScenario;
    }

    view ipcFlow : SequenceView {
        expose CPScoreInteractionModels::IPCScenario;
    }

    view serialFlow : SequenceView {
        expose CPScoreInteractionModels::SerialScenario;
    }

    view idcFlow : SequenceView {
        expose CPScoreInteractionModels::IDCScenario;
    }

    view utilitiesFlow : SequenceView {
        expose CPScoreInteractionModels::UtilitiesScenario;
    }

    view signalHandlerFlow : SequenceView {
        expose CPScoreInteractionModels::SignalHandlerScenario;
    }

    view testFlow : SequenceView {
        expose CPScoreInteractionModels::TestScenario;
    }

    view testExecutionFlow : SequenceView {
        expose CPScoreInteractionModels::TestExecutionScenario;
    }

    view miscellaneousFlow : SequenceView {
        expose CPScoreInteractionModels::MiscellaneousScenario;
    }
}