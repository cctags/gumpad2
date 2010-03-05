#!/usr/bin/env python
# coding: utf-8

import wx
import wx.richtext
import wx.lib
import wx.lib.wordwrap

import os
import sys
import uuid
import tempfile
import optparse
import StringIO
import time
import locale

import zshelve
import PyRTFParser

from wx.lib.embeddedimage import PyEmbeddedImage

try:
    dirName = os.path.dirname(os.path.abspath(__file__))
except:
    dirName = os.path.dirname(os.path.abspath(sys.argv[0]))

sys.path.append(os.path.split(dirName)[0])

try:
    from agw import aui
    from agw.aui import aui_switcherdialog as ASD
except ImportError: # if it's not there locally, try the wxPython lib.
    import wx.lib.agw.aui as aui
    from wx.lib.agw.aui import aui_switcherdialog as ASD

import images

program_name = "Gumpad2"
program_version = "v0.1.1"

program_title = "%s %s" % (program_name, program_version)

program_dbpath = "%s.db" % (program_name.lower())

program_main_icon = os.path.join(dirName, "main.ico")

############################################################################
#
# debug tools
#

import inspect


def debug_line():
    try:
        raise Exception
    except:
        return sys.exc_info()[2].tb_frame.f_back.f_lineno


def debug_file():
    return inspect.currentframe().f_code.co_filename


def fall_into(x, a, b):
    assert a < b
    return a <= x and x < b

############################################################################
#
# VsTempFile
#

class VsTempFile:

    def __init__(self):
        self.fd, self.filename = tempfile.mkstemp()

    def __del__(self):
        self.Close()

    def AppendString(self, str):
        os.write(self.fd, str)

    def Close(self):
        os.close(self.fd)
        os.unlink(self.filename)

############################################################################
#
# data format:
#   version:    xx
#   magic:      xx
#   [uuid]:     {type: xx, title: xx, body: xx}, type = (root, dir, html)
#   tree:       item = {id: xx, subs: [item *]}
#

VsData_Format_Version   = 1
VsData_Format_Magic     = "gumpad_magic_jshcm"

VsData_Type_Root    = 1
VsData_Type_Dir     = 2
VsData_Type_Html    = 3


class VsData:

    def __init__(self, filename):
        self.m_filename = filename
        bFileExist = os.access(filename, os.R_OK | os.W_OK)
        self.db = zshelve.btopen(filename)
        if not bFileExist:
            self.__CreateData__()

    def __CreateData__(self):
        self.SetMagic(VsData_Format_Magic)
        self.SetVersion(VsData_Format_Version)
        id = self.GenerateId()
        self.db[id] = {"type": VsData_Type_Root, "title": "root", "body": ""}
        self.db["tree"] = {"id": id, "subs": []}
        self.db.sync()

    def __GetTree__(self, tree, id):
        if id == tree["id"]:
            return None, tree
        for i in tree["subs"]:
            parent, t = self.__GetTree__(i, id)
            if t is not None:
                if parent is None:
                    parent = tree
                return parent, t
        return None, None

    def GetFileName(self):
        return self.m_filename

    def GetVersion(self):
        return self.db["version"]

    def SetVersion(self, version):
        self.db["version"] = version
        self.db.sync()

    def GetMagic(self):
        return self.db["magic"]

    def SetMagic(self, magic):
        self.db["magic"] = magic
        self.db.sync()

    def GetTree(self, parent, id = None):
        """从 parent 往下查找指定 id 的结点，返回 父结点、结点，
        不存在时返回 None
        """
        if id is None:
            return None, parent
        else:
            return self.__GetTree__(parent, id)

    def GetRoot(self):
        return self.db["tree"]

    def SetRoot(self, dir_tree):
        """更新目录树"""
        self.set_root_tree_root = None
        self.set_root_last_node = []
        for i in dir_tree:
            id = i[0]
            path = i[1]
            new = {"id": id, "subs": []}
            if path == 0:
                self.set_root_tree_root = new
                self.set_root_last_node.append(new)
            else:
                while len(self.set_root_last_node) > path:
                    self.set_root_last_node.pop()
                assert len(self.set_root_last_node) == path

                parent = self.set_root_last_node[-1]
                parent["subs"].append(new)
                self.set_root_last_node.append(new)

        assert self.set_root_tree_root is not None
        self.db["tree"] = self.set_root_tree_root
        self.db.sync()

    def GenerateId(self):
        return str(uuid.uuid1())

    def Add(self, title, body, parent_id = None, type = None):
        root = self.db["tree"]
        dummy, t = self.GetTree(root, parent_id)
        if type is None:
            type = VsData_Type_Html
        elif type not in (VsData_Type_Dir, VsData_Type_Html):
            type = VsData_Type_Dir
        new_id = self.GenerateId()
        t["subs"].append({"id": new_id, "subs": []})
        self.db["tree"] = root
        self.db[new_id] = {"type": type, "title": title, "body": body}
        self.db.sync()
        return new_id

    def Delete(self, id):
        """删除指定Id的叶子结点，根结点除外
        成功时返回 True，失败时返回 False
        """
        if id is None:
            return False
        root = self.db["tree"]
        if id == root["id"]:
            return False
        parent, t = self.GetTree(root, id)
        if t is None:
            return False
        if len(t["subs"]) != 0:
            return False

        # 删除关系记录
        for i in range(len(parent["subs"])):
            if id == parent["subs"][i]["id"]:
                del parent["subs"][i]
                break
        self.db["tree"] = root

        # 删除结点记录
        if id in self.db:
            del self.db[id]
        self.db.sync()

    def GetTitle(self, id = None):
        if id is None:
            id = self.db["tree"]["id"]
        return self.db[id]["title"]

    def SetTitle(self, id, title):
        if id is None:
            id = self.db["tree"]["id"]
        t = self.db[id]
        t["title"] = title
        self.db[id] = t
        self.db.sync()

    def GetBody(self, id = None):
        if id is None:
            id = self.db["tree"]["id"]
        return self.db[id]["body"]

    def SetBody(self, id, body):
        if id is None:
            id = self.db["tree"]["id"]
        t = self.db[id]
        t["body"] = body
        self.db[id] = t
        self.db.sync()

    def GetType(self, id = None):
        if id is None:
            id = self.db["tree"]["id"]
        return self.db[id]["type"]

    def IsEditable(self, id = None):
        """判断指定Id对应的内容是否允许编辑"""
        if id is None:
            return False
        t = self.GetType(id)
        return VsData_Type_Html == t


############################################################################
#
# VsConfig
#

class VsConfig:

    def __init__(self):
        pass

def GetDefaultFont():
    return wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, u"宋体", wx.FONTENCODING_SYSTEM)


############################################################################
#
# Control item Id
#

VsGenerateMenuId_Start = wx.ID_HIGHEST + 1

def VsGenerateMenuId():
    global VsGenerateMenuId_Start
    VsGenerateMenuId_Start += 1
    return VsGenerateMenuId_Start

ID_Menu_CreateHtml      = VsGenerateMenuId()
ID_Menu_CreateDir       = VsGenerateMenuId()
ID_Menu_RenameEntry     = VsGenerateMenuId()
ID_Menu_DeleteEntry     = VsGenerateMenuId()
ID_Menu_Save            = VsGenerateMenuId()
ID_Menu_SaveAs          = VsGenerateMenuId()
ID_Menu_Exit            = VsGenerateMenuId()

ID_Menu_ToogleDirectory = VsGenerateMenuId()
ID_Menu_ToogleToolBar   = VsGenerateMenuId()
ID_Menu_Search          = VsGenerateMenuId()

ID_Menu_About           = VsGenerateMenuId()

ID_ToolBar_Bold         = VsGenerateMenuId()
ID_ToolBar_Italic       = VsGenerateMenuId()
ID_ToolBar_Underline    = VsGenerateMenuId()
ID_ToolBar_AlignLeft    = VsGenerateMenuId()
ID_ToolBar_Center       = VsGenerateMenuId()
ID_ToolBar_AlignRight   = VsGenerateMenuId()
ID_ToolBar_IndentLess   = VsGenerateMenuId()
ID_ToolBar_IndentMore   = VsGenerateMenuId()
ID_ToolBar_Font         = VsGenerateMenuId()
ID_ToolBar_FontColor    = VsGenerateMenuId()

ID_Ctx_InsertAsSibling  = VsGenerateMenuId()
ID_Ctx_InsertAsChild    = VsGenerateMenuId()


############################################################################
#
# VsStatusBar
#

class VsStatusBar(wx.StatusBar):

    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent, -1)
        self.SetFieldsCount(3)
        self.SetStatusStyles([wx.SB_FLAT, wx.SB_NORMAL, wx.SB_NORMAL])

        # 显示当前操作数据
        str = "@ %s" % (self.GetParent().db.GetFileName())
        self.SetStatusText(str, 1)

        # 初始时显示时间
        self.OnTimer()

        # 调整控件大小
        width, height = self.GetTextExtent(self.GetStatusText(2))
        width += 48
        self.SetStatusWidths([0, -1, width])

        # 控件时间显示
        self.timer = wx.PyTimer(self.OnTimer)
        self.timer.Start(1000 * 20)

    def OnTimer(self):
        # 显示当前时间
        t = time.localtime(time.time())
        str = time.strftime("[%Y-%m-%d %H:%M %A]", t)
        self.SetStatusText(str, 2)


############################################################################
#
# VsTreeCtrl
#

class VsTreeCtrl(wx.TreeCtrl):
    def __init__(self, parent, id, pos, size, style):
        wx.TreeCtrl.__init__(self, parent, id, pos, size, style)

    def Traverse(self, func, startNode):
        """Apply 'func' to each node in a branch, beginning with 'startNode'. """
        def TraverseAux(node, depth, func):
            nc = self.GetChildrenCount(node, 0)
            child, cookie = self.GetFirstChild(node)
            # In wxPython 2.5.4, GetFirstChild only takes 1 argument
            for i in xrange(nc):
                func(child, depth)
                TraverseAux(child, depth + 1, func)
                child, cookie = self.GetNextChild(node, cookie)
        func(startNode, 0)
        TraverseAux(startNode, 1, func)

    def ItemIsChildOf(self, item1, item2):
        ''' Tests if item1 is a child of item2, using the Traverse function '''
        self.result = False
        def test_func(node, depth):
            if node == item1:
                self.result = True

        self.Traverse(test_func, item2)
        return self.result


############################################################################
#
# VsFrame
#

class VsFrame(wx.Frame):

    def __init__(self, parent, id=wx.ID_ANY, title="", pos=wx.DefaultPosition,
                 size=wx.DefaultSize,
                 style=wx.DEFAULT_FRAME_STYLE | wx.SUNKEN_BORDER):
        wx.Frame.__init__(self, parent, id, title, pos, size, style)
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

        self.db = VsData(program_dbpath)
        self.tree = None
        self.editor_list = []

        self._mgr = aui.AuiManager()

        # tell AuiManager to manage this frame
        self._mgr.SetManagedWindow(self)

        # set frame icon
        icon = wx.EmptyIcon()
        icon.LoadFile(program_main_icon, wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)

        # set up default notebook style
        self._notebook_style = aui.AUI_NB_DEFAULT_STYLE | aui.AUI_NB_TAB_EXTERNAL_MOVE | wx.NO_BORDER
        self._notebook_theme = 0

        # 状态栏
        self.SetStatusBar(VsStatusBar(self))

        self.CreateMenuBar()
        self.BuildPanes()

    def CreateMenuBar(self):
        """创建菜单"""
        mb = wx.MenuBar()

        def DoBindMenuHandler(item, handler, updateUI=None):
            self.Bind(wx.EVT_MENU, handler, item)
            if updateUI is not None:
                self.Bind(wx.EVT_UPDATE_UI, updateUI, item)

        file_menu = wx.Menu()
        DoBindMenuHandler(file_menu.Append(ID_Menu_CreateHtml, u"新建笔记"), self.OnCreateHtml, self.OnMenuUpdateUI)
        DoBindMenuHandler(file_menu.Append(ID_Menu_CreateDir, u"新建目录"), self.OnCreateDir, self.OnMenuUpdateUI)
        file_menu.AppendSeparator()
        DoBindMenuHandler(file_menu.Append(ID_Menu_Save, u"保存(&S)\tCtrl-S"), self.OnSave, self.OnMenuUpdateUI)
        DoBindMenuHandler(file_menu.Append(ID_Menu_SaveAs, u"另存为(&A)"), self.OnSaveAs, self.OnMenuUpdateUI)
        file_menu.AppendSeparator()
        self.Bind(wx.EVT_MENU, self.OnExit, file_menu.Append(ID_Menu_Exit, u"退出(&X)"))

        ope_menu = wx.Menu()
        DoBindMenuHandler(ope_menu.AppendCheckItem(ID_Menu_ToogleDirectory, u"显示目录树(&D)\tCtrl-D"), self.OnToogleDirTree, self.OnMenuUpdateUI)
        DoBindMenuHandler(ope_menu.AppendCheckItem(ID_Menu_ToogleToolBar, u"显示工具栏(&T)\tCtrl-T"), self.OnToogleToolBar, self.OnMenuUpdateUI)
        ope_menu.AppendSeparator()
        ope_menu.Append(ID_Menu_Search, u"查找(&I)")

        help_menu = wx.Menu()
        self.Bind(wx.EVT_MENU, self.OnAbout, help_menu.Append(ID_Menu_About, u"关于(&A)..."))

        mb.Append(file_menu, u"文件(&F)")
        mb.Append(ope_menu, u"操作(&O)")
        mb.Append(help_menu, u"帮助(&H)")

        self.SetMenuBar(mb)

    def CreateToolBar(self):
        def DoBind(item, handler, updateUI=None):
            self.Bind(wx.EVT_TOOL, handler, item)
            if updateUI is not None:
                self.Bind(wx.EVT_UPDATE_UI, updateUI, item)

        tb = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize, aui.AUI_TB_DEFAULT_STYLE | aui.AUI_TB_OVERFLOW)
        tb.SetToolBitmapSize(wx.Size(16, 16))

        DoBind(tb.AddToggleTool(wx.ID_CUT, images._rt_cut.GetBitmap(), wx.NullBitmap, False, None, "Cut"), self.ForwardEvent, self.ForwardEvent)
        DoBind(tb.AddToggleTool(wx.ID_COPY, images._rt_copy.GetBitmap(), wx.NullBitmap, False, None, "Copy"), self.ForwardEvent, self.ForwardEvent)
        DoBind(tb.AddToggleTool(wx.ID_PASTE, images._rt_paste.GetBitmap(), wx.NullBitmap, False, None, "Paste"), self.ForwardEvent, self.ForwardEvent)
        tb.AddSeparator()
        DoBind(tb.AddToggleTool(wx.ID_UNDO, images._rt_undo.GetBitmap(), wx.NullBitmap, False, None, "Undo"), self.ForwardEvent, self.ForwardEvent)
        DoBind(tb.AddToggleTool(wx.ID_REDO, images._rt_redo.GetBitmap(), wx.NullBitmap, False, None, "Redo"), self.ForwardEvent, self.ForwardEvent)
        tb.AddSeparator()

        DoBind(tb.AddToggleTool(ID_ToolBar_Bold, images._rt_bold.GetBitmap(), wx.NullBitmap, True, None, "Bold"), self.OnBold, self.OnToolBarUpdateUI)
        DoBind(tb.AddToggleTool(ID_ToolBar_Italic, images._rt_italic.GetBitmap(), wx.NullBitmap, True, None, "Italic"), self.OnItalics, self.OnToolBarUpdateUI)
        DoBind(tb.AddToggleTool(ID_ToolBar_Underline, images._rt_underline.GetBitmap(), wx.NullBitmap, True, None, "Underline"), self.OnUnderline, self.OnToolBarUpdateUI)
        tb.AddSeparator()
        DoBind(tb.AddToggleTool(ID_ToolBar_AlignLeft, images._rt_alignleft.GetBitmap(), wx.NullBitmap, True, None, "Align left"), self.OnAlignLeft, self.OnToolBarUpdateUI)
        DoBind(tb.AddToggleTool(ID_ToolBar_Center, images._rt_centre.GetBitmap(), wx.NullBitmap, True, None, "Center"), self.OnAlignCenter, self.OnToolBarUpdateUI)
        DoBind(tb.AddToggleTool(ID_ToolBar_AlignRight, images._rt_alignright.GetBitmap(), wx.NullBitmap, True, None, "Align right"), self.OnAlignRight, self.OnToolBarUpdateUI)
        tb.AddSeparator()
        DoBind(tb.AddToggleTool(ID_ToolBar_IndentLess, images._rt_indentless.GetBitmap(), wx.NullBitmap, False, None, "Indent Less"), self.OnIndentLess, self.OnToolBarUpdateUI)
        DoBind(tb.AddToggleTool(ID_ToolBar_IndentMore, images._rt_indentmore.GetBitmap(), wx.NullBitmap, False, None, "Indent More"), self.OnIndentMore, self.OnToolBarUpdateUI)

        tb.AddSeparator()

        DoBind(tb.AddToggleTool(ID_ToolBar_Font, images._rt_font.GetBitmap(), wx.NullBitmap, False, None, "Font"), self.OnFont, self.OnToolBarUpdateUI)
        DoBind(tb.AddToggleTool(ID_ToolBar_FontColor, images._rt_colour.GetBitmap(), wx.NullBitmap, False, None, "Font Color"), self.OnColour, self.OnToolBarUpdateUI)
        tb.Realize()

        self.toolbar_updateui_funcs = {
            ID_ToolBar_Bold: self.OnUpdateBold,
            ID_ToolBar_Italic: self.OnUpdateItalic,
            ID_ToolBar_Underline: self.OnUpdateUnderline,
            ID_ToolBar_AlignLeft: self.OnUpdateAlignLeft,
            ID_ToolBar_Center: self.OnUpdateAlignCenter,
            ID_ToolBar_AlignRight: self.OnUpdateAlignRight,
            ID_ToolBar_IndentLess: None,
            ID_ToolBar_IndentMore: None,
            ID_ToolBar_Font: None,
            ID_ToolBar_FontColor: None,
        }

        return tb

    def BuildPanes(self):
        # min size for the frame itself isn't completely done.
        # see the end up AuiManager.Update() for the test
        # code. For now, just hard code a frame minimum size
        self.SetMinSize(wx.Size(400, 300))

        self._mgr.AddPane(self.CreateTreeCtrl(), aui.AuiPaneInfo().Name("VsFrame_Dir_Tree").Caption(u"目录树").
                          Left().Layer(1).Position(1).CloseButton(True).MaximizeButton(False).
                          MinimizeButton(False))

        self._mgr.AddPane(self.CreateNotebook(), aui.AuiPaneInfo().Name("VsFrame_Notebook").
                          CenterPane().PaneBorder(False))

        self._mgr.AddPane(self.CreateToolBar(), aui.AuiPaneInfo().Name("VsFrame_Html_Edit_Toolbar").Caption("Toobar").ToolbarPane().Top())

        # make some default perspectives
        #
        perspective_all = self._mgr.SavePerspective()

        all_panes = self._mgr.GetAllPanes()
        for pane in all_panes:
            if not pane.IsToolbar():
                pane.Hide()

        self._mgr.GetPane("VsFrame_Dir_Tree").Show().Left().Layer(0).Row(0).Position(0)
        self._mgr.GetPane("VsFrame_Notebook").Show()
        perspective_default = self._mgr.SavePerspective()

        self._nb_perspectives = []
        auibook = self._mgr.GetPane("VsFrame_Notebook").window
        nb_perspective_default = auibook.SavePerspective()
        self._nb_perspectives.append(nb_perspective_default)

        self._mgr.LoadPerspective(perspective_default)

        # "commit" all changes made to AuiManager
        self._mgr.Update()

    def IsModified(self, index):
        """检查指定编辑控件是否已经有修改而未保存"""
        assert fall_into(index, 0, len(self.editor_list))
        return self.editor_list[index][2]

    def SetModified(self, index, modified=True):
        """标记为已经修改"""
        self.editor_list[index][2] = modified

    def GetToolBarPanelInfo(self):
        return self._mgr.GetPane("VsFrame_Html_Edit_Toolbar")

    def GetNotebook(self):
        notebook = self._mgr.GetPane("VsFrame_Notebook").window
        assert notebook is not None
        return notebook

    def GetDirTreePanelInfo(self):
        return self._mgr.GetPane("VsFrame_Dir_Tree")

    def GetDirTree(self):
        tree = self.GetDirTreePanelInfo().window
        assert tree is not None
        return tree

    def GetDirTreeImageIndexByType(self, t):
        if t == VsData_Type_Root:
            return 0
        elif t == VsData_Type_Dir:
            return 0
        elif t == VsData_Type_Html:
            return 1
        else:
            assert False

    def GetView(self, index=None):
        parent = self.GetNotebook()
        if index is None:
            index = parent.GetSelection()
        if index < 0:
            return parent, None, None
        assert fall_into(index, 0, len(self.editor_list))
        return parent, index, self.editor_list[index][1]

    def GetCurrentView(self):
        """获取当前窗口视图"""
        return self.GetView()

    def UpdateViewTitle(self, index=None):
        parent, index, ctrl = self.GetView(index)

        id = self.editor_list[index][0]
        str = self.db.GetTitle(id)
        if self.IsModified(index):
            str = "* " + str
        parent.SetPageText(index, str)

    def SaveDirTree(self, tree):
        self.save_dir_tree = []
        tree.Traverse(lambda node, path: \
            self.save_dir_tree.append((tree.GetItemPyData(node), path)),
            tree.GetRootItem())
        self.db.SetRoot(self.save_dir_tree)

    def OnSave(self, event):
        parent, index, ctrl = self.GetCurrentView()

        if index is None:
            return

        # 如果没有改动，则直接返回
        if not self.IsModified(index):
            return

        # 恢复标题
        self.SetModified(index, False)
        id = self.editor_list[index][0]
        self.UpdateViewTitle()

        # 保存内容
        s = StringIO.StringIO()
        handler = wx.richtext.RichTextXMLHandler()
        handler.SaveStream(ctrl.GetBuffer(), s)
        self.db.SetBody(id, s.getvalue())

    def OnSaveAs(self, event):
        parent, index, ctrl = self.GetCurrentView()
        assert ctrl is not None

        # 默认的文件名
        default_title = parent.GetPageText(index)

        # Display a File Save Dialog for RTF files
        dlg = wx.FileDialog(self, "Choose a filename",
                            wildcard=u'Rich Text Format files (*.rtf)|*.rtf',
                            defaultFile=default_title,
                            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() != wx.ID_OK:
            return

        # assign it to path
        path = dlg.GetPath()
        dlg.Destroy()

        # Use the custom RTF Handler to save the file
        handler = PyRTFParser.PyRichTextRTFHandler()
        handler.SaveFile(ctrl.GetBuffer(), path)

    def OnToogleDirTree(self, event):
        panel = self.GetDirTreePanelInfo()
        panel.Show(not panel.IsShown())
        self._mgr.Update()

    def OnToogleToolBar(self, event):
        panel = self.GetToolBarPanelInfo()
        panel.Show(not panel.IsShown())
        self._mgr.Update()

    def OnMenuUpdateUI(self, event):
        evId = event.GetId()
        if evId == ID_Menu_ToogleDirectory:
            event.Check(self.GetDirTreePanelInfo().IsShown())
        elif evId == ID_Menu_ToogleToolBar:
            event.Check(self.GetToolBarPanelInfo().IsShown())
        elif evId == ID_Menu_SaveAs or evId == ID_Menu_Save:
            parent, index, ctrl = self.GetCurrentView()
            exist = ctrl is not None
            event.Enable(exist)
            if evId == ID_Menu_Save and exist:
                event.Enable(self.IsModified(index))
        elif evId == ID_Menu_CreateHtml or evId == ID_Menu_CreateDir:
            # 目录树隐藏时，禁用菜单里的新建功能
            event.Enable(self.GetDirTreePanelInfo().IsShown())

    def OnRichtextContentChanged(self, event):
        parent, index, ctrl = self.GetCurrentView()
        assert index is not None
        assert event.GetEventObject() is ctrl

        if not self.IsModified(index):
            self.SetModified(index, True)
            self.UpdateViewTitle()

    def OnTreeItemActivated(self, event):
        id = self.tree.GetItemPyData(event.GetItem())
        parent = self.GetNotebook()

        # 如果内容不可编辑，则直接返回
        if not self.db.IsEditable(id):
            return

        # 如果已经打开，则将其选中，并返回
        for i in range(len(self.editor_list)):
            if id == self.editor_list[i][0]:
                parent.SetSelection(i)
                return

        # 创建新的编辑页
        ctrl = wx.richtext.RichTextCtrl(parent, style=wx.VSCROLL | wx.HSCROLL | wx.NO_BORDER)
        ctrl.Bind(wx.richtext.EVT_RICHTEXT_CONTENT_INSERTED, self.OnRichtextContentChanged)
        ctrl.Bind(wx.richtext.EVT_RICHTEXT_CONTENT_DELETED, self.OnRichtextContentChanged)
        ctrl.Bind(wx.richtext.EVT_RICHTEXT_STYLE_CHANGED, self.OnRichtextContentChanged)

        # 设置默认字体
        ctrl.SetFont(GetDefaultFont())

        # 解析正文内容
        body = self.db.GetBody(id)
        if len(body) != 0:
            tmpfile = VsTempFile()
            tmpfile.AppendString(body)

            ctrl.Freeze()
            ctrl.BeginSuppressUndo()
            handler = wx.richtext.RichTextXMLHandler()
            # Load the XML file via the XML Handler.
            # Note that for XML, the BUFFER is passed.
            handler.LoadFile(ctrl.GetBuffer(), tmpfile.filename)
            # Signal the end of changing the control
            ctrl.EndSuppressUndo()
            ctrl.Thaw()

        # 更新到内存记录里去
        self.editor_list.append([id, ctrl, False])
        parent.AddPage(ctrl, self.db.GetTitle(id), select = True)

    def OnTreeEndLabelEdit_After(self, item, old_text):
        """更新 title，如果已经打开，则同步更新"""
        item_text = self.tree.GetItemText(item)
        s = item_text.strip()

        # 更新目录树里的显示
        if s != item_text:
            self.tree.SetItemText(item, s)

        # 如果没有变化，则直接返回
        if old_text == s:
            return

        # 更新数据
        id = self.tree.GetItemPyData(item)
        self.db.SetTitle(id, s)

        # 更新打开文件标题
        for i in range(len(self.editor_list)):
            if id == self.editor_list[i][0]:
                self.UpdateViewTitle(i)
                break

    def OnTreeEndLabelEdit(self, event):
        item = event.GetItem()
        wx.CallAfter(self.OnTreeEndLabelEdit_After, item, self.tree.GetItemText(item))

    def OnTreeBeginDrag(self, event):
        tree = event.GetEventObject()
        self.drag_source = event.GetItem()
        if self.drag_source != tree.GetRootItem():
            event.Allow()
        else:
            event.Veto()

    def OnTreeEndDrag(self, event):
        drop_target = event.GetItem()
        if not drop_target.IsOk():
            return
        tree = event.GetEventObject()
        source_id = tree.GetItemPyData(self.drag_source)

        # 不允许目标项是源项的子项
        if tree.ItemIsChildOf(drop_target, self.drag_source):
            tree.Unselect()
            return

        # One of the following methods of inserting will be called...
        def MoveNodes(parent, target):
            # 删除源项及子项
            tree.Delete(self.drag_source)

            # 将源项添加到目标位置
            imgidx = self.GetDirTreeImageIndexByType(self.db.GetType(source_id))
            title = self.db.GetTitle(source_id)
            if target is not None:
                new_item = tree.InsertItem(parent, target, title, imgidx)
            else:
                new_item = tree.InsertItemBefore(parent, 0, title, imgidx)
            tree.SetItemPyData(new_item, source_id)

            # 添加子项
            dummy, t = self.db.GetTree(self.db.GetRoot(), source_id)
            self.Tree_AddNode(t, new_item)

            # 设置树结点属性
            tree.ExpandAllChildren(new_item)
            tree.SelectItem(new_item)

            # 保存目录树
            self.SaveDirTree(tree)

        def InsertAsSibling(event):
            MoveNodes(tree.GetItemParent(drop_target), drop_target)

        def InsertAsChild(event):
            MoveNodes(drop_target, None)

        # 如果不是根项，则询问是作为目标项的兄弟项还是子项
        if drop_target == tree.GetRootItem():
            InsertAsChild(None)
        else:
            menu = wx.Menu()
            menu.Append(ID_Ctx_InsertAsSibling, u"与目标项平级", "")
            menu.Append(ID_Ctx_InsertAsChild, u"作为目标项的子项", "")
            menu.UpdateUI()
            menu.Bind(wx.EVT_MENU, InsertAsSibling, id=ID_Ctx_InsertAsSibling)
            menu.Bind(wx.EVT_MENU, InsertAsChild, id=ID_Ctx_InsertAsChild)
            self.PopupMenu(menu)

    def OnBold(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            ctrl.ApplyBoldToSelection()

    def OnItalics(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            ctrl.ApplyItalicToSelection()

    def OnAlignLeft(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            ctrl.ApplyAlignmentToSelection(wx.richtext.TEXT_ALIGNMENT_LEFT)

    def OnAlignCenter(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            ctrl.ApplyAlignmentToSelection(wx.richtext.TEXT_ALIGNMENT_CENTRE)

    def OnAlignRight(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            ctrl.ApplyAlignmentToSelection(wx.richtext.TEXT_ALIGNMENT_RIGHT)

    def OnIndentLess(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is None:
            return

        attr = wx.richtext.TextAttrEx()
        attr.SetFlags(wx.richtext.TEXT_ATTR_LEFT_INDENT)
        ip = ctrl.GetInsertionPoint()
        if ctrl.GetStyle(ip, attr):
            r = wx.richtext.RichTextRange(ip, ip)
            if ctrl.HasSelection():
                r = ctrl.GetSelectionRange()

        if attr.GetLeftIndent() >= 100:
            attr.SetLeftIndent(attr.GetLeftIndent() - 100)
            attr.SetFlags(wx.richtext.TEXT_ATTR_LEFT_INDENT)
            ctrl.SetStyle(r, attr)

    def OnIndentMore(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is None:
            return

        attr = wx.richtext.TextAttrEx()
        attr.SetFlags(wx.richtext.TEXT_ATTR_LEFT_INDENT)
        ip = ctrl.GetInsertionPoint()
        if ctrl.GetStyle(ip, attr):
            r = wx.richtext.RichTextRange(ip, ip)
            if ctrl.HasSelection():
                r = ctrl.GetSelectionRange()

            attr.SetLeftIndent(attr.GetLeftIndent() + 100)
            attr.SetFlags(wx.richtext.TEXT_ATTR_LEFT_INDENT)
            ctrl.SetStyle(r, attr)

    def OnUnderline(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            ctrl.ApplyUnderlineToSelection()

    def OnFont(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is None:
            return

        if not ctrl.HasSelection():
            return

        r = ctrl.GetSelectionRange()
        fontData = wx.FontData()
        fontData.EnableEffects(False)
        attr = wx.richtext.TextAttrEx()
        attr.SetFlags(wx.richtext.TEXT_ATTR_FONT)
        if ctrl.GetStyle(ctrl.GetInsertionPoint(), attr):
            fontData.SetInitialFont(attr.GetFont())

        dlg = wx.FontDialog(ctrl, fontData)
        if dlg.ShowModal() == wx.ID_OK:
            fontData = dlg.GetFontData()
            font = fontData.GetChosenFont()
            if font:
                attr.SetFlags(wx.richtext.TEXT_ATTR_FONT)
                attr.SetFont(font)
                ctrl.SetStyle(r, attr)
        dlg.Destroy()

    def OnColour(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is None:
            return

        if not ctrl.HasSelection():
            return

        colourData = wx.ColourData()
        attr = wx.richtext.TextAttrEx()
        attr.SetFlags(wx.richtext.TEXT_ATTR_TEXT_COLOUR)
        if ctrl.GetStyle(ctrl.GetInsertionPoint(), attr):
            colourData.SetColour(attr.GetTextColour())

        dlg = wx.ColourDialog(self, colourData)
        if dlg.ShowModal() == wx.ID_OK:
            colourData = dlg.GetColourData()
            colour = colourData.GetColour()
            if colour:
                if not ctrl.HasSelection():
                    ctrl.BeginTextColour(colour)
                else:
                    r = ctrl.GetSelectionRange()
                    attr.SetFlags(wx.richtext.TEXT_ATTR_TEXT_COLOUR)
                    attr.SetTextColour(colour)
                    ctrl.SetStyle(r, attr)
        dlg.Destroy()

    def ForwardEvent(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            event.Enable(True)
            ctrl.ProcessEvent(event)
        else:
            event.Enable(False)

    def OnToolBarUpdateUI(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            event.Enable(True)
            id = event.GetId()
            if self.toolbar_updateui_funcs.has_key(id):
                f = self.toolbar_updateui_funcs[id]
                if f is not None:
                    f(event)
        else:
            event.Enable(False)

    def OnUpdateBold(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            event.Check(ctrl.IsSelectionBold())

    def OnUpdateItalic(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            event.Check(ctrl.IsSelectionItalics())

    def OnUpdateUnderline(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            event.Check(ctrl.IsSelectionUnderlined())

    def OnUpdateAlignLeft(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            event.Check(ctrl.IsSelectionAligned(wx.richtext.TEXT_ALIGNMENT_LEFT))

    def OnUpdateAlignCenter(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            event.Check(ctrl.IsSelectionAligned(wx.richtext.TEXT_ALIGNMENT_CENTRE))

    def OnUpdateAlignRight(self, event):
        parent, index, ctrl = self.GetCurrentView()
        if ctrl is not None:
            event.Check(ctrl.IsSelectionAligned(wx.richtext.TEXT_ALIGNMENT_RIGHT))

    def OnRightDown(self, event):
        tree = self.GetDirTree()
        pt = event.GetPosition()
        item, flags = tree.HitTest(pt)
        if item:
            tree.SelectItem(item)

    def OnRightUp(self, event):
        tree = self.GetDirTree()
        menu = wx.Menu()
        self.Bind(wx.EVT_MENU, self.OnCreateHtml, menu.Append(ID_Menu_CreateHtml, u"新建笔记"))
        self.Bind(wx.EVT_MENU, self.OnCreateDir, menu.Append(ID_Menu_CreateDir, u"新建目录"))
        menu.AppendSeparator()
        self.Bind(wx.EVT_MENU, self.OnRenameEntry, menu.Append(ID_Menu_RenameEntry, u"重命名"))
        self.Bind(wx.EVT_MENU, self.OnDeleteEntry, menu.Append(ID_Menu_DeleteEntry, u"删除"))

        # 如果当前选择了根结点，则禁用 ID_Menu_DeleteEntry
        # 如果有子结点，也禁用
        #
        cursel = tree.GetSelection()
        if cursel == tree.GetRootItem():
            menu.Enable(ID_Menu_DeleteEntry, False)
        if tree.ItemHasChildren(cursel):
            menu.Enable(ID_Menu_DeleteEntry, False)

        self.PopupMenu(menu)
        menu.Destroy()

        event.Skip()

    def OnCreateEntry(self, event, type):
        tree = self.GetDirTree()
        parent_item = tree.GetSelection()
        parent_id = tree.GetItemPyData(parent_item)
        name = "new item"
        if VsData_Type_Dir == type:
            image_index = 0
        else:
            image_index = 1
        child_id = self.db.Add(name, "", parent_id, type)
        child_item = tree.AppendItem(parent_item, name, image_index)
        tree.SetItemPyData(child_item, child_id)
        tree.SelectItem(child_item)
        tree.EditLabel(child_item)

    def OnCreateHtml(self, event):
        self.OnCreateEntry(event, VsData_Type_Html)

    def OnCreateDir(self, event):
        self.OnCreateEntry(event, VsData_Type_Dir)

    def OnRenameEntry(self, event):
        tree = self.GetDirTree()
        item = tree.GetSelection()
        tree.EditLabel(item)

    def OnDeleteEntry(self, event):
        """删除一个结点"""
        tree = self.GetDirTree()
        item = tree.GetSelection()
        id = tree.GetItemPyData(item)

        # 确认删除
        dlg = wx.MessageDialog(self, u'确实要删除吗？', u'确认删除',
                                wx.YES_NO | wx.ICON_QUESTION)
        ret = dlg.ShowModal()
        dlg.Destroy()
        if wx.ID_YES != ret:
            return

        # 从数据库里删除
        self.db.Delete(id)

        # 如果已经打开，则关闭
        for i in range(len(self.editor_list)):
            if id == self.editor_list[i][0]:
                self.GetNotebook().DeletePage(i)
                break

        # 从目录树里删除
        tree.Delete(item)

    def UserQuitConfirm(self):
        dlg = wx.MessageDialog(self, u'内容已经修改但没有保存，确认要继续吗？',
                               u'确认关闭', wx.YES_NO | wx.ICON_QUESTION)
        ret = dlg.ShowModal()
        dlg.Destroy()
        return ret

    def OnNotebookPageClose(self, event):
        index = event.GetSelection()
        assert fall_into(index, 0, len(self.editor_list))

        # 提示当前内容已经修改但还没有保存
        if self.IsModified(index):
            if wx.ID_YES != self.UserQuitConfirm():
                event.Veto()
                return

        # 确认关闭，清除相应数据结构
        del self.editor_list[index]

    def OnExit(self, event):
        self.Close(False)

    def OnCloseWindow(self, event):

        # 查看是否有已经修复但还没有保存的内容
        modified = False
        for i in range(len(self.editor_list)):
            if self.IsModified(i):
                modified = True
                break

        # 用户确认
        if modified:
            if wx.ID_YES != self.UserQuitConfirm():
                event.Veto()
                return

        # 退出
        self.Destroy()

    def OnAbout(self, event):
        info = wx.AboutDialogInfo()
        info.Name = program_name
        info.Version = program_version
        info.Copyright = "(C) 2010 sherking@gmail.com"
        info.Description = wx.lib.wordwrap.wordwrap(
            program_name + " is a simple richtext notepad.\n\nTHIS SOFTWARE COMES WITH ABSOLUTELY NO WARRANTY! USE AT YOUR OWN RISK!",
            430, wx.ClientDC(self))
        info.WebSite = ("http://code.google.com/p/gumpad2")
        info.Developers = ["sherking@gmail.com"]
        info.License = wx.lib.wordwrap.wordwrap("The MIT License", 500, wx.ClientDC(self))
        # Then we call wx.AboutBox giving it that info object
        wx.AboutBox(info)

    def Tree_AddNode(self, db_node, node):
        for i in range(len(db_node["subs"])):
            child_id = db_node["subs"][i]["id"]
            imgidx = self.GetDirTreeImageIndexByType(self.db.GetType(child_id))
            n = self.tree.AppendItem(node, self.db.GetTitle(child_id), imgidx)
            self.tree.SetItemPyData(n, child_id)

            self.Tree_AddNode(db_node["subs"][i], n)

    def CreateTreeCtrl(self):

        self.tree = VsTreeCtrl(self, -1, wx.Point(0, 0), wx.Size(200, 250),
                           wx.TR_DEFAULT_STYLE | wx.NO_BORDER | wx.TR_EDIT_LABELS | wx.TR_NO_BUTTONS)

        imglist = wx.ImageList(16, 16, True, 2)
        imglist.Add(wx.ArtProvider.GetBitmap(wx.ART_FOLDER, wx.ART_OTHER, wx.Size(16, 16)))
        imglist.Add(wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, wx.Size(16, 16)))
        self.tree.AssignImageList(imglist)

        db_root = self.db.GetRoot()

        root = self.tree.AddRoot(self.db.GetTitle(), 0)
        self.tree.SetItemPyData(root, db_root["id"])

        self.Tree_AddNode(db_root, root)
        self.tree.ExpandAllChildren(root)
        self.tree.SelectItem(root)

        self.tree.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.tree.Bind(wx.EVT_RIGHT_UP, self.OnRightUp)
        self.tree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.OnTreeItemActivated)
        self.tree.Bind(wx.EVT_TREE_END_LABEL_EDIT, self.OnTreeEndLabelEdit)
        self.tree.Bind(wx.EVT_TREE_BEGIN_DRAG, self.OnTreeBeginDrag)
        self.tree.Bind(wx.EVT_TREE_END_DRAG, self.OnTreeEndDrag)

        return self.tree

    def CreateNotebook(self):
        client_size = self.GetClientSize()
        ctrl = aui.AuiNotebook(self, -1, wx.Point(client_size.x, client_size.y),
                              wx.Size(430, 200), self._notebook_style)

        ctrl.SetArtProvider(aui.AuiDefaultTabArt())
        ctrl.Bind(aui.EVT_AUINOTEBOOK_PAGE_CLOSE, self.OnNotebookPageClose)
        return ctrl


class MyApp(wx.App):

    def __init__(self):
        wx.App.__init__(self, 0)

    def OnInit(self):
        self.frame = VsFrame(None, -1, program_title, size=(800, 600))
        self.frame.CenterOnScreen()
        self.frame.Show()

        self.Bind(wx.EVT_ACTIVATE_APP, self.OnActivate)

        return True

    def OnActivate(self, event):
        if event.GetActive():
            pass


def main():
    global program_dbpath

    # 本地化设置
    locale.setlocale(locale.LC_ALL, '')

    # 命令行参数解析
    usage = program_name + " [-f <file>] [-h] [-v]"
    program_dbpath = os.path.join(os.path.expanduser("~"), program_dbpath)
    parser = optparse.OptionParser(usage)
    parser.add_option("-v", "--version", action="store_true", dest="version", default = False, help = "print the version number of the executable and exit")
    parser.add_option("-f", "--file", action = "store", type = "string", dest = "file", default = program_dbpath, help = "specify the data file")

    options, args = parser.parse_args(sys.argv[1:])

    if options.version:
        print program_title
        return

    if len(args) > 0:
        parser.print_help()
        return

    # 解析用户指定文件是否有效
    program_dbpath = os.path.expanduser(options.file)
    if not os.path.isabs(program_dbpath):
        program_dbpath = os.path.realpath(os.path.join(os.curdir, program_dbpath))

    # 创建多层目录
    dirname = os.path.dirname(program_dbpath)
    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname)
        except:
            print "Error: " + options.file + " is not a valid filename"
            return
    elif not os.path.isdir(dirname):
        print "Error: " + options.file + " is not a valid filename"
        return

    if os.path.exists(program_dbpath):
        # 如果路径存在、且不是文件，则退出
        if not os.path.isfile(program_dbpath):
            print "Error: " + options.file + " is not a valid filename"
            return

        # 如果不是有效的数据库，则退出
        try:
            db = VsData(program_dbpath)
            assert db.GetMagic() == VsData_Format_Magic
            if db.GetVersion() > VsData_Format_Version:
                print "Error: " + options.file + " has version (%d), higher than the executable (%d)" % (db.GetVersion(), VsData_Format_Version)
                return
        except:
            print "Error: " + options.file + " exists but corrupted"
            return

    # 启动程序界面
    app = MyApp()
    app.MainLoop()

if __name__ == '__main__':
    main()
