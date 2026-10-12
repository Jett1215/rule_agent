from typing import List
from loguru import logger

from fastapi import FastAPI, APIRouter, Body, Depends
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from starlette.responses import StreamingResponse

from agentchat.api.services.user import UserPayload, get_login_user
from agentchat.prompts.mars import Mars_System_Prompt
from agentchat.schemas.usage_stats import UsageStatsAgentType
from agentchat.services.mars.mars_agent import MarsAgent, MarsConfig
from agentchat.services.mars.mars_tools.autobuild import construct_auto_build_prompt
from agentchat.services.memory.client import memory_client
from agentchat.utils.contexts import set_user_id_context, set_agent_name_context

router = APIRouter(tags=["Mars"])

class MarsExampleEnum:
    Autobuild_Agent = 1
    Deep_Search = 2
    AI_News = 3
    Query_Knowledge = 4

# 注册 POST 接口；加上项目的 API 前缀后，前端请求 /api/v1/mars/chat。
@router.post("/mars/chat")
# Body(...) 表示必填；embed=True 要求请求体形如 {"user_input": "用户的问题"}。
# Depends 会先执行 get_login_user，由认证依赖提供登录用户信息，而非由模型提供。
async def chat_mars(user_input: str = Body(..., description="用户输入", embed=True),
                    login_user: UserPayload = Depends(get_login_user)):
    # 设置当前执行上下文中的用户和 Agent 标识，供下游调用、用量统计等使用。
    set_user_id_context(login_user.user_id)
    set_agent_name_context(UsageStatsAgentType.mars_agent)

    # 每次请求创建一个 MarsAgent，并绑定服务端认证得到的用户 ID。
    # 工具执行中间件会使用该 ID 填充工具参数中的 user_id。
    mars_config = MarsConfig(user_id=login_user.user_id)
    mars_agent = MarsAgent(mars_config)

    # 异步初始化：加载四个 Mars 工具、模型和中间件，再创建 Agent 执行流程。
    # 这里准备模型可使用的工具；真正的工具选择发生在后面的模型调用阶段。
    await mars_agent.init_mars_agent()

    # 默认不附加记忆；如果记忆服务不可用，仍然继续处理用户问题。
    memory_content = ""
    try:
        # 按当前问题检索当前用户的相关长期记忆，不是直接加载全部历史对话。
        memory_messages = await memory_client.search(query=user_input, user_id=login_user.user_id)
        # 提取 results 中每条记录的 memory 字段。
        # 注意：这里将列表整体转成字符串，保留列表表示形式，并非用换行符 join。
        memory_content = str([f"- {msg.get('memory', '')} \n" for msg in memory_messages.get('results', [])])
    except Exception as exc:
        # 记忆检索失败仅记录异常类型，不阻断后续 Agent 调用。
        logger.warning("Mars memory search unavailable; continuing without memory ({})", type(exc).__name__)

    # 组装本次输入：系统消息提供行为规则和检索到的记忆，用户消息提供当前问题。
    # 工具定义由初始化后的 Agent 另行提供，不在这里手动拼接成消息。
    messages: List[BaseMessage] = [
        SystemMessage(content=Mars_System_Prompt.format(memory_content=memory_content)),
        HumanMessage(content=user_input)
    ]

    # 内部异步生成器：StreamingResponse 消费它时才开始执行这里的代码。
    # yield 允许响应逐段发送，而不是等完整答案生成后一次性返回。
    async def general_generate():
        # 累积回答文本，供流正常结束后的记忆写入使用。
        final_response = ""
        # 启动 Mars 的流式执行，持续获取推理片段、回答片段或工具输出事件。
        # 工具选择和执行由 MarsAgent 内部的模型及 Agent 框架负责。
        async for chunk in mars_agent.ainvoke_stream(messages):
            # SSE 以 data: 开头，以空行结束一条事件。
            # 此处直接插入 Python 对象的字符串表示，并非 json.dumps 序列化。
            yield f"data: {chunk}\n\n"
            # 只累积回答类型的事件，不把 reasoning_chunk 等其他事件写入回答文本。
            if chunk.get("type") == "response_chunk":
                final_response += chunk.get("data", "")

        # 流正常遍历结束后，将本轮问题和累积回答提交给记忆服务。
        # 这不是 finally：若流提前异常退出，这一段不保证会执行。
        try:
            await memory_client.add(
                user_id=login_user.user_id,
                messages=[{"role": "user", "content": user_input}, {"role": "assistant", "content": final_response}]
            )
        except Exception as exc:
            # 记忆保存失败只记录日志，已经发送给前端的回答不受影响。
            logger.warning("Mars memory save unavailable; response preserved ({})", type(exc).__name__)

    # 返回 SSE 流式 HTTP 响应；框架逐次消费生成器，将事件发送给前端。
    return StreamingResponse(general_generate(), media_type="text/event-stream")

@router.post("/mars/example")
async def chat_mars_example(
    example_id: int = Body(..., description="例子ID", embed=True),
    login_user: UserPayload = Depends(get_login_user)
):
    # 设置全局变量
    set_user_id_context(login_user.user_id)
    set_agent_name_context(UsageStatsAgentType.mars_agent)

    mars_config = MarsConfig(user_id=login_user.user_id)
    mars_agent = MarsAgent(mars_config)

    await mars_agent.init_mars_agent()

    user_input = ""
    if example_id == MarsExampleEnum.Autobuild_Agent:
        user_input = "帮我生成一个智能体，它可以给我预报每天的天气情况并且可以帮我生成图片，名称跟描述的话请你给他起一个吧，智能体名称字数要处于2-10字之间"
    elif example_id == MarsExampleEnum.AI_News:
        user_input = "请帮我生成一份今天的AI日报，然后总结之后提供给我一个AI日报的图片，不需要详细内容"
    elif example_id == MarsExampleEnum.Query_Knowledge:
        user_input = "请你帮我查询我所有的知识库，然后告诉我知识库中都是什么信息，最好还有图表展示什么的。"
    elif example_id == MarsExampleEnum.Deep_Search:
        user_input = "使用深度搜索查泰山游玩攻略"

    messages: List[BaseMessage] = [
        SystemMessage(content=Mars_System_Prompt.format(memory_content="")),
        HumanMessage(content=user_input)
    ]

    async def general_generate():
        async for chunk in mars_agent.ainvoke_stream(messages):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(general_generate(), media_type="text/event-stream")
