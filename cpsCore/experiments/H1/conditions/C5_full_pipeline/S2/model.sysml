package ComponentModel_S2 {

    port def Stream;

    part def Configuration {
        port clientStream : Stream;
    }

    part def Logging {
        port serverStream : Stream;
    }

    part def S2System {
        part configuration : Configuration;
        part logging : Logging;

        connect logging.serverStream to configuration.clientStream;
    }

}

package CPScoreInteractionModels_S2 {
    private import ScalarValues::String;

    part def InteractionScenario;
    part def Lifeline;

    part def Message {
        attribute label : String;
        ref from : Lifeline;
        ref to   : Lifeline;
    }

    part def SynchronousCall :> Message;

    part def S2Scenario :> InteractionScenario {

        part configuration : Lifeline;
        part logging : Lifeline;

        part m1_stream : SynchronousCall {
            ref from : Lifeline = configuration;
            ref to   : Lifeline = logging;
            attribute :>> label = "1. stream (from PropertyMapper.add)";
        }

        part m2_stream : SynchronousCall {
            ref from : Lifeline = configuration;
            ref to   : Lifeline = logging;
            attribute :>> label = "2. stream (from PropertyMapper.add)";
        }

        part m3_stream : SynchronousCall {
            ref from : Lifeline = configuration;
            ref to   : Lifeline = logging;
            attribute :>> label = "3. stream (from PropertyMapper.addEigen)";
        }

        part m4_stream : SynchronousCall {
            ref from : Lifeline = configuration;
            ref to   : Lifeline = logging;
            attribute :>> label = "4. stream (from PropertyMapper.addEnum)";
        }

        part m5_stream : SynchronousCall {
            ref from : Lifeline = configuration;
            ref to   : Lifeline = logging;
            attribute :>> label = "5. stream (from PropertyMapper.addVector)";
        }

        part m6_stream : SynchronousCall {
            ref from : Lifeline = configuration;
            ref to   : Lifeline = logging;
            attribute :>> label = "6. stream (from PropertyMapper.getChild)";
        }

        part m7_stream : SynchronousCall {
            ref from : Lifeline = configuration;
            ref to   : Lifeline = logging;
            attribute :>> label = "7. stream (from PropertyMapper.mandatoryCheck)";
        }

    }
}
