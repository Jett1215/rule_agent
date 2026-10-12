import os
import base64
import tempfile
from agentchat.core.models.manager import ModelManager


def image_to_txt(image_path: str):
    vl_model = ModelManager.get_qwen_vl_model()
    # 将本地图片转成 base64，完整提取文字后用于知识库分块。
    image_type = image_path.split('.')[-1]
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")
    response = vl_model.invoke(
        input=[
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are a helpful assistant."}]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{image_type};base64,{base64_image}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "请完整提取图片中可辨认的文字，按原有阅读顺序输出。\n"
                            "保留标题、段落、编号和换行；表格按行输出，保留各列对应关系。\n"
                            "不要概括、省略或改写原文，不限制为300字。\n"
                            "无法辨认的文字标记为[无法辨认]，不要猜测。\n"
                            "只输出提取结果，不添加图片描述、解释或开场白。"
                        ),
                    },
                ],
            }
        ],
    )

    fd, txt_path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(response.content.strip())

    return txt_path
