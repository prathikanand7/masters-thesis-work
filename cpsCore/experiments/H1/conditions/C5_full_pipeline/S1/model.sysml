package ComponentModel_S1 {

    port def Flush;
    port def GetAll;
    port def Instance;
    port def Stream;

    part def Aggregation {
        port serverGetAll : GetAll;
    }

    part def Logging {
        port serverFlush : Flush;
        port serverInstance : Instance;
        port serverStream : Stream;
    }

    part def Synchronization {
        port clientFlush : Flush;
        port clientGetAll : GetAll;
        port clientInstance : Instance;
        port clientStream : Stream;
    }

    part def System {
        part aggregation : Aggregation;
        part logging : Logging;
        part synchronization : Synchronization;

        connect aggregation.serverGetAll to synchronization.clientGetAll;
        connect logging.serverFlush to synchronization.clientFlush;
        connect logging.serverInstance to synchronization.clientInstance;
        connect logging.serverStream to synchronization.clientStream;
    }
}

package CPScoreInteractionModels_S1 {
    private import ScalarValues::String;

    part def InteractionScenario;
    part def Lifeline;

    part def Message {
        attribute label : String;
        ref from : Lifeline;
        ref to   : Lifeline;
    }

    part def SynchronousCall :> Message;

    part def S1Scenario :> InteractionScenario {

        part synchronization : Lifeline;
        part aggregation : Lifeline;
        part logging : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = aggregation;
            attribute :>> label = "1. getAll";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "2. stream";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = aggregation;
            attribute :>> label = "3. getAll";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "4. stream";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "5. stream";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = aggregation;
            attribute :>> label = "6. getAll";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "7. flush";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "8. instance";
        }

        part m9 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "9. stream";
        }

        part m10 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "10. stream";
        }

        part m11 : SynchronousCall {
            ref from : Lifeline = synchronization;
            ref to   : Lifeline = logging;
            attribute :>> label = "11. stream";
        }

    }
}
