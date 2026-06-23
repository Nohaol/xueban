# 小智AI配置MCP接入点使用说明（官方）

## 概述

一个强大的接口，用于通过远程控制、计算、邮件操作、知识搜索等方式扩展AI能力。



**MCP（模型上下文协议）**：是一个允许服务器向语言模型暴露可调用工具的协议。这些工具使模型能够与外部系统交互，例如查询数据库、调用API或执行计算。每个工具都由一个唯一的名称标识，并包含描述其模式的元数据。



**MCP接入点**：用于把本地的MCP服务接入到小智AI的大模型，提供给语音终端使用的接口。



## 获取 MCP 接入点

登录 xiaozhi\.me 的控制台，进入智能体的配置角色页面，右下角可以看到该智能体专属的 MCP 接入点。

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=OTU5MmMzMjFjNjllMGYyZmYxNGI3MDYyMmUzYjJlMGJfM2NjZjI1Njc0OGE0MDFlZDE2ZmM0MjVhNTllYjY0YzZfSUQ6NzUwNDg1NDM2ODgyNTUyNDIyNl8xNzgwMzgyOTY2OjE3ODA0NjkzNjZfVjM)



## 示例代码

GitHub：https://github\.com/78/mcp\-calculator



### MCP示例

```python
*# server.py*
*from* mcp.server.fastmcp *import* FastMCP
*import* logging
logger = logging.getLogger('test_mcp')

*import* math
*import* random

*# Create an MCP server*
mcp = FastMCP("Calculator")

*# Add an addition tool*
@mcp.tool()
def **calculator**(*python_expression*: str) -> dict:
    """For mathamatical calculation, always use this tool to calculate the result of a python expression. `math` and `random` are available."""
    result = eval(*python_expression*)
    logger.info(f"Calculating formula: {*python_expression*}, result: {result}")
    *return* {"success": True, "result": result}

*# Start the server*
*if* __name__ == "__main__":
    mcp.run(*transport*="stdio")

```



### 注意事项⚠️

1. MCP里工具的名字和参数的命名一定要清晰的让大模型知道它的作用，尽量不要用缩写，同时提供一段注释来说明工具的作用以及在何时使用。例如`calculator`让大模型知道它是个计算器，参数`python_expression`是要求大模型输入一个Python表达式。如果你要写一个`bing_search`工具，那么它的参数名应该是`keywords`。

2. 函数内的文档注释（使用"""\.\.\."""引用的部分）引导大模型何时使用该工具，同时提及了可以在表达式中使用`math`和`random`两个库里的函数，这两个库我们已经在前面的代码中`import`进来了。

3. 由于本示例项目中MCP Server中的标准输入输出被用来做数据传输，所以无法使用`print`来打印信息，改为通过`logger`来输出调试信息。

4. MCP的返回值通常是一个字符串或者JSON，示例中把计算结果放在一个JSON的`result`字段里进行返回。返回值的长度通常是有限制的，跟设备上的IoT指令一样，通常限制在1024字节内。

5. MCP的工具列表报文是有上限的，后期会在配置页面中显示，以token数计算。

6. 每个MCP接入点的连接数是有上限的。



### 运行效果

```JSON
% export MCP_ENDPOINT=<your_mcp_endpoint>
% python mcp_pipe.py calculator.py
2025-05-16 09:07:09,009 - MCP_PIPE - INFO - Connecting to WebSocket server...
2025-05-16 09:07:09,096 - MCP_PIPE - INFO - Successfully connected to WebSocket server
2025-05-16 09:07:09,097 - MCP_PIPE - INFO - Started test.py process
Processing request of type ListToolsRequest
Processing request of type CallToolRequest
Calculating formula: 3.14159 * (8 / 2) ** 2, result: 50.26544
Processing request of type CallToolRequest
Calculating formula: random.randint(1, 100), result: 11
```



### 对话内容

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=YzkxNGMyNGVjNmQ5N2RkN2JkZGY1MTI5MTNkMjdkMTBfNWQzMGUzNDg3ZWFiNWE3ZWY1Y2M0OWRlN2I4MDRjOTNfSUQ6NzUwNDg1NTA3NDM2MDUwODQzNV8xNzgwMzgyOTY2OjE3ODA0NjkzNjZfVjM)



