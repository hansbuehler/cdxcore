# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

def import_local():
    return
    """
    In order to be able to run our tests manually from the 'tests' directory
    we force import from the local package.
    """
    me = "cdxcore"
    import os
    import sys
    cwd = os.getcwd()
    if cwd[-len(me):] == me:
        return
    assert cwd[-5:] == "tests",("Expected current working directory to be in a 'tests' directory", cwd[-5:], "from", cwd)
    assert cwd[-6] in ['/', '\\'],("Expected current working directory 'tests' to be lead by a '\\' or '/'", cwd[-6:], "from", cwd)
    sys.path.insert( 0, cwd[:-6] )
import_local()

import unittest as unittest
import dataclasses as dataclasses
import os as os
import pickle as pickle
import tempfile as tempfile
import shutil as shutil

from cdxcore.config import Config, Int, Float
from cdxcore.pretty import PrettyObject as pdct
from cdxcore.uniquehash import unique_hash16

class Test(unittest.TestCase):

    def test_config(self):

        config = Config(x=0., z=-1.)
        x = config("x", 10., float, "test x")
        self.assertEqual( x, 0. )
        y = config("y", 10., float, "test y")
        self.assertEqual( y, 10. )

        with self.assertRaises(Exception):
            # 'z' was not read
            config.done()

        # calling twice with different values
        config = Config(x=0.)
        x = config("x", 1., float, "test x")
        x = config("x", 1., float, "test x")   # ok: same parameters
        with self.assertRaises(Exception):
            x = config("x", 1., Float<0.5, "test x") # not ok: Float condition
        with self.assertRaises(Exception):
            x = config("x", 2., float, "test x") # not ok: different default
        config.done()

        # test usage per access method:
        #   __call__('a')
        #   get('a')
        #   get_default('a', ...)
        # all register usage;
        #   get_raw('a')
        #   ['a']
        # do not.
        config = Config(a=1)
        _ = config.get("a")
        self.assertTrue( not 'a' in config.not_done )
        config = Config(a=1)
        _ = config.get_default("a", 0)
        self.assertTrue( not 'a' in config.not_done )
        config = Config(a=1)
        _ = config("a")
        self.assertTrue( not 'a' in config.not_done )
        config = Config(a=1)
        _ = config("a", 0)
        self.assertTrue( not 'a' in config.not_done )

        config = Config(a=1)
        _ = config.get_raw('a')
        self.assertTrue( 'a' in config.not_done )
        config = Config(a=1)
        _ = config['a']
        self.assertTrue( 'a' in config.not_done )

        # test sub configs
        config = Config()
        config.x = 1
        config.a = "a"
        config.sub.x = 2.

        self.assertEqual(1., config("x", 0., float, "x"))
        self.assertEqual("a", config("a", None, str, "a"))
        self.assertEqual(2, config.sub("x", 0, int, "x"))
        self.assertTrue( isinstance( config.sub, Config ) )
        config.done()

        # test detach
        config = Config()
        config.sub.x = 1
        with self.assertRaises(Exception):
            config.done() # 'sub.x' not read

        config = Config()
        config.sub.x = 1
        sub = config.sub.detach()
        config.done() # ok
        _ = sub("x", 1)
        config.done() # fine now

        # test list (_Enum)
        config = Config(t="a", q="q")
        _ = config("t", "b", ['a', 'b', 'c'] )
        self.assertEqual(_, 'a')
        with self.assertRaises(Exception):
            _ = config("q", "b", ['a', 'b', 'c'] )   # exception: 'q' not in set

        # test tuple (_Alt)
        config = Config(t="a")
        _ = config("t", "b", (None, str) )
        self.assertEqual(_, 'a')
        config = Config(t=None)
        _ = config("t", "b", (None, str) )
        self.assertEqual(_, None)
        with self.assertRaises(Exception):
            config = Config(t="a")
            _ = config("t", 1, (None, int) )
        self.assertEqual(_, None)
        config = Config()
        _ = config("t", "b", (None, ['a','b']) )
        self.assertEqual(_, 'b')
        config = Config(t=2)
        _ = config("t", 1, (Int>=1, Int<=1) )
        self.assertEqual(_, 2)
        config = Config()
        _ = config("t", 3, (Int>=1, Int<=1) )
        self.assertEqual(_, 3)
        with self.assertRaises(Exception):
            config = Config()
            _ = config("t", 0, (Int>=1, Int<=-1) )
        with self.assertRaises(Exception):
            config = Config(t=0)
            _ = config("t", 3, (Int>=1, Int<=-1) )

        # combined conditons
        config = Config(x=1., y=1.)

        x = config("x", 1., ( Float>=0.) & (Float<=1.), "test x")
        with self.assertRaises(Exception):
            # test that violated condition is caught
            y = config("y", 1., ( Float>=0.) & (Float<1.), "test y")

        config = Config(x=1., y=1.)
        with self.assertRaises(NotImplementedError):
            # left hand must be > or >=
            y = config("y", 1., ( Float<=0.) & (Float<1.), "test x")
        config = Config(x=1., y=1.)
        with self.assertRaises(NotImplementedError):
            # right hand must be < or <=
            y = config("y", 1., ( Float>=0.) & (Float>1.), "test x")

        # test int
        config = Config(x=1)
        x = config("x", 0, ( Int>=0 ) & ( Int<=1), "int test")
        config = Config(x=1)
        with self.assertRaises(NotImplementedError):
            # cannot mix types
            x = config("x", 1., ( Float>=0.) & (Int<=1), "test x")

        # test deleting children
        config = Config()
        config.a.x = 1
        config.b.x = 2
        config.c.x = 3
        config.delete_children( 'a' )
        l = sorted( config.children )
        self.assertEqual(l, ['b', 'c'])
        config = Config()
        config.a.x = 1
        config.b.x = 2
        config.c.x = 3
        config.delete_children( ['a','b'] )
        l = sorted( config.children )
        self.assertEqual(l, ['c'])

        # test conversion to dictionaries
        config = Config()
        config.x = 1
        config.y = 2
        config.sub.x = 10
        config.sub.y = 20
        inp_dict = config.input_dict()

        test = pdct()
        test.x = 1
        test.y = 2
        test.sub = pdct()
        test.sub.x = 10
        test.sub.y = 20

        self.assertEqual( test, inp_dict)

        # clean_copy
        config = Config()
        config.gym.user_version = 1
        config.gym.world_character_id = 2
        config.gym.vol_model.type = "decoder"
        _ = config.clean_copy()

        """
        test = PrettyDict()
        test.x = config("x", 1)
        test.y = config("y", 22)
        test.z = config("z", 33)
        test.sub = PrettyDict()
        test.sub.x = config.sub("x", 10)
        test.sub.y = config.sub("y", 222)
        test.sub.z = config.sub("z", 333)
        usd_dict = config.usage_dict()
        self.assertEqual( usd_dict, test )
        """

        # test keys()

        config = Config()
        config.a = 1
        config.x.b = 2
        keys = list(config)
        sorted(keys)
        self.assertEqual( keys, ['a'])
        keys = list(config.keys())
        sorted(keys)
        self.assertEqual( keys, ['a'])

        # test update

        config = Config()
        config.a = 1
        config.x.a = 1
        config.z.a =1

        config2 = Config()
        config2.b = 2
        config2.x.a = 2
        config2.x.b = 2
        config2.y.b = 2
        config2.z = 2
        config.update( config2 )
        ur1 = config.input_report()

        econfig = Config()
        econfig.a = 1
        econfig.b = 2
        econfig.x.a = 2
        econfig.x.b = 2
        econfig.y.b = 2
        econfig.z = 2
        ur2 = econfig.input_report()
        self.assertEqual( ur1, ur2 )

        config = Config()
        config.a = 1
        config.x.a = 1

        d = dict(b=2,x=dict(a=2,b=2),y=dict(b=2),z=2)
        config.update(d)
        ur2 = econfig.input_report()
        self.assertEqual( ur1, ur2 )

        # test str and repr

        config = Config()
        config.x = 1
        config.y = 2
        config.sub.x = 10
        config.sub.y = 20

        self.assertEqual( str(config), "config{'x': 1, 'y': 2, 'sub': {'x': 10, 'y': 20}}")
        self.assertEqual( repr(config), "Config( **{'x': 1, 'y': 2, 'sub': {'x': 10, 'y': 20}}, config_name='config' )")

        # test recorded usage

        config = Config()
        config.x = 1
        config.sub.a = 1
        config.det.o = 1

        _ = config("x", 11)
        _ = config("y", 22)
        _ = config.sub("a", 11)
        _ = config.sub("b", 22)
        det = config.det.detach() # shares the same recorder !
        _ = det("o", 11)
        _ = det("p", 22)

        self.assertEqual( config.get_recorded("x"), 1)
        self.assertEqual( config.get_recorded("y"), 22)
        self.assertEqual( config.sub.get_recorded("a"), 1)
        self.assertEqual( config.sub.get_recorded("b"), 22)
        self.assertEqual( config.det.get_recorded("o"), 1)
        self.assertEqual( config.det.get_recorded("p"), 22)

        # unique ID

        config = Config()
        # world
        config.world.samples = 10000
        config.world.steps = 20
        config.world.black_scholes = True
        config.world.rvol = 0.2    # 20% volatility
        config.world.drift = 0.    # real life drift
        config.world.cost_s = 0.
        # gym
        config.gym.objective.utility = "cvar"
        config.gym.objective.lmbda = 1.
        config.gym.agent.network.depth = 6
        config.gym.agent.network.width = 40
        config.gym.agent.network.activation = "softplus"
        # trainer
        config.trainer.train.optimizer = "adam"
        config.trainer.train.batch_size = None
        config.trainer.train.epochs = 400
        config.trainer.caching.epoch_freq = 10
        config.trainer.caching.mode = "on"
        config.trainer.visual.epoch_refresh = 1
        config.trainer.visual.time_refresh = 10
        config.trainer.visual.confidence_pcnt_lo = 0.25
        config.trainer.visual.confidence_pcnt_hi = 0.75

        id1 = config.unique_hash()

        config = Config()
        # world
        config.world.samples = 10000
        config.world.steps = 20
        config.world.black_scholes = True
        config.world.rvol = 0.2    # 20% volatility
        config.world.drift = 0.    # real life drift
        config.world.cost_s = 0.
        # gym
        config.gym.objective.utility = "cvar"
        config.gym.objective.lmbda = 1.
        config.gym.agent.network.depth = 5   # <====== changed this
        config.gym.agent.network.width = 40
        config.gym.agent.network.activation = "softplus"
        # trainer
        config.trainer.train.optimizer = "adam"
        config.trainer.train.batch_size = None
        config.trainer.train.epochs = 400
        config.trainer.caching.epoch_freq = 10
        config.trainer.caching.mode = "on"
        config.trainer.visual.epoch_refresh = 1
        config.trainer.visual.time_refresh = 10
        config.trainer.visual.confidence_pcnt_lo = 0.25
        config.trainer.visual.confidence_pcnt_hi = 0.75

        id2 = config.unique_hash()
        self.assertNotEqual(id1,id2)
        self.assertEqual(id2,"cfef59b69770d0a973342ad68f38fba2")

        _ = config.nothing("get_nothing", 0)  # this triggered a new ID in old versions

        id3 = config.unique_hash()
        self.assertEqual(id2,id3)
        
        idempty = Config().unique_hash()
        self.assertEqual(idempty,"64550d6ffe2c0a01a14aba1eade0200c")
        self.assertNotEqual(idempty,id3)

        # pickle test

        binary   = pickle.dumps(config)
        restored = pickle.loads(binary)
        idrest   = restored.unique_hash()
        self.assertEqual(idrest,id2)

        # unique ID test

        config1 = Config()
        config1.x = 1
        config1.sub.y = 2
        config2 = Config()
        config2.x = 1
        config2.sub.y = 3
        self.assertNotEqual( unique_hash16(config1), unique_hash16(config2) )

        config1 = Config()
        config1.x = 1
        config1.sub.y = 2
        config2 = Config()
        config2.x = 2
        config2.sub.y = 2
        self.assertNotEqual( unique_hash16(config1), unique_hash16(config2) )

        config1 = Config()
        config1.x = 1
        config1.sub.y = 2
        config2 = Config()
        config2.x = 1
        config2.sub.y = 2
        self.assertEqual( unique_hash16(config1), unique_hash16(config2) )

        # unique_hash16() ignores protected and private members
        config1 = Config()
        config1.x = 1
        config1.sub._y = 2
        config2 = Config()
        config2.x = 1
        config2.sub._y = 3
        self.assertEqual( unique_hash16(config1), unique_hash16(config2) )

    def test_detach(self):
        """ testing detach/copy/clean_cooy """

        config = Config(a=1,b=2)
        config.child.x = 1
        _ = config("a", 2)
        c1 = config.detach()
        with self.assertRaises(Exception):
            _ = c1("a", 1)  # different default
        _ = c1("b", 3)
        with self.assertRaises(Exception):
            _ = config("b", 2)  # different default

        config = Config(a=1,b=2)
        config.child.x = 1
        _ = config("a", 2)
        c1 = config.copy()
        with self.assertRaises(Exception):
            _ = c1("a", 1)  # different default
        _ = c1("b", 3)
        _ = config("b", 2)  # different default - ok

        config = Config(a=1,b=2)
        config.child.x = 1
        _ = config("a", 2)
        c1 = config.clean_copy()
        _ = c1("a", 1)  # different default - ok
        _ = c1("b", 3)
        _ = config("b", 2)  # different default - ok

    def test_dataclass(self):
        
        @dataclasses.dataclass
        class A:
            i : int = 0
            config : Config = Config().as_field()
            
            def f(self):
                return self.config("a", 1, int, "Test")
            
        a = A()
        self.assertEqual(a.f(),1)
        c = Config()
        a = A(i=2,config=Config(c))
        self.assertEqual(a.f(),1)
        c = Config(a=2)
        a = A(i=2,config=Config(c))
        self.assertEqual(a.f(),2)
        a = A(i=2,config=Config(a=2))
        self.assertEqual(a.f(),2)
            
    def test_io(self):

        config = Config(x=1)
        config.child.y = 2
        config._test = 33        

        try:
            tmp_dir  = tempfile.mkdtemp()    
            self.assertNotEqual(tmp_dir[-1],"/")
            self.assertNotEqual(tmp_dir[-1],"\\")
            tmp_file = tmp_dir + "/test_pretty_object.pck"
            
            with open(tmp_file, "wb") as f:
                pickle.dump(config,f)
                
            with open(tmp_file, "rb") as f:
                config2 = pickle.load(f)
                self.assertEqual(config,config2)
                
            os.remove(tmp_file)
        finally:
            shutil.rmtree(tmp_dir)

    def test_config_edge_cases(self):
        """Test edge cases and error handling in Config"""
        
        # Test empty config
        config = Config()
        config.done()
        self.assertTrue(config.is_empty)
        
        # Test config value conversion with type constraints
        config = Config(val="5")
        result = config("val", 0, int, "test conversion")
        self.assertEqual(result, 5)
        self.assertIsInstance(result, int)
        config.done()
        
        # Test config with None values
        config = Config(optional=None)
        result = config("optional", "default", (None, str), "optional parameter")
        self.assertIsNone(result)
        config.done()
        
        # Test config inconsistency detection
        config = Config(x=1)
        config("x", 1, int, "parameter x")
        with self.assertRaises(Exception):
            config("x", 2, int, "parameter x")  # Different default
        config.done()
        
        # Test shallow copy shares usage tracking
        config1 = Config(x=1)
        config2 = Config(config1)
        _ = config1("x", 0, int, "test")
        self.assertTrue("x" in config1._done)
        self.assertTrue("x" in config2._done)  # shared tracking
        config1.done(include_children=False)
        config2.done(include_children=False)
        
        # Test clean copy is independent
        config1 = Config(x=1)
        config2 = config1.clean_copy()
        _ = config1("x", 0, int, "test")
        self.assertTrue("x" in config1._done)
        self.assertFalse("x" in config2._done)  # independent tracking
        _ = config2("x", 0, int, "test")  # Read x in config2 as well
        config1.done(include_children=False)
        config2.done(include_children=False)
        
    def test_config_vector_operations(self):
        """Test vector/list operations in Config"""
        
        config = Config()
        config.items = [1, 2, 3]
        
        # Test reading as list
        result = config("items", [], list, "list of items")
        self.assertEqual(result, [1, 2, 3])
        config.done()
        
    def test_config_key_methods(self):
        """Test Config key access methods"""
        
        config = Config(a=1, b=2, c=3)
        
        # Test keys iteration
        keys_list = list(config.keys())
        self.assertEqual(set(keys_list), {'a', 'b', 'c'})
        
        # Test values iteration
        values_list = list(config.values())
        self.assertEqual(set(values_list), {1, 2, 3})
        
        # Test items iteration
        items_list = list(config.items())
        self.assertEqual(len(items_list), 3)
        
        config.mark_done()
        config.done()

        
if __name__ == '__main__':
    unittest.main()


