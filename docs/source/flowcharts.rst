Flowcharts
==========

.. figure:: illustrations/flowchart.png
   :align: center
   :width: 80%

   Flowchart of the encoder

.. mermaid::

   sequenceDiagram
      participant Alice
      participant Bob
      Alice->John: Hello John, how are you?
      loop Healthcheck
          John->John: Fight against hypochondria
      end
      Note right of John: Rational thoughts <br/>prevail...
      John-->Alice: Great!
      John->Bob: How about you?
      Bob-->John: Jolly good!


.. mermaid:: 
   _static/fig1.mmd

.. mermaid:: 
   _static/fig2.mmd
