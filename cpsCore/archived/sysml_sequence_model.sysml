package CPScoreInteractionModels {
    private import ScalarValues::String;

    // =========================================================
    // Interaction stereotypes
    // =========================================================

    part def InteractionScenario;
    part def Lifeline;

    part def Message {
        attribute label : String;
        ref from : Lifeline;
        ref to   : Lifeline;
    }

    part def SynchronousCall     :> Message;
    part def ReturnMessage       :> Message;
    part def AsynchronousMessage :> Message;

    // =========================================================
    // SCENARIO 1: TestExecution
    // =========================================================

    part def TestExecutionScenario :> InteractionScenario {

        part filterTest : Lifeline;
        part catch2 : Lifeline;
        part angleTest : Lifeline;
        part loggerTest : Lifeline;
        part logger : Lifeline;
        part angle : Lifeline;
        part enumMapTest : Lifeline;
        part enumMap : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = filterTest;
            ref to   : Lifeline = catch2;
            attribute :>> label = "1. complete";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = filterTest;
            ref to   : Lifeline = catch2;
            attribute :>> label = "2. handleExpr";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = angleTest;
            ref to   : Lifeline = catch2;
            attribute :>> label = "3. complete";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = angleTest;
            ref to   : Lifeline = catch2;
            attribute :>> label = "4. handleExpr";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = angleTest;
            ref to   : Lifeline = catch2;
            attribute :>> label = "5. margin";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = loggerTest;
            ref to   : Lifeline = logger;
            attribute :>> label = "6. instance";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = loggerTest;
            ref to   : Lifeline = logger;
            attribute :>> label = "7. setSink";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = loggerTest;
            ref to   : Lifeline = logger;
            attribute :>> label = "8. setLogLevel";
        }

        part m9 : SynchronousCall {
            ref from : Lifeline = angleTest;
            ref to   : Lifeline = angle;
            attribute :>> label = "9. degrees";
        }

        part m10 : SynchronousCall {
            ref from : Lifeline = loggerTest;
            ref to   : Lifeline = logger;
            attribute :>> label = "10. flush";
        }

        part m11 : SynchronousCall {
            ref from : Lifeline = loggerTest;
            ref to   : Lifeline = logger;
            attribute :>> label = "11. stream";
        }

        part m12 : SynchronousCall {
            ref from : Lifeline = enumMapTest;
            ref to   : Lifeline = enumMap;
            attribute :>> label = "12. getInstance";
        }

    }

    // =========================================================
    // SCENARIO 2: SignalHandler
    // =========================================================

    part def SignalHandlerScenario :> InteractionScenario {

        part signalHandler : Lifeline;
        part logger : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = signalHandler;
            ref to   : Lifeline = logger;
            attribute :>> label = "1. flush";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = signalHandler;
            ref to   : Lifeline = logger;
            attribute :>> label = "2. instance";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = signalHandler;
            ref to   : Lifeline = logger;
            attribute :>> label = "3. stream";
        }

    }

    // =========================================================
    // SCENARIO 3: Test
    // =========================================================

    part def TestScenario :> InteractionScenario {

        part testRunner : Lifeline;
        part testInfo : Lifeline;
        part logger : Lifeline;
        part catch2 : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = testRunner;
            ref to   : Lifeline = testInfo;
            attribute :>> label = "1. getInstance";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = testRunner;
            ref to   : Lifeline = testInfo;
            attribute :>> label = "2. initialize";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = testInfo;
            ref to   : Lifeline = logger;
            attribute :>> label = "3. stream";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = testRunner;
            ref to   : Lifeline = catch2;
            attribute :>> label = "4. run";
        }

    }

    // =========================================================
    // SCENARIO 4: Redis
    // =========================================================

    part def RedisScenario :> InteractionScenario {

        part redisPublisher : Lifeline;
        part cppRedis : Lifeline;
        part redisSubscriber : Lifeline;
        part logger : Lifeline;
        part packet : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = redisPublisher;
            ref to   : Lifeline = cppRedis;
            attribute :>> label = "1. connect";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = redisSubscriber;
            ref to   : Lifeline = cppRedis;
            attribute :>> label = "2. disconnect";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = redisPublisher;
            ref to   : Lifeline = cppRedis;
            attribute :>> label = "3. disconnect";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = redisPublisher;
            ref to   : Lifeline = cppRedis;
            attribute :>> label = "4. is_connected";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = redisPublisher;
            ref to   : Lifeline = logger;
            attribute :>> label = "5. stream";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = redisSubscriber;
            ref to   : Lifeline = cppRedis;
            attribute :>> label = "6. commit";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = redisPublisher;
            ref to   : Lifeline = cppRedis;
            attribute :>> label = "7. publish";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = redisPublisher;
            ref to   : Lifeline = packet;
            attribute :>> label = "8. getBuffer";
        }

        part m9 : SynchronousCall {
            ref from : Lifeline = redisPublisher;
            ref to   : Lifeline = cppRedis;
            attribute :>> label = "9. commit";
        }

        part m10 : SynchronousCall {
            ref from : Lifeline = redisSubscriber;
            ref to   : Lifeline = cppRedis;
            attribute :>> label = "10. connect";
        }

        part m11 : SynchronousCall {
            ref from : Lifeline = redisSubscriber;
            ref to   : Lifeline = logger;
            attribute :>> label = "11. stream";
        }

        part m12 : SynchronousCall {
            ref from : Lifeline = redisSubscriber;
            ref to   : Lifeline = cppRedis;
            attribute :>> label = "12. auth";
        }

    }

    // =========================================================
    // SCENARIO 5: DataPresentation
    // =========================================================

    part def DataPresentationScenario :> InteractionScenario {

        part basicSerialization : Lifeline;
        part linearAlgebra : Lifeline;
        part packet : Lifeline;
        part binaryFromArchive : Lifeline;
        part binaryToArchive : Lifeline;
        part fileFromArchive : Lifeline;
        part fileToArchive : Lifeline;
        part split : Lifeline;
        part binarySerialization : Lifeline;
        part logger : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = basicSerialization;
            ref to   : Lifeline = linearAlgebra;
            attribute :>> label = "1. load";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = basicSerialization;
            ref to   : Lifeline = packet;
            attribute :>> label = "2. load";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = basicSerialization;
            ref to   : Lifeline = binaryFromArchive;
            attribute :>> label = "3. begin";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = basicSerialization;
            ref to   : Lifeline = binaryFromArchive;
            attribute :>> label = "4. consume";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = basicSerialization;
            ref to   : Lifeline = linearAlgebra;
            attribute :>> label = "5. store";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = basicSerialization;
            ref to   : Lifeline = packet;
            attribute :>> label = "6. store";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = basicSerialization;
            ref to   : Lifeline = binaryToArchive;
            attribute :>> label = "7. append";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = basicSerialization;
            ref to   : Lifeline = fileFromArchive;
            attribute :>> label = "8. read";
        }

        part m9 : SynchronousCall {
            ref from : Lifeline = basicSerialization;
            ref to   : Lifeline = fileToArchive;
            attribute :>> label = "9. append";
        }

        part m10 : SynchronousCall {
            ref from : Lifeline = basicSerialization;
            ref to   : Lifeline = split;
            attribute :>> label = "10. split";
        }

        part m11 : SynchronousCall {
            ref from : Lifeline = binarySerialization;
            ref to   : Lifeline = packet;
            attribute :>> label = "11. getSize";
        }

        part m12 : SynchronousCall {
            ref from : Lifeline = binarySerialization;
            ref to   : Lifeline = logger;
            attribute :>> label = "12. stream";
        }

    }

    // =========================================================
    // SCENARIO 6: Aggregation
    // =========================================================

    part def AggregationScenario :> InteractionScenario {

        part aggregator : Lifeline;
        part dynamicObjectContainer : Lifeline;
        part logger : Lifeline;
        part aggregatableObject : Lifeline;
        part objectHandleContainer : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = dynamicObjectContainer;
            attribute :>> label = "1. add";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = dynamicObjectContainer;
            attribute :>> label = "2. notifyAggregationOnUpdate";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = dynamicObjectContainer;
            attribute :>> label = "3. clear";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = dynamicObjectContainer;
            attribute :>> label = "4. empty";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = dynamicObjectContainer;
            attribute :>> label = "5. size";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = logger;
            attribute :>> label = "6. stream";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = aggregatableObject;
            ref to   : Lifeline = logger;
            attribute :>> label = "7. stream";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = dynamicObjectContainer;
            attribute :>> label = "8. getOne";
        }

        part m9 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = dynamicObjectContainer;
            attribute :>> label = "9. getAll";
        }

        part m10 : SynchronousCall {
            ref from : Lifeline = objectHandleContainer;
            ref to   : Lifeline = aggregator;
            attribute :>> label = "10. getAll";
        }

        part m11 : SynchronousCall {
            ref from : Lifeline = objectHandleContainer;
            ref to   : Lifeline = aggregator;
            attribute :>> label = "11. getOne";
        }

        part m12 : SynchronousCall {
            ref from : Lifeline = objectHandleContainer;
            ref to   : Lifeline = logger;
            attribute :>> label = "12. stream";
        }

    }

    // =========================================================
    // SCENARIO 7: Synchronization
    // =========================================================

    part def SynchronizationScenario :> InteractionScenario {

        part aggregatableRunner : Lifeline;
        part iRunnableObject : Lifeline;
        part simpleRunner : Lifeline;
        part logger : Lifeline;
        part enumMap : Lifeline;
        part aggregator : Lifeline;
        part synchronizedRunnerMaster : Lifeline;
        part synchronizedRunner : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = aggregatableRunner;
            ref to   : Lifeline = iRunnableObject;
            attribute :>> label = "1. run";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = simpleRunner;
            ref to   : Lifeline = logger;
            attribute :>> label = "2. stream";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = simpleRunner;
            ref to   : Lifeline = enumMap;
            attribute :>> label = "3. convert";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = simpleRunner;
            ref to   : Lifeline = aggregator;
            attribute :>> label = "4. getAll";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = aggregatableRunner;
            ref to   : Lifeline = aggregator;
            attribute :>> label = "5. getAll";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = simpleRunner;
            ref to   : Lifeline = iRunnableObject;
            attribute :>> label = "6. run";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = synchronizedRunnerMaster;
            ref to   : Lifeline = logger;
            attribute :>> label = "7. stream";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = synchronizedRunner;
            ref to   : Lifeline = aggregator;
            attribute :>> label = "8. getAll";
        }

        part m9 : SynchronousCall {
            ref from : Lifeline = synchronizedRunner;
            ref to   : Lifeline = iRunnableObject;
            attribute :>> label = "9. run";
        }

        part m10 : SynchronousCall {
            ref from : Lifeline = synchronizedRunner;
            ref to   : Lifeline = logger;
            attribute :>> label = "10. flush";
        }

        part m11 : SynchronousCall {
            ref from : Lifeline = synchronizedRunner;
            ref to   : Lifeline = logger;
            attribute :>> label = "11. instance";
        }

    }

    // =========================================================
    // SCENARIO 8: IDC
    // =========================================================

    part def IDCScenario :> InteractionScenario {

        part idc : Lifeline;
        part aggregatableObject : Lifeline;
        part logger : Lifeline;
        part idcSender : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = idc;
            ref to   : Lifeline = aggregatableObject;
            attribute :>> label = "1. isSet";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = idc;
            ref to   : Lifeline = logger;
            attribute :>> label = "2. stream";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = idcSender;
            ref to   : Lifeline = logger;
            attribute :>> label = "3. stream";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = idc;
            ref to   : Lifeline = aggregatableObject;
            attribute :>> label = "4. get";
        }

    }

    // =========================================================
    // SCENARIO 9: IPC
    // =========================================================

    part def IPCScenario :> InteractionScenario {

        part messageQueuePublisher : Lifeline;
        part logger : Lifeline;
        part packet : Lifeline;
        part sharedMemoryPublisher : Lifeline;
        part sharedMemorySubscription : Lifeline;
        part messageQueueSubscription : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = messageQueuePublisher;
            ref to   : Lifeline = logger;
            attribute :>> label = "1. stream";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = messageQueuePublisher;
            ref to   : Lifeline = packet;
            attribute :>> label = "2. getSize";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = sharedMemoryPublisher;
            ref to   : Lifeline = logger;
            attribute :>> label = "3. stream";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = messageQueuePublisher;
            ref to   : Lifeline = packet;
            attribute :>> label = "4. getStart";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = sharedMemorySubscription;
            ref to   : Lifeline = logger;
            attribute :>> label = "5. stream";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = sharedMemoryPublisher;
            ref to   : Lifeline = packet;
            attribute :>> label = "6. getSize";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = sharedMemorySubscription;
            ref to   : Lifeline = packet;
            attribute :>> label = "7. getBuffer";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = sharedMemoryPublisher;
            ref to   : Lifeline = packet;
            attribute :>> label = "8. getStart";
        }

        part m9 : SynchronousCall {
            ref from : Lifeline = messageQueueSubscription;
            ref to   : Lifeline = logger;
            attribute :>> label = "9. stream";
        }

        part m10 : SynchronousCall {
            ref from : Lifeline = sharedMemorySubscription;
            ref to   : Lifeline = packet;
            attribute :>> label = "10. getStartAddress";
        }

    }

    // =========================================================
    // SCENARIO 10: Serial
    // =========================================================

    part def SerialScenario :> InteractionScenario {

        part serialHandler : Lifeline;
        part logger : Lifeline;
        part packet : Lifeline;
        part binarySerialization : Lifeline;
        part hamming74 : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = serialHandler;
            ref to   : Lifeline = logger;
            attribute :>> label = "1. stream";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = serialHandler;
            ref to   : Lifeline = logger;
            attribute :>> label = "2. flush";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = serialHandler;
            ref to   : Lifeline = logger;
            attribute :>> label = "3. instance";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = serialHandler;
            ref to   : Lifeline = packet;
            attribute :>> label = "4. getBuffer";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = serialHandler;
            ref to   : Lifeline = packet;
            attribute :>> label = "5. getCRC16";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = serialHandler;
            ref to   : Lifeline = binarySerialization;
            attribute :>> label = "6. serialize";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = serialHandler;
            ref to   : Lifeline = hamming74;
            attribute :>> label = "7. encode";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = serialHandler;
            ref to   : Lifeline = packet;
            attribute :>> label = "8. hamming74Decode";
        }

        part m9 : SynchronousCall {
            ref from : Lifeline = serialHandler;
            ref to   : Lifeline = binarySerialization;
            attribute :>> label = "9. extract";
        }

    }

    // =========================================================
    // SCENARIO 11: Utilities
    // =========================================================

    part def UtilitiesScenario :> InteractionScenario {

        part enumMap : Lifeline;
        part logger : Lifeline;
        part packet : Lifeline;
        part hamming74 : Lifeline;
        part split : Lifeline;
        part time : Lifeline;
        part linearAlgebra : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = enumMap;
            ref to   : Lifeline = logger;
            attribute :>> label = "1. stream";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = packet;
            ref to   : Lifeline = hamming74;
            attribute :>> label = "2. encode";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = packet;
            ref to   : Lifeline = hamming74;
            attribute :>> label = "3. decode";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = packet;
            ref to   : Lifeline = split;
            attribute :>> label = "4. split";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = time;
            ref to   : Lifeline = split;
            attribute :>> label = "5. split";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = linearAlgebra;
            ref to   : Lifeline = split;
            attribute :>> label = "6. split";
        }

    }

    // =========================================================
    // SCENARIO 12: Miscellaneous
    // =========================================================

    part def MiscellaneousScenario :> InteractionScenario {

        part propertyMapper : Lifeline;
        part logger : Lifeline;
        part dynamicObjectContainer : Lifeline;
        part iAggregatableObject : Lifeline;
        part staticFactory : Lifeline;
        part event : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = propertyMapper;
            ref to   : Lifeline = logger;
            attribute :>> label = "1. stream";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = dynamicObjectContainer;
            ref to   : Lifeline = iAggregatableObject;
            attribute :>> label = "2. notifyAggregationOnUpdate";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = dynamicObjectContainer;
            ref to   : Lifeline = logger;
            attribute :>> label = "3. stream";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = staticFactory;
            ref to   : Lifeline = logger;
            attribute :>> label = "4. stream";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = event;
            ref to   : Lifeline = logger;
            attribute :>> label = "5. stream";
        }

    }

}
