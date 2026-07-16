package ComponentModel_S4 {

    port def OnStageEvent;
    port def Stream;

    part def Aggregation {
        port serverOnStageEvent : OnStageEvent;
    }

    part def Logging {
        port serverStream : Stream;
    }

    part def Synchronization {
        port clientOnStageEvent : OnStageEvent;
        port clientStream : Stream;
    }

    part def System {
        part aggregation : Aggregation;
        part logging : Logging;
        part synchronization : Synchronization;

        connect aggregation.serverOnStageEvent to synchronization.clientOnStageEvent;
        connect logging.serverStream to synchronization.clientStream;
    }
}

package CPScoreInteractionModels_S4 {
    private import ScalarValues::String;

    part def InteractionScenario;
    part def Lifeline;

    part def Message {
        attribute label : String;
        ref from : Lifeline;
        ref to   : Lifeline;
    }

    part def SynchronousCall :> Message;

    part def S4Scenario :> InteractionScenario {

        part synchronization : Lifeline;
        part aggregation : Lifeline;
        part logging : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = aggregation;
            attribute :>> label = "1. onStageEvent (indirect dispatch via boost::signals2 from StageEventBridge.publishStage; dynamic-only (no static call site))";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "2. stream (fault-path inside StageEventBridge.publishStage when no listeners are attached; statically present but suppressed at runtime by LogLevel::NONE in the test)";
        }

    }
}
