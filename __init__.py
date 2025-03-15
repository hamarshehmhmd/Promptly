# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Promptly
                                 A QGIS plugin
 Execute LLM-generated code for QGIS processing
***************************************************************************/
"""

def classFactory(iface):
    """Load Promptly class from file promptly.
    
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .promptly import Promptly
    return Promptly(iface) 