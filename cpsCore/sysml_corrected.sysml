/**
 * CPScore Interaction Models — SysML v2
 * spec42-compatible, following elan8/sysml-examples webshop pattern exactly
 *
 * Key pattern (from working WebShopArchitecture.sysml):
 *   - All scenario participants typed as Lifeline (not component types)
 *   - part def :> InteractionScenario for scenarios
 *   - SynchronousCall / ReturnMessage / AsynchronousMessage for messages
 *   - ref from/to : Lifeline = participantName
 *   - Activation with ref on/startMessage/finishMessage
 *   - AltFragment / InteractionOperand for conditional flows
 */

package CPScoreArchitecture {
    private import ScalarValues::String;

    // =========================================================
    // Interaction stereotypes (identical to WebShopArchitecture)
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
    part def CreationMessage     :> Message;

    part def Activation {
        ref on            : Lifeline;
        ref startMessage  : Message;
        ref finishMessage : Message;
    }

    part def InteractionOperand {
        attribute guard : String;
    }

    part def AltFragment;


    // =========================================================
    // SCENARIO 1: Redis Connection
    // Trigger: RedisPublisher or RedisSubscriber initialised
    // Static+Trace: msgs 11,12,32,83,141,168,194,202
    // =========================================================

    part def RedisConnectionScenario :> InteractionScenario {

        part publisher  : Lifeline;
        part subscriber : Lifeline;
        part client     : Lifeline;
        part subCore    : Lifeline;
        part network    : Lifeline;
        part logger     : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = client;
            attribute :>> label = "connect(host, port)";
        }

        part m2 : ReturnMessage {
            ref from : Lifeline = client;
            ref to   : Lifeline = publisher;
            attribute :>> label = "onConnectionEvent(status)";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = client;
            attribute :>> label = "auth(password)";
        }

        part m4 : AsynchronousMessage {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(connectionMsg)";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = subscriber;
            ref to   : Lifeline = subCore;
            attribute :>> label = "connect(host, port)";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = subscriber;
            ref to   : Lifeline = subCore;
            attribute :>> label = "auth(password)";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = subscriber;
            ref to   : Lifeline = subCore;
            attribute :>> label = "subscribe(channel, callback)";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = subscriber;
            ref to   : Lifeline = subCore;
            attribute :>> label = "commit()";
        }

        part m9 : ReturnMessage {
            ref from : Lifeline = subCore;
            ref to   : Lifeline = subscriber;
            attribute :>> label = "onChannel(channel, callback)";
        }

        part m10 : AsynchronousMessage {
            ref from : Lifeline = client;
            ref to   : Lifeline = network;
            attribute :>> label = "track(fd)";
        }

        part publisherActivation : Activation {
            ref on            : Lifeline = publisher;
            ref startMessage  : Message  = m1;
            ref finishMessage : Message  = m4;
        }

        part subscriberActivation : Activation {
            ref on            : Lifeline = subscriber;
            ref startMessage  : Message  = m5;
            ref finishMessage : Message  = m9;
        }
    }


    // =========================================================
    // SCENARIO 2: Redis Publish
    // Trigger: RedisPublisher::publish()
    // Static+Trace: msgs 67,77,89,90,93,216,220
    // =========================================================

    part def RedisPublishScenario :> InteractionScenario {

        part publisher : Lifeline;
        part client    : Lifeline;
        part pkt       : Lifeline;
        part logger    : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = client;
            attribute :>> label = "is_connected()";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = pkt;
            attribute :>> label = "getBuffer()";
        }

        part m3 : AsynchronousMessage {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(publishMsg)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = client;
            attribute :>> label = "publish(channel, data)";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = client;
            attribute :>> label = "commit()";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = client;
            attribute :>> label = "auth(password)";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = client;
            attribute :>> label = "commit()";
        }

        part publishActivation : Activation {
            ref on            : Lifeline = publisher;
            ref startMessage  : Message  = m1;
            ref finishMessage : Message  = m5;
        }
    }


    // =========================================================
    // SCENARIO 3: Redis Disconnect
    // Trigger: ~RedisPublisher / ~RedisSubscriber destructor
    // Static+Trace: msgs 32,43,141,145
    // =========================================================

    part def RedisDisconnectScenario :> InteractionScenario {

        part publisher  : Lifeline;
        part subscriber : Lifeline;
        part client     : Lifeline;
        part subCore    : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = publisher;
            ref to   : Lifeline = client;
            attribute :>> label = "disconnect()";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = subscriber;
            ref to   : Lifeline = subCore;
            attribute :>> label = "disconnect()";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = subscriber;
            ref to   : Lifeline = subCore;
            attribute :>> label = "cancel()";
        }
    }


    // =========================================================
    // SCENARIO 4: Runner Lifecycle
    // Trigger: run() called on a Runner instance
    // Static+Trace: msgs 30,66,122,126,138,149,264
    // =========================================================

    part def RunnerLifecycleScenario :> InteractionScenario {

        part runner     : Lifeline;
        part aggregator : Lifeline;
        part runnable   : Lifeline;
        part logger     : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = runner;
            ref to   : Lifeline = aggregator;
            attribute :>> label = "getAll()";
        }

        part m2 : AsynchronousMessage {
            ref from : Lifeline = runner;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(stageMsg)";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = runner;
            ref to   : Lifeline = runnable;
            attribute :>> label = "runStage(stageId)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = runner;
            ref to   : Lifeline = runnable;
            attribute :>> label = "run()";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = runner;
            ref to   : Lifeline = aggregator;
            attribute :>> label = "getAll()";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = runner;
            ref to   : Lifeline = runnable;
            attribute :>> label = "run()";
        }

        part runnerActivation : Activation {
            ref on            : Lifeline = runner;
            ref startMessage  : Message  = m1;
            ref finishMessage : Message  = m6;
        }
    }


    // =========================================================
    // SCENARIO 5: Object Aggregation
    // Trigger: Aggregator::add()
    // Static+Trace: msgs 25,27,61,130,133,161,167,200,305
    // =========================================================

    part def AggregationScenario :> InteractionScenario {

        part aggregator : Lifeline;
        part container  : Lifeline;
        part obj        : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = container;
            attribute :>> label = "add(obj)";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = container;
            ref to   : Lifeline = obj;
            attribute :>> label = "notifyAggregationOnUpdate(obj)";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = container;
            attribute :>> label = "mergeInto(target)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = container;
            ref to   : Lifeline = obj;
            attribute :>> label = "notifyAggregationOnUpdate(obj)";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = aggregator;
            ref to   : Lifeline = container;
            attribute :>> label = "clear()";
        }
    }


    // =========================================================
    // SCENARIO 6: Binary Serialisation
    // Trigger: Serializer::serialize() / load() / store()
    // Static+Trace: msgs 22,42,47,50,72,146,154
    // =========================================================

    part def SerializationScenario :> InteractionScenario {

        part serializer : Lifeline;
        part pkt        : Lifeline;
        part logger     : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = serializer;
            ref to   : Lifeline = serializer;
            attribute :>> label = "split(data)";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = serializer;
            ref to   : Lifeline = serializer;
            attribute :>> label = "begin()";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = serializer;
            ref to   : Lifeline = serializer;
            attribute :>> label = "consume(bytes)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = serializer;
            ref to   : Lifeline = serializer;
            attribute :>> label = "load(data)";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = serializer;
            ref to   : Lifeline = serializer;
            attribute :>> label = "append(bytes)";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = serializer;
            ref to   : Lifeline = pkt;
            attribute :>> label = "getSize()";
        }

        part m7 : AsynchronousMessage {
            ref from : Lifeline = serializer;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(serMsg)";
        }
    }


    // =========================================================
    // SCENARIO 7: Signal Handling
    // Trigger: subscribeOnSigint() / callSigHandlers()
    // Static+Trace: msgs 3,4,7,33,35,36,56,63,64,82
    // =========================================================

    part def SignalHandlingScenario :> InteractionScenario {

        part handler : Lifeline;
        part logger  : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = handler;
            ref to   : Lifeline = handler;
            attribute :>> label = "getInstance()";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = handler;
            ref to   : Lifeline = handler;
            attribute :>> label = "subscribeOnSigint(callback)";
        }

        part m3 : AsynchronousMessage {
            ref from : Lifeline = handler;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(sigMsg)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = handler;
            ref to   : Lifeline = handler;
            attribute :>> label = "subscribeOnExit(callback)";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = handler;
            ref to   : Lifeline = handler;
            attribute :>> label = "callSigHandlers(signum)";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = handler;
            ref to   : Lifeline = handler;
            attribute :>> label = "joinHandler()";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = handler;
            ref to   : Lifeline = logger;
            attribute :>> label = "flush()";
        }
    }


    // =========================================================
    // SCENARIO 8: IPC Channel Communication
    // Trigger: IpcChannel connect / publish / start
    // Static+Trace: msgs 26,28,29,148,195
    // =========================================================

    part def IpcChannelScenario :> InteractionScenario {

        part ipc    : Lifeline;
        part pkt    : Lifeline;
        part logger : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = ipc;
            ref to   : Lifeline = ipc;
            attribute :>> label = "connect(queueName)";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = ipc;
            ref to   : Lifeline = ipc;
            attribute :>> label = "onMessageQueue(callback)";
        }

        part m3 : AsynchronousMessage {
            ref from : Lifeline = ipc;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(connectMsg)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = ipc;
            ref to   : Lifeline = ipc;
            attribute :>> label = "connect(shmName)";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = ipc;
            ref to   : Lifeline = ipc;
            attribute :>> label = "onSharedMemory(callback)";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = ipc;
            ref to   : Lifeline = ipc;
            attribute :>> label = "publish(data)";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = ipc;
            ref to   : Lifeline = pkt;
            attribute :>> label = "getSize()";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = ipc;
            ref to   : Lifeline = pkt;
            attribute :>> label = "getStart()";
        }
    }


    // =========================================================
    // SCENARIO 9: Serial Send Packet
    // Trigger: SerialHandler::sendPacket()
    // Static+Trace: msgs 208,224,243,246,273,347
    // =========================================================

    part def SerialSendScenario :> InteractionScenario {

        part serial     : Lifeline;
        part codec      : Lifeline;
        part pkt        : Lifeline;
        part serializer : Lifeline;
        part logger     : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = serial;
            ref to   : Lifeline = serializer;
            attribute :>> label = "serialize(payload)";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = serial;
            ref to   : Lifeline = codec;
            attribute :>> label = "encode(data)";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = serial;
            ref to   : Lifeline = pkt;
            attribute :>> label = "getBuffer()";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = serial;
            ref to   : Lifeline = pkt;
            attribute :>> label = "getCRC16()";
        }

        part m5 : ReturnMessage {
            ref from : Lifeline = serial;
            ref to   : Lifeline = serial;
            attribute :>> label = "sendStatus(status)";
        }

        part m6 : AsynchronousMessage {
            ref from : Lifeline = serial;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(sendMsg)";
        }

        part sendActivation : Activation {
            ref on            : Lifeline = serial;
            ref startMessage  : Message  = m1;
            ref finishMessage : Message  = m6;
        }
    }


    // =========================================================
    // SCENARIO 10: Serial Receive Packet
    // Trigger: SerialHandler::receive()
    // Static+Trace: msgs 68,472,528,533,534
    // =========================================================

    part def SerialReceiveScenario :> InteractionScenario {

        part serial     : Lifeline;
        part codec      : Lifeline;
        part pkt        : Lifeline;
        part serializer : Lifeline;
        part logger     : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = serial;
            ref to   : Lifeline = serial;
            attribute :>> label = "receive(buffer)";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = serial;
            ref to   : Lifeline = pkt;
            attribute :>> label = "hamming74Decode(data)";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = pkt;
            ref to   : Lifeline = codec;
            attribute :>> label = "decode(data)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = serial;
            ref to   : Lifeline = serializer;
            attribute :>> label = "extract(bytes)";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = serial;
            ref to   : Lifeline = pkt;
            attribute :>> label = "getCRC16()";
        }

        part m6 : AsynchronousMessage {
            ref from : Lifeline = serial;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(receiveMsg)";
        }
    }


    // =========================================================
    // SCENARIO 11: IDC Packet Dispatch
    // Trigger: Idc::sendPacket() / subscribeOnPacket()
    // Static+Trace: msgs 31,38,53,140,173,297,331,412
    // =========================================================

    part def IdcDispatchScenario :> InteractionScenario {

        part idc    : Lifeline;
        part obj    : Lifeline;
        part logger : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = idc;
            ref to   : Lifeline = obj;
            attribute :>> label = "isSet()";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = idc;
            ref to   : Lifeline = obj;
            attribute :>> label = "get(senderId)";
        }

        part m3 : AsynchronousMessage {
            ref from : Lifeline = idc;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(idcMsg)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = idc;
            ref to   : Lifeline = idc;
            attribute :>> label = "sendPacket(pkt)";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = idc;
            ref to   : Lifeline = obj;
            attribute :>> label = "get(subscriberId)";
        }

        part m6 : AsynchronousMessage {
            ref from : Lifeline = idc;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(subMsg)";
        }
    }


    // =========================================================
    // SCENARIO 12: Configuration Mapping
    // Trigger: PropertyMapper::add()
    // Static+Trace: msgs 2,16,104,142,238,282,397,642
    // =========================================================

    part def ConfigMappingScenario :> InteractionScenario {

        part config : Lifeline;
        part logger : Lifeline;

        part m1 : AsynchronousMessage {
            ref from : Lifeline = config;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(configMsg)";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = config;
            ref to   : Lifeline = config;
            attribute :>> label = "add(key, value)";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = config;
            ref to   : Lifeline = config;
            attribute :>> label = "mandatoryCheck(key)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = config;
            ref to   : Lifeline = config;
            attribute :>> label = "addVector(key, values)";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = config;
            ref to   : Lifeline = config;
            attribute :>> label = "mandatoryCheck(key)";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = config;
            ref to   : Lifeline = config;
            attribute :>> label = "addMap(key, map)";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = config;
            ref to   : Lifeline = config;
            attribute :>> label = "parseConfigString(str)";
        }
    }


    // =========================================================
    // SCENARIO 13: Hamming 7/4 Codec
    // Trigger: HammingCodec::encode() / decode()
    // Static+Trace: msgs 1,37,99,219,272,330
    // =========================================================

    part def HammingCodecScenario :> InteractionScenario {

        part codec : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = codec;
            ref to   : Lifeline = codec;
            attribute :>> label = "encode(data)";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = codec;
            ref to   : Lifeline = codec;
            attribute :>> label = "getBit(pos)";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = codec;
            ref to   : Lifeline = codec;
            attribute :>> label = "setBit(pos, val)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = codec;
            ref to   : Lifeline = codec;
            attribute :>> label = "decode(encoded)";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = codec;
            ref to   : Lifeline = codec;
            attribute :>> label = "getBit(pos)";
        }

        part m6 : SynchronousCall {
            ref from : Lifeline = codec;
            ref to   : Lifeline = codec;
            attribute :>> label = "setBit(pos, val)";
        }
    }


    // =========================================================
    // SCENARIO 14: Framework API and Factory
    // Trigger: FrameworkApi::lockAggregator() / create()
    // Static+Trace: msgs 41,71,84,159,235,258,345
    // =========================================================

    part def FrameworkScenario :> InteractionScenario {

        part fw         : Lifeline;
        part aggregator : Lifeline;
        part logger     : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = fw;
            ref to   : Lifeline = fw;
            attribute :>> label = "instance()";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = fw;
            ref to   : Lifeline = fw;
            attribute :>> label = "lockAggregator()";
        }

        part m3 : SynchronousCall {
            ref from : Lifeline = fw;
            ref to   : Lifeline = fw;
            attribute :>> label = "instance()";
        }

        part m4 : ReturnMessage {
            ref from : Lifeline = fw;
            ref to   : Lifeline = aggregator;
            attribute :>> label = "getAggregator()";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = fw;
            ref to   : Lifeline = fw;
            attribute :>> label = "create(typeName)";
        }

        part m6 : AsynchronousMessage {
            ref from : Lifeline = fw;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(createMsg)";
        }

        part m7 : SynchronousCall {
            ref from : Lifeline = fw;
            ref to   : Lifeline = fw;
            attribute :>> label = "createSpecific(typeName)";
        }

        part m8 : SynchronousCall {
            ref from : Lifeline = fw;
            ref to   : Lifeline = fw;
            attribute :>> label = "createDefaultImpl(typeName)";
        }
    }


    // =========================================================
    // SCENARIO 15: Test Execution
    // Trigger: Catch2 main() via TestRunner
    // Static+Trace: msgs 5,6,9,10,21
    // =========================================================

    part def TestExecutionScenario :> InteractionScenario {

        part runner    : Lifeline;
        part testInfo  : Lifeline;
        part framework : Lifeline;
        part logger    : Lifeline;

        part m1 : SynchronousCall {
            ref from : Lifeline = runner;
            ref to   : Lifeline = testInfo;
            attribute :>> label = "getInstance()";
        }

        part m2 : SynchronousCall {
            ref from : Lifeline = runner;
            ref to   : Lifeline = testInfo;
            attribute :>> label = "initialize()";
        }

        part m3 : AsynchronousMessage {
            ref from : Lifeline = testInfo;
            ref to   : Lifeline = logger;
            attribute :>> label = "stream(initMsg)";
        }

        part m4 : SynchronousCall {
            ref from : Lifeline = runner;
            ref to   : Lifeline = framework;
            attribute :>> label = "run()";
        }

        part m5 : SynchronousCall {
            ref from : Lifeline = framework;
            ref to   : Lifeline = framework;
            attribute :>> label = "handleExpr(expr)";
        }

        part m6 : ReturnMessage {
            ref from : Lifeline = framework;
            ref to   : Lifeline = runner;
            attribute :>> label = "complete(result)";
        }

        part runActivation : Activation {
            ref on            : Lifeline = runner;
            ref startMessage  : Message  = m1;
            ref finishMessage : Message  = m6;
        }
    }
}