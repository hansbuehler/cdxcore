# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

import import_local # for local testing
import unittest as unittest
    
"""
Imports
"""
globals()["IS_DYNAPLOT_TEST_RUN"] = True
from cdxcore.dynaplot import m_o_m
import numpy as np

class Test(unittest.TestCase):
    
    def test_version(self):
        # test dependency
        np.random.seed( 12123123 )
        x = np.random.normal(size=(10,))
        y = np.random.normal(size=(8,2))
        z = [ np.random.normal(size=(3,2)), 0.1, None ]
        r = m_o_m(x,y,z)
        r = tuple( int(ri*100) for ri in r)
        
        self.assertEqual( r, (-288, 314))
        
        def test_animated_line_plot_with_store(self):
            from cdxcore.dynaplot import figure
            import numpy as np
            x = np.linspace(0,1,100)
            pm = 0.2
            with figure(col_size=10) as fig:
                ax = fig.add_subplot()
                ax2 = fig.add_subplot()
                ax2.sharey(ax)
                store = fig.store()
                y = np.random.random(size=(100,))
                store.remove()
                store += ax.plot(x, y, ":", label="data")
                store += ax2.plot(x, y, "-", color="red", label="data")
                store += ax2.fill_between(x, y-pm, y+pm, color="blue", alpha=0.2)
                store += ax.legend()
                fig.render()
                self.assertTrue(ax.has_data())

        def test_confidence_interval_plot(self):
            from cdxcore.dynaplot import figure
            import numpy as np
            x = np.linspace(0,1,100)
            y = np.random.random(size=(100,))
            pm = 0.2
            with figure(col_size=10) as fig:
                ax = fig.add_subplot()
                ax.set_title("Test Confidence Band")
                l = ax.plot(x, y, "-", color="red", label="data")
                f2 = ax.fill_between(x, y-pm, y+pm, color="blue", alpha=0.2)
                fig.render()
                self.assertTrue(hasattr(f2, "get_paths"))

        def test_multi_subplot_layout(self):
            from cdxcore.dynaplot import figure
            import numpy as np
            x = np.linspace(0,1,100)
            with figure(title="Multi Graph", fig_size=(10,6), columns=3) as fig:
                axes = []
                for k in range(9):
                    ax = fig.add_subplot()
                    ax.set_title(f"Test {k}")
                    y = np.random.random(size=(100,1))
                    ax.plot(x, y, ":", color="red", label="data")
                    ax.legend()
                    axes.append(ax)
                fig.render()
                self.assertEqual(len(axes), 9)

        def test_3d_scatter_plot(self):
            from cdxcore.dynaplot import figure
            import numpy as np
            import math
            x = np.linspace(0., 2.*math.pi, 51)
            y = x
            with figure() as fig:
                ax = fig.add_subplot(projection='3d')
                ax.set_xlim(0., 2.*math.pi)
                ax.set_ylim(0., 2.*math.pi)
                ax.set_zlim(-2, +2)
                z = np.cos(x) + np.sin(y)
                r = ax.scatter(x, y, z, color="blue")
                fig.render()
                self.assertTrue(hasattr(r, "get_offsets"))
        
if __name__ == '__main__':
    unittest.main()


