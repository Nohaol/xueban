# 小智接入联网查询教程mcp

# 教程

###### 先说效果：

###### 工具根据小智后台虾哥提供的mcp参考文档写的，能够实现联网查询

###### 例如查新闻、热播电视、今天黄金价格等 

###### 大多情况下，直接问小智问题，小智不会启用联网查询。

###### 需要带有“联网查询”的命令，或者查询

### 下载python代码

\[联网查询python代码\.zip\]

下载完解压备用，步骤不多赘述

### 安装python

\[python\-3\.13\.3\-amd64\.exe\]

勾选后点击install now安装

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=OTIwNDFiZTZiNjIzNDM1NzJmNjg0NDEwODdmZGE1NDRfY2MyOWM2YzVmYzNjNjVlMWYyNzhhNzBiNzczYjQwNzBfSUQ6NzUxMTIwNTIxMzE5NDMwNTUzOV8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

安装成功关闭窗口

### 安装依赖

在python文件的解压目录下输入cmd 回车打开终端

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZmVlYmZiYTBmZWE2MzYyNzI0MDExNTYyY2FiOGY3MTRfYWMyZjM4YTEzYzRkMmVkNGU4NDI1YzJiODNjMjBjMjBfSUQ6NzUxMTIxMjk5MDc2MzUxNTkwNl8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

输入命令pip install \-r requirements\.txt 回车

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=YWJmMzA3MjY1NDk4ZDA3MGNhY2Q5NjlhZTQzZWJlZTdfYjQ3ZTBjZmQ2YTNhNjE3NDBkMTViNTMwZDY2ZWQ5MWNfSUQ6NzUxMTIwNzQwODIzMDcxMTMwMF8xNzgwMzgzMDM3OjE3ODA0Njk0MzdfVjM)

没有报错一般就是安装完了，我电脑安装过，安装完成的样子会不太一样

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=OGU2Njg4NTdjMTBhYzYwZWM0MTAyYTI3OGQ1MGVhZTZfYzg4MzUzNGY1NGU1YjE1NGE1NjVmMGVjODBkZTg4YjBfSUQ6NzUxMTIxMDAxMDgyNzg2NjEzMV8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

如果报错 复制错误信息问ai，不多赘述



### 启动程序

双击启动\_main\.py 打开程序主页面

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NmJiNmM5ZTc2YTYwMTJjN2E2ZTYyMTkyNWE1ZDVjMmNfMzk0M2Q3MzgyYjVhZjIxZDMxMDE2MTk0MjRmOTJhYWJfSUQ6NzUxMTIxNDYyMjM0OTYzOTY4NF8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZTUxMmQwOGE3NTUxMTVjNDgwNjdjN2YzYmVkODllMTBfYmQ0OTM5MTA5MjAwZmEwMDUxM2U2ZDRmYzI1Yjg5NDJfSUQ6NzUxMDk0MDAyNjg0MzI1MDY4OV8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

### 填入小智mcp

##### 小智后台打开配置角色，拉到最后，查看mcp地址

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=M2ZkZDc3ZDM4NGU3YzhiNGFjNDcxZDIzMjM5YWU5MGZfYTE3NzA4NTVkYWYzMTc3YTc3ZGQwZDlmYTA1Mzc0NjBfSUQ6NzUxMDk0MDM5MzU2ODE0MTMzMV8xNzgwMzgzMDM3OjE3ODA0Njk0MzdfVjM)

###### 复制mcp地址，填入软件第一行中

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZWFlYTcxZmU0NTE2MmI0YzcwZmIxZTkxMzIxNzU5Y2JfYjY3NDMxNjk4Zjg1ZDk1ZmZlNGY5OTIyYjhkYzIwM2JfSUQ6NzUxMDk0MDkxOTEzNzE0MDc0MF8xNzgwMzgzMDM3OjE3ODA0Njk0MzdfVjM)

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=MjRkMjc3YjM2OWFmODU3ZmM5NzhlNjhkOTgwN2I0MjhfMzBlNjYxZjUyZGJjZDhjYTBjMzMyYmI5N2JhMThlODVfSUQ6NzUxMDk0MTA3MjM3MDEwNjM3Ml8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

### 填入智普密钥

###### 打开智普官网注册

https://www\.bigmodel\.cn/usercenter/proj\-mgmt/apikeys

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NmJmMTljM2E5YzkzNmUzMjZlNTMzNGU3ZWU1N2Q3OWRfMTc1NmE0Y2VlZTI0OWMxMDExNGIyZTdkOWQwMDBjMDJfSUQ6NzUxMDk0MzgwNDA4NjU2NjkxM18xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

###### 侧边栏选择api keys

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=OTZlNzQyZGI2N2IzZWQyY2ZiNjc0YzE4YzU2MjY3NDlfMWMxYjA1ZjUxZTg5ZGY4M2UwODIzYjRmMzM0OTZlYTFfSUQ6NzUxMDk0Mzk0NTU3MzEyMjA1Ml8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

###### 右上角添加一个新的key

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=MThlODljZGQwMDRhYzcxMTI5ZjY3OTk3NmZiYmRmMjFfZDI2NDVkMjY1NzQ5NGU2YTRlMmFiZDg3NjFhYTVkNjhfSUQ6NzUxMDk0NDI4MDkzMzAwNzM2M18xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

###### 复制key到工具第二行中

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=YjFhNDBmNmEyOTAxZWZkNzI4OGZkN2MzYjE4OGIzZTdfNDU3ZmEyODFmNjRmZTUwNTRkMTJlZWJiZDlkYmI1ZjZfSUQ6NzUxMDk0NDc5OTE0NzY1NTE3Ml8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NjFlMDg5NmEzYTcxNWZmZWNmMzE1MjA3MGZhYjI3OTFfNWUxNTdiM2Q2ZDI3MjMyNTdmYThhYjdlZTEwY2Y1YjlfSUQ6NzUxMDk0NTA5ODU3ODkzNTgxMF8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

搜索功能用的是通用模型search\-std，目前免费，不清楚后面会不会收费，新人送蛮多资源包的，大家可以玩玩。

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NzI5YzY0MWYxZjBiM2Y0ODQyYzQwMjdhZDBhN2RkZDVfZWI2Y2YyYzA5NWI5OGY1Mzc0N2VlMzg0NmE3YTJmOGVfSUQ6NzUxMDk0ODE2ODY2MDM4NTc5NF8xNzgwMzgzMDM3OjE3ODA0Njk0MzdfVjM)

### 启动服务

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NGVkMWE4NDAyOGIyMjZhNzI3NDkyZmJlMmViMTg0YjNfNzFkZmY5M2E0ZWExZGJjZjk1MDk3NDNmMGYxZTJiMWJfSUQ6NzUxMDk0NTIzODM1NDAwMTkyNF8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

###### 成功启动小智后台就会显示在线状态，并且多了可用工具

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=YTAzMmI3ZGZkZjRjZGM4ZjVkNTA3Nzc1Njk0MTI0NTdfYmJkNmMzNjQ0NzhmZDQ2YmE1Yjc0OGE3Njk2Yjk3NWRfSUQ6NzUxMDk0NTU3NzM4NjM3NzIxOV8xNzgwMzgzMDM4OjE3ODA0Njk0MzhfVjM)

###### 这时候你就可以通过命令联网查询来问小智一些问题



问题反馈Q68717030

小智套件材料包，成品套件出售

【淘宝】7天无理由退货 https://e\.tb\.cn/h\.7EafhlWOV6iRNiw?tk=4zkRUOMv4K8 HU591 「拷贝链接」
点击链接直接打开 或者 淘宝搜索直接打开





