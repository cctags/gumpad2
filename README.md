## Gumpad2 - a simple richtext notepad ##

[sherking@gmail.com](mailto:sherking@gmail.com)

The latest version of this document can be found at [here](https://github.com/cctags/gumpad2/blob/master/README.md).

### 说明 ###

Gumpad2 是一个简单的富文本笔记工具，支持树形结构，支持 RTF 格式的导出。

### 开发环境 ###

使用的 python 版本

* python 2.6.1
* wxPython 2.8.10.1 unicode

### 使用到的其他模块 ###

这些模块已经添加，不需要额外下载。

* zshelve @ http://code.google.com/p/zshelve/ (by jhuangjiahua)
* PyRTFParser @ http://www.transana.org/developers/PyRTFParser/ (by David Woods)
* XTEA @ http://code.activestate.com/recipes/496737/ (by Paul Chakravarti)

感谢他们的分享。

另外，还参考了 wxPython 里的 AUI、RichTextCtrl 等例子。简单地说，整个工具也就是这些例子的堆砌而已。

### 使用说明 ###

命令行参数

```
Usage: Gumpad2 [-f <file>] [-h] [-v]

Options:
  -h, --help            show this help message and exit
  -v, --version         print the version number of the executable and exit
  -f FILE, --file=FILE  specify the data file
```

其中 -f 参数可以指定所使用的文件，不使用这个选项时，默认使用 ~/gumpad2.db。

```
/* TODO */
```

### 修改记录 ###

* **__v0.1.3:__** (2011-03-16)
    * 实现加密存储的功能


* **__v0.1.2:__** (2010-03-29)
    * 实现图片插入功能
    * 实现字符串查找功能


* **__v0.1.1:__** (2010-03-05)
    * 实现了目录树结构的拖拽调整
    * 实现了以 RTF 格式导出内容
    * 实现了状态栏里显示当前正在使用的文件，以及当前系统时间
    * 实现了命令行参数，即可以在命令行下指定 ~/gumpad2.db 以外的文件
    * 修复若干 BUG


* **__v0.1.0:__** (2010-02-21)
    * Initial directory structure
