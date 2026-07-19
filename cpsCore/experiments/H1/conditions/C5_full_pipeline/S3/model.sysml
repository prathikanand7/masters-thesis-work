package ComponentModel_S3 {

    port def Convert;
    port def Flush;
    port def GetAll;
    port def Stream;

    part def Aggregation {
        port serverGetAll : GetAll;
    }

    part def Logging {
        port serverFlush : Flush;
        port serverStream : Stream;
    }

    part def Synchronization {
        port clientConvert : Convert;
        port clientFlush : Flush;
        port clientGetAll : GetAll;
        port clientStream : Stream;
    }

    part def Utilities {
        port serverConvert : Convert;
    }

    part def S3System {
        part aggregation : Aggregation;
        part logging : Logging;
        part synchronization : Synchronization;
        part utilities : Utilities;

        connect aggregation.serverGetAll to synchronization.clientGetAll;
        connect logging.serverFlush to synchronization.clientFlush;
        connect logging.serverStream to synchronization.clientStream;
        connect utilities.serverConvert to synchronization.clientConvert;
    }

}

package CPScoreInteractionModels_S3 {
    private import ScalarValues::String;

    part def InteractionScenario;
    part def Lifeline;

    part def Message {
        attribute label : String;
        ref from : Lifeline;
        ref to   : Lifeline;
    }

    part def SynchronousCall :> Message;

    part def S3Scenario :> InteractionScenario {

        part synchronization : Lifeline;
        part aggregation : Lifeline;
        part logging : Lifeline;
        part utilities : Lifeline;

        part m1_getAll : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = aggregation;
            attribute :>> label = "1. getAll";
        }

        part m2_stream : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "2. stream";
        }

        part m3_convert : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = utilities;
            attribute :>> label = "3. convert";
        }

        part m4_stream : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "4. stream";
        }

        part m5_convert : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = utilities;
            attribute :>> label = "5. convert";
        }

        part m6_stream : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "6. stream";
        }

        part m7_flush : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "7. flush (static-only; suppressed at runtime (buffered logging; flush disabled/deferred))";
        }

    }
}
