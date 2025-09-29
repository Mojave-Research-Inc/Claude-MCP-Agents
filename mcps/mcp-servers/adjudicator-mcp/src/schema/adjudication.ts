export const ADJUDICATION_SCHEMA = {
  name: "adjudication",
  schema: {
    type: "object",
    required: ["verdict","confidence","rationale","citations"],
    properties: {
      verdict: { type: "string", enum: ["approve","deny","insufficient"] },
      confidence: { type: "number", minimum: 0, maximum: 1 },
      rationale: { type: "string", minLength: 1 },
      citations: { type: "array", items: { type: "string" } }
    },
    additionalProperties: false
  },
  strict: true
};