import os
from openai import OpenAI


class AIQuestionProvider:

    def __init__(self):

        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )


    def get_questions(self):

        prompt = """
你是一名中国计算机技术能力考试(CSP)出题老师。

现在给一名计算机科学专业本科生制定每日训练。

学生情况：

- C++基础
- STL
- 数据结构
- 回溯算法
- 基础图算法
- 正在准备CSP 100分

请生成今天3道CSP训练题。

要求：

第1题：
接近CSP第一题难度

第2题：
接近CSP第二题难度

第3题：
稍有挑战

每道题必须包含：

【题目名称】

【题目描述】

【输入格式】

【输出格式】

【输入样例】

【输出样例】

【考察知识点】

不要输出代码和答案。
"""


        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )


        return response.choices[0].message.content