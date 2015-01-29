#!/usr/bin/env python
# coding: utf-8

import wx
import wx.html
import wx.grid
import wx.richtext
import wx.lib
import wx.lib.wordwrap

import os
import sys
import uuid
import tempfile
import optparse

import zshelve

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

import random
import images

program_name = "gumpad2"
program_version = "v0.1.0"

program_title = "%s %s" % (program_name, program_version)

program_dbpath = "%s.db" % (program_name)

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

    # 从 parent 往下查找指定 id 的结点，返回 父结点、结点
    # 不存在时返回 None
    #
    def GetTree(self, parent, id = None):
        if id is None:
            return None, parent
        else:
            return self.__GetTree__(parent, id)

    def GetRoot(self):
        return self.db["tree"]

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

    # 删除指定Id的叶子结点，根结点除外
    # 成功时返回 True，失败时返回 False
    #
    def Delete(self, id):
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
        if self.db.has_key(id):
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

############################################################################
#
# Menu Id
#

ID_Menu_CreateHtml      = wx.ID_HIGHEST + 0x01
ID_Menu_CreateDir       = wx.ID_HIGHEST + 0x02
ID_Menu_RenameEntry     = wx.ID_HIGHEST + 0x03
ID_Menu_DeleteEntry     = wx.ID_HIGHEST + 0x04
ID_Menu_Save            = wx.ID_HIGHEST + 0x05
ID_Menu_ExportAsHtml    = wx.ID_HIGHEST + 0x06
ID_Menu_ExportAsTxt     = wx.ID_HIGHEST + 0x07
ID_Menu_Exit            = wx.ID_HIGHEST + 0x08

ID_Menu_ToogleDirectory = wx.ID_HIGHEST + 0x10
ID_Menu_Search          = wx.ID_HIGHEST + 0x11

ID_Menu_About           = wx.ID_HIGHEST + 0x20

############################################################################
#
# VsFrame
#

class VsFrame(wx.Frame):

    def __init__(self, parent, id=wx.ID_ANY, title="", pos= wx.DefaultPosition,
                 size=wx.DefaultSize, style=wx.DEFAULT_FRAME_STYLE|wx.SUNKEN_BORDER):
        wx.Frame.__init__(self, parent, id, title, pos, size, style)

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

        self.CreateStatusBar()
        self.GetStatusBar().SetStatusText(self.db.GetFileName())

        self.CreateMenuBar()
        self.BuildPanes()

    # 创建菜单
    #
    def CreateMenuBar(self):

        mb = wx.MenuBar()

        file_menu = wx.Menu()
        self.Bind(wx.EVT_MENU, self.OnCreateHtml, file_menu.Append(ID_Menu_CreateHtml, "新建笔记"))
        self.Bind(wx.EVT_MENU, self.OnCreateDir, file_menu.Append(ID_Menu_CreateDir, "新建目录"))
        file_menu.AppendSeparator()
        self.Bind(wx.EVT_MENU, self.OnRenameEntry, file_menu.Append(ID_Menu_RenameEntry, "重命名"))
        self.Bind(wx.EVT_MENU, self.OnDeleteEntry, file_menu.Append(ID_Menu_RenameEntry, "删除"))
        file_menu.AppendSeparator()
        self.Bind(wx.EVT_MENU, self.OnSave, file_menu.Append(ID_Menu_Save, "保存"))
        self.Bind(wx.EVT_MENU, self.OnExportAsHtml, file_menu.Append(ID_Menu_ExportAsHtml, "另存为HTML"))
        self.Bind(wx.EVT_MENU, self.OnExportAsTxt, file_menu.Append(ID_Menu_ExportAsTxt, "另存为文本"))
        file_menu.AppendSeparator()
        self.Bind(wx.EVT_MENU, self.OnExit, file_menu.Append(ID_Menu_Exit, "退出(&X)"))

        ope_menu = wx.Menu()
        ope_menu.Append(ID_Menu_ToogleDirectory, "显示目录树(&T)")
        ope_menu.AppendSeparator()
        ope_menu.Append(ID_Menu_Search, "查找(&I)")

        help_menu = wx.Menu()
        self.Bind(wx.EVT_MENU, self.OnAbout, help_menu.Append(ID_Menu_About, "关于(&A)..."))

        mb.Append(file_menu, "文件(&F)")
        mb.Append(ope_menu, "操作(&O)")
        mb.Append(help_menu, "帮助(&H)")

        self.SetMenuBar(mb)

    def BuildPanes(self):

        # min size for the frame itself isn't completely done.
        # see the end up AuiManager.Update() for the test
        # code. For now, just hard code a frame minimum size
        self.SetMinSize(wx.Size(400, 300))

        def DoBind(item, handler, updateUI = None):
            self.Bind(wx.EVT_TOOL, handler, item)
            if updateUI is not None:
                self.Bind(wx.EVT_UPDATE_UI, updateUI, item)

        tb = aui.AuiToolBar(self, -1, wx.DefaultPosition, wx.DefaultSize, aui.AUI_TB_DEFAULT_STYLE | aui.AUI_TB_OVERFLOW)
        tb.SetToolBitmapSize(wx.Size(16, 16))
#        doBind( tb.AddSimpleTool(-1, "Open", images._rt_open.GetBitmap()), None)
#        doBind( tb.AddSimpleTool(-1, "Save", images._rt_save.GetBitmap()), None)
#        tb.AddSeparator()
        DoBind(tb.AddToggleTool(wx.ID_CUT, images._rt_cut.GetBitmap(), wx.NullBitmap, False, None, "Cut"), self.ForwardEvent, self.ForwardEvent)
        DoBind(tb.AddToggleTool(wx.ID_COPY, images._rt_copy.GetBitmap(), wx.NullBitmap, False, None, "Copy"), self.ForwardEvent, self.ForwardEvent)
        DoBind(tb.AddToggleTool(wx.ID_PASTE, images._rt_paste.GetBitmap(), wx.NullBitmap, False, None, "Paste"), self.ForwardEvent, self.ForwardEvent)
        tb.AddSeparator()
        DoBind(tb.AddToggleTool(wx.ID_UNDO, images._rt_undo.GetBitmap(), wx.NullBitmap, False, None, "Undo"), self.ForwardEvent, self.ForwardEvent)
        DoBind(tb.AddToggleTool(wx.ID_REDO, images._rt_redo.GetBitmap(), wx.NullBitmap, False, None, "Redo"), self.ForwardEvent, self.ForwardEvent)
        tb.AddSeparator()

        DoBind(tb.AddToggleTool(-1, images._rt_bold.GetBitmap(), wx.NullBitmap, True, None, "Bold"), self.OnBold, self.OnUpdateBold)
        DoBind(tb.AddToggleTool(-1, images._rt_italic.GetBitmap(), wx.NullBitmap, True, None, "Italic"), self.OnItalics, self.OnUpdateItalic)
        DoBind(tb.AddToggleTool(-1, images._rt_underline.GetBitmap(), wx.NullBitmap, True, None, "Underline"), self.OnUnderline, self.OnUpdateUnderline)
        tb.AddSeparator()
        DoBind(tb.AddToggleTool(-1, images._rt_alignleft.GetBitmap(), wx.NullBitmap, True, None, "Align left"), self.OnAlignLeft, self.OnUpdateAlignLeft)
        DoBind(tb.AddToggleTool(-1, images._rt_centre.GetBitmap(), wx.NullBitmap, True, None, "Center"), self.OnAlignCenter, self.OnUpdateAlignCenter)
        DoBind(tb.AddToggleTool(-1, images._rt_alignright.GetBitmap(), wx.NullBitmap, True, None, "Align right"), self.OnAlignRight, self.OnUpdateAlignRight)
        tb.AddSeparator()
        DoBind(tb.AddToggleTool(-1, images._rt_indentless.GetBitmap(), wx.NullBitmap, False, None, "Indent Less"), self.OnIndentLess)
        DoBind(tb.AddToggleTool(-1, images._rt_indentmore.GetBitmap(), wx.NullBitmap, False, None, "Indent More"), self.OnIndentMore)

        tb.AddSeparator()

        DoBind(tb.AddToggleTool(-1, images._rt_font.GetBitmap(), wx.NullBitmap, False, None, "Font"), self.OnFont)
        DoBind(tb.AddToggleTool(-1, images._rt_colour.GetBitmap(), wx.NullBitmap, False, None, "Font Color"), self.OnColour)
        tb.Realize()

        self._mgr.AddPane(self.CreateTreeCtrl(), aui.AuiPaneInfo().Name("VsFrame_Dir_Tree").Caption("目录树").
                          Left().Layer(1).Position(1).CloseButton(True).MaximizeButton(True).
                          MinimizeButton(True).MinimizeButton(True))

        self._mgr.AddPane(self.CreateNotebook(), aui.AuiPaneInfo().Name("VsFrame_Notebook").
                          CenterPane().PaneBorder(False))

        self._mgr.AddPane(tb, aui.AuiPaneInfo().Name("VsFrame_Html_Edit_Toolbar").Caption("Toobar").ToolbarPane().Top())

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

    def OnSave(self, event):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        import StringIO
        s = StringIO.StringIO()
        handler = wx.richtext.RichTextXMLHandler()
        handler.SaveStream(self.editor_list[index][1].GetBuffer(), s)
        self.db.SetBody(self.editor_list[index][0], s.getvalue())

    def OnExportAsHtml(self, event):
        pass

    def OnExportAsTxt(self, event):
        pass

    def OnTreeItemActivated(self, event):
        id = self.tree.GetItemPyData(event.GetItem())
        parent = self._mgr.GetPane("VsFrame_Notebook").window

        # 如果已经打开，则将其选中，并返回
        for i in range(len(self.editor_list)):
            if id == self.editor_list[i][0]:
                parent.SetSelection(i)
                return

        # 创建新的编辑页
        ctrl = wx.richtext.RichTextCtrl(parent, style=wx.VSCROLL | wx.HSCROLL | wx.NO_BORDER)

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
        self.editor_list.append([id, ctrl])
        parent.AddPage(ctrl, self.db.GetTitle(id), select = True)

    # 更新 title，如果已经打开，则同步更新
    #
    def OnTreeEndLabelEdit_After(self, item, old_text):
        str = self.tree.GetItemText(item)
        str = str.strip()
        if old_text == str:
            return

        # 更新目录树里的显示
        self.tree.SetItemText(item, str.strip())

        # 更新数据
        id = self.tree.GetItemPyData(item)
        self.db.SetTitle(id, str)

        # 更新打开文件标题
        for i in range(len(self.editor_list)):
            if id == self.editor_list[i][0]:
                self._mgr.GetPane("VsFrame_Notebook").window.SetPageText(i, str)
                break

    def OnTreeEndLabelEdit(self, event):
        item = event.GetItem()
        wx.CallAfter(self.OnTreeEndLabelEdit_After, item, self.tree.GetItemText(item))


    def OnBold(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]

        ctrl.ApplyBoldToSelection()

    def OnItalics(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]

        ctrl.ApplyItalicToSelection()

    def OnAlignLeft(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))
        ctrl = self.editor_list[index][1]
        ctrl.ApplyAlignmentToSelection(wx.richtext.TEXT_ALIGNMENT_LEFT)

    def OnAlignCenter(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))
        ctrl = self.editor_list[index][1]
        ctrl.ApplyAlignmentToSelection(wx.richtext.TEXT_ALIGNMENT_CENTRE)

    def OnAlignRight(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))
        ctrl = self.editor_list[index][1]
        ctrl.ApplyAlignmentToSelection(wx.richtext.TEXT_ALIGNMENT_RIGHT)

    def OnIndentLess(self,evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))
        ctrl = self.editor_list[index][1]

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

    def OnIndentMore(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))
        ctrl = self.editor_list[index][1]

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

    def OnUnderline(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]

        ctrl.ApplyUnderlineToSelection()

    def OnFont(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]

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

    def OnColour(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]

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

    def ForwardEvent(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]
        ctrl.ProcessEvent(evt)

    def OnUpdateBold(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]
        evt.Check(ctrl.IsSelectionBold())

    def OnUpdateItalic(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]
        evt.Check(ctrl.IsSelectionItalics())

    def OnUpdateUnderline(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]
        evt.Check(ctrl.IsSelectionUnderlined())

    def OnUpdateAlignLeft(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]
        evt.Check(ctrl.IsSelectionAligned(wx.richtext.TEXT_ALIGNMENT_LEFT))

    def OnUpdateAlignCenter(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]
        evt.Check(ctrl.IsSelectionAligned(wx.richtext.TEXT_ALIGNMENT_CENTRE))

    def OnUpdateAlignRight(self, evt):
        parent = self._mgr.GetPane("VsFrame_Notebook").window
        index = parent.GetSelection()
        if index < 0:
            return
        assert fall_into(index, 0, len(self.editor_list))

        ctrl = self.editor_list[index][1]
        evt.Check(ctrl.IsSelectionAligned(wx.richtext.TEXT_ALIGNMENT_RIGHT))

    def OnRightDown(self, evt):
        tree = self._mgr.GetPane("VsFrame_Dir_Tree").window
        pt = evt.GetPosition()
        item, flags = tree.HitTest(pt)
        if item:
            tree.SelectItem(item)

    def OnRightUp(self, evt):
        tree = self._mgr.GetPane("VsFrame_Dir_Tree").window
        menu = wx.Menu()
        self.Bind(wx.EVT_MENU, self.OnCreateHtml, menu.Append(ID_Menu_CreateHtml, "新建笔记"))
        self.Bind(wx.EVT_MENU, self.OnCreateDir, menu.Append(ID_Menu_CreateDir, "新建目录"))
        menu.AppendSeparator()
        self.Bind(wx.EVT_MENU, self.OnRenameEntry, menu.Append(ID_Menu_RenameEntry, "重命名"))
        self.Bind(wx.EVT_MENU, self.OnDeleteEntry, menu.Append(ID_Menu_DeleteEntry, "删除"))

        # 如果当前选择了根结点，则禁用 ID_Menu_DeleteEntry
        # 如果有子结点，也禁用
        #
        cursel = tree.GetSelection()
        if cursel == tree.GetRootItem():
            menu.Enable(ID_Menu_DeleteEntry, False)
        if tree.GetChildrenCount(cursel) > 0:
           menu.Enable(ID_Menu_DeleteEntry, False)

        self.PopupMenu(menu)
        menu.Destroy()

        evt.Skip()

    def OnCreateHtml(self, evt):
        tree = self._mgr.GetPane("VsFrame_Dir_Tree").window
        parent_item = tree.GetSelection()
        parent_id = tree.GetItemPyData(parent_item)
        child_id = self.db.Add("new item", "", parent_id, VsData_Type_Html)
        child_item = tree.AppendItem(parent_item, "new item", 1)
        tree.SetItemPyData(child_item, child_id)
        tree.SelectItem(child_item)
        tree.EditLabel(child_item)

    def OnCreateDir(self, evt):
        tree = self._mgr.GetPane("VsFrame_Dir_Tree").window
        parent_item = tree.GetSelection()
        parent_id = tree.GetItemPyData(parent_item)
        child_id = self.db.Add("new item", "", parent_id, VsData_Type_Dir)
        child_item = tree.AppendItem(parent_item, "new item", 0)
        tree.SetItemPyData(child_item, child_id)
        tree.SelectItem(child_item)
        tree.EditLabel(child_item)

    def OnRenameEntry(self, evt):
        tree = self._mgr.GetPane("VsFrame_Dir_Tree").window
        item = tree.GetSelection()
        tree.EditLabel(item)

    # 删除一个结点
    #
    def OnDeleteEntry(self, evt):
        tree = self._mgr.GetPane("VsFrame_Dir_Tree").window
        item = tree.GetSelection()
        id = tree.GetItemPyData(item)

        # 确认删除
        dlg = wx.MessageDialog(self, '确实要删除吗？', '确认删除', wx.YES_NO | wx.ICON_QUESTION)
        ret = dlg.ShowModal()
        dlg.Destroy()
        if wx.ID_YES != ret:
            return

        # 从数据库里删除
        self.db.Delete(id)

        # 如果已经打开，则关闭
        for i in range(len(self.editor_list)):
            if id == self.editor_list[i][0]:
                self._mgr.GetPane("VsFrame_Notebook").window.DeletePage(i)
                break

        # 从目录树里删除
        tree.Delete(item)

    def OnNotebookPageClose(self, event):
        index = event.GetSelection()
        assert fall_into(index, 0, len(self.editor_list))
        del self.editor_list[index]

    def OnExit(self, event):
        self.Close(True)

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
            t = self.db.GetType(child_id)
            if VsData_Type_Html == t:
                image_index = 1
            else:
                image_index = 0
            n = self.tree.AppendItem(node, self.db.GetTitle(child_id), image_index)
            self.tree.SetItemPyData(n, child_id)

            self.Tree_AddNode(db_node["subs"][i], n)

    def CreateTreeCtrl(self):

        self.tree = wx.TreeCtrl(self, -1, wx.Point(0, 0), wx.Size(160, 250),
                           wx.TR_DEFAULT_STYLE | wx.NO_BORDER | wx.TR_EDIT_LABELS | wx.TR_NO_BUTTONS )

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
        self.m_frame = VsFrame(None, -1, program_title, size=(800, 600))
        self.m_frame.CenterOnScreen()
        self.m_frame.Show()

        self.Bind(wx.EVT_ACTIVATE_APP, self.OnActivate)

        return True

    def OnActivate(self, event):
        if event.GetActive():
            pass

def main():
    global program_dbpath

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
