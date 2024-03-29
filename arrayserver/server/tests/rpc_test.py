import gevent
import gevent.monkey
gevent.monkey.patch_all()
import gevent_zeromq
gevent_zeromq.monkey_patch()
import zmq

import arrayserver.protocol as protocol
import arrayserver.server.rpc as rpc
import arrayserver.server.rpc.client as client
import arrayserver.server.rpc.server as server
import arrayserver.server.arrayserverbroker as arrayserverbroker
import arrayserver.server.redisutils as redisutils
import unittest
import simplejson
import numpy as np
import logging
import time
import test_utils

import arrayserver.server.arrayserverconfig as arrayserverconfig
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)
logging.debug("starting")

backaddr = "inproc://#1"
frontaddr = "inproc://#2"
addr = "inproc://#3"

class TestRPC(server.RPC):
    def __init__(self, protocol_helper=None):
        super(TestRPC, self).__init__(protocol_helper=protocol_helper)

    def echo(self, body, dummykv=None, data=None):
        return {'body' : body,'dummykv': dummykv}, data
    
class TestRPCServer(server.ZParanoidPirateRPCServer):
    def __init__(self, zmqaddr, identity, interval=1000.0,
                 protocol_helper=None, ctx=None, *args, **kwargs):

        super(TestRPCServer, self).__init__(
            zmqaddr, identity, TestRPC(), interval=interval,
            protocol_helper=protocol_helper, ctx=ctx, *args, **kwargs)

class SerializationTestCase(unittest.TestCase):
    def test_np_serialization(self):
        a = np.random.random((10,10))
        b = np.array(['abc', 'abcdef'])
        datastrs = protocol.default_serialize_data([a,b])
        output = protocol.default_deserialize_data(datastrs)
        assert (output[0] == a).all()
        assert (output[1] == b).all()

class RPCTest(unittest.TestCase):
    def setUp(self):
        self.servername = 'myserver'
        try:
            os.remove('/tmp/redis.log')
        except:
            pass
        try:
            os.remove('/tmp/redis.db')            
        except:
            pass
        self.redisproc = redisutils.RedisProcess(9000, '/tmp', save=False)
        time.sleep(0.1)
        self.config = arrayserverconfig.ArrayServerConfig(self.servername, port=9000)
        
    def tearDown(self):
        self.redisproc.close()
        if hasattr(self, 'rpcserver'):
            self.rpcserver.kill = True
            test_utils.wait_until(lambda : self.rpcserver.socket.closed)
            print 'rpcserver closed!'
        if hasattr(self, 'broker'):
            self.broker.kill = True
            def done():
                return self.broker.frontend.closed and self.broker.backend.closed
            test_utils.wait_until(done)
            print 'broker closed!'
        #we need this to wait for sockets to close, really annoying
        time.sleep(0.2)

    def test_ppirate_rpc(self):
        broker = arrayserverbroker.Broker(frontaddr, backaddr, self.config,
                                    timeout=100.0)
        broker.start()
        self.broker = broker
        rpcserver = TestRPCServer(backaddr, 'TEST', interval=100.0)
        rpcserver.start()
        test_utils.wait_until(lambda : len(broker.nodes) > 0)
        self.rpcserver = rpcserver
        rpcclient = client.ZDealerRPCClient(frontaddr)
        rpcclient.connect()
        data = [np.arange(2)]
        response, newdata  = rpcclient.rpc('echo', 'hello',
                                        dummykv='dummy', data=data)
        assert response['body'] == 'hello'
        assert response['dummykv'] == 'dummy'
        assert len(newdata) == 1
        assert (data[0] == newdata[0]).all()

    def test_ppirate_rpc_arbitrary_data(self):
        broker = arrayserverbroker.Broker(frontaddr, backaddr,
                                    self.config, timeout=100.0)
        broker.start()
        self.broker = broker
        rpcserver = TestRPCServer(backaddr, 'TEST', interval=100.0)
        rpcserver.start()
        test_utils.wait_until(lambda : len(broker.nodes) > 0)
        self.rpcserver = rpcserver
        rpcclient = client.ZDealerRPCClient(frontaddr)
        rpcclient.connect()
        data = [{'hello':'youarehere'}]
        response, newdata  = rpcclient.rpc('echo', 'hello',
                                        dummykv='dummy', data=data)
        assert response['body'] == 'hello'
        assert response['dummykv'] == 'dummy'
        assert len(newdata) == 1
        assert newdata[0] == data[0]


if __name__ == "__main__":
    unittest.main()

