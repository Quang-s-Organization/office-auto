const LLAMA_BASE_URL = process.env.LLAMA_BASE_URL || "http://127.0.0.1:8080";

export interface GenerateJSONOpts {
  prompt: string;
  jsonSchema: object;
  temperature?: number;
  n_predict?: number;
  cache_prompt?: boolean;
}

export async function generateJSON(opts: GenerateJSONOpts): Promise<unknown> {
  const {
    prompt,
    jsonSchema,
    temperature = 0.2,
    n_predict = 2048,
    cache_prompt = true,
  } = opts;

  const res = await fetch(`${LLAMA_BASE_URL}/completion`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt,
      json_schema: jsonSchema,
      temperature,
      n_predict,
      cache_prompt,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`llama-server error ${res.status}: ${text.slice(0, 500)}`);
  }

  const data: any = await res.json();

  let content = data.content;
  if (typeof content !== "string") {
    throw new Error(`Unexpected response content type: ${typeof content}`);
  }

  // Try to extract JSON from the response
  content = content.trim();
  const jsonStart = content.indexOf("{");
  const jsonEnd = content.lastIndexOf("}");
  if (jsonStart >= 0 && jsonEnd > jsonStart) {
    content = content.slice(jsonStart, jsonEnd + 1);
  }

  return JSON.parse(content);
}
