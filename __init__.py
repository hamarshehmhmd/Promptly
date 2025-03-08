# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QGISPromptExecutor
                                 A QGIS plugin
 Execute LLM-generated code for QGIS processing
***************************************************************************/
"""

def classFactory(iface):
    """Load QGISPromptExecutor class from file QGISPromptExecutor.
    
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .qgis_prompt_executor import QGISPromptExecutor
    return QGISPromptExecutor(iface) 