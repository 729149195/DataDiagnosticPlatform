# -*- coding: utf-8 -*-

import numpy as np
from MDSplus import Tree, mdsExceptions, Connection


def judge_data(npary):
    """ 判断MDSplus返回数据是否是一维数据 """
    if len(npary.shape) == 1:
        return npary, ''
    elif len(npary.shape) == 2:
        if npary.shape[0] == 1:
            return npary[0], ''
        elif npary.shape[1] == 1:
            return npary.T[0], ''
        else:
            return np.array([]), '解析二维数据出错'
    else:
        return np.array([]), '解析多维数据出错'


class MdsConn:
    """ 构建MDSplus.Connection 获取数据 """

    def __init__(self, dbname, ipAddress):
        self.dbname = dbname
        self.conn = Connection(ipAddress)

    def openTree(self, shot):
        self.conn.openTree(self.dbname, shot)

    def closeTree(self, shot):
        self.conn.closeTree(self.dbname, shot)

    def closeConn(self):
        self.conn.closeAllTrees()
        self.conn.disconnect()

    def setTimeContext(self, begin, end, delta):
        """ 设置起止时间及采样率，参数单位s """
        timeContext = 'SetTimeContext({},{},{})'.format(begin, end, delta)
        self.conn.get(timeContext)

    def getOneData(self, channel_name):
        """
        返回x, y, unit, message数据
        """
        try:
            data_x = self.conn.get(r"dim_of(\{})".format(channel_name)).data()
            data_y = self.conn.get(r"\{}".format(channel_name)).data()
            # data = self.conn.get(r"[dim_of(\{}),\{}]".format(channel_name,channel_name)).data()
            unit = self.conn.get(r"units_of(\{})".format(channel_name))
            unit = '' if unit == ' ' else str(unit).replace('"', r'\"').replace("'", r"\'")
            data_x, err_x = judge_data(data_x)
            data_y, err_y = judge_data(data_y)
            message = err_x + err_y
        except mdsExceptions.TreeNOT_OPEN:
            data_x, data_y, unit = np.array([]), np.array([]), ''
            message = f'{channel_name} %TREE-W-NOT_OPEN, Tree not currently open.'
        except mdsExceptions.TdiINVCLADSC:
            data_x, data_y, unit = np.array([]), np.array([]), ''
            # message = f'{channel_name} %TDI-E-INVCLADSC, Storage class not valid, must be scalar or array.'
            message = f'{channel_name} No data available for this time slice.'
        except mdsExceptions.TreeNODATA:
            data_x, data_y, unit = np.array([]), np.array([]), ''
            message = f'{channel_name} %TREE-E-NODATA, No data available for this node.'
        except mdsExceptions.TreeNNF:
            data_x, data_y, unit = np.array([]), np.array([]), ''
            message = f'{channel_name} %TREE-W-NNF, Node Not Found.'
        except Exception as e:
            data_x, data_y, unit = np.array([]), np.array([]), ''
            message = f'Check {channel_name} find that {str(e)}'

        return {'data_x': data_x, 'data_y': data_y, 'unit': unit, 'message': message, }

    def getManyData(self, db_caches, channels_set, begin='', end='', delta=''):
        """
        获取多个通道数据
        db_caches: 缓存, tools文件下的类
        channels_set: {'shotnum':[{'channel':'','formula':'','location':'','name':'','unit':'','color':'',},],'shotnum':[...]}
        return {'shot_channel_begin_end_delta':{data_x, data_y, unit, message},...}
        返回结果需要放入缓存，给前端前再定制formula 与 location
        """
        task_list, result = [], {}
        for shot, cha_list in channels_set.items():
            self.openTree(int(shot))
            self.setTimeContext(begin, end, delta)
            for cha in cha_list:
                key = f"{shot}/{cha['channel']}/{begin}/{end}/{delta}"
                if db_caches.exists(key):
                    value = db_caches.read(key)
                else:
                    value = self.getOneData(cha['channel'])
                    db_caches.write(key, value)
                result[f"{key}_{cha['id']}"] = {**value, **cha}

        return result

    def initPackage(self):
        return self.conn.GetMany()

    def formPackage(self, pack, channel):
        pack.append(f'{channel}_dim', f'dim_of(\{channel})')
        pack.append(f'{channel}_value', f'\{channel}')
        pack.append(f'{channel}_unit', f'units_of(\{channel})')

    def getManyData2(self, channels_set, begin='', end='', delta=''):
        """
        通过GetMany() 获取多个通道数据
        """
        task_list, result = [], []
        for shot_dic in channels_set:
            self.openTree(shot_dic['shot'])
            self.setTimeContext(begin, end, delta)
            package = self.initPackage()
            key = f"{shot_dic['shot']}_{begin}_{end}_{delta}"
            for channel in shot_dic['channels']:
                self.formPackage(package, channel)
            package_result = package.execute()
            result.append({key: package_result})

        return result


class MdsTree:
    """ 构建MDSplus.Tree的一些常用方法 """

    def __init__(self, shot, dbname, path, subtrees):
        self.shot = shot
        self.dbname = dbname
        self.subtrees = subtrees
        self.tree = Tree(self.dbname, self.shot, path=path)

    def formChannelPool(self):
        """ 构建一个通道池 """
        channels = []
        for subTree in self.subtrees:
            sub_nodes = self.tree.getNode(r'\TOP.{}'.format(subTree)).getNodeWild("***")
            channels += [node.name.strip() for node in sub_nodes if str(node.usage) == 'SIGNAL' and len(node.tags) > 0]

        return channels

    def close(self):
        self.tree.close()

    def getCurrentShot(self):
        """ 获取当前炮号 """
        try:
            shot_num = self.tree.getCurrent()
        except mdsExceptions.TreeNOCURRENT:
            shot_num = ''
        return shot_num

    def renameChaName(self, channel_name):
        """ 通道名加r'\'是通道的tags, 不在使用'子树:通道名'方式进行索引"""
        return '\\' + channel_name.upper()

    def isHaveData(self, channel_name):
        """ 返回储存内容长度, 当里面不是数据是公式的时候也有长度(此时如果公式索引的通道没数据同样没有数据) """
        length = self.tree.getNode(self.renameChaName(channel_name)).getLength()
        return length

    def getWrittenTime(self, channel_name):
        """ 获得数据写入时间 """
        return self.tree.getNode(self.renameChaName(channel_name)).getTimeInserted().date

    def setTimeContext(self, begin, end, delta):
        """ 设置起止时间及采样率，参数单位s """
        self.tree.setTimeContext(begin, end, delta)

    def getData(self, channel_name, begin=None, end=None, delta=None, isSetTime=True):
        """
        返回x, y, unit数据
        """
        if isSetTime:
            self.setTimeContext(begin, end, delta)
        channel_name = self.renameChaName(channel_name)
        try:
            data_x = self.tree.getNode(channel_name).dim_of().data()
            data_y = self.tree.getNode(channel_name).data()
            unit = self.tree.getNode(channel_name).units_of()
            unit = '' if unit == ' ' else unit
        except mdsExceptions.TreeNODATA:
            # MDSplus.mdsExceptions.TreeNODATA: %TREE-E-NODATA, No data available for this node
            data_x, data_y, unit = [], [], ''
        except mdsExceptions.TreeNNF:
            # MDSplus.mdsExceptions.TreeNNF: %TREE-W-NNF, Node Not Found
            data_x, data_y, unit = [], [], ''
        except Exception as e:
            # print('Check {} find that {}'.format(channel_name, str(e)))
            data_x, data_y, unit = [], [], ''

        return data_x, data_y, unit


def currentShot(dbname, path):
    """ -1: template shot, 0: current shot """
    try:
        tree = Tree(dbname, 0, path=path)
        shot_num = tree.shotid
        if tree.getDatafileSize() < Tree(dbname, -1, path=path).getDatafileSize() * 2:
            shot_num -= 1
    except:
        shot_num = ''
    return shot_num


def formChaPool(dbname, shot, path, subtrees):
    """ 构建一个通道池, 与mdsTree类分开原因：调用的时候不用先实例化一个tree了 """
    tree = Tree(dbname, shot, path=path)
    channels = []
    for subTree in subtrees:
        sub_nodes = tree.getNode(r'\TOP.{}'.format(subTree)).getNodeWild("***")
        channels += [node.name.strip() for node in sub_nodes if str(node.usage) == 'SIGNAL' and len(node.tags) > 0]

    tree.close()
    return channels





