1. Do not use docker. Make sure the project can be run on Vercel.
2. Based on the updated codes, modify /docs/tech-stack.md to reflect the changes in the tech stack.
3. When ever modifying or implementing new features, make sure to update the documentation in /docs as well. This includes but not limited to tech-stack.md, architecture.md, and any relevant markdown files in the /docs directory.
4. When ever modifying or implementing a function, make sure to add comments in the code to explain the purpose and functionality of the code. This will help other developers understand the code better and maintain it in the future.
5. Never change .env file, instead, update the .env.example file with the new environment variables and their descriptions. This will ensure that sensitive information is not exposed and that other developers can easily set up their own .env file based on the example.
6. Whenever updating codes, if the previous variable names are still relevant, keep them unchanged to avoid confusion. If new variables are added, make sure to use descriptive names that clearly indicate their purpose.
7. When using LLM api, always use GitHub models if possible, and make sure to update the environment variables in .env.example accordingly. A basic code sample for using GitHub models is as follows:
```python
import os
from openai import OpenAI

token = os.environ["GITHUB_TOKEN"]
endpoint = "https://models.github.ai/inference"
model = "openai/gpt-4.1"

client = OpenAI(
    base_url=endpoint,
    api_key=token,
)

response = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant.",
        },
        {
            "role": "user",
            "content": "What is the capital of France?",
        }
    ],
    temperature=1.0,
    top_p=1.0,
    model=model
)

print(response.choices[0].message.content)
```
8. Before implementing any codes, review /docs/architecture.md to understand the overall architecture of the project and ensure that the new codes align with the existing structure and design principles. If there are any discrepancies or if the new codes introduce new architectural components, ask for verification. If verification is given, update the architecture documentation accordingly to reflect the changes. This will help maintain a clear and up-to-date understanding of the project's architecture for all developers.
9. Record in a file /docs/lessons_learnt.md to record the user preferences, mistakes and modifications that you have made, and how you can do better next time. This will help you to avoid making the same mistakes in the future and to better understand the user preferences over time. Make sure to update this file regularly as you learn more about the user's preferences and as you make modifications to the codebase.