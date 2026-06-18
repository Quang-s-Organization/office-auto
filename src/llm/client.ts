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

  const useNative = process.env.LLAMA_USE_NATIVE === "1"
    || !process.env.LLAMA_USE_OPENAI
    || process.env.LLAMA_USE_OPENAI === "0";
  const endpoint = useNative
    ? `${LLAMA_BASE_URL}/completion`
    : `${LLAMA_BASE_URL}/v1/chat/completions`;

  if (useNative) {
    return await fetchNativeCompletion(endpoint, { prompt, jsonSchema, temperature, n_predict, cache_prompt });
  }
  return await fetchOpenAICompletion(endpoint, { prompt, jsonSchema, temperature, n_predict });
}

async function fetchNativeCompletion(endpoint: string, params: {
  prompt: string;
  jsonSchema: object;
  temperature: number;
  n_predict: number;
  cache_prompt: boolean;
}): Promise<unknown> {
  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: params.prompt,
      json_schema: params.jsonSchema,
      temperature: params.temperature,
      n_predict: params.n_predict,
      cache_prompt: params.cache_prompt,
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
  return extractJSON(content);
}

async function fetchOpenAICompletion(endpoint: string, params: {
  prompt: string;
  jsonSchema: object;
  temperature: number;
  n_predict: number;
}): Promise<unknown> {
  const responseFormat = {
    type: "json_schema",
    json_schema: {
      name: "content",
      strict: true,
      schema: params.jsonSchema,
    },
  };

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: process.env.LLAMA_MODEL || "sglang/Qwen3.6-35B-A3B-GGUF",
      messages: [
        { role: "system", content: params.prompt.split("\n").find(l => l.startsWith("Bạn là")) || params.prompt.split("\n")[0] },
        { role: "user", content: params.prompt },
      ],
      temperature: params.temperature,
      max_tokens: params.n_predict,
      response_format: responseFormat,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`OpenAI-compat error ${res.status}: ${text.slice(0, 500)}`);
  }

  const data: any = await res.json();
  const content = data.choices?.[0]?.message?.content;
  if (typeof content !== "string") {
    throw new Error(`Unexpected OpenAI response format: ${JSON.stringify(data).slice(0, 200)}`);
  }
  return extractJSON(content);
}

function extractJSON(content: string): unknown {
  content = content.trim();
  const jsonStart = content.indexOf("{");
  const jsonEnd = content.lastIndexOf("}");
  if (jsonStart >= 0 && jsonEnd > jsonStart) {
    content = content.slice(jsonStart, jsonEnd + 1);
  }
  return JSON.parse(content);
}
